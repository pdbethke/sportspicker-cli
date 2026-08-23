"""Reading the JSON these commands operate on."""
import json as _json
import sys
from dataclasses import dataclass

from ._output import fail


@dataclass(frozen=True)
class Score:
    """
    What one member scored in a round.

    A plain frozen dataclass on purpose: the scoring library takes anything
    carrying these four attributes, so the command line can feed it JSON with no
    ORM anywhere nearby.
    """

    membership_id: int
    raw_points: float
    wins: int = 0
    tiebreaker_total: int | None = None


def read_payload(source: str | None) -> dict:
    """Read JSON from a file, or from stdin when given '-' or nothing."""
    if source in (None, "-"):
        raw = sys.stdin.read()
    else:
        try:
            with open(source, encoding="utf-8") as handle:
                raw = handle.read()
        except OSError as exc:
            fail(f"cannot read {source}: {exc}")
    try:
        payload = _json.loads(raw)
    except ValueError as exc:
        fail(f"input is not valid JSON: {exc}")
    if not isinstance(payload, dict):
        fail("input must be a JSON object")
    return payload


def scores_from(payload: dict) -> list[Score]:
    rows = payload.get("scores")
    if not isinstance(rows, list):
        fail('input needs a "scores" array')
    out = []
    for row in rows:
        if not isinstance(row, dict) or "membership_id" not in row or "raw_points" not in row:
            fail('every score needs "membership_id" and "raw_points"')
        out.append(Score(
            membership_id=int(row["membership_id"]),
            raw_points=float(row["raw_points"]),
            wins=int(row.get("wins", 0)),
            tiebreaker_total=row.get("tiebreaker_total"),
        ))
    return out
