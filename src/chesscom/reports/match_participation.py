"""Match Participation Report.

Analyses club member participation and performance across all team
matches played in a configured year.

Replaces ``src/club_contribution_report.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from chesscom.domain.models import Match, Member
from chesscom.domain.services import build_participation_stats
from chesscom.export.excel import SheetConfig
from chesscom.reports.base import BaseReport

_CHESSCOM_PROFILE_URL = "https://www.chess.com/member/{value}"


class MatchParticipationReport(BaseReport):
    """Exports member participation stats and per-match details.

    Produces a two-sheet workbook:

    * **Member Metrics** — one row per member with participation %, win
      rate %, rating, and timeout stats.  Usernames are hyperlinked.
    * **Match Data** — one row per match, with per-member result columns.

    Raises:
        ValueError: If ``config.data_analysis_year`` is ``None``.
    """

    def get_report_name(self) -> str:
        year = self.config.data_analysis_year or ""
        return f"{self.config.club_name} Club Contribution Report {year}".strip()

    def collect_data(self) -> list[dict]:
        """Fetch member and match data for the configured analysis year.

        Side-effect: populates ``self._matches_data`` which is used by
        :meth:`build_sheet_configs` to create the second sheet.

        Raises:
            ValueError: When ``config.data_analysis_year`` is not set.

        Returns:
            List of member metric dicts (primary / first sheet).
        """
        if self.config.data_analysis_year is None:
            raise ValueError(
                "data_analysis_year is required for MatchParticipationReport "
                "but was not set in the configuration."
            )

        year = self.config.data_analysis_year

        # --- Members --------------------------------------------------------
        raw_members = self._all_club_members()

        # --- Matches (filtered by year) ------------------------------------
        raw_matches_resp = self.client.get_club_matches(self.config.club_ref)
        raw_finished = raw_matches_resp.get("finished", [])
        raw_in_year = [
            m for m in raw_finished
            if datetime.fromtimestamp(m.get("start_time", 0), tz=UTC).year >= year
        ]

        # Hydrate each match once
        matches: list[Match] = []
        match_meta: list[dict] = []  # for Match Data sheet
        for raw in raw_in_year:
            url: str = raw.get("@id", "")
            match_id = url.rstrip("/").rsplit("/", maxsplit=1)[-1]
            data = self.client.get_match(url)
            match = Match.from_api_response(data, match_id, url, self.config.club_name)
            matches.append(match)
            match_meta.append({"Match Name": raw.get("name", ""), "Match URL": url})

        # --- Per-member stats + per-match result columns -------------------
        members_data: list[dict] = []
        for raw in raw_members:
            username: str = raw.get("username", "")
            if not username:
                continue

            profile = self.client.get_player_profile(username)
            stats = self.client.get_player_stats(username)
            member = Member.from_api_response(profile, stats, raw.get("joined"))
            participation = build_participation_stats(member, matches)

            # Inject per-match result columns into match_meta rows
            for i, match in enumerate(matches):
                participant = next(
                    (p for p in match.participants if p.username.lower() == username.lower()),
                    None,
                )
                if participant:
                    match_meta[i][f"{username}_white"] = participant.result_white
                    match_meta[i][f"{username}_black"] = participant.result_black
                else:
                    match_meta[i][f"{username}_white"] = "not played"
                    match_meta[i][f"{username}_black"] = "not played"

            members_data.append({
                "Username": member.username,
                "Daily Rating": (
                    member.daily_rating if member.daily_rating is not None else "Unrated"
                ),
                "Joined Chess.com": _fmt(member.joined_chess_com),
                "Joined Club": _fmt(member.joined_club),
                "Last Online": _fmt(member.last_online),
                "Timeout Percentage": member.timeout_percent,
                "Club Timeouts": participation.timeouts,
                "Total Matches": participation.matches_played,
                "Participation %": participation.participation_pct,
                "Win Rate %": participation.win_rate_pct,
            })

        self._matches_data = match_meta
        return members_data

    def build_sheet_configs(self, members_data: list[dict]) -> list[SheetConfig]:
        matches_data = getattr(self, "_matches_data", [])
        return [
            SheetConfig(
                name="Member Metrics",
                dataframe=pd.DataFrame(members_data),
                hyperlink_column="Username",
                hyperlink_url_template=_CHESSCOM_PROFILE_URL,
            ),
            SheetConfig(
                name="Match Data",
                dataframe=pd.DataFrame(matches_data),
            ),
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _all_club_members(self) -> list[dict]:
        data = self.client.get_club_members(self.config.club_ref)
        return (
            data.get("weekly", [])
            + data.get("monthly", [])
            + data.get("all_time", [])
        )


def _fmt(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(UTC).strftime("%d/%m/%Y")
