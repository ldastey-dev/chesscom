"""Command-line interface for the Chess.com club management tools.

Exposes five subcommands, each corresponding to one of the report classes:

* ``match-participation``  — :class:`~chesscom.reports.match_participation.MatchParticipationReport`
* ``member-summary``       — :class:`~chesscom.reports.member_summary.MemberSummaryReport`
* ``prospects``            — :class:`~chesscom.reports.prospect.ProspectReport`
* ``match-eligibility``    — :class:`~chesscom.reports.match_eligibility.MatchEligibilityReport`
* ``timeout-check``        — :class:`~chesscom.reports.timeout_check.TimeoutCheckReport`

Usage::

    python -m chesscom <subcommand> [options]

All configuration is loaded from environment variables (see ``.env.template``).
CLI arguments override environment variables when both are provided.
A ``.env`` file in the project root is automatically sourced at startup.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
import time

from dotenv import load_dotenv

from chesscom.api.client import ChessComClient
from chesscom.config import AppConfig
from chesscom.reports.base import BaseReport
from chesscom.reports.match_eligibility import MatchEligibilityReport
from chesscom.reports.match_participation import MatchParticipationReport
from chesscom.reports.member_summary import MemberSummaryReport
from chesscom.reports.prospect import ProspectReport
from chesscom.reports.timeout_check import TimeoutCheckReport

# ---------------------------------------------------------------------------
# CLI → config merging
# ---------------------------------------------------------------------------


def _apply_cli_overrides(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    """Return a copy of *config* with fields overridden by CLI arguments.

    Only non-``None`` CLI values are applied; absent flags leave the
    environment-sourced config value unchanged.

    Args:
        config: Base configuration loaded from environment variables.
        args: Parsed CLI arguments.

    Returns:
        A new :class:`AppConfig` instance with overrides applied.
    """
    overrides: dict = {}

    if getattr(args, "club_ref", None) is not None:
        overrides["club_ref"] = args.club_ref
    if getattr(args, "club_name", None) is not None:
        overrides["club_name"] = args.club_name
    if getattr(args, "match_id", None) is not None:
        overrides["match_id"] = args.match_id
    if getattr(args, "year", None) is not None:
        overrides["data_analysis_year"] = args.year
    if getattr(args, "clubs", None) is not None:
        overrides["prospect_clubs"] = args.clubs
    if getattr(args, "exclusion_club", None) is not None:
        overrides["exclusion_club"] = args.exclusion_club
    if getattr(args, "threshold", None) is not None:
        overrides["timeout_threshold_hours"] = args.threshold

    return dataclasses.replace(config, **overrides) if overrides else config


# ---------------------------------------------------------------------------
# Timing helper
# ---------------------------------------------------------------------------


def _run_timed(report: BaseReport) -> None:
    """Run *report* and print the output path and elapsed time."""
    start = time.monotonic()
    path = report.run()
    elapsed = time.monotonic() - start
    print(f"Report written: {path}")
    print(f"Execution time: {elapsed:.2f}s ({elapsed / 60:.2f} min)")


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _handle_match_participation(args: argparse.Namespace) -> None:
    config = _apply_cli_overrides(AppConfig.from_env(), args)
    _run_timed(MatchParticipationReport(ChessComClient(), config))


def _handle_member_summary(args: argparse.Namespace) -> None:
    config = _apply_cli_overrides(AppConfig.from_env(), args)
    _run_timed(MemberSummaryReport(ChessComClient(), config))


def _handle_prospects(args: argparse.Namespace) -> None:
    config = _apply_cli_overrides(AppConfig.from_env(), args)
    _run_timed(ProspectReport(ChessComClient(), config))


def _handle_match_eligibility(args: argparse.Namespace) -> None:
    config = _apply_cli_overrides(AppConfig.from_env(), args)
    _run_timed(MatchEligibilityReport(ChessComClient(), config))


def _handle_timeout_check(args: argparse.Namespace) -> None:
    config = _apply_cli_overrides(AppConfig.from_env(), args)
    match_ids = args.match_ids if args.match_ids else config.timeout_match_ids
    if not match_ids:
        raise ValueError(
            "No match IDs provided. Supply them as positional arguments "
            "or set TIMEOUT_MATCH_IDS in your .env file."
        )
    report = TimeoutCheckReport(ChessComClient(), config, match_ids=match_ids)
    start = time.monotonic()
    path = report.run()
    elapsed = time.monotonic() - start
    print(report.format_console_summary())
    print(f"Report written: {path}")
    print(f"Execution time: {elapsed:.2f}s ({elapsed / 60:.2f} min)")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

_HANDLERS = {
    "match-participation": _handle_match_participation,
    "member-summary": _handle_member_summary,
    "prospects": _handle_prospects,
    "match-eligibility": _handle_match_eligibility,
    "timeout-check": _handle_timeout_check,
}


class _HelpOnErrorParser(argparse.ArgumentParser):
    """ArgumentParser that prints full help on any usage error."""

    def error(self, message: str) -> None:  # noqa: D102
        print(f"error: {message}\n", file=sys.stderr)
        self.print_help(sys.stderr)
        sys.exit(2)


def _common_parser() -> argparse.ArgumentParser:
    """Return a parent parser with flags shared by every subcommand.

    These flags override the corresponding environment variables when
    provided.
    """
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--club-ref",
        metavar="SLUG",
        default=None,
        help="Club slug for API paths (overrides CLUB_REF env var).",
    )
    parent.add_argument(
        "--club-name",
        metavar="NAME",
        default=None,
        help="Club display name (overrides CLUB_NAME env var).",
    )
    return parent


def build_parser() -> argparse.ArgumentParser:
    """Construct and return the top-level :class:`argparse.ArgumentParser`.

    Returns:
        Fully configured parser with all five subcommands registered.
    """
    common = _common_parser()

    parser = _HelpOnErrorParser(
        prog="chesscom",
        description="Chess.com club management tools.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Configuration is read from environment variables (see .env.template).\n"
            "CLI arguments override environment variables when both are provided."
        ),
    )

    sub = parser.add_subparsers(
        dest="subcommand",
        required=True,
        metavar="<subcommand>",
    )

    # -- match-participation ------------------------------------------------
    mp_parser = sub.add_parser(
        "match-participation",
        parents=[common],
        help="Export club contribution / match-participation report.",
        description=(
            "Analyses member participation and win rates across all team matches "
            "completed in DATA_ANALYSIS_YEAR and writes a two-sheet Excel workbook."
        ),
    )
    mp_parser.add_argument(
        "--year",
        metavar="YYYY",
        type=int,
        default=None,
        help="Analysis year (overrides DATA_ANALYSIS_YEAR env var).",
    )

    # -- member-summary -----------------------------------------------------
    sub.add_parser(
        "member-summary",
        parents=[common],
        help="Export a roster of all current club members with key stats.",
        description=(
            "Fetches every club member's profile and stats from the Chess.com API "
            "and writes a single-sheet Excel workbook."
        ),
    )

    # -- prospects ----------------------------------------------------------
    pr_parser = sub.add_parser(
        "prospects",
        parents=[common],
        help="Export a de-duplicated prospect list from multiple clubs.",
        description=(
            "Collects members from LIST_OF_CLUBS, removes anyone already in "
            "EXCLUSION_CLUB, de-duplicates, and exports to Excel."
        ),
    )
    pr_parser.add_argument(
        "--clubs",
        nargs="+",
        metavar="SLUG",
        default=None,
        help="Club slugs to inspect for prospects (overrides LIST_OF_CLUBS env var).",
    )
    pr_parser.add_argument(
        "--exclusion-club",
        metavar="SLUG",
        default=None,
        help=(
            "Club whose members are excluded from the prospect list "
            "(overrides EXCLUSION_CLUB env var)."
        ),
    )

    # -- match-eligibility --------------------------------------------------
    me_parser = sub.add_parser(
        "match-eligibility",
        parents=[common],
        help="Export eligible members for a specific team match.",
        description=(
            "Lists club members whose rating falls within the match cap for the "
            "detected chess variant (standard or Chess960) and flags signed-up players."
        ),
    )
    me_parser.add_argument(
        "--match-id",
        metavar="ID",
        default=None,
        help=(
            "Chess.com match ID to analyse "
            "(overrides MATCH_ID env var; required if MATCH_ID is not set)."
        ),
    )

    # -- timeout-check ------------------------------------------------------
    tc_parser = sub.add_parser(
        "timeout-check",
        parents=[common],
        help="Check matches for timeouts and near-timeout conditions.",
        description=(
            "Inspects in-progress team matches for actual timeouts and games "
            "where a team member's clock is running low. Outputs both a "
            "console summary and an Excel workbook."
        ),
    )
    tc_parser.add_argument(
        "match_ids",
        nargs="*",
        metavar="MATCH_ID",
        help=(
            'One or more match IDs to check, or "all" to check every '
            "in-progress match for the configured club. "
            "Falls back to TIMEOUT_MATCH_IDS env var if not provided."
        ),
    )
    tc_parser.add_argument(
        "--threshold",
        metavar="HOURS",
        type=float,
        default=None,
        help=(
            "Hours remaining below which a game is flagged as at risk "
            "(overrides TIMEOUT_THRESHOLD_HOURS env var; default: 5)."
        ),
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Parse *argv* (or ``sys.argv[1:]``) and dispatch to the correct handler.

    Args:
        argv: Argument list to parse.  When ``None`` the process argument
            vector is used (standard ``argparse`` behaviour).

    Raises:
        SystemExit(0): On ``--help``.
        SystemExit(1): On configuration or validation errors.
        SystemExit(130): On ``KeyboardInterrupt``.
    """
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        _HANDLERS[args.subcommand](args)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
