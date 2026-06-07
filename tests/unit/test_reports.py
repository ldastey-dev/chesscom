"""Unit tests for chesscom.reports.*

All HTTP I/O is eliminated by providing a MagicMock for ChessComClient.
AppConfig instances are created directly via the constructor (no env vars
needed).

Test strategy
-------------
- Each report class has its own test class.
- client methods are configured per-test via MagicMock return_value.
- run() tests use tmp_path to avoid hitting the real filesystem.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from datetime import timedelta as td
from unittest.mock import MagicMock, patch

import pytest

from chesscom.config import AppConfig
from chesscom.reports.match_eligibility import MatchEligibilityReport
from chesscom.reports.match_participation import MatchParticipationReport
from chesscom.reports.member_summary import MemberSummaryReport
from chesscom.reports.prospect import ProspectReport
from chesscom.reports.timeout_check import TimeoutCheckReport

# ---------------------------------------------------------------------------
# Shared fixtures / factories
# ---------------------------------------------------------------------------

_PROFILE = {
    "username": "alice",
    "name": "Alice Smith",
    "title": "FM",
    "joined": 1_600_000_000,
    "last_online": 1_700_000_000,
}

_STATS = {
    "chess_daily": {
        "last": {"rating": 1500},
        "record": {"timeout_percent": 2.5},
    },
    "chess960_daily": {
        "last": {"rating": 1400},
    },
}

_CLUB_MEMBERS = [
    {"username": "alice", "joined": 1_600_000_000},
]

_MATCH_DATA = {
    "name": "League Match 1",
    "start_time": 1_704_067_200,  # 2024-01-01
    "settings": {"max_rating": 1800, "rules": "chess"},
    "teams": {
        "team1": {
            "name": "Team Scotland",
            "players": [
                {
                    "username": "alice",
                    "played_as_white": "win",
                    "played_as_black": "checkmated",  # realistic Chess.com string
                }
            ],
        },
        "team2": {"name": "Opponents", "players": []},
    },
}

_CLUB_MATCHES = {
    "finished": [
        {
            "@id": "https://api.chess.com/pub/match/999",
            "name": "League Match 1",
            "start_time": 1_704_067_200,
        }
    ],
    "in_progress": [],
    "registered": [],
}


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


def _make_client(
    profile=None,
    stats=None,
    club_members=None,
    match_data=None,
    club_matches=None,
) -> MagicMock:
    client = MagicMock()
    client.get_player_profile.return_value = profile or _PROFILE
    client.get_player_stats.return_value = stats or _STATS
    client.get_club_members.return_value = club_members or _CLUB_MEMBERS
    client.get_match.return_value = match_data or _MATCH_DATA
    client.get_club_matches.return_value = club_matches or _CLUB_MATCHES
    return client


# ===========================================================================
# MemberSummaryReport
# ===========================================================================


class TestMemberSummaryReport:
    def test_get_report_name(self):
        r = MemberSummaryReport(_make_client(), _make_config())
        assert r.get_report_name() == "Club Member Summary Report"

    def test_collect_data_returns_one_row_per_member(self):
        r = MemberSummaryReport(_make_client(), _make_config())
        data = r.collect_data()
        assert len(data) == 1
        assert data[0]["Username"] == "alice"

    def test_collect_data_has_expected_columns(self):
        r = MemberSummaryReport(_make_client(), _make_config())
        row = r.collect_data()[0]
        for col in (
            "FIDE Title",
            "Username",
            "Name",
            "Joined Chess.com",
            "Joined Club",
            "Last Online",
            "Daily Rating",
            "Chess960 Rating",
            "Timeout Percentage",
        ):
            assert col in row, f"Missing column: {col}"

    def test_collect_data_daily_rating(self):
        r = MemberSummaryReport(_make_client(), _make_config())
        assert r.collect_data()[0]["Daily Rating"] == 1500

    def test_collect_data_chess960_unrated_when_absent(self):
        stats = {"chess_daily": {"last": {"rating": 1200}, "record": {"timeout_percent": 0}}}
        r = MemberSummaryReport(_make_client(stats=stats), _make_config())
        assert r.collect_data()[0]["Chess960 Rating"] == "Unrated"

    def test_collect_data_fetches_profile_and_stats_per_member(self):
        client = _make_client()
        MemberSummaryReport(client, _make_config()).collect_data()
        client.get_player_profile.assert_called_once_with("alice")
        client.get_player_stats.assert_called_once_with("alice")

    def test_run_creates_file(self, tmp_path):
        r = MemberSummaryReport(_make_client(), _make_config())
        path = _run_with_tmpdir(r, tmp_path)
        assert os.path.isfile(path)

    def test_multiple_members(self):
        club_members = [
            {"username": "alice", "joined": 1_600_000_000},
            {"username": "bob", "joined": 1_600_000_001},
        ]
        bob_profile = {**_PROFILE, "username": "bob", "name": "Bob Jones"}
        client = _make_client(club_members=club_members)
        client.get_player_profile.side_effect = [_PROFILE, bob_profile]
        client.get_player_stats.side_effect = [_STATS, _STATS]
        r = MemberSummaryReport(client, _make_config())
        data = r.collect_data()
        assert len(data) == 2
        assert {row["Username"] for row in data} == {"alice", "bob"}


# ===========================================================================
# ProspectReport
# ===========================================================================


class TestProspectReport:
    def test_get_report_name(self):
        r = ProspectReport(_make_client(), _make_config())
        assert r.get_report_name() == "Member Prospects"

    def test_collect_data_returns_rows(self):
        r = ProspectReport(_make_client(), _make_config())
        data = r.collect_data()
        assert len(data) == 1
        assert data[0]["Username"] == "alice"

    def test_collect_data_has_sourced_club(self):
        r = ProspectReport(_make_client(), _make_config(prospect_clubs=["team-ireland"]))
        data = r.collect_data()
        assert data[0]["Sourced Club"] == "team-ireland"

    def test_exclusion_removes_member(self):
        # exclusion club also contains "alice"
        config = _make_config(exclusion_club="team-scotland")
        client = _make_client()
        # Both prospect club and exclusion club return "alice"
        client.get_club_members.return_value = _CLUB_MEMBERS
        r = ProspectReport(client, config)
        data = r.collect_data()
        assert all(row["Username"] != "alice" for row in data)

    def test_deduplication_across_clubs(self):
        """Duplicate across two clubs → only one row."""
        config = _make_config(prospect_clubs=["team-ireland", "team-england"])
        # Both clubs return the same member "alice"
        alice_members = [{"username": "alice", "joined": 1_600_000_000}]
        client = _make_client(club_members=alice_members)
        r = ProspectReport(client, config)
        data = r.collect_data()
        alice_rows = [row for row in data if row["Username"] == "alice"]
        assert len(alice_rows) == 1

    def test_no_prospect_clubs_returns_empty(self):
        config = _make_config(prospect_clubs=[])
        r = ProspectReport(_make_client(), config)
        assert r.collect_data() == []

    def test_collect_data_columns(self):
        r = ProspectReport(_make_client(), _make_config())
        row = r.collect_data()[0]
        for col in (
            "FIDE Title",
            "Username",
            "Name",
            "Sourced Club",
            "Daily Rating",
            "Chess960 Rating",
            "Timeout Percentage",
            "Last Online",
            "Joined Chess.com",
        ):
            assert col in row, f"Missing column: {col}"

    def test_full_data_not_fetched_for_excluded_member(self):
        """Excluded members should not trigger profile/stats calls."""
        config = _make_config(
            prospect_clubs=["team-ireland"],
            exclusion_club="team-scotland",
        )
        # prospect club returns "alice"; exclusion club also returns "alice"
        client = _make_client()
        client.get_club_members.return_value = _CLUB_MEMBERS
        ProspectReport(client, config).collect_data()
        client.get_player_profile.assert_not_called()


# ===========================================================================
# MatchEligibilityReport
# ===========================================================================


class TestMatchEligibilityReport:
    def test_get_report_name(self):
        r = MatchEligibilityReport(_make_client(), _make_config())
        assert r.get_report_name() == "Match Eligibility"

    def test_collect_data_returns_rows(self):
        r = MatchEligibilityReport(_make_client(), _make_config())
        data = r.collect_data()
        assert len(data) == 1
        assert data[0]["Username"] == "alice"

    def test_collect_data_columns(self):
        r = MatchEligibilityReport(_make_client(), _make_config())
        row = r.collect_data()[0]
        for col in (
            "Username",
            "Daily Rating",
            "Chess960 Rating",
            "Variant",
            "Last Online",
            "Timeout Percentage",
            "Signed Up",
        ):
            assert col in row, f"Missing column: {col}"

    def test_collect_data_raises_when_no_match_id(self):
        config = _make_config(match_id=None)
        r = MatchEligibilityReport(_make_client(), config)
        with pytest.raises(ValueError, match="match_id"):
            r.collect_data()

    def test_signed_up_flag_yes_for_participant(self):
        """alice is in the match participants → Signed Up: Yes."""
        r = MatchEligibilityReport(_make_client(), _make_config())
        data = r.collect_data()
        assert data[0]["Signed Up"] == "Yes"

    def test_signed_up_flag_no_for_non_participant(self):
        """bob is eligible but not in participants → Signed Up: No."""
        club_members = [
            {"username": "bob", "joined": 1_600_000_000},
        ]
        bob_profile = {**_PROFILE, "username": "bob"}
        client = _make_client(club_members=club_members)
        client.get_player_profile.return_value = bob_profile
        r = MatchEligibilityReport(client, _make_config())
        data = r.collect_data()
        assert data[0]["Signed Up"] == "No"

    def test_member_above_max_rating_excluded(self):
        """alice (1500) is excluded when max_rating is 1000."""
        match_data = {
            **_MATCH_DATA,
            "settings": {"max_rating": 1000, "rules": "chess"},
        }
        r = MatchEligibilityReport(_make_client(match_data=match_data), _make_config())
        data = r.collect_data()
        # alice's 1500 > 1000 → no rows
        assert data == []

    def test_sheet_name_includes_variant(self):
        r = MatchEligibilityReport(_make_client(), _make_config())
        r.collect_data()  # populates _variant
        configs = r.build_sheet_configs([])
        assert "CHESS" in configs[0].name.upper()

    def test_chess960_variant_detected(self):
        match_data = {
            **_MATCH_DATA,
            "settings": {"max_rating": 1800, "rules": "chess960"},
        }
        r = MatchEligibilityReport(_make_client(match_data=match_data), _make_config())
        data = r.collect_data()
        assert data[0]["Variant"] == "CHESS960"

    def test_no_max_rating_includes_all_members(self):
        """When max_rating is absent no rating filter is applied."""
        match_data = {
            **_MATCH_DATA,
            "settings": {"rules": "chess"},  # no max_rating key
        }
        r = MatchEligibilityReport(_make_client(match_data=match_data), _make_config())
        data = r.collect_data()
        assert len(data) == 1  # alice still included


# ===========================================================================
# MatchParticipationReport
# ===========================================================================


class TestMatchParticipationReport:
    def test_get_report_name_includes_club_and_year(self):
        r = MatchParticipationReport(_make_client(), _make_config())
        name = r.get_report_name()
        assert "Team Scotland" in name
        assert "2024" in name

    def test_collect_data_returns_member_rows(self):
        r = MatchParticipationReport(_make_client(), _make_config())
        data = r.collect_data()
        assert len(data) == 1
        assert data[0]["Username"] == "alice"

    def test_collect_data_columns(self):
        r = MatchParticipationReport(_make_client(), _make_config())
        row = r.collect_data()[0]
        for col in (
            "Username",
            "Daily Rating",
            "Joined Chess.com",
            "Joined Club",
            "Last Online",
            "Timeout Percentage",
            "Club Timeouts",
            "Total Matches",
            "Participation %",
            "Win Rate %",
        ):
            assert col in row, f"Missing column: {col}"

    def test_collect_data_raises_when_no_year(self):
        config = _make_config(data_analysis_year=None)
        r = MatchParticipationReport(_make_client(), config)
        with pytest.raises(ValueError, match="data_analysis_year"):
            r.collect_data()

    def test_collect_data_filters_matches_by_year(self):
        """Matches from 2023 should be excluded when year=2024."""
        club_matches = {
            "finished": [
                {  # 2023 match — should be excluded
                    "@id": "https://api.chess.com/pub/match/100",
                    "name": "Old Match",
                    "start_time": 1_672_531_200,  # 2023-01-01
                },
                {  # 2024 match — should be included
                    "@id": "https://api.chess.com/pub/match/999",
                    "name": "League Match 1",
                    "start_time": 1_704_067_200,  # 2024-01-01
                },
            ],
            "in_progress": [],
            "registered": [],
        }
        client = _make_client(club_matches=club_matches)
        r = MatchParticipationReport(client, _make_config(data_analysis_year=2024))
        data = r.collect_data()
        # Only 1 match (2024) should count
        assert data[0]["Total Matches"] == 1

    def test_build_sheet_configs_produces_two_sheets(self):
        r = MatchParticipationReport(_make_client(), _make_config())
        members_data = r.collect_data()
        configs = r.build_sheet_configs(members_data)
        assert len(configs) == 2
        sheet_names = [c.name for c in configs]
        assert "Member Metrics" in sheet_names
        assert "Match Data" in sheet_names

    def test_member_metrics_sheet_has_username_hyperlink(self):
        r = MatchParticipationReport(_make_client(), _make_config())
        members_data = r.collect_data()
        configs = r.build_sheet_configs(members_data)
        member_sheet = next(c for c in configs if c.name == "Member Metrics")
        assert member_sheet.hyperlink_column == "Username"

    def test_participation_percentage_calculated(self):
        r = MatchParticipationReport(_make_client(), _make_config())
        data = r.collect_data()
        # alice is in the match → 1/1 = 100%
        assert data[0]["Participation %"] == 100.0

    def test_win_rate_calculated(self):
        r = MatchParticipationReport(_make_client(), _make_config())
        data = r.collect_data()
        # alice: 1 win (white) + 1 loss/checkmated (black) → 50%
        assert data[0]["Win Rate %"] == 50.0


# ===========================================================================
# BaseReport – abstract interface enforced
# ===========================================================================


class TestBaseReportAbstract:
    def test_cannot_instantiate_directly(self):
        from chesscom.reports.base import BaseReport

        with pytest.raises(TypeError):
            BaseReport(_make_client(), _make_config())  # type: ignore[abstract]

    def test_concrete_subclass_without_collect_data_raises(self):
        from chesscom.reports.base import BaseReport

        class Incomplete(BaseReport):
            def get_report_name(self) -> str:
                return "X"

        with pytest.raises(TypeError):
            Incomplete(_make_client(), _make_config())  # type: ignore[abstract]


# ===========================================================================
# Integration-style: run() creates an actual file
# ===========================================================================


def _run_with_tmpdir(report, tmp_path) -> str:
    """Monkey-patch ExcelReportWriter to write into tmp_path."""
    from chesscom.export.excel import ExcelReportWriter

    orig_init = ExcelReportWriter.__init__

    def patched_init(self, output_dir, base_name, sheets):
        orig_init(self, str(tmp_path / "output"), base_name, sheets)

    with patch.object(ExcelReportWriter, "__init__", patched_init):
        return report.run()


class TestRunCreatesFile:
    def test_member_summary_run(self, tmp_path):
        r = MemberSummaryReport(_make_client(), _make_config())
        path = _run_with_tmpdir(r, tmp_path)
        assert os.path.isfile(path)

    def test_prospect_run(self, tmp_path):
        r = ProspectReport(_make_client(), _make_config())
        path = _run_with_tmpdir(r, tmp_path)
        assert os.path.isfile(path)

    def test_match_eligibility_run(self, tmp_path):
        r = MatchEligibilityReport(_make_client(), _make_config())
        path = _run_with_tmpdir(r, tmp_path)
        assert os.path.isfile(path)

    def test_match_participation_run(self, tmp_path):
        r = MatchParticipationReport(_make_client(), _make_config())
        path = _run_with_tmpdir(r, tmp_path)
        assert os.path.isfile(path)

    def test_timeout_check_run(self, tmp_path):
        client = _make_timeout_client()
        r = TimeoutCheckReport(client, _make_config(), match_ids=["999"])
        path = _run_with_tmpdir(r, tmp_path)
        assert os.path.isfile(path)


# ===========================================================================
# TimeoutCheckReport — test data
# ===========================================================================

_IN_PROGRESS_MATCH_DATA = {
    "name": "League Match Live",
    "start_time": 1_704_067_200,
    "settings": {"rules": "chess"},
    "teams": {
        "team1": {
            "name": "Team Scotland",
            "players": [
                {
                    "username": "alice",
                    "board": "https://api.chess.com/pub/match/999/1",
                    "played_as_white": "timeout",
                    "played_as_black": "win",
                },
                {
                    "username": "bob",
                    "board": "https://api.chess.com/pub/match/999/2",
                    # No played_as_white/black — both games in progress
                },
            ],
        },
        "team2": {"name": "Opponents", "players": []},
    },
}

_NO_TIMEOUT_MATCH_DATA = {
    "name": "Clean Match",
    "start_time": 1_704_067_200,
    "settings": {"rules": "chess"},
    "teams": {
        "team1": {
            "name": "Team Scotland",
            "players": [
                {
                    "username": "alice",
                    "board": "https://api.chess.com/pub/match/999/1",
                    "played_as_white": "win",
                    "played_as_black": "win",
                },
            ],
        },
        "team2": {"name": "Opponents", "players": []},
    },
}

_CLUB_MATCHES_IN_PROGRESS = {
    "finished": [],
    "in_progress": [
        {
            "@id": "https://api.chess.com/pub/match/999",
            "name": "League Match Live",
            "start_time": 1_704_067_200,
        }
    ],
    "registered": [],
}


def _make_board_data(hours_from_now: float) -> dict:
    """Build board data with a game whose move_by is *hours_from_now* away."""
    move_by_ts = int((datetime.now(tz=UTC) + td(hours=hours_from_now)).timestamp())
    return {
        "board_scores": {},
        "games": [
            {
                "white": {
                    "username": "bob",
                    "team": "https://api.chess.com/pub/club/team-scotland",
                },
                "black": {
                    "username": "opponent1",
                    "team": "https://api.chess.com/pub/club/opponents",
                },
                "turn": "white",
                "move_by": move_by_ts,
                "time_control": "1/259200",
                "time_class": "daily",
                "rules": "chess",
            }
        ],
    }


def _make_timeout_client(match_data=None, board_data=None, club_matches=None):
    client = MagicMock()
    client.get_match.return_value = match_data or _IN_PROGRESS_MATCH_DATA
    client.get_match_board.return_value = board_data or _make_board_data(2)
    client.get_club_matches.return_value = club_matches or _CLUB_MATCHES_IN_PROGRESS
    return client


# ===========================================================================
# TimeoutCheckReport
# ===========================================================================


class TestTimeoutCheckReport:
    def test_get_report_name(self):
        r = TimeoutCheckReport(_make_timeout_client(), _make_config(), match_ids=["999"])
        assert r.get_report_name() == "Timeout Check Report"

    def test_collect_data_detects_completed_timeout(self):
        r = TimeoutCheckReport(_make_timeout_client(), _make_config(), match_ids=["999"])
        data = r.collect_data()
        timed_out = [row for row in data if row["Status"] == "Timed Out"]
        assert len(timed_out) >= 1
        assert timed_out[0]["Username"] == "alice"
        assert timed_out[0]["Colour"] == "white"

    def test_collect_data_detects_at_risk(self):
        # bob has no results + board shows move_by 2h away, threshold 5h
        r = TimeoutCheckReport(_make_timeout_client(), _make_config(), match_ids=["999"])
        data = r.collect_data()
        at_risk = [row for row in data if row["Status"] == "At Risk"]
        assert len(at_risk) >= 1
        assert at_risk[0]["Username"] == "bob"

    def test_collect_data_no_at_risk_when_safe(self):
        # move_by is 48h away, threshold 5h → not at risk
        client = _make_timeout_client(board_data=_make_board_data(48))
        r = TimeoutCheckReport(client, _make_config(), match_ids=["999"])
        data = r.collect_data()
        at_risk = [row for row in data if row["Status"] == "At Risk"]
        assert len(at_risk) == 0

    def test_collect_data_no_alerts_for_clean_match(self):
        client = _make_timeout_client(match_data=_NO_TIMEOUT_MATCH_DATA)
        r = TimeoutCheckReport(client, _make_config(), match_ids=["999"])
        data = r.collect_data()
        assert len(data) == 0

    def test_build_sheet_configs_produces_two_sheets(self):
        r = TimeoutCheckReport(_make_timeout_client(), _make_config(), match_ids=["999"])
        data = r.collect_data()
        configs = r.build_sheet_configs(data)
        assert len(configs) == 2
        names = [c.name for c in configs]
        assert "Timeout Alerts by Match" in names
        assert "Timeout Summary by Player" in names

    def test_player_summary_sheet_counts_timeouts(self):
        r = TimeoutCheckReport(_make_timeout_client(), _make_config(), match_ids=["999"])
        data = r.collect_data()
        configs = r.build_sheet_configs(data)
        player_sheet = next(c for c in configs if c.name == "Timeout Summary by Player")
        df = player_sheet.dataframe
        # alice has 1 completed timeout
        alice_rows = df[df["Username"] == "alice"]
        assert len(alice_rows) == 1
        assert alice_rows.iloc[0]["Total Timeouts"] == 1

    def test_format_console_summary_no_alerts(self):
        client = _make_timeout_client(match_data=_NO_TIMEOUT_MATCH_DATA)
        r = TimeoutCheckReport(client, _make_config(), match_ids=["999"])
        r.collect_data()
        summary = r.format_console_summary()
        assert "No timeout issues found" in summary

    def test_format_console_summary_with_alerts(self):
        r = TimeoutCheckReport(_make_timeout_client(), _make_config(), match_ids=["999"])
        r.collect_data()
        summary = r.format_console_summary()
        assert "TIMED OUT" in summary
        assert "alice" in summary
        assert "League Match Live" in summary

    def test_all_keyword_fetches_in_progress(self):
        client = _make_timeout_client()
        r = TimeoutCheckReport(client, _make_config(), match_ids=["all"])
        r.collect_data()
        client.get_club_matches.assert_called_once_with("team-scotland")

    def test_specific_ids_do_not_fetch_club_matches(self):
        client = _make_timeout_client()
        r = TimeoutCheckReport(client, _make_config(), match_ids=["999"])
        r.collect_data()
        client.get_club_matches.assert_not_called()

    def test_collect_data_has_expected_columns(self):
        r = TimeoutCheckReport(_make_timeout_client(), _make_config(), match_ids=["999"])
        data = r.collect_data()
        assert len(data) > 0
        row = data[0]
        for col in (
            "Match Name",
            "Match ID",
            "Username",
            "Board",
            "Colour",
            "Status",
            "Move By",
            "Hours Remaining",
        ):
            assert col in row, f"Missing column: {col}"
