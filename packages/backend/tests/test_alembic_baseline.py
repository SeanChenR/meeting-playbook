"""Smoke tests for the Alembic baseline — config files exist, env.py compiles."""

from __future__ import annotations

import py_compile
from pathlib import Path


def _backend_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def test_alembic_ini_exists():
    assert (_backend_dir() / "alembic.ini").is_file()


def test_alembic_env_py_exists():
    assert (_backend_dir() / "alembic" / "env.py").is_file()


def test_alembic_script_template_exists():
    assert (_backend_dir() / "alembic" / "script.py.mako").is_file()


def test_alembic_env_py_compiles():
    """env.py is syntactically valid Python."""
    py_compile.compile(
        str(_backend_dir() / "alembic" / "env.py"),
        doraise=True,
    )
