# sportspicker-cli

A command line over the pick'em scoring arithmetic. Scores and a strategy go in
as JSON; weights, ranks and points come out.

No database, no server, no clock — none of that is arithmetic. One dependency,
[sportspicker-core][core], which has none of its own.

## Why it exists

The guarantee the whole design rests on is this:

> A contest contributes **exactly** its budget, whatever scoring rule is chosen,
> however many members played, and however they scored.

That is a claim, and claims should be checkable. This is one command:

```console
$ sportspicker award round.json --budget 1000 --rounds 4 --round 1
rank  membership_id  raw_score  points_awarded
----  -------------  ---------  --------------
1     1              9          107.7586
2     2              6          71.1207
2     3              6          71.1207
4     4              0          0

  pot 250.0000   awarded 250.0000
```

Run the same round through a different strategy and the split changes while the
total does not:

```console
$ sportspicker award round.json --budget 1000 --rounds 4 --round 1 --strategy share
...
  pot 250.0000   awarded 250.0000
```

That is the invariant, on your own data, in a second. If those two numbers ever
disagree, by so much as a ten-thousandth, the command says so.

"Exactly" is literal. Amounts are exact decimals in ten-thousandths of a point:
a pot that does not divide evenly gives its leftover ten-thousandths to the
members whose shares were cut the most, and a budget that does not divide
evenly across its rounds gives them to the earliest rounds. That is why pricing
a round from a budget needs `--round` as well as `--rounds`. Amounts are read as
text, never as floats; one finer than a ten-thousandth is refused.

## Commands

| | |
|---|---|
| `award` | award one round — scores and a strategy in, points out |
| `weigh` | the relative weights a strategy gives a round, before normalization |
| `strategies` | what is available, and which one deliberately ignores budgets |
| `pot` | what each round of a contest is worth, adding back up to the budget |

All of them take `--json` for scripting. Input is a file or stdin.

## Input

```json
{
  "scores": [
    {"membership_id": 1, "raw_points": 9},
    {"membership_id": 2, "raw_points": 6}
  ],
  "params": {"points_table": [25, 18, 15], "tail_value": 0}
}
```

`membership_id` and `raw_points` are required; `wins` and `tiebreaker_total` are
optional.

## Install

```console
pip install sportspicker-cli
```

Or run it out of a checkout with nothing installed at all:

```console
PYTHONPATH=.:../sportspicker-core python3 -m sportspicker_cli pot 1000 4
```

## Why argparse

Because the only dependency is the scoring library, this runs anywhere that
library does — including inside an offline sandbox that mounts the system but
not your home directory, which is what lets [the core][core] be audited without
installing anything. A nicer argument parser would cost that property, and the
property is worth more than the ergonomics.

## Tests

```console
python -m pytest tests -q
```

They drive `main()` with real argv and read the output a person would see,
because what this package promises is that the guarantee can be *watched*.

## License

[Elastic License 2.0](LICENSE).

[core]: https://github.com/pdbethke/sportspicker-core
