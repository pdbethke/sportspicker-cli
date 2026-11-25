"""
The command line, end to end.

Every test drives main() with real argv and reads what a user would see. The
point of this package is that the scoring guarantee can be WATCHED rather than
taken on trust, so the tests check the output a person reads, not internals.
"""
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from sportspicker_cli.main import main

ROUND = {
    "scores": [
        {"membership_id": 1, "raw_points": 9},
        {"membership_id": 2, "raw_points": 6},
        {"membership_id": 3, "raw_points": 6},
        {"membership_id": 4, "raw_points": 0},
    ],
    "params": {"points_table": [25, 18, 15], "tail_value": 0},
}


@pytest.fixture
def round_file(tmp_path):
    p = tmp_path / "round.json"
    p.write_text(json.dumps(ROUND))
    return str(p)


def exact(text: str):
    """
    Parse JSON output with every number read as a Decimal.

    The numbers this prints are exact decimals in ten-thousandths. Reading
    them back as floats would put the drift back in and make an exact
    comparison meaningless.
    """
    return json.loads(text, parse_float=Decimal)


class TestPotExactness:
    """The guarantee this command line exists to make visible."""

    @pytest.mark.parametrize("strategy", ["rank", "share", "equal"])
    def test_every_strategy_awards_exactly_the_pot(self, round_file, strategy, capsys):
        main(["award", round_file, "--strategy", strategy, "--pot", "250", "--json"])

        awards = exact(capsys.readouterr().out)
        assert sum(a["points_awarded"] for a in awards) == Decimal(250)

    @pytest.mark.parametrize("strategy", ["rank", "share", "equal"])
    def test_a_pot_that_does_not_divide_is_still_paid_exactly(self, round_file, strategy, capsys):
        main(["award", round_file, "--strategy", strategy, "--pot", "1000", "--json"])

        awards = exact(capsys.readouterr().out)
        assert sum(a["points_awarded"] for a in awards) == Decimal(1000)

    def test_deriving_the_pot_from_a_budget_matches_asking_for_it(self, round_file, capsys):
        """--budget with --rounds and --round is how a contest prices a round."""
        main(["award", "--strategy", "rank", round_file, "--budget", "1000", "--rounds", "3", "--round", "1", "--json"])
        derived = exact(capsys.readouterr().out)

        main(["award", "--strategy", "rank", round_file, "--pot", "333.3334", "--json"])
        direct = exact(capsys.readouterr().out)

        assert derived == direct

    def test_a_budget_needs_the_round_it_is_pricing(self, round_file, capsys):
        """
        A budget that does not divide evenly gives its leftover ten-thousandths
        to the earliest rounds, so which round is being priced matters and is
        never assumed.
        """
        with pytest.raises(SystemExit):
            main(["award", "--strategy", "rank", round_file, "--budget", "1000", "--rounds", "3"])

        assert "--round" in capsys.readouterr().err

    def test_a_round_outside_the_contest_is_refused(self, round_file, capsys):
        with pytest.raises(SystemExit):
            main(["award", "--strategy", "rank", round_file, "--budget", "1000", "--rounds", "3", "--round", "4"])

        assert "round" in capsys.readouterr().err

    def test_the_human_readable_output_states_both_numbers(self, round_file, capsys):
        """
        A reader must be able to see the pot and the awarded total together —
        that comparison IS the guarantee, and burying either one turns a
        checkable claim back into a promise.
        """
        main(["award", "--strategy", "rank", round_file, "--budget", "1000", "--rounds", "4", "--round", "1"])

        out = capsys.readouterr().out
        assert "pot 250.0000" in out and "awarded 250.0000" in out
        assert "WARNING" not in out


    def test_a_pot_shrunk_by_min_participants_is_named_not_flagged(self, tmp_path, capsys):
        """
        Two of a required four scored, so half the pot is at stake. That is
        the rule working, not the guarantee breaking, and the output says which.
        """
        p = tmp_path / "thin.json"
        p.write_text(json.dumps({**ROUND, "params": {**ROUND["params"], "min_participants": 6,
                                                 "min_participants_mode": "scale"}}))

        main(["award", "--strategy", "rank", str(p), "--pot", "300"])

        out = capsys.readouterr().out
        assert "awarded 150.0000" in out
        assert "shrank this round's pot to 150.0000" in out
        assert "WARNING" not in out


