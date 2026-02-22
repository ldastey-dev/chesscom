"""Domain model dataclasses for the Chess.com club management tools.

These classes represent the entities used throughout the business logic
layer and decouple the API response shapes from downstream code.  All
fields use Python-native types; the factory classmethods on :class:`Member`
and :class:`Match` handle the translation from raw API JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Member:
    """Represents a Chess.com club member with their ratings and activity.

    Attributes:
        username: Chess.com username (case-preserved).
        name: Real name from the public profile, or an empty string.
        fide_title: FIDE title abbreviation (e.g. ``"GM"``, ``"FM"``), or
            an empty string if no title is held.
        daily_rating: Current standard daily chess rating, or ``None`` if
            the player has never played daily chess.
        chess960_rating: Current Chess960 daily rating, or ``None`` if the
            player has no Chess960 games.
        timeout_percent: Percentage of games finished by timeout (0–100).
        joined_chess_com: UTC datetime when the player created their account.
        last_online: UTC datetime of the player's last recorded activity.
        joined_club: UTC datetime when the player joined the club, or
            ``None`` if the data is not available.
    """

    username: str
    name: str
    fide_title: str
    daily_rating: int | None
    chess960_rating: int | None
    timeout_percent: float
    joined_chess_com: datetime
    last_online: datetime
    joined_club: datetime | None

    @classmethod
    def from_api_response(
        cls,
        profile: dict,
        stats: dict,
        joined_club_timestamp: int | None = None,
    ) -> Member:
        """Construct a :class:`Member` from raw Chess.com API responses.

        Args:
            profile: JSON body from ``GET /player/{username}``.
            stats: JSON body from ``GET /player/{username}/stats``.
            joined_club_timestamp: Unix timestamp of when the member joined
                the club, sourced from the club-members endpoint.  Pass
                ``None`` when the information is not available.

        Returns:
            A fully populated :class:`Member` instance.
        """
        chess_daily = stats.get("chess_daily") or {}
        daily_last = chess_daily.get("last") or {}
        daily_rating_raw = daily_last.get("rating")
        daily_rating = daily_rating_raw if isinstance(daily_rating_raw, int) else None

        chess960_daily = stats.get("chess960_daily") or {}
        chess960_last = chess960_daily.get("last") or {}
        chess960_rating_raw = chess960_last.get("rating")
        chess960_rating = (
            chess960_rating_raw if isinstance(chess960_rating_raw, int) else None
        )

        timeout_percent = float(
            (chess_daily.get("record") or {}).get("timeout_percent", 0.0)
        )

        joined_club: datetime | None = (
            datetime.fromtimestamp(joined_club_timestamp, tz=UTC)
            if joined_club_timestamp is not None
            else None
        )

        return cls(
            username=profile.get("username", ""),
            name=profile.get("name", ""),
            fide_title=profile.get("title", ""),
            daily_rating=daily_rating,
            chess960_rating=chess960_rating,
            timeout_percent=timeout_percent,
            joined_chess_com=datetime.fromtimestamp(
                profile.get("joined", 0), tz=UTC
            ),
            last_online=datetime.fromtimestamp(
                profile.get("last_online", 0), tz=UTC
            ),
            joined_club=joined_club,
        )


@dataclass
class MatchResult:
    """Records how one player performed in a team match.

    Chess.com team matches have each player playing one game as White and
    one as Black against a single opponent.

    Attributes:
        username: Chess.com username of the player.
        result_white: Outcome of the game played as White (e.g. ``"win"``,
            ``"checkmated"``, ``"timeout"``, ``"in progress"``).
        result_black: Outcome of the game played as Black.
    """

    username: str
    result_white: str
    result_black: str


@dataclass
class Match:
    """Represents a Chess.com team match and its participants.

    Attributes:
        match_id: Numeric match identifier as a string.
        name: Human-readable match name.
        url: Fully-qualified API URL for this match.
        start_time: UTC datetime when the match started.
        max_rating: Maximum daily rating required to participate, or
            ``None`` if there is no rating cap.
        variant: ``"chess960"`` or ``"chess"`` (standard daily).
        participants: :class:`MatchResult` records for the club's players
            only (not the opponents).
    """

    match_id: str
    name: str
    url: str
    start_time: datetime
    max_rating: int | None
    variant: str
    participants: list[MatchResult] = field(default_factory=list)

    @classmethod
    def from_api_response(
        cls,
        data: dict,
        match_id: str,
        url: str,
        club_name: str,
    ) -> Match:
        """Construct a :class:`Match` from a raw match-detail API response.

        Args:
            data: JSON body from ``GET /match/{id}``.
            match_id: The match identifier (used to populate
                :attr:`match_id` since it is not always present in the
                response body).
            url: The canonical URL for this match.
            club_name: The club's display name exactly as it appears in the
                API response (e.g. ``"Team Scotland"``).  Used to identify
                which side is ``team1`` vs ``team2``.

        Returns:
            A :class:`Match` with :attr:`participants` populated from the
            club's side of the match only.
        """
        settings = data.get("settings") or {}

        max_rating_raw = settings.get("max_rating")
        max_rating = max_rating_raw if isinstance(max_rating_raw, int) else None

        rules = (settings.get("rules") or "").lower()
        variant_str = (settings.get("variant") or "").lower()
        is_chess960 = "chess960" in rules or "chess960" in variant_str or "960" in rules

        # Identify the club's team (team1 or team2)
        teams = data.get("teams") or {}
        club_team: dict | None = None
        for team_key in ("team1", "team2"):
            team = teams.get(team_key) or {}
            if team.get("name") == club_name:
                club_team = team
                break

        participants: list[MatchResult] = []
        if club_team:
            for player in club_team.get("players") or []:
                participants.append(
                    MatchResult(
                        username=player.get("username", ""),
                        result_white=player.get("played_as_white", "in progress"),
                        result_black=player.get("played_as_black", "in progress"),
                    )
                )

        return cls(
            match_id=match_id,
            name=data.get("name", ""),
            url=url,
            start_time=datetime.fromtimestamp(
                data.get("start_time", 0), tz=UTC
            ),
            max_rating=max_rating,
            variant="chess960" if is_chess960 else "chess",
            participants=participants,
        )


@dataclass
class MemberParticipation:
    """Aggregated participation and performance statistics for one member.

    Produced by the services layer — see
    :func:`chesscom.domain.services.build_participation_stats`.

    Attributes:
        username: Chess.com username.
        daily_rating: Member's current daily rating, or ``None``.
        matches_played: Total number of team matches the club played in the
            analysis window.
        matches_participated: Number of those matches the member took part in.
        wins: Total game wins (White + Black combined).
        losses: Total game losses.
        draws: Total drawn games.
        timeouts: Total games decided by timeout.
        participation_pct: ``matches_participated / matches_played * 100``.
        win_rate_pct: ``wins / (wins + losses + draws) * 100``.
    """

    username: str
    daily_rating: int | None
    matches_played: int
    matches_participated: int
    wins: int
    losses: int
    draws: int
    timeouts: int
    participation_pct: float
    win_rate_pct: float
