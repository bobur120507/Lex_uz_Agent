"""One small database layer: PostgreSQL for real runs (DATABASE_URL), SQLite for offline tests.

All SQL in the project is written once with `?` placeholders (or `:name`) and ANSI upserts
(`INSERT … ON CONFLICT … DO UPDATE`), which both engines understand. Rows can be read by
name (`row["doc_title"]`) or by position (`row[0]`).
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path


class Row(dict):
    __slots__ = ("_values",)

    def __init__(self, names, values):
        super().__init__(zip(names, values))
        self._values = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)

    def values_tuple(self) -> tuple:
        return self._values


_NAMED = re.compile(r"(?<!:):([A-Za-z_]\w*)")


def _to_pg(sql: str) -> str:
    sql = sql.replace("%", "%%")                 # literal % (LIKE patterns are always parameters here)
    sql = _NAMED.sub(r"%(\1)s", sql)
    return sql.replace("?", "%s")


class Database:
    def __init__(self, url: str | None = None, sqlite_path: Path | None = None):
        if url and url.startswith(("postgres://", "postgresql://")):
            try:
                import psycopg
            except ImportError as exc:  # pragma: no cover - depends on the machine
                raise SystemExit('PostgreSQL uchun: uv pip install "psycopg[binary]"') from exc

            def row_factory(cursor):
                names = [c.name for c in cursor.description] if cursor.description else []
                return lambda values: Row(names, values)

            self.kind = "postgres"
            try:
                self.con = psycopg.connect(url, row_factory=row_factory, autocommit=False)
            except psycopg.OperationalError as exc:
                raise RuntimeError(f"PostgreSQL’ga ulanib boʻlmadi: {str(exc).strip().splitlines()[0]}") from exc
            self.label = re.sub(r"//([^:@/]+):[^@]*@", r"//\1:***@", url)
        else:
            self.kind = "sqlite"
            path = Path(sqlite_path or "data/modda.sqlite")
            path.parent.mkdir(parents=True, exist_ok=True)
            self.con = sqlite3.connect(path)
            self.con.row_factory = lambda cur, values: Row([d[0] for d in cur.description], values)
            self.con.execute("PRAGMA journal_mode=WAL")
            self.label = str(path)

    def _sql(self, sql: str) -> str:
        return _to_pg(sql) if self.kind == "postgres" else sql

    def execute(self, sql: str, params=()):
        return self.con.execute(self._sql(sql), params)

    def executemany(self, sql: str, seq) -> None:
        seq = list(seq)
        if not seq:
            return
        if self.kind == "postgres":
            with self.con.cursor() as cur:
                cur.executemany(self._sql(sql), seq)
        else:
            self.con.executemany(sql, seq)

    def script(self, ddl: str) -> None:
        for stmt in [s.strip() for s in ddl.split(";") if s.strip()]:
            self.con.execute(stmt)
        self.con.commit()

    def commit(self) -> None:
        self.con.commit()

    def add_column(self, table: str, column: str, sqltype: str) -> None:
        """Schema migration for databases created by an older version."""
        if self.kind == "postgres":
            self.con.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {sqltype}")
        else:
            cols = [r[1] for r in self.con.execute(f"PRAGMA table_info({table})")]
            if column not in cols:
                self.con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sqltype}")
        self.con.commit()

    def close(self) -> None:
        self.con.close()
