"""Club Member Summary Report.

Produces a single-sheet workbook listing every current member of the club
with their ratings, activity dates, and timeout percentage.

Replaces ``src/generate_club_member_report.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from chesscom.domain.models import Member
from chesscom.reports.base import BaseReport


class MemberSummaryReport(BaseReport):
    """Exports a roster of all club members with their key statistics.

    Sheet: ``"Club Member Summary Report"``

    Columns: FIDE Title, Username (hyperlinked), Name, Joined Chess.com,
    Joined Club, Last Online, Daily Rating, Chess960 Rating,
    Timeout Percentage.
    """

    def get_report_name(self) -> str:
        return "Club Member Summary Report"

    def collect_data(self) -> list[dict]:
        """Fetch every club member's profile and stats.

        Returns:
            One dict per member, ready to write to Excel.
        """
        raw_members = self._all_members(self.config.club_ref)

        results: list[dict] = []
        for raw in raw_members:
            username: str = raw.get("username", "")
            joined_ts: int | None = raw.get("joined")

            profile = self.client.get_player_profile(username)
            stats = self.client.get_player_stats(username)
            member = Member.from_api_response(profile, stats, joined_ts)

            results.append(self._to_row(member))

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _all_members(self, club_ref: str) -> list[dict]:
        return self.client.get_club_members(club_ref)

    @staticmethod
    def _to_row(m: Member) -> dict:
        return {
            "FIDE Title": m.fide_title,
            "Username": m.username,
            "Name": m.name,
            "Joined Chess.com": _fmt(m.joined_chess_com),
            "Joined Club": _fmt(m.joined_club),
            "Last Online": _fmt(m.last_online),
            "Daily Rating": m.daily_rating if m.daily_rating is not None else "Unrated",
            "Chess960 Rating": (
                m.chess960_rating if m.chess960_rating is not None else "Unrated"
            ),
            "Timeout Percentage": m.timeout_percent,
        }


def _fmt(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(UTC).strftime("%d/%m/%Y")