class TestRanking:

    def test_tied_members_share_a_rank_and_the_next_place_is_skipped(self, round_file, capsys):
        main(["award", "--strategy", "rank", round_file, "--pot", "250", "--json"])

        ranks = [a["rank"] for a in json.loads(capsys.readouterr().out)]
        assert ranks == [1, 2, 2, 4]


class TestStrategies:

    def test_the_baseline_is_listed_and_labelled_as_one(self, capsys):
        """
        `raw` deliberately ignores budgets. Listing it without saying so would
        invite someone to run a contest on it.
        """
        main(["strategies", "--json"])

        rows = {r["slug"]: r for r in json.loads(capsys.readouterr().out)}
        assert rows["raw"]["baseline"] is True
        assert "harness" in rows["raw"]["note"]
        assert rows["rank"]["baseline"] is False


class TestPot:

    def test_pot_divides_the_budget_across_every_round(self, capsys):
        main(["pot", "1000", "4", "--json"])
        assert exact(capsys.readouterr().out)["round_pots"] == [Decimal(250)] * 4

    def test_the_round_pots_add_back_up_to_the_budget(self, capsys):
        """Three rounds of 1000: the leftover ten-thousandth goes to the first."""
        main(["pot", "1000", "3", "--json"])

        shown = exact(capsys.readouterr().out)
        assert shown["round_pots"] == [Decimal("333.3334"), Decimal("333.3333"), Decimal("333.3333")]
        assert sum(shown["round_pots"]) == shown["budget"] == Decimal(1000)

    def test_a_single_round_contest_pays_its_whole_budget(self, capsys):
        """A fight card is one round and must be worth its whole budget."""
        main(["pot", "1000", "1", "--json"])
        assert exact(capsys.readouterr().out)["round_pots"] == [Decimal(1000)]


class TestFailures:
    """A command line people script against has to fail usefully."""

    def test_bad_json_exits_non_zero_and_says_so(self, tmp_path, capsys):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json")

        with pytest.raises(SystemExit) as exit_info:
            main(["award", "--strategy", "rank", str(bad), "--pot", "250"])

        assert exit_info.value.code == 1
        assert "not valid JSON" in capsys.readouterr().err

    def test_missing_scores_array_is_named(self, tmp_path, capsys):
        p = tmp_path / "p.json"
        p.write_text('{"params": {}}')

        with pytest.raises(SystemExit):
            main(["award", "--strategy", "rank", str(p), "--pot", "250"])

        assert '"scores"' in capsys.readouterr().err

    def test_an_unknown_strategy_fails_rather_than_falling_back(self, round_file, capsys):
        """
        Silently substituting a default here would change every score in the
        contest and look like a working run.
        """
        with pytest.raises(SystemExit):
            main(["award", round_file, "--strategy", "nope", "--pot", "250"])

        assert capsys.readouterr().err.strip() != ""

    def test_a_pot_finer_than_a_ten_thousandth_is_refused(self, round_file, capsys):
        """Rounding it quietly would pay out a pot nobody asked for."""
        with pytest.raises(SystemExit) as exit_info:
            main(["award", "--strategy", "rank", round_file, "--pot", "250.00001"])

        assert exit_info.value.code == 1
        assert "ten-thousandth" in capsys.readouterr().err

    def test_a_budget_that_is_not_a_number_is_refused(self, capsys):
        with pytest.raises(SystemExit) as exit_info:
            main(["pot", "lots", "4"])

        assert exit_info.value.code == 1
        assert "budget" in capsys.readouterr().err

    def test_awarding_without_a_pot_or_a_budget_refuses(self, round_file, capsys):
        with pytest.raises(SystemExit):
            main(["award", "--strategy", "rank", round_file])

        assert "--pot" in capsys.readouterr().err


