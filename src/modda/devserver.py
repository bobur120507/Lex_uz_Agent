"""The same HTTP API as `api.py`, using only the Python standard library.

`python -m modda serve` uses it automatically when FastAPI/uvicorn are not installed (for example when
`pip install ".[api]"` fails on a slow connection). Routes, JSON and SSE events are identical.
"""

from __future__ import annotations

import json
import mimetypes
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import service
from .service import BadRequest, NotFound


def _int(qs: dict, key: str, default: int, lo: int, hi: int) -> int:
    try:
        v = int(qs.get(key, [default])[0])
    except ValueError:
        raise BadRequest(f"{key} butun son boʻlishi kerak") from None
    if not lo <= v <= hi:
        raise BadRequest(f"{key}: {lo}…{hi}")
    return v


class Handler(BaseHTTPRequestHandler):
    server_version = "modda-dev/0.3"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):            # one short line per request
        print(f"{self.address_string()} {self.command} {self.path[:80]} → {args[1] if len(args) > 1 else ''}", flush=True)

    # ------------------------------------------------------------------ helpers
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):   # the page gave up or moved on — nothing to answer
            self.close_connection = True

    def _error(self, status, detail):
        self._json({"detail": detail}, status)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > 100_000:
            raise BadRequest("soʻrov juda katta")
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            raise BadRequest("JSON notoʻgʻri") from None

    # ------------------------------------------------------------------ routes
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        parts = [unquote(p) for p in u.path.strip("/").split("/") if p]
        try:
            if parts == ["health"]:
                return self._json(service.health())
            if parts == ["model", "info"]:
                return self._json(service.model_info())
            if len(parts) == 3 and parts[0] == "ask" and parts[2] == "embedding":
                return self._json(service.embedding(parts[1]))
            if len(parts) == 3 and parts[0] == "ask" and parts[2] == "trace":
                return self._json(service.trace(parts[1]))
            if len(parts) == 3 and parts[0] == "chunks" and parts[2] == "context":
                return self._json(service.chunk_context(parts[1], _int(qs, "n", 5, 0, 10)))
            if len(parts) == 3 and parts[0] == "articles" and parts[2] == "context":
                return self._json(service.article_context(parts[1], _int(qs, "n", 5, 0, 10)))
            if parts == ["documents"]:
                return self._json(service.documents(qs.get("q", [""])[0], _int(qs, "limit", 20, 1, 100),
                                                    qs.get("doc_type", [None])[0]))
            if len(parts) == 2 and parts[0] == "documents":
                return self._json(service.document(parts[1], _int(qs, "offset", 0, 0, 10**7),
                                                   _int(qs, "limit", 20, 1, 100)))
            return self._static(u.path)
        except NotFound as exc:
            return self._error(404, str(exc))
        except BadRequest as exc:
            return self._error(422, str(exc))
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as exc:
            return self._error(500, str(exc)[:300])

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        try:
            body = self._body()
            q = service.check_question(body.get("question"))
        except BadRequest as exc:
            return self._error(422, str(exc))
        if path == "/ask":
            try:
                return self._json(service.run(q))
            except RuntimeError as exc:
                return self._error(503, str(exc))
        if path == "/ask/stream":
            return self._stream(q)
        return self._error(404, "Not Found")

    def _stream(self, q: str):
        events: queue.Queue = queue.Queue()

        def work():
            try:
                service.run(q, emit=events.put)
            except Exception as exc:
                events.put({"type": "stage.failed", "data": {"stage": "server", "message": str(exc)[:300]}})
            finally:
                events.put(None)

        threading.Thread(target=work, daemon=True).start()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self._cors()
        self.end_headers()
        self.close_connection = True
        try:
            while (ev := events.get()) is not None:
                self.wfile.write(f"event: {ev['type']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):  # the page started a new question
            pass

    def handle(self):                                 # a client that disconnects mid-request is not an error
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _static(self, path: str):
        root = service.web_dist()
        if not root:
            return self._error(404, "Not Found")
        root = Path(root).resolve()
        f = (root / path.lstrip("/")).resolve()
        if root not in f.parents and f != root:
            return self._error(404, "Not Found")
        if f.is_dir():
            f = f / "index.html"
        if not f.exists():
            f = root / "index.html"
        data = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def serve(host: str = "0.0.0.0", port: int = 8080) -> None:
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    print(f"Modda API (standart kutubxona): http://localhost:{port}  — /health, /ask, /ask/stream", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
