"""Match Eligibility Report.

Lists club members who are eligible to play in a specific team match
(based on rating cap and chess variant), and flags which ones have
already signed up.

Replaces ``src/match_strengthening_extract.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from chesscom.domain.models import Match, Member
from chesscom.domain.services import filter_members_by_rating
from chesscom.export.excel import SheetConfig
from chesscom.reports.base import BaseReport

_CHESSCOM_PROFILE_URL = "https://www.chess.com/member/{value}"


class MatchEligibilityReport(BaseReport):
    """Exports eligible members for a specific team match.

    Eligibility is determined by the match's ``max_rating`` setting and
    chess variant (standard or Chess960).  Members already signed up are
    flagged in the ``Signed Up`` column.

    Raises:
        ValueError: If ``config.match_id`` is ``None`` or empty.

    Sheet name: ``"Match Eligibility {VARIANT} Data"``

    Columns: Username (hyperlinked), Daily Rating, Chess960 Rating,
    Variant, Last Online, Timeout Percentage, Signed Up.
    """

    def get_report_name(self) -> str:
        return "Match Eligibility"

    def collect_data(self) -> list[dict]:
        """Identify and return eligible club members for the configured match.

        Raises:
            ValueError: When ``config.match_id`` is absent.

        Returns:
            One dict per eligible member.
        """
        if not self.config.match_id:
            raise ValueError(
                "match_id is required for MatchEligibilityReport but was not set"
                " in the configuration."
            )

        match_id = self.config.match_id

        # --- Match metadata -------------------------------------------------
        match_data = self.client.get_match(match_id)
        match = Match.from_api_response(
            match_data, match_id, f"https://api.chess.com/pub/match/{match_id}",
            self.config.club_name,
        )
        variant = match.variant
        max_rating = match.max_rating

        # Store variant for sheet naming (used in build_sheet_configs)
        self._variant = variant

        # --- Participants already signed up ---------------------------------
        signed_up_lower: set[str] = {
            p.username.lower() for p in match.participants
        }

        # --- All club members with full Member objects ----------------------
        raw_members = self._all_club_members()
        members: list[Member] = []
        for raw in raw_members:
            username = raw.get("username", "")
            if not username:
                continue
            profile = self.client.get_player_profile(username)
            stats = self.client.get_player_stats(username)
            members.append(Member.from_api_response(profile, stats, raw.get("joined")))

        # --- Apply rating filter (skip if no cap) ---------------------------
        if max_rating is not None:
            members = filter_members_by_rating(members, max_rating, variant)

        # --- Build result rows ----------------------------------------------
        results: list[dict] = []
        for m in members:
            chess960_display = (
                m.chess960_rating if m.chess960_rating is not None else "Unrated"
            )
            results.append({
                "Username": m.username,
                "Daily Rating": m.daily_rating if m.daily_rating is not None else "Unrated",
                "Chess960 Rating": chess960_display,
                "Variant": variant.upper(),
                "Last Online": _fmt(m.last_online),
                "Timeout Percentage": m.timeout_percent,
                "Signed Up": "Yes" if m.username.lower() in signed_up_lower else "No",
            })

        return results

    def build_sheet_configs(self, data: list[dict]) -> list[SheetConfig]:
        variant = getattr(self, "_variant", "chess")
        sheet_name = f"Match Eligibility {variant.upper()} Data"
        return [
            SheetConfig(
                name=sheet_name[:31],
                dataframe=pd.DataFrame(data),
                hyperlink_column="Username",
                hyperlink_url_template=_CHESSCOM_PROFILE_URL,
            )
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
