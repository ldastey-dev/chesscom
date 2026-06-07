"""Unit tests for chesscom.cli."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from chesscom.cli import build_parser, main
from chesscom.config import AppConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides) -> AppConfig:
    defaults = dict(
        club_ref="team-scotland",
        club_name="Team Scotland",
        data_analysis_year=2024,
        match_id="999",
        prospect_clubs=["team-ireland"],
        exclusion_club=None,
    )
    defaults.update(overrides)
    return AppConfig(**defaults)


def _base_patches(config=None):
    """Return a context-manager stack that mocks env + client."""
    return [
        patch("chesscom.cli.load_dotenv"),
        patch("chesscom.cli.AppConfig.from_env", return_value=config or _make_config()),
        patch("chesscom.cli.ChessComClient", return_value=MagicMock()),
    ]


# ===========================================================================
# build_parser — subcommand registration
# ===========================================================================


class TestBuildParser:
    def test_match_participation_subcommand(self):
        args = build_parser().parse_args(["match-participation"])
        assert args.subcommand == "match-participation"

    def test_member_summary_subcommand(self):
        args = build_parser().parse_args(["member-summary"])
        assert args.subcommand == "member-summary"

    def test_prospects_subcommand(self):
        args = build_parser().parse_args(["prospects"])
        assert args.subcommand == "prospects"

    def test_match_eligibility_subcommand(self):
        args = build_parser().parse_args(["match-eligibility"])
        assert args.subcommand == "match-eligibility"

    def test_match_eligibility_accepts_match_id_flag(self):
        args = build_parser().parse_args(["match-eligibility", "--match-id", "42"])
        assert args.match_id == "42"

    def test_match_eligibility_match_id_defaults_to_none(self):
        args = build_parser().parse_args(["match-eligibility"])
        assert args.match_id is None

    def test_no_subcommand_exits(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args([])

    def test_unknown_subcommand_exits(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["unknown-report"])


# ===========================================================================
# main() — subcommand routing
# ===========================================================================


class TestMainSubcommandRouting:
    def _run(self, argv, mock_report_cls, config=None):
        """Helper: run main(argv) with the named report class mocked."""
        mock_instance = MagicMock()
        mock_instance.run.return_value = "output/test.xlsx"
        mock_report_cls.return_value = mock_instance

        patches = _base_patches(config)
        with patches[0], patches[1], patches[2]:
            main(argv)

        return mock_report_cls, mock_instance

    def test_match_participation_runs_correct_report(self):
        with patch("chesscom.cli.MatchParticipationReport") as mock_cls:
            self._run(["match-participation"], mock_cls)
        mock_cls.assert_called_once()
        mock_cls.return_value.run.assert_called_once()

    def test_member_summary_runs_correct_report(self):
        with patch("chesscom.cli.MemberSummaryReport") as mock_cls:
            self._run(["member-summary"], mock_cls)
        mock_cls.assert_called_once()
        mock_cls.return_value.run.assert_called_once()

    def test_prospects_runs_correct_report(self):
        with patch("chesscom.cli.ProspectReport") as mock_cls:
            self._run(["prospects"], mock_cls)
        mock_cls.assert_called_once()
        mock_cls.return_value.run.assert_called_once()

    def test_match_eligibility_runs_correct_report(self):
        with patch("chesscom.cli.MatchEligibilityReport") as mock_cls:
            self._run(["match-eligibility"], mock_cls)
        mock_cls.assert_called_once()
        mock_cls.return_value.run.assert_called_once()


# ===========================================================================
# main() — load_dotenv and AppConfig.from_env called on every subcommand
# ===========================================================================


class TestMainEnvironmentLoading:
    def _run_patched(self, argv):
        mock_instance = MagicMock()
        mock_instance.run.return_value = "output/test.xlsx"
        with (
            patch("chesscom.cli.load_dotenv") as mock_ld,
            patch("chesscom.cli.AppConfig.from_env", return_value=_make_config()) as mock_cfg,
            patch("chesscom.cli.ChessComClient"),
            patch("chesscom.cli.MemberSummaryReport", return_value=mock_instance),
            patch("chesscom.cli.MatchParticipationReport", return_value=mock_instance),
            patch("chesscom.cli.ProspectReport", return_value=mock_instance),
            patch("chesscom.cli.MatchEligibilityReport", return_value=mock_instance),
        ):
            main(argv)
            return mock_ld, mock_cfg

    def test_load_dotenv_called(self):
        mock_ld, _ = self._run_patched(["member-summary"])
        mock_ld.assert_called_once()

    def test_app_config_from_env_called(self):
        _, mock_cfg = self._run_patched(["member-summary"])
        mock_cfg.assert_called_once()


# ===========================================================================
# main() — --match-id flag
# ===========================================================================


class TestMatchIdFlag:
    def test_match_id_flag_overrides_config(self):
        """--match-id replaces config.match_id via dataclasses.replace."""
        config_without_id = _make_config(match_id=None)
        mock_instance = MagicMock()
        mock_instance.run.return_value = "output/test.xlsx"

        with (
            patch("chesscom.cli.load_dotenv"),
            patch("chesscom.cli.AppConfig.from_env", return_value=config_without_id),
            patch("chesscom.cli.ChessComClient"),
            patch("chesscom.cli.MatchEligibilityReport", return_value=mock_instance) as mock_cls,
        ):
            main(["match-eligibility", "--match-id", "12345"])

        # The config passed to MatchEligibilityReport should have match_id="12345"
        _, kwargs = mock_cls.call_args
        passed_config = mock_cls.call_args[0][1]  # second positional arg
        assert passed_config.match_id == "12345"

    def test_env_match_id_used_when_no_flag(self):
        """When --match-id absent, config.match_id from env is preserved."""
        config_with_id = _make_config(match_id="env-42")
        mock_instance = MagicMock()
        mock_instance.run.return_value = "output/test.xlsx"

        with (
            patch("chesscom.cli.load_dotenv"),
            patch("chesscom.cli.AppConfig.from_env", return_value=config_with_id),
            patch("chesscom.cli.ChessComClient"),
            patch("chesscom.cli.MatchEligibilityReport", return_value=mock_instance) as mock_cls,
        ):
            main(["match-eligibility"])

        passed_config = mock_cls.call_args[0][1]
        assert passed_config.match_id == "env-42"


# ===========================================================================
# main() — error handling
# ===========================================================================


class TestMainErrorHandling:
    def test_config_value_error_exits_with_code_1(self):
        with (
            patch("chesscom.cli.load_dotenv"),
            patch("chesscom.cli.AppConfig.from_env", side_effect=ValueError("Missing CLUB_REF")),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main(["member-summary"])
        assert exc_info.value.code == 1

    def test_report_value_error_exits_with_code_1(self):
        mock_instance = MagicMock()
        mock_instance.run.side_effect = ValueError("data_analysis_year required")
        with (
            patch("chesscom.cli.load_dotenv"),
            patch("chesscom.cli.AppConfig.from_env", return_value=_make_config()),
            patch("chesscom.cli.ChessComClient"),
            patch("chesscom.cli.MatchParticipationReport", return_value=mock_instance),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main(["match-participation"])
        assert exc_info.value.code == 1

    def test_keyboard_interrupt_exits_with_code_130(self):
        mock_instance = MagicMock()
        mock_instance.run.side_effect = KeyboardInterrupt
        with (
            patch("chesscom.cli.load_dotenv"),
            patch("chesscom.cli.AppConfig.from_env", return_value=_make_config()),
            patch("chesscom.cli.ChessComClient"),
            patch("chesscom.cli.MemberSummaryReport", return_value=mock_instance),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main(["member-summary"])
        assert exc_info.value.code == 130

    def test_config_error_message_printed_to_stderr(self, capsys):
        with (
            patch("chesscom.cli.load_dotenv"),
            patch("chesscom.cli.AppConfig.from_env", side_effect=ValueError("Missing CLUB_REF")),
        ):
            with pytest.raises(SystemExit):
                main(["member-summary"])
        captured = capsys.readouterr()
        assert "Configuration error" in captured.err
        assert "Missing CLUB_REF" in captured.err


# ===========================================================================
# main() — output printed on success
# ===========================================================================


class TestMainOutput:
    def test_report_path_printed_on_success(self, capsys):
        mock_instance = MagicMock()
        mock_instance.run.return_value = "output/My Report.xlsx"
        with (
            patch("chesscom.cli.load_dotenv"),
            patch("chesscom.cli.AppConfig.from_env", return_value=_make_config()),
            patch("chesscom.cli.ChessComClient"),
            patch("chesscom.cli.MemberSummaryReport", return_value=mock_instance),
        ):
            main(["member-summary"])
        captured = capsys.readouterr()
        assert "output/My Report.xlsx" in captured.out

    def test_execution_time_printed_on_success(self, capsys):
        mock_instance = MagicMock()
        mock_instance.run.return_value = "output/test.xlsx"
        with (
            patch("chesscom.cli.load_dotenv"),
            patch("chesscom.cli.AppConfig.from_env", return_value=_make_config()),
            patch("chesscom.cli.ChessComClient"),
            patch("chesscom.cli.MemberSummaryReport", return_value=mock_instance),
        ):
            main(["member-summary"])
        captured = capsys.readouterr()
        assert "Execution time" in captured.out


# ===========================================================================
# build_parser — timeout-check subcommand
# ===========================================================================


class TestTimeoutCheckParser:
    def test_timeout_check_subcommand(self):
        args = build_parser().parse_args(["timeout-check", "12345"])
        assert args.subcommand == "timeout-check"
        assert args.match_ids == ["12345"]

    def test_timeout_check_multiple_ids(self):
        args = build_parser().parse_args(["timeout-check", "111", "222", "333"])
        assert args.match_ids == ["111", "222", "333"]

    def test_timeout_check_all_keyword(self):
        args = build_parser().parse_args(["timeout-check", "all"])
        assert args.match_ids == ["all"]

    def test_timeout_check_threshold_flag(self):
        args = build_parser().parse_args(["timeout-check", "999", "--threshold", "10"])
        assert args.threshold == 10.0

    def test_timeout_check_threshold_defaults_to_none(self):
        args = build_parser().parse_args(["timeout-check", "999"])
        assert args.threshold is None

    def test_timeout_check_no_ids_exits(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["timeout-check"])


# ===========================================================================
# build_parser — common CLI args
# ===========================================================================


class TestCommonCliArgs:
    def test_club_ref_flag(self):
        args = build_parser().parse_args(["member-summary", "--club-ref", "my-club"])
        assert args.club_ref == "my-club"

    def test_club_name_flag(self):
        args = build_parser().parse_args(["member-summary", "--club-name", "My Club"])
        assert args.club_name == "My Club"

    def test_club_ref_defaults_to_none(self):
        args = build_parser().parse_args(["member-summary"])
        assert args.club_ref is None

    def test_year_flag_on_match_participation(self):
        args = build_parser().parse_args(["match-participation", "--year", "2025"])
        assert args.year == 2025

    def test_clubs_flag_on_prospects(self):
        args = build_parser().parse_args(["prospects", "--clubs", "club-a", "club-b"])
        assert args.clubs == ["club-a", "club-b"]

    def test_exclusion_club_flag_on_prospects(self):
        args = build_parser().parse_args(["prospects", "--exclusion-club", "home-club"])
        assert args.exclusion_club == "home-club"

    def test_common_args_available_on_all_subcommands(self):
        for subcmd_argv in [
            ["member-summary", "--club-ref", "x"],
            ["match-participation", "--club-ref", "x"],
            ["prospects", "--club-ref", "x"],
            ["match-eligibility", "--club-ref", "x"],
            ["timeout-check", "all", "--club-ref", "x"],
        ]:
            args = build_parser().parse_args(subcmd_argv)
            assert args.club_ref == "x"


# ===========================================================================
# main() — CLI override precedence
# ===========================================================================


class TestCliOverridePrecedence:
    def test_club_ref_cli_overrides_env(self):
        config = _make_config(club_ref="env-club")
        mock_instance = MagicMock()
        mock_instance.run.return_value = "output/test.xlsx"

        with (
            patch("chesscom.cli.load_dotenv"),
            patch("chesscom.cli.AppConfig.from_env", return_value=config),
            patch("chesscom.cli.ChessComClient"),
            patch("chesscom.cli.MemberSummaryReport", return_value=mock_instance) as mock_cls,
        ):
            main(["member-summary", "--club-ref", "cli-club"])

        passed_config = mock_cls.call_args[0][1]
        assert passed_config.club_ref == "cli-club"

    def test_env_used_when_no_cli_flag(self):
        config = _make_config(club_ref="env-club")
        mock_instance = MagicMock()
        mock_instance.run.return_value = "output/test.xlsx"

        with (
            patch("chesscom.cli.load_dotenv"),
            patch("chesscom.cli.AppConfig.from_env", return_value=config),
            patch("chesscom.cli.ChessComClient"),
            patch("chesscom.cli.MemberSummaryReport", return_value=mock_instance) as mock_cls,
        ):
            main(["member-summary"])

        passed_config = mock_cls.call_args[0][1]
        assert passed_config.club_ref == "env-club"

    def test_year_cli_overrides_env(self):
        config = _make_config(data_analysis_year=2024)
        mock_instance = MagicMock()
        mock_instance.run.return_value = "output/test.xlsx"

        with (
            patch("chesscom.cli.load_dotenv"),
            patch("chesscom.cli.AppConfig.from_env", return_value=config),
            patch("chesscom.cli.ChessComClient"),
            patch("chesscom.cli.MatchParticipationReport", return_value=mock_instance) as mock_cls,
        ):
            main(["match-participation", "--year", "2025"])

        passed_config = mock_cls.call_args[0][1]
        assert passed_config.data_analysis_year == 2025


# ===========================================================================
# main() — timeout-check routing
# ===========================================================================


class TestTimeoutCheckRouting:
    def test_timeout_check_runs_correct_report(self):
        mock_instance = MagicMock()
        mock_instance.run.return_value = "output/test.xlsx"
        mock_instance.format_console_summary.return_value = "No issues"

        with (
            patch("chesscom.cli.load_dotenv"),
            patch("chesscom.cli.AppConfig.from_env", return_value=_make_config()),
            patch("chesscom.cli.ChessComClient"),
            patch("chesscom.cli.TimeoutCheckReport", return_value=mock_instance) as mock_cls,
        ):
            main(["timeout-check", "999"])

        mock_cls.assert_called_once()
        mock_instance.run.assert_called_once()

    def test_timeout_check_prints_console_summary(self, capsys):
        mock_instance = MagicMock()
        mock_instance.run.return_value = "output/test.xlsx"
        mock_instance.format_console_summary.return_value = "Summary text here"

        with (
            patch("chesscom.cli.load_dotenv"),
            patch("chesscom.cli.AppConfig.from_env", return_value=_make_config()),
            patch("chesscom.cli.ChessComClient"),
            patch("chesscom.cli.TimeoutCheckReport", return_value=mock_instance),
        ):
            main(["timeout-check", "999"])

        captured = capsys.readouterr()
        assert "Summary text here" in captured.out

    def test_timeout_check_passes_match_ids(self):
        mock_instance = MagicMock()
        mock_instance.run.return_value = "output/test.xlsx"
        mock_instance.format_console_summary.return_value = ""

        with (
            patch("chesscom.cli.load_dotenv"),
            patch("chesscom.cli.AppConfig.from_env", return_value=_make_config()),
            patch("chesscom.cli.ChessComClient"),
            patch("chesscom.cli.TimeoutCheckReport", return_value=mock_instance) as mock_cls,
        ):
            main(["timeout-check", "111", "222"])

        _, kwargs = mock_cls.call_args
        assert kwargs["match_ids"] == ["111", "222"]

    def test_timeout_check_threshold_overrides_config(self):
        config = _make_config()
        mock_instance = MagicMock()
        mock_instance.run.return_value = "output/test.xlsx"
        mock_instance.format_console_summary.return_value = ""

        with (
            patch("chesscom.cli.load_dotenv"),
            patch("chesscom.cli.AppConfig.from_env", return_value=config),
            patch("chesscom.cli.ChessComClient"),
            patch("chesscom.cli.TimeoutCheckReport", return_value=mock_instance) as mock_cls,
        ):
            main(["timeout-check", "999", "--threshold", "24"])

        passed_config = mock_cls.call_args[0][1]
        assert passed_config.timeout_threshold_hours == 24.0
