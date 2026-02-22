"""Unit tests for domain model dataclasses.

Tests cover :meth:`Member.from_api_response` and
:meth:`Match.from_api_response` factory methods, verifying happy paths,
missing/malformed data, and edge cases.  No HTTP or I/O is involved.
"""

from __future__ import annotations

from datetime import UTC, datetime

from chesscom.domain.models import Match, MatchResult, Member, MemberParticipation

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ts(year: int, month: int = 1, day: int = 1) -> int:
    """Return a UTC unix timestamp for the given date."""
    return int(datetime(year, month, day, tzinfo=UTC).timestamp())


# ---------------------------------------------------------------------------
# Member.from_api_response
# ---------------------------------------------------------------------------


class TestMemberFromApiResponse:
    def test_happy_path(self, player_profile_response, player_stats_response):
        member = Member.from_api_response(
            profile=player_profile_response,
            stats=player_stats_response,
            joined_club_timestamp=1700000010,
        )
        assert member.username == "testplayer"
        assert member.name == "Test Player"
        assert member.fide_title == "FM"
        assert member.daily_rating == 1200
        assert member.chess960_rating == 1100
        assert member.timeout_percent == 5.0
        assert member.joined_club is not None
        assert member.joined_club == datetime.fromtimestamp(1700000010, tz=UTC)

    def test_joined_chess_com_is_utc_datetime(self, player_profile_response, player_stats_response):
        member = Member.from_api_response(
            profile=player_profile_response,
            stats=player_stats_response,
        )
        assert isinstance(member.joined_chess_com, datetime)
        assert member.joined_chess_com.tzinfo is UTC
        assert member.joined_chess_com == datetime.fromtimestamp(1690000000, tz=UTC)

    def test_last_online_is_utc_datetime(self, player_profile_response, player_stats_response):
        member = Member.from_api_response(
            profile=player_profile_response,
            stats=player_stats_response,
        )
        assert isinstance(member.last_online, datetime)
        assert member.last_online == datetime.fromtimestamp(1700000000, tz=UTC)

    def test_joined_club_none_when_not_provided(self, player_profile_response, player_stats_response):
        member = Member.from_api_response(
            profile=player_profile_response,
            stats=player_stats_response,
        )
        assert member.joined_club is None

    def test_joined_club_set_from_timestamp(self, player_profile_response, player_stats_response):
        ts = _ts(2024, 6, 15)
        member = Member.from_api_response(
            profile=player_profile_response,
            stats=player_stats_response,
            joined_club_timestamp=ts,
        )
        assert member.joined_club == datetime.fromtimestamp(ts, tz=UTC)

    def test_unrated_player_has_none_daily_rating(
        self, player_profile_response, player_stats_response_unrated
    ):
        member = Member.from_api_response(
            profile=player_profile_response,
            stats=player_stats_response_unrated,
        )
        assert member.daily_rating is None
        assert member.chess960_rating is None
        assert member.timeout_percent == 0.0

    def test_no_chess960_stats_gives_none_rating(self, player_profile_response):
        stats = {
            "chess_daily": {
                "last": {"rating": 1500},
                "record": {"timeout_percent": 2.5},
            }
            # chess960_daily intentionally absent
        }
        member = Member.from_api_response(profile=player_profile_response, stats=stats)
        assert member.daily_rating == 1500
        assert member.chess960_rating is None

    def test_non_int_rating_treated_as_none(self, player_profile_response):
        stats = {
            "chess_daily": {
                "last": {"rating": "Unrated"},
                "record": {"timeout_percent": 0},
            }
        }
        member = Member.from_api_response(profile=player_profile_response, stats=stats)
        assert member.daily_rating is None

    def test_missing_profile_fields_use_defaults(self):
        member = Member.from_api_response(profile={}, stats={})
        assert member.username == ""
        assert member.name == ""
        assert member.fide_title == ""
        assert member.daily_rating is None
        assert member.chess960_rating is None
        assert member.timeout_percent == 0.0
        assert member.joined_chess_com == datetime.fromtimestamp(0, tz=UTC)
        assert member.last_online == datetime.fromtimestamp(0, tz=UTC)
        assert member.joined_club is None

    def test_no_fide_title_is_empty_string(self, player_stats_response):
        profile = {"username": "noob", "last_online": 1700000000, "joined": 1690000000}
        member = Member.from_api_response(profile=profile, stats=player_stats_response)
        assert member.fide_title == ""

    def test_timeout_percent_defaults_to_zero_when_record_missing(
        self, player_profile_response
    ):
        stats = {"chess_daily": {"last": {"rating": 1200}}}
        member = Member.from_api_response(profile=player_profile_response, stats=stats)
        assert member.timeout_percent == 0.0


# ---------------------------------------------------------------------------
# MatchResult (dataclass — no factory, test construction directly)
# ---------------------------------------------------------------------------


class TestMatchResult:
    def test_construction(self):
        mr = MatchResult(username="Alice", result_white="win", result_black="checkmated")
        assert mr.username == "Alice"
        assert mr.result_white == "win"
        assert mr.result_black == "checkmated"

    def test_equality(self):
        a = MatchResult("Alice", "win", "win")
        b = MatchResult("Alice", "win", "win")
        assert a == b

    def test_inequality(self):
        a = MatchResult("Alice", "win", "win")
        b = MatchResult("Alice", "win", "loss")
        assert a != b


