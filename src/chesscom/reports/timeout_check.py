"""Timeout Check Report.

Inspects in-progress team matches for actual timeouts (completed games
lost on time) and potential timeouts (in-progress games where a team
member's clock is running low).

Outputs both an Excel workbook and a concise console summary.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

import pandas as pd

from chesscom.domain.models import TimeoutAlert
from chesscom.domain.services import calculate_hours_remaining, is_timeout_risk
from chesscom.export.excel import SheetConfig
from chesscom.reports.base import BaseReport

_CHESSCOM_PROFILE_URL = "https://www.chess.com/member/{value}"
_CHESSCOM_MATCH_URL = "https://www.chess.com/club/matches/{value}"


class TimeoutCheckReport(BaseReport):
    """Checks matches for timeouts and near-timeout conditions.

    Produces a two-sheet workbook:

    * **Timeout Alerts by Match** — one row per flagged game, grouped by
      match, showing the player, colour, status, and time remaining.
    * **Timeout Summary by Player** — one row per player who has at least
      one timeout, ordered by total timeout count descending.

    The report also provides :meth:`format_console_summary` for a concise
    stdout overview.

    Args:
        match_ids: List of match ID strings, or ``["all"]`` to check
            every in-progress match for the configured club.
    """

    def __init__(self, client, config, *, match_ids: list[str]) -> None:
        super().__init__(client, config)
        self._match_ids = match_ids
        self._alerts: list[TimeoutAlert] = []

    def get_report_name(self) -> str:
        return "Timeout Check Report"

    # ------------------------------------------------------------------
    # Data collection
    # ------------------------------------------------------------------

    def collect_data(self) -> list[dict]:
        """Fetch match and board data, identify timeouts and at-risk games.

        Side-effect: populates ``self._alerts`` for use by
        :meth:`format_console_summary` and :meth:`build_sheet_configs`.

        Returns:
            List of row dicts for the by-match sheet.
        """
        raw_matches = self._resolve_matches()
        alerts: list[TimeoutAlert] = []

        for raw in raw_matches:
            url: str = raw.get("@id", "")
            match_id = url.rstrip("/").rsplit("/", maxsplit=1)[-1]
            data = self.client.get_match(url)
            match_name = data.get("name", "")

            club_team = self._find_club_team(data)
            if club_team is None:
                continue

            players = club_team.get("players") or []
            boards_checked: set[str] = set()

            for player in players:
                username = player.get("username", "")
                board_url = player.get("board", "")
                if not username:
                    continue

                # Check for completed timeouts
                for colour, key in [("white", "played_as_white"), ("black", "played_as_black")]:
                    result = player.get(key, "")
                    if result == "timeout":
                        alerts.append(
                            TimeoutAlert(
                                match_name=match_name,
                                match_id=match_id,
                                username=username,
                                board_url=board_url,
                                colour=colour,
                                status="timed_out",
                                move_by=None,
                                hours_remaining=None,
                            )
                        )

                # Check for in-progress games (result absent or empty)
                has_in_progress = any(
                    not player.get(key) for key in ("played_as_white", "played_as_black")
                )

                if has_in_progress and board_url and board_url not in boards_checked:
                    boards_checked.add(board_url)
                    self._check_board_for_risks(board_url, match_name, match_id, alerts)

        self._alerts = alerts
        return self._alerts_to_rows(alerts)

    # ------------------------------------------------------------------
    # Sheet configuration
    # ------------------------------------------------------------------

    def build_sheet_configs(self, data: list[dict]) -> list[SheetConfig]:
        alerts = self._alerts

        # Sheet 1: by-match alerts
        by_match_df = (
            pd.DataFrame(data)
            if data
            else pd.DataFrame(
                columns=[
                    "Match Name",
                    "Match ID",
                    "Username",
                    "Board",
                    "Colour",
                    "Status",
                    "Move By",
                    "Hours Remaining",
                ]
            )
        )

        # Sheet 2: by-player summary (only players with timeouts > 0)
        timeout_counts: Counter[str] = Counter()
        matches_with_timeouts: dict[str, set[str]] = {}
        for alert in alerts:
            if alert.status == "timed_out":
                timeout_counts[alert.username] += 1
                matches_with_timeouts.setdefault(alert.username, set()).add(alert.match_id)

        player_rows: list[dict] = []
        for username, count in timeout_counts.most_common():
            player_rows.append(
                {
                    "Username": username,
                    "Total Timeouts": count,
                    "Matches With Timeouts": len(matches_with_timeouts.get(username, set())),
                }
            )

        by_player_df = (
            pd.DataFrame(player_rows)
            if player_rows
            else pd.DataFrame(columns=["Username", "Total Timeouts", "Matches With Timeouts"])
        )

        sheets = [
            SheetConfig(
                name="Timeout Alerts by Match",
                dataframe=by_match_df,
                hyperlink_column="Username" if "Username" in by_match_df.columns else None,
                hyperlink_url_template=(
                    _CHESSCOM_PROFILE_URL if "Username" in by_match_df.columns else None
                ),
            ),
            SheetConfig(
                name="Timeout Summary by Player",
                dataframe=by_player_df,
                hyperlink_column="Username" if "Username" in by_player_df.columns else None,
                hyperlink_url_template=(
                    _CHESSCOM_PROFILE_URL if "Username" in by_player_df.columns else None
                ),
            ),
        ]
        return sheets

    # ------------------------------------------------------------------
    # Console summary
    # ------------------------------------------------------------------

    def format_console_summary(self) -> str:
        """Return a concise console summary of timeout alerts.

        Call this after :meth:`run` (which invokes :meth:`collect_data`
        internally) so that ``self._alerts`` is populated.

        Returns:
            Formatted multi-line string suitable for printing to stdout.
        """
        if not self._alerts:
            return "No timeout issues found across checked matches."

        # Group alerts by match
        by_match: dict[str, list[TimeoutAlert]] = {}
        for alert in self._alerts:
            key = f"{alert.match_name} (ID: {alert.match_id})"
            by_match.setdefault(key, []).append(alert)

        lines: list[str] = ["=== Timeout Check Summary ===", ""]
        for match_label, match_alerts in by_match.items():
            timed_out = [a for a in match_alerts if a.status == "timed_out"]
            at_risk = [a for a in match_alerts if a.status == "at_risk"]
            lines.append(f"Match: {match_label}")

            parts: list[str] = []
            if at_risk:
                parts.append(f"{len(at_risk)} at risk")
            if timed_out:
                parts.append(f"{len(timed_out)} timed out")
            lines.append(f"  {', '.join(parts)}")

            for a in timed_out:
                lines.append(f"  TIMED OUT: {a.username} ({a.colour})")
            for a in at_risk:
                hrs = f"{a.hours_remaining:.1f}" if a.hours_remaining is not None else "?"
                lines.append(f"  AT RISK:  {a.username} ({a.colour}) — {hrs} hours remaining")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_matches(self) -> list[dict]:
        """Return the list of raw match summary dicts to check."""
        if self._match_ids == ["all"]:
            resp = self.client.get_club_matches(self.config.club_ref)
            return resp.get("in_progress", [])

        return [{"@id": f"https://api.chess.com/pub/match/{mid}"} for mid in self._match_ids]

    def _find_club_team(self, match_data: dict) -> dict | None:
        """Identify the club's team (team1 or team2) within match data."""
        teams = match_data.get("teams") or {}
        for team_key in ("team1", "team2"):
            team = teams.get(team_key) or {}
            if team.get("name") == self.config.club_name:
                return team
        return None

    def _check_board_for_risks(
        self,
        board_url: str,
        match_name: str,
        match_id: str,
        alerts: list[TimeoutAlert],
    ) -> None:
        """Fetch board data and append at-risk alerts for our team's players."""
        try:
            board_data = self.client.get_match_board(board_url)
        except Exception:
            return

        club_ref_lower = self.config.club_ref.lower()

        for game in board_data.get("games") or []:
            # Skip finished games (they have an end_time)
            if game.get("end_time"):
                continue

            move_by_ts = game.get("move_by")
            if not move_by_ts or move_by_ts == 0:
                # move_by == 0 means the player-to-move is on vacation
                continue

            move_by_dt = datetime.fromtimestamp(move_by_ts, tz=UTC)
            if not is_timeout_risk(move_by_dt, self.config.timeout_threshold_hours):
                continue

            hours_left = calculate_hours_remaining(move_by_dt)

            # Determine which side's move it is
            turn = game.get("turn", "")
            for colour in ("white", "black"):
                if colour != turn:
                    continue
                player_data = game.get(colour) or {}
                # Check if this player is on our team
                team_url = player_data.get("team", "")
                player_username = player_data.get("username", "")

                if self._is_our_player(team_url, club_ref_lower):
                    alerts.append(
                        TimeoutAlert(
                            match_name=match_name,
                            match_id=match_id,
                            username=player_username,
                            board_url=board_url,
                            colour=colour,
                            status="at_risk",
                            move_by=move_by_dt,
                            hours_remaining=hours_left,
                        )
                    )

    @staticmethod
    def _is_our_player(team_url: str, club_ref_lower: str) -> bool:
        """Check if a player belongs to our club using the team URL."""
        if team_url:
            return club_ref_lower in team_url.lower()
        return False

    @staticmethod
    def _alerts_to_rows(alerts: list[TimeoutAlert]) -> list[dict]:
        """Convert alert objects to row dicts for the by-match sheet."""
        rows: list[dict] = []
        for a in alerts:
            rows.append(
                {
                    "Match Name": a.match_name,
                    "Match ID": a.match_id,
                    "Username": a.username,
                    "Board": a.board_url,
                    "Colour": a.colour,
                    "Status": "Timed Out" if a.status == "timed_out" else "At Risk",
                    "Move By": (a.move_by.strftime("%d/%m/%Y %H:%M UTC") if a.move_by else ""),
                    "Hours Remaining": (
                        round(a.hours_remaining, 1) if a.hours_remaining is not None else ""
                    ),
                }
            )
        return rows
