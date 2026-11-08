"""The GPU laptop runs Python 3.10 (8-noyabr: the server did not start — `f"{re.sub(r'[^\\w]', …)}"`). Python 3.12+
accepts f-strings that 3.10 rejects, so code written and tested on a newer Python can break there. This test finds
the two such forms in every .py file: a backslash inside an f-string expression, and the f-string's own quote reused
inside it. (On Python < 3.12 importing such a file already fails, so the test only runs on 3.12+.)"""

import io
import sys
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="older Python rejects these forms itself")


def problems(source: str) -> list[tuple[int, str]]:
    out, stack = [], []                                  # stack: [quote, depth of {…} fields]
    prefix = "rRbBuUfF"
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.FSTRING_START:
            q = tok.string.lstrip(prefix)
            if stack and stack[-1][1] > 0 and (q == stack[-1][0] or (len(stack[-1][0]) == 1 and q.startswith(stack[-1][0]))):
                out.append((tok.start[0], "f-string ichida oʻsha qoʻshtirnoq"))
            stack.append([q, 0])
        elif tok.type == tokenize.FSTRING_END:
            stack.pop()
        elif stack:
            top = stack[-1]
            if tok.type == tokenize.OP and tok.string == "{":
                top[1] += 1
            elif tok.type == tokenize.OP and tok.string == "}":
                top[1] -= 1
            elif top[1] > 0 and tok.type == tokenize.STRING:
                q = tok.string.lstrip(prefix)
                if "\\" in tok.string:
                    out.append((tok.start[0], "f-string ifodasida backslash"))
                elif q == top[0] or (len(top[0]) == 1 and q.startswith(top[0])):
                    out.append((tok.start[0], "f-string ichida oʻsha qoʻshtirnoq"))
    return out


def test_checker_finds_the_bug():
    assert problems("""x = f"{re.sub(r'[^\\w]', '_', b)}.json"\n""")
    assert problems("""x = f"{d["a"]}"\n""")
    assert not problems("""x = f"{d['a']} {y!r:>{w}}"\ny = f'''{d["a"]}'''\n""")


def test_code_runs_on_python_310():
    bad = [f"{p.relative_to(ROOT)}:{line} {why}" for p in [*ROOT.glob("src/**/*.py"), *ROOT.glob("scripts/*.py"), *ROOT.glob("tests/*.py")]
           for line, why in problems(p.read_text(encoding="utf-8"))]
    assert not bad, bad