class TestStrategyIsChosen:
    """
    Which rule scores a round is the caller's decision. The command line used
    to pick `rank` when none was named.
    """

    @pytest.mark.parametrize("command", ["award", "weigh"])
    def test_leaving_out_the_strategy_is_refused(self, round_file, command, capsys):
        with pytest.raises(SystemExit) as exit_info:
            main([command, round_file, "--pot", "250"] if command == "award"
                 else [command, round_file])

        assert exit_info.value.code == 2
        assert "--strategy" in capsys.readouterr().err


class TestParamsAreValidated:
    """
    The command line validates a strategy's params with sportspicker-core's
    own check, the one the application runs before a config is saved, so it
    cannot accept a configuration the application would refuse.
    """

    @pytest.mark.parametrize("params, named", [
        ({"points_table": [25, 18, 15], "tail_value": 0, "drop_worst_n": 2}, "drop_worst_n"),
        ({"points_table": [25, 18, 15], "tail_value": 0, "min_participants": 3},
         "min_participants_mode"),
        ({"points_table": [25, 18, 15]}, "tail_value"),
        ({"points_table": [], "tail_value": 0}, "points_table"),
    ])
    @pytest.mark.parametrize("command", ["award", "weigh"])
    def test_params_the_application_refuses_are_refused(self, tmp_path, capsys,
                                                         params, named, command):
        p = tmp_path / "round.json"
        p.write_text(json.dumps({**ROUND, "params": params}))
        argv = [command, str(p), "--strategy", "rank"]
        if command == "award":
            argv += ["--pot", "250"]

        with pytest.raises(SystemExit) as exit_info:
            main(argv)

        assert exit_info.value.code == 1
        assert named in capsys.readouterr().err

    def test_the_baseline_can_still_be_run_to_watch_it_miss_the_pot(self, round_file, capsys):
        """
        `raw` cannot be a group's current strategy, but running it here is how
        you see the defect the normalising strategies fix. Its params are still
        validated; it is only the "may be current" check that does not apply.
        """
        main(["award", round_file, "--strategy", "raw", "--pot", "250", "--json"])

        total = sum(a["points_awarded"] for a in exact(capsys.readouterr().out))
        assert total == Decimal(21)


class TestConsoleScript:
    """
    The installed command is `sportspicker-calc`. The application installs its
    own `sportspicker` command, and two packages providing one script name
    overwrite each other in whichever environment has both.
    """

    def test_the_installed_script_is_sportspicker_calc(self):
        import tomllib

        root = Path(__file__).resolve().parent.parent
        scripts = tomllib.loads((root / "pyproject.toml").read_text())["project"]["scripts"]

        assert scripts == {"sportspicker-calc": "sportspicker_cli.main:main"}

    def test_help_names_the_command_people_type(self, capsys):
        with pytest.raises(SystemExit):
            main(["--help"])

        assert capsys.readouterr().out.startswith("usage: sportspicker-calc")


class TestCoreDependency:
    """
    sportspicker-core is not on PyPI, so a bare requirement could be satisfied
    by any package someone else publishes under that name. It is pinned to a
    release archive on GitHub instead.
    """

    def test_core_is_pinned_to_a_release_tag_archive(self):
        import tomllib

        root = Path(__file__).resolve().parent.parent
        deps = tomllib.loads((root / "pyproject.toml").read_text())["project"]["dependencies"]

        assert deps == [
            "sportspicker-core @ "
            "https://github.com/pdbethke/sportspicker-core/archive/refs/tags/v0.3.0.tar.gz"
        ]

    def test_ci_tests_against_the_same_tag(self):
        """CI checking out core's moving main would test a version nobody installs."""
        root = Path(__file__).resolve().parent.parent
        workflow = (root / ".github" / "workflows" / "tests.yml").read_text()

        assert "repository: pdbethke/sportspicker-core\n          ref: v0.3.0\n" in workflow


def test_it_runs_as_a_module_without_being_installed():
    """`python -m sportspicker_cli` is the zero-install path the README promises."""
    root = Path(__file__).resolve().parent.parent
    core = root.parent / "sportspicker-core"
    env = {"PYTHONPATH": f"{root}:{core}", "PATH": "/usr/bin:/bin"}
    result = subprocess.run([sys.executable, "-m", "sportspicker_cli", "pot", "1000", "4"],
                            capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    assert "250" in result.stdout