# ---------------------------------------------------------------------------
# Match.from_api_response
# ---------------------------------------------------------------------------


class TestMatchFromApiResponse:
    def test_happy_path_team1(self, match_detail_response_team1):
        match = Match.from_api_response(
            data=match_detail_response_team1,
            match_id="12345",
            url="https://api.chess.com/pub/match/12345",
            club_name="Test Club",
        )
        assert match.match_id == "12345"
        assert match.name == "Test Match"
        assert match.url == "https://api.chess.com/pub/match/12345"
        assert match.max_rating == 1400
        assert match.variant == "chess"
        assert len(match.participants) == 2
        alice = next(p for p in match.participants if p.username == "Alice")
        assert alice.result_white == "win"
        assert alice.result_black == "checkmated"

    def test_happy_path_team2(self, match_detail_response_team2):
        match = Match.from_api_response(
            data=match_detail_response_team2,
            match_id="99",
            url="https://api.chess.com/pub/match/99",
            club_name="Test Club",
        )
        assert len(match.participants) == 1
        assert match.participants[0].username == "Alice"

    def test_chess960_detected_via_rules(self, match_detail_response_chess960):
        match = Match.from_api_response(
            data=match_detail_response_chess960,
            match_id="960",
            url="https://api.chess.com/pub/match/960",
            club_name="Test Club",
        )
        assert match.variant == "chess960"

    def test_chess960_detected_via_variant_field(self):
        data = {
            "name": "960 Test",
            "settings": {"rules": "chess", "variant": "chess960"},
            "teams": {
                "team1": {"name": "Test Club", "players": []},
                "team2": {"name": "Other", "players": []},
            },
        }
        match = Match.from_api_response(data, "1", "http://x", "Test Club")
        assert match.variant == "chess960"

    def test_standard_chess_variant(self, match_detail_response_team1):
        match = Match.from_api_response(
            match_detail_response_team1, "1", "http://x", "Test Club"
        )
        assert match.variant == "chess"

    def test_no_max_rating_returns_none(self):
        data = {
            "name": "Open Match",
            "settings": {"rules": "chess", "variant": ""},
            "teams": {
                "team1": {"name": "Test Club", "players": []},
                "team2": {"name": "Other", "players": []},
            },
        }
        match = Match.from_api_response(data, "1", "http://x", "Test Club")
        assert match.max_rating is None

    def test_non_int_max_rating_treated_as_none(self):
        data = {
            "name": "Weird Match",
            "settings": {"rules": "chess", "variant": "", "max_rating": "unlimited"},
            "teams": {
                "team1": {"name": "Test Club", "players": []},
                "team2": {"name": "Other", "players": []},
            },
        }
        match = Match.from_api_response(data, "1", "http://x", "Test Club")
        assert match.max_rating is None

    def test_club_not_in_match_returns_empty_participants(self):
        data = {
            "name": "Other Match",
            "settings": {"rules": "chess", "variant": ""},
            "teams": {
                "team1": {"name": "Club A", "players": [{"username": "x", "played_as_white": "win", "played_as_black": "win"}]},
                "team2": {"name": "Club B", "players": []},
            },
        }
        match = Match.from_api_response(data, "1", "http://x", "Unknown Club")
        assert match.participants == []

    def test_start_time_is_utc_datetime(self, match_detail_response_team1):
        ts = _ts(2025, 3, 10)
        data = {**match_detail_response_team1, "start_time": ts}
        match = Match.from_api_response(data, "1", "http://x", "Test Club")
        assert match.start_time == datetime.fromtimestamp(ts, tz=UTC)

    def test_missing_start_time_defaults_to_epoch(self, match_detail_response_team1):
        data = {k: v for k, v in match_detail_response_team1.items() if k != "start_time"}
        match = Match.from_api_response(data, "1", "http://x", "Test Club")
        assert match.start_time == datetime.fromtimestamp(0, tz=UTC)

    def test_in_progress_results_default(self):
        data = {
            "name": "Live Match",
            "settings": {"rules": "chess", "variant": ""},
            "teams": {
                "team1": {
                    "name": "Test Club",
                    "players": [{"username": "Bob"}],  # no played_as_* keys
                },
                "team2": {"name": "Other", "players": []},
            },
        }
        match = Match.from_api_response(data, "1", "http://x", "Test Club")
        assert match.participants[0].result_white == "in progress"
        assert match.participants[0].result_black == "in progress"


# ---------------------------------------------------------------------------
# MemberParticipation (dataclass — no factory, test construction)
# ---------------------------------------------------------------------------


class TestMemberParticipation:
    def test_construction(self):
        mp = MemberParticipation(
            username="testplayer",
            daily_rating=1200,
            matches_played=10,
            matches_participated=8,
            wins=12,
            losses=3,
            draws=1,
            timeouts=0,
            participation_pct=80.0,
            win_rate_pct=75.0,
        )
        assert mp.username == "testplayer"
        assert mp.participation_pct == 80.0
        assert mp.win_rate_pct == 75.0

    def test_none_daily_rating_allowed(self):
        mp = MemberParticipation(
            username="unrated",
            daily_rating=None,
            matches_played=5,
            matches_participated=0,
            wins=0,
            losses=0,
            draws=0,
            timeouts=0,
            participation_pct=0.0,
            win_rate_pct=0.0,
        )
        assert mp.daily_rating is None
