"""Unit tests for the services layer.

All functions under test are pure (no I/O, no HTTP), so no mocking is
needed — just input/output assertions.

Edge cases covered: zero division, empty lists, unknown result strings,
members with None ratings, case-insensitive username matching.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from chesscom.domain.models import Match, MatchResult, Member, MemberParticipation
from chesscom.domain.services import (
    build_participation_stats,
    calculate_participation_percentage,
    calculate_win_rate,
    classify_result,
    deduplicate_members,
    exclude_members,
    filter_members_by_rating,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_EPOCH = datetime.fromtimestamp(0, tz=UTC)


def _member(
    username: str,
    daily_rating: int | None = 1200,
    chess960_rating: int | None = 1100,
) -> Member:
    return Member(
        username=username,
        name="",
        fide_title="",
        daily_rating=daily_rating,
        chess960_rating=chess960_rating,
        timeout_percent=0.0,
        joined_chess_com=_EPOCH,
        last_online=_EPOCH,
        joined_club=None,
    )


def _match(match_id: str, participants: list[MatchResult] | None = None) -> Match:
    return Match(
        match_id=match_id,
        name=f"Match {match_id}",
        url=f"https://api.chess.com/pub/match/{match_id}",
        start_time=_EPOCH,
        max_rating=None,
        variant="chess",
        participants=participants or [],
    )


def _result(username: str, white: str = "win", black: str = "win") -> MatchResult:
    return MatchResult(username=username, result_white=white, result_black=black)


# ---------------------------------------------------------------------------
# calculate_participation_percentage
# ---------------------------------------------------------------------------


class TestCalculateParticipationPercentage:
    def test_full_participation(self):
        assert calculate_participation_percentage(10, 10) == 100.0

    def test_half_participation(self):
        assert calculate_participation_percentage(10, 5) == 50.0

    def test_zero_participation(self):
        assert calculate_participation_percentage(10, 0) == 0.0

    def test_zero_total_matches_returns_zero(self):
        assert calculate_participation_percentage(0, 0) == 0.0

    def test_result_is_rounded_to_two_decimal_places(self):
        # 1/3 = 33.333...
        result = calculate_participation_percentage(3, 1)
        assert result == 33.33

    def test_single_match_participated(self):
        assert calculate_participation_percentage(1, 1) == 100.0

    def test_returns_float(self):
        assert isinstance(calculate_participation_percentage(5, 3), float)


# ---------------------------------------------------------------------------
# calculate_win_rate
# ---------------------------------------------------------------------------


class TestCalculateWinRate:
    def test_all_wins(self):
        assert calculate_win_rate(10, 0, 0) == 100.0

    def test_no_wins(self):
        assert calculate_win_rate(0, 10, 0) == 0.0

    def test_mixed_results(self):
        # 3 wins / 6 total = 50%
        assert calculate_win_rate(3, 2, 1) == 50.0

    def test_zero_games_returns_zero(self):
        assert calculate_win_rate(0, 0, 0) == 0.0

    def test_rounded_to_two_decimal_places(self):
        # 1 win / 3 total = 33.333...
        assert calculate_win_rate(1, 1, 1) == 33.33

    def test_draws_only(self):
        assert calculate_win_rate(0, 0, 5) == 0.0

    def test_losses_only(self):
        assert calculate_win_rate(0, 5, 0) == 0.0

    def test_returns_float(self):
        assert isinstance(calculate_win_rate(2, 1, 1), float)


# ---------------------------------------------------------------------------
# classify_result
# ---------------------------------------------------------------------------


class TestClassifyResult:
    @pytest.mark.parametrize("result", ["win"])
    def test_win(self, result):
        assert classify_result(result) == "win"

    @pytest.mark.parametrize("result", ["checkmated", "resigned"])
    def test_loss(self, result):
        assert classify_result(result) == "loss"

    @pytest.mark.parametrize("result", ["agreed", "repetition", "stalemate", "insufficient"])
    def test_draw(self, result):
        assert classify_result(result) == "draw"

    @pytest.mark.parametrize("result", ["timeout"])
    def test_timeout(self, result):
        assert classify_result(result) == "timeout"

    @pytest.mark.parametrize("result", ["in progress", "abandoned", "", "unknown_value"])
    def test_unknown(self, result):
        assert classify_result(result) == "unknown"

    def test_whitespace_is_stripped(self):
        assert classify_result("  win  ") == "win"

    def test_case_insensitive(self):
        assert classify_result("WIN") == "win"
        assert classify_result("Checkmated") == "loss"


# ---------------------------------------------------------------------------
# filter_members_by_rating
# ---------------------------------------------------------------------------


class TestFilterMembersByRating:
    def test_filters_by_daily_rating(self):
        members = [
            _member("alice", daily_rating=1200),
            _member("bob", daily_rating=1500),
            _member("carol", daily_rating=1400),
        ]
        result = filter_members_by_rating(members, max_rating=1400, variant="chess")
        usernames = [m.username for m in result]
        assert "alice" in usernames
        assert "carol" in usernames
        assert "bob" not in usernames

    def test_filters_by_chess960_rating(self):
        members = [
            _member("alice", chess960_rating=1000),
            _member("bob", chess960_rating=1600),
        ]
        result = filter_members_by_rating(members, max_rating=1200, variant="chess960")
        assert len(result) == 1
        assert result[0].username == "alice"

    def test_max_rating_is_inclusive(self):
        members = [_member("alice", daily_rating=1400)]
        result = filter_members_by_rating(members, max_rating=1400, variant="chess")
        assert len(result) == 1

    def test_none_rating_excluded(self):
        members = [_member("alice", daily_rating=None)]
        result = filter_members_by_rating(members, max_rating=1400, variant="chess")
        assert result == []

    def test_none_chess960_rating_excluded(self):
        members = [_member("alice", chess960_rating=None)]
        result = filter_members_by_rating(members, max_rating=1400, variant="chess960")
        assert result == []

    def test_empty_list_returns_empty(self):
        assert filter_members_by_rating([], max_rating=1400) == []

    def test_all_excluded(self):
        members = [_member("alice", daily_rating=1600), _member("bob", daily_rating=1800)]
        result = filter_members_by_rating(members, max_rating=1400)
        assert result == []

    def test_preserves_order(self):
        members = [_member("c", daily_rating=1000), _member("a", daily_rating=900)]
        result = filter_members_by_rating(members, max_rating=1200)
        assert [m.username for m in result] == ["c", "a"]


# ---------------------------------------------------------------------------
# exclude_members
# ---------------------------------------------------------------------------


class TestExcludeMembers:
    def test_excludes_matching_usernames(self):
        members = [_member("alice"), _member("bob"), _member("carol")]
        result = exclude_members(members, {"alice", "carol"})
        assert [m.username for m in result] == ["bob"]

    def test_case_insensitive_exclusion(self):
        members = [_member("Alice"), _member("bob")]
        result = exclude_members(members, {"alice"})
        assert [m.username for m in result] == ["bob"]

    def test_empty_exclusion_set_returns_all(self):
        members = [_member("alice"), _member("bob")]
        assert exclude_members(members, set()) == members

    def test_empty_members_returns_empty(self):
        assert exclude_members([], {"alice"}) == []

    def test_all_excluded_returns_empty(self):
        members = [_member("alice"), _member("bob")]
        result = exclude_members(members, {"alice", "bob"})
        assert result == []

    def test_non_matching_exclusions_ignored(self):
        members = [_member("alice")]
        result = exclude_members(members, {"charlie"})
        assert result == members


# ---------------------------------------------------------------------------
# deduplicate_members
# ---------------------------------------------------------------------------


class TestDeduplicateMembers:
    def test_removes_exact_duplicates(self):
        members = [_member("alice"), _member("alice"), _member("bob")]
        result = deduplicate_members(members)
        assert len(result) == 2
        assert result[0].username == "alice"
        assert result[1].username == "bob"

    def test_case_insensitive_deduplication(self):
        members = [_member("Alice"), _member("alice")]
        result = deduplicate_members(members)
        assert len(result) == 1
        assert result[0].username == "Alice"  # first occurrence kept

    def test_empty_list_returns_empty(self):
        assert deduplicate_members([]) == []

    def test_no_duplicates_unchanged(self):
        members = [_member("alice"), _member("bob")]
        result = deduplicate_members(members)
        assert [m.username for m in result] == ["alice", "bob"]

    def test_preserves_first_occurrence(self):
        m1 = _member("alice")
        m1_dup = _member("alice")
        result = deduplicate_members([m1, m1_dup])
        assert result[0] is m1


# ---------------------------------------------------------------------------
# build_participation_stats
# ---------------------------------------------------------------------------


class TestBuildParticipationStats:
    def test_full_participation_all_wins(self):
        member = _member("alice")
        matches = [
            _match("1", [_result("alice", "win", "win")]),
            _match("2", [_result("alice", "win", "win")]),
        ]
        stats = build_participation_stats(member, matches)
        assert stats.matches_played == 2
        assert stats.matches_participated == 2
        assert stats.wins == 4
        assert stats.losses == 0
        assert stats.draws == 0
        assert stats.timeouts == 0
        assert stats.participation_pct == 100.0
        assert stats.win_rate_pct == 100.0

    def test_partial_participation(self):
        member = _member("alice")
        matches = [
            _match("1", [_result("alice", "win", "win")]),
            _match("2"),  # alice not in this match
        ]
        stats = build_participation_stats(member, matches)
        assert stats.matches_played == 2
        assert stats.matches_participated == 1
        assert stats.participation_pct == 50.0

    def test_timeout_counts_as_loss(self):
        member = _member("alice")
        matches = [_match("1", [_result("alice", "timeout", "win")])]
        stats = build_participation_stats(member, matches)
        assert stats.timeouts == 1
        assert stats.losses == 1  # timeout counted as loss
        assert stats.wins == 1
        assert stats.win_rate_pct == calculate_win_rate(1, 1, 0)

    def test_in_progress_excluded_from_win_rate(self):
        member = _member("alice")
        matches = [_match("1", [_result("alice", "in progress", "in progress")])]
        stats = build_participation_stats(member, matches)
        assert stats.wins == 0
        assert stats.losses == 0
        assert stats.draws == 0
        assert stats.win_rate_pct == 0.0

    def test_draw_results(self):
        member = _member("alice")
        matches = [_match("1", [_result("alice", "agreed", "stalemate")])]
        stats = build_participation_stats(member, matches)
        assert stats.draws == 2

    def test_mixed_results(self):
        member = _member("alice")
        matches = [
            _match("1", [_result("alice", "win", "checkmated")]),
            _match("2", [_result("alice", "agreed", "timeout")]),
        ]
        stats = build_participation_stats(member, matches)
        assert stats.wins == 1
        assert stats.losses == 2  # checkmated + timeout
        assert stats.draws == 1
        assert stats.timeouts == 1

    def test_no_matches_returns_zeroes(self):
        member = _member("alice")
        stats = build_participation_stats(member, [])
        assert stats.matches_played == 0
        assert stats.matches_participated == 0
        assert stats.participation_pct == 0.0
        assert stats.win_rate_pct == 0.0

    def test_case_insensitive_username_matching(self):
        member = _member("Alice")
        matches = [_match("1", [_result("alice", "win", "win")])]
        stats = build_participation_stats(member, matches)
        assert stats.matches_participated == 1

    def test_daily_rating_propagated(self):
        member = _member("alice", daily_rating=1350)
        stats = build_participation_stats(member, [])
        assert stats.daily_rating == 1350

    def test_none_daily_rating_propagated(self):
        member = _member("alice", daily_rating=None)
        stats = build_participation_stats(member, [])
        assert stats.daily_rating is None

    def test_username_propagated(self):
        member = _member("testuser")
        stats = build_participation_stats(member, [])
        assert stats.username == "testuser"

    def test_returns_member_participation_instance(self):
        member = _member("alice")
        stats = build_participation_stats(member, [])
        assert isinstance(stats, MemberParticipation)
