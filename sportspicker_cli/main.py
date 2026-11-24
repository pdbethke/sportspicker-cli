"""The command line itself: argparse, four commands, no dependencies."""
import argparse
import sys

from sportspicker_core import (
    award_round, effective_pot, normalization_registry, pot_for, round_pots,
    to_amount,
)

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

    try:
        if args.pot is not None:
            pot = to_amount(args.pot, "--pot")
        elif args.budget is None or args.rounds is None:
            fail("give --pot, or --budget with --rounds and --round")
        elif args.round is None:
            fail("give --round: which round of the contest to price, from 1. "
                 "A budget that does not divide evenly gives its leftover "
                 "ten-thousandths to the earliest rounds, so it matters")
        else:
            pot = pot_for(args.budget, args.rounds, args.round - 1)

        chosen = normalization_registry.get(args.strategy)
        weights = chosen.weigh_round(scores, params)
        awards = award_round(scores, weights, pot, params, is_baseline=chosen.is_baseline)
    except (TypeError, ValueError, KeyError) as exc:
        fail(str(exc))

    rows = [
        {
            "rank": a.rank_in_round,
            "membership_id": a.membership_id,
            "raw_score": a.raw_score,
            "points_awarded": a.points_awarded,
        }
        for a in sorted(awards, key=lambda a: (a.rank_in_round, a.membership_id))
    ]
    if args.json:
        emit(rows, True)
        return

    emit(rows, False, empty="(no scores)")
    total = sum((a.points_awarded for a in awards), to_amount(0, "total"))
    payable = effective_pot(pot, scores, params)
    print(f"\n  pot {pot:.4f}   awarded {total:.4f}")
    if payable != pot:
        print(f"  min_participants shrank this round's pot to {payable:.4f}")
    # The line worth running this for. Every non-baseline strategy must hand out
    # exactly the pot, whatever it does internally — so if these two numbers
    # ever disagree, by so much as a ten-thousandth, the guarantee the design
    # rests on has been broken and you are looking at it rather than reading
    # about it. Amounts are exact decimals, so there is no tolerance to allow.
    if not chosen.is_baseline and total != payable:
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
    try:
        budget = to_amount(args.budget, "budget")
        pots = round_pots(budget, args.rounds)
    except (TypeError, ValueError) as exc:
        fail(str(exc))
    emit_pairs({"budget": budget, "rounds": args.rounds, "round_pots": list(pots)},
               args.json)


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
    # Amounts are read as text, never float: the library works in exact
    # ten-thousandths, and a float would already have lost the typed value.
    a.add_argument("--pot", help="this round's pot")
    a.add_argument("--budget", help="contest budget, with --rounds and --round")
    a.add_argument("--rounds", type=int, help="rounds in the contest, with --budget")
    a.add_argument("--round", type=int, help="which round to price, from 1, with --budget")
    a.set_defaults(func=_award)

    s = add_json(sub.add_parser("strategies", help="list the normalization strategies"))
    s.set_defaults(func=_strategies)

    p = add_json(sub.add_parser("pot", help="what each round of a contest is worth"))
    p.add_argument("budget")
    p.add_argument("rounds", type=int)
    p.set_defaults(func=_pot)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    args.func(args)
    return 0
