"""False-positive regression tests for ``scan_file``.

A hallucination detector's most important property is that it stays quiet on
legitimate code. Each test here is a piece of perfectly valid Python that
has historically tripped naive "undefined call" detectors; ``scan_file``
must report **zero** issues on each.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from repograph_honest.mcp.tools import index_project, scan_file

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def project(tmp_path: Path):
    """A project that defines the symbols the legitimate snippets rely on."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "helpers.py").write_text(
        "def compute(x):\n    return x * 2\n\n"
        "class Client:\n    def fetch(self):\n        return 1\n",
        encoding="utf-8",
    )
    index_project(str(tmp_path), force_rebuild=True)
    return tmp_path


def _scan(tmp_path: Path, code: str) -> list[dict]:
    f = tmp_path / "snippet.py"
    f.write_text(code, encoding="utf-8")
    res = scan_file(str(f))
    assert res["success"], f"scan failed: {res.get('error')}"
    return res["issues"]


def test_no_false_positive_on_all_builtins(project: Path):
    """Every builtin (any/all/frozenset/id/hash/ord/chr/pow/...) must be known."""
    code = (
        "x = [1, 2, 3]\n"
        "print(any(x), all(x))\n"
        "print(frozenset(x), complex(1, 2))\n"
        "print(id(x), hash(x), ord('a'), chr(65))\n"
        "print(hex(255), oct(8), bin(5))\n"
        "print(pow(2, 10), divmod(7, 2))\n"
        "print(format(3.14, '.2f'))\n"
        "it = iter(x); print(next(it))\n"
        "print(repr(x), ascii(x), vars(), dir(x))\n"
        "print(bin(0b1010), oct(0o17), hex(0xff))\n"
        "print(StopIteration, RuntimeError, NotImplementedError)\n"
        "print(OSError, FileNotFoundError, PermissionError)\n"
        "print(Warning, DeprecationWarning, UserWarning)\n"
        "assert isinstance(x, list)\n"
        "assert issubclass(TypeError, Exception)\n"
        "assert hasattr(x, 'append')\n"
        "print(getattr(x, 'append', None))\n"
        "print(callable(print), callable(1))\n"
        "print(isinstance(3, int))\n"
        "print(type(x), type(1), type('a'))\n"
        "print(property, classmethod, staticmethod)\n"
        "print(memoryview(b'abc'), bytearray(b'x'), bytes(5))\n"
        "print(complex, bool, float, int, str, list, dict, set, tuple)\n"
        "print(slice(1, 5), object, enumerate(x), zip(x, x), map(print, x), filter(None, x))\n"
        "print(sorted(x), reversed(x), sum(x), min(x), max(x), abs(-3), round(3.14))\n"
        "print(len(x), range(3), input, open, print, breakpoint)  # noqa\n"
        "try:\n    pass\nexcept (KeyError, IndexError, AttributeError):\n    pass\n"
    )
    issues = _scan(project, code)
    assert issues == [], f"False positives: {issues}"


def test_no_false_positive_on_self_method(project: Path):
    """``self.helper()`` must not be reported as undefined."""
    code = (
        "class Service:\n"
        "    def __init__(self):\n        self.value = 0\n"
        "    def run(self):\n        return self._compute()\n"
        "    def _compute(self):\n        return self.value + 1\n"
    )
    issues = _scan(project, code)
    assert issues == [], f"False positives on self.method: {issues}"


def test_no_false_positive_on_from_import(project: Path):
    """``from pkg.helpers import compute; compute(5)`` must resolve."""
    code = (
        "from pkg.helpers import compute\n"
        "from pkg.helpers import Client as Cl\n"
        "compute(5)\n"
        "c = Cl()\n"
        "c.fetch()\n"
    )
    issues = _scan(project, code)
    assert issues == [], f"False positives on from-import: {issues}"


def test_no_false_positive_on_relative_import(project: Path):
    """Relative imports inside a package must resolve."""
    (project / "pkg" / "user.py").write_text(
        "from .helpers import compute, Client\ncompute(5)\nClient().fetch()\n",
        encoding="utf-8",
    )
    f = project / "pkg" / "user.py"
    res = scan_file(str(f))
    assert res["success"]
    assert res["issues"] == [], f"False positives on relative import: {res['issues']}"


def test_no_false_positive_on_import_as(project: Path):
    """``import numpy as np; np.array(...)`` — np is bound by the alias."""
    code = "import os\nimport os.path as op\nprint(os.getcwd())\nprint(op.join('a', 'b'))\n"
    issues = _scan(project, code)
    assert issues == [], f"False positives on import-as: {issues}"


def test_no_false_positive_on_walrus(project: Path):
    """``if (n := compute(5)):`` binds n, so n must not be flagged."""
    code = "from pkg.helpers import compute\nif (n := compute(5)):\n    print(n)\n"
    issues = _scan(project, code)
    assert issues == [], f"False positives on walrus: {issues}"


def test_no_false_positive_on_loop_variable(project: Path):
    """``for item in items: item.x`` — item is bound by the for-target."""
    code = "items = [1, 2, 3]\nfor item in items:\n    print(item)\nwhile items:\n    items.pop()\n"
    issues = _scan(project, code)
    assert issues == [], f"False positives on loop var: {issues}"


def test_no_false_positive_on_nested_function(project: Path):
    """A nested function calling its enclosing sibling must resolve."""
    code = (
        "def outer():\n"
        "    def inner():\n        return 1\n"
        "    return inner()\n"
        "def caller():\n    return outer()\n"
    )
    issues = _scan(project, code)
    assert issues == [], f"False positives on nested funcs: {issues}"


def test_no_false_positive_on_dataclass_style(project: Path):
    """Type-annotated assignments and dataclass-style code must not trip."""
    code = (
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Point:\n    x: int = 0\n    y: int = 0\n"
        "p = Point(x=1)\n"
        "print(p.x, p.y)\n"
    )
    issues = _scan(project, code)
    assert issues == [], f"False positives on dataclass: {issues}"


def test_no_false_positive_on_complex_call_target(project: Path):
    """``(a + b).foo()`` — call_name returns None, must be skipped, not flagged."""
    code = "a = 'x'; b = 'y'\nprint((a + b).upper())\n"
    issues = _scan(project, code)
    assert issues == [], f"False positives on complex call target: {issues}"


def test_undefined_call_still_detected(project: Path):
    """Sanity check: a truly undefined call must still be reported."""
    code = "totally_made_up_function_xyz()\n"
    issues = _scan(project, code)
    assert any(i["name"] == "totally_made_up_function_xyz" for i in issues)
