"""Centralised application configuration for the Chess.com club tools.

All environment-variable access is funnelled through :class:`AppConfig`.
Callers obtain a validated config object via :meth:`AppConfig.from_env`
and pass it as a parameter — there are no module-level ``os.getenv`` calls
anywhere else in the package.

Environment variables
---------------------
Required:
  CLUB_REF    Slug used in Chess.com API paths (e.g. ``"team-scotland"``).
  CLUB_NAME   Human-readable club name (e.g. ``"Team Scotland"``).

Optional:
  DATA_ANALYSIS_YEAR  Four-digit year for match-participation analysis.
                      Parsed to ``int``; silently ignored if blank.
  MATCH_ID            Chess.com match identifier for the match-eligibility
                      report.  May also be supplied via CLI prompt at runtime.
  LIST_OF_CLUBS       Comma-separated club slugs used by the prospect report.
                      Blank entries are discarded.
  EXCLUSION_CLUB      Club slug whose members are excluded from the prospect
                      report (defaults to ``None``; previously hard-coded as
                      ``"team-scotland"``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class AppConfig:
    """Validated, typed collection of runtime configuration values.

    Create via :meth:`from_env` rather than the ordinary constructor to
    ensure that required fields are present and that types are correct.

    Attributes:
        club_ref: Chess.com club slug used in API paths.
        club_name: Human-readable display name of the club.
        data_analysis_year: Optional year to filter match-participation data.
        match_id: Optional Chess.com match identifier for the eligibility
            report.
        prospect_clubs: Ordered list of club slugs to inspect for prospects.
        exclusion_club: Optional club slug whose members are excluded from
            the prospect report.
    """

    club_ref: str
    club_name: str
    data_analysis_year: int | None = field(default=None)
    match_id: str | None = field(default=None)
    prospect_clubs: list[str] = field(default_factory=list)
    exclusion_club: str | None = field(default=None)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> AppConfig:
        """Build an :class:`AppConfig` from environment variables.

        Returns:
            A fully-validated :class:`AppConfig` instance.

        Raises:
            ValueError: If any *required* environment variable is absent or
                empty.
        """
        missing: list[str] = []

        club_ref = os.getenv("CLUB_REF", "").strip()
        if not club_ref:
            missing.append("CLUB_REF")

        club_name = os.getenv("CLUB_NAME", "").strip()
        if not club_name:
            missing.append("CLUB_NAME")

        if missing:
            raise ValueError(
                f"Missing required environment variable(s): {', '.join(missing)}"
            )

        # --- optional fields ------------------------------------------------
        data_analysis_year: int | None = None
        raw_year = os.getenv("DATA_ANALYSIS_YEAR", "").strip()
        if raw_year:
            try:
                data_analysis_year = int(raw_year)
            except ValueError as exc:
                raise ValueError(
                    f"DATA_ANALYSIS_YEAR must be an integer; got '{raw_year}'"
                ) from exc

        match_id = os.getenv("MATCH_ID", "").strip() or None

        raw_clubs = os.getenv("LIST_OF_CLUBS", "")
        prospect_clubs = [c.strip() for c in raw_clubs.split(",") if c.strip()]

        exclusion_club = os.getenv("EXCLUSION_CLUB", "").strip() or None

        return cls(
            club_ref=club_ref,
            club_name=club_name,
            data_analysis_year=data_analysis_year,
            match_id=match_id,
            prospect_clubs=prospect_clubs,
            exclusion_club=exclusion_club,
        )
