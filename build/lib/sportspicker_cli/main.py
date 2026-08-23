"""The command line itself: argparse, four commands, no dependencies."""
import argparse
import sys

from sportspicker_core import award_round, normalization_registry, pot_for

from ._input import read_payload, scores_from
from ._output import emit, emit_pairs, fail


def _weigh(args) -> None:
    payload = read_payload(args.source)
    scores = scores_from(payload)
    params = payload.get("params", {})
    try:
        weights = normalization_registry.get(args.strategy).weigh_round(scores, params)
    except (ValueError, KeyError) as exc:
        fail(str(exc))
    emit([{"membership_id": m, "weight": w} for m, w in sorted(weights.items())],
         args.json, empty="(no scores)")


def _award(args) -> None:
    payload = read_payload(args.source)
    scores = scores_from(payload)
    params = payload.get("params", {})

    pot = args.pot
    if pot is None:
        if args.budget is None or args.rounds is None:
            fail("give --pot, or both --budget and --rounds")
        pot = pot_for(args.budget, args.rounds)

    try:
        chosen = normalization_registry.get(args.strategy)
        weights = chosen.weigh_round(scores, params)
    except (ValueError, KeyError) as exc:
        fail(str(exc))

    awards = award_round(scores, weights, pot, params, is_baseline=chosen.is_baseline)
    rows = [
        {
            "rank": a.rank_in_round,
            "membership_id": a.membership_id,
            "raw_score": a.raw_score,
            "points_awarded": round(a.points_awarded, 4),
        }
        for a in sorted(awards, key=lambda a: (a.rank_in_round, a.membership_id))
    ]
    if args.json:
        emit(rows, True)
        return

    emit(rows, False, empty="(no scores)")
    total = sum(a.points_awarded for a in awards)
    print(f"\n  pot {pot:.4f}   awarded {total:.4f}")
    # The line worth running this for. Every non-baseline strategy must hand out
    # exactly the pot, whatever it does internally — so if these two numbers
    # ever disagree, the guarantee the design rests on has been broken and you
    # are looking at it rather than reading about it.
    if not chosen.is_baseline and abs(total - pot) > max(0.01, pot * 1e-3):
        print("  WARNING: awarded total does not match the pot")


def _strategies(args) -> None:
    rows = []
    for slug in normalization_registry.slugs():
        strategy = normalization_registry.get(slug)
        rows.append({
            "slug": slug,
            "baseline": strategy.is_baseline,
            "note": "bypasses budgets; harness only" if strategy.is_baseline else "",
        })
    emit(rows, args.json)


def _pot(args) -> None:
    emit_pairs({"budget": args.budget, "rounds": args.rounds,
                "pot_per_round": pot_for(args.budget, args.rounds)}, args.json)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sportspicker",
        description="Scoring arithmetic on JSON. No database, no server.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_json(p):
        p.add_argument("--json", action="store_true", help="emit JSON instead of a table")
        return p

    w = add_json(sub.add_parser("weigh", help="relative weights a strategy gives one round"))
    w.add_argument("source", nargs="?", help="JSON file, or - for stdin")
    w.add_argument("--strategy", default="rank")
    w.set_defaults(func=_weigh)

    a = add_json(sub.add_parser("award", help="award one round: scores in, points out"))
    a.add_argument("source", nargs="?", help="JSON file, or - for stdin")
    a.add_argument("--strategy", default="rank")
    a.add_argument("--pot", type=float, help="this round's pot")
    a.add_argument("--budget", type=float, help="contest budget, with --rounds")
    a.add_argument("--rounds", type=int, help="rounds in the contest, with --budget")
    a.set_defaults(func=_award)

    s = add_json(sub.add_parser("strategies", help="list the normalization strategies"))
    s.set_defaults(func=_strategies)

    p = add_json(sub.add_parser("pot", help="what one round of a contest is worth"))
    p.add_argument("budget", type=float)
    p.add_argument("rounds", type=int)
    p.set_defaults(func=_pot)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    args.func(args)
    return 0
