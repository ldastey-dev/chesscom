"""Pure business logic functions for the Chess.com club management tools.

All functions in this module are side-effect-free: they take plain Python
values as input and return plain Python values as output.  No HTTP calls,
no file I/O.  This makes them straightforward to unit-test without mocking.
"""

from __future__ import annotations

from typing import Literal

from chesscom.domain.models import Match, MatchResult, Member, MemberParticipation

# Result strings that Chess.com uses in team match player records
_WIN_RESULTS = frozenset({"win"})
_LOSS_RESULTS = frozenset({"checkmated", "resigned"})
_DRAW_RESULTS = frozenset({"agreed", "repetition", "stalemate", "insufficient"})
_TIMEOUT_RESULTS = frozenset({"timeout"})


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


def calculate_participation_percentage(total_matches: int, participated: int) -> float:
    """Return the percentage of matches a member participated in.

    Args:
        total_matches: Total number of matches played by the club in the
            analysis window.
        participated: Number of those matches the member took part in.

    Returns:
        A float in the range 0–100, rounded to two decimal places.
        Returns ``0.0`` when *total_matches* is zero to avoid division by
        zero.
    """
    if total_matches == 0:
        return 0.0
    return round((participated / total_matches) * 100, 2)


def calculate_win_rate(wins: int, losses: int, draws: int) -> float:
    """Return the win percentage from completed games.

    Timeout games are counted as losses by the caller before this function
    is called (i.e. *losses* already includes timeouts).

    Args:
        wins: Number of won games.
        losses: Number of lost games (including timeouts).
        draws: Number of drawn games.

    Returns:
        A float in the range 0–100, rounded to two decimal places.
        Returns ``0.0`` when no completed games have been played.
    """
    total = wins + losses + draws
    if total == 0:
        return 0.0
    return round((wins / total) * 100, 2)


# ---------------------------------------------------------------------------
# Result classification
# ---------------------------------------------------------------------------


ResultOutcome = Literal["win", "loss", "draw", "timeout", "unknown"]


def classify_result(result: str) -> ResultOutcome:
    """Map a raw Chess.com result string to a normalised outcome.

    Chess.com stores individual game outcomes as strings such as
    ``"win"``, ``"checkmated"``, ``"resigned"``, ``"agreed"`` (draw), etc.
    This function groups them into five canonical categories.

    Args:
        result: The raw result string from the Chess.com API
            (``played_as_white`` / ``played_as_black`` fields).

    Returns:
        One of: ``"win"``, ``"loss"``, ``"draw"``, ``"timeout"``,
        ``"unknown"`` (covers ``"in progress"`` and unexpected values).
    """
    r = result.strip().lower()
    if r in _WIN_RESULTS:
        return "win"
    if r in _LOSS_RESULTS:
        return "loss"
    if r in _DRAW_RESULTS:
        return "draw"
    if r in _TIMEOUT_RESULTS:
        return "timeout"
    return "unknown"


# ---------------------------------------------------------------------------
# Member filtering
# ---------------------------------------------------------------------------


def filter_members_by_rating(
    members: list[Member],
    max_rating: int,
    variant: str = "chess",
) -> list[Member]:
    """Return only the members whose rating is at or below *max_rating*.

    Members with a ``None`` rating for the requested variant are excluded
    because their eligibility cannot be determined.

    Args:
        members: Candidate member list.
        max_rating: Maximum allowable rating (inclusive).
        variant: ``"chess"`` uses :attr:`Member.daily_rating`; any other
            value (e.g. ``"chess960"``) uses
            :attr:`Member.chess960_rating`.

    Returns:
        Filtered list preserving the original order.
    """
    result: list[Member] = []
    for member in members:
        rating = member.daily_rating if variant == "chess" else member.chess960_rating
        if isinstance(rating, int) and rating <= max_rating:
            result.append(member)
    return result


def exclude_members(
    all_members: list[Member],
    exclusion_set: set[str],
) -> list[Member]:
    """Remove members whose username appears in *exclusion_set*.

    Comparison is case-insensitive on both sides.

    Args:
        all_members: Full candidate list.
        exclusion_set: Usernames to exclude (e.g. existing club members
            when building a prospect list).

    Returns:
        Filtered list preserving the original order.
    """
    lower_exclusions = {u.lower() for u in exclusion_set}
    return [m for m in all_members if m.username.lower() not in lower_exclusions]


def deduplicate_members(members: list[Member]) -> list[Member]:
    """Return *members* with duplicate usernames removed.

    When the same username appears more than once (e.g. sourced from
    multiple clubs), only the first occurrence is kept.  Comparison is
    case-insensitive.

    Args:
        members: List that may contain duplicate usernames.

    Returns:
        De-duplicated list preserving the original order.
    """
    seen: set[str] = set()
    result: list[Member] = []
    for member in members:
        key = member.username.lower()
        if key not in seen:
            seen.add(key)
            result.append(member)
    return result


# ---------------------------------------------------------------------------
# Participation stats aggregation
# ---------------------------------------------------------------------------


def build_participation_stats(
    member: Member,
    matches: list[Match],
) -> MemberParticipation:
    """Aggregate a member's participation and performance across a set of matches.

    Iterates over each :class:`~chesscom.domain.models.Match` and, when the
    member appears in :attr:`~chesscom.domain.models.Match.participants`,
    tallies wins, losses, draws and timeouts from their white and black
    game results.  Timeouts count as losses for the purposes of
    :func:`calculate_win_rate`.

    Only *completed* games (classified as win/loss/draw/timeout) contribute
    to the win-rate calculation; ``"in progress"`` and other unknown result
    strings are excluded.

    Args:
        member: The :class:`~chesscom.domain.models.Member` to analyse.
        matches: All matches to consider (typically the club's finished
            matches in the analysis window).

    Returns:
        A :class:`~chesscom.domain.models.MemberParticipation` instance
        with all counters and percentages populated.
    """
    total_matches = len(matches)
    matches_participated = 0
    wins = 0
    losses = 0
    draws = 0
    timeouts = 0

    username_lower = member.username.lower()

    for match in matches:
        player_result: MatchResult | None = next(
            (
                p
                for p in match.participants
                if p.username.lower() == username_lower
            ),
            None,
        )
        if player_result is None:
            continue

        matches_participated += 1

        for raw_result in (player_result.result_white, player_result.result_black):
            outcome = classify_result(raw_result)
            if outcome == "win":
                wins += 1
            elif outcome == "loss":
                losses += 1
            elif outcome == "draw":
                draws += 1
            elif outcome == "timeout":
                timeouts += 1
                losses += 1  # timeouts count as losses for win-rate

    participation_pct = calculate_participation_percentage(
        total_matches, matches_participated
    )
    win_rate_pct = calculate_win_rate(wins, losses, draws)

    return MemberParticipation(
        username=member.username,
        daily_rating=member.daily_rating,
        matches_played=total_matches,
        matches_participated=matches_participated,
        wins=wins,
        losses=losses,
        draws=draws,
        timeouts=timeouts,
        participation_pct=participation_pct,
        win_rate_pct=win_rate_pct,
    )
