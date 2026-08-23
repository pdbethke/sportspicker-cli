"""
Printing, with no dependencies.

The application's own CLI renders through Typer. This package deliberately does
not: its only dependency is sportspicker-core, which has none, so the whole
thing runs inside a sandbox that mounts the system and not your home directory
— the same property that lets the scoring library be audited offline. A
formatting convenience is not worth giving that up.
"""
import json as _json
import sys


def _fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".") or "0"
    return str(value)


def emit(rows: list[dict], as_json: bool, empty: str = "(nothing to show)") -> None:
    """Print a list of uniform dicts as a table, or as JSON."""
    if as_json:
        print(_json.dumps(rows, indent=2))
        return
    if not rows:
        print(empty)
        return
    columns = list(rows[0])
    widths = {c: max(len(c), max(len(_fmt(r.get(c))) for r in rows)) for c in columns}
    print("  ".join(c.ljust(widths[c]) for c in columns))
    print("  ".join("-" * widths[c] for c in columns))
    for row in rows:
        print("  ".join(_fmt(row.get(c)).ljust(widths[c]) for c in columns))


def emit_pairs(pairs: dict, as_json: bool) -> None:
    """Print a single record as aligned key/value lines, or as JSON."""
    if as_json:
        print(_json.dumps(pairs, indent=2))
        return
    width = max((len(k) for k in pairs), default=0)
    for key, value in pairs.items():
        print(f"  {key.ljust(width)}  {_fmt(value)}")


def fail(message: str) -> None:
    """Print an error and exit non-zero, so scripts can branch on it."""
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)
