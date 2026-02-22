"""Prospect Report.

Identifies potential new recruits across a set of Chess.com clubs,
excluding members who are already in a specified exclusion club
(typically the home club).

Replaces ``src/generate_prospect_data.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from chesscom.domain.models import Member
from chesscom.reports.base import BaseReport


class ProspectReport(BaseReport):
    """Exports a de-duplicated list of prospects from multiple source clubs.

    Members of ``config.exclusion_club`` are removed from the results.
    Where the same username appears in more than one source club the first
    occurrence (by club order in ``config.prospect_clubs``) is kept.

    Sheet: ``"Member Prospects"``

    Columns: FIDE Title, Username (hyperlinked), Name, Sourced Club,
    Daily Rating, Chess960 Rating, Timeout Percentage, Last Online,
    Joined Chess.com.
    """

    def get_report_name(self) -> str:
        return "Member Prospects"

    def collect_data(self) -> list[dict]:
        """Aggregate prospects across all configured source clubs.

        Returns:
            One dict per unique eligible prospect.
        """
        # 1. Gather raw (username, source_club) pairs from all prospect clubs
        all_raw: list[tuple[str, str]] = []
        for club in self.config.prospect_clubs:
            for raw in self._all_members(club):
                username = raw.get("username", "")
                if username:
                    all_raw.append((username, club))

        # 2. Build exclusion set (case-insensitive)
        exclusion_lower: set[str] = set()
        if self.config.exclusion_club:
            for raw in self._all_members(self.config.exclusion_club):
                u = raw.get("username", "")
                if u:
                    exclusion_lower.add(u.lower())

        # 3. Filter and de-duplicate by username
        seen: set[str] = set()
        eligible: list[tuple[str, str]] = []
        for username, club in all_raw:
            key = username.lower()
            if key not in exclusion_lower and key not in seen:
                seen.add(key)
                eligible.append((username, club))

        # 4. Fetch full data only for eligible, unique members
        results: list[dict] = []
        for username, source_club in eligible:
            profile = self.client.get_player_profile(username)
            stats = self.client.get_player_stats(username)
            member = Member.from_api_response(profile, stats)
            results.append(self._to_row(member, source_club))

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _all_members(self, club_ref: str) -> list[dict]:
        return self.client.get_club_members(club_ref)

    @staticmethod
    def _to_row(m: Member, source_club: str) -> dict:
        return {
            "FIDE Title": m.fide_title,
            "Username": m.username,
            "Name": m.name,
            "Sourced Club": source_club,
            "Daily Rating": m.daily_rating if m.daily_rating is not None else "Unrated",
            "Chess960 Rating": (
                m.chess960_rating if m.chess960_rating is not None else "Unrated"
            ),
            "Timeout Percentage": m.timeout_percent,
            "Last Online": _fmt(m.last_online),
            "Joined Chess.com": _fmt(m.joined_chess_com),
        }


def _fmt(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(UTC).strftime("%d/%m/%Y")
