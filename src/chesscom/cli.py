"""Command-line interface for the Chess.com club management tools.

Exposes four subcommands, each corresponding to one of the report classes:

* ``match-participation``  — :class:`~chesscom.reports.match_participation.MatchParticipationReport`
* ``member-summary``       — :class:`~chesscom.reports.member_summary.MemberSummaryReport`
* ``prospects``            — :class:`~chesscom.reports.prospect.ProspectReport`
* ``match-eligibility``    — :class:`~chesscom.reports.match_eligibility.MatchEligibilityReport`

Usage::

    python -m chesscom <subcommand> [options]

All configuration is loaded from environment variables (see ``.env.template``).
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


def _handle_match_participation(args: argparse.Namespace) -> None:  # noqa: ARG001
    config = AppConfig.from_env()
    _run_timed(MatchParticipationReport(ChessComClient(), config))


def _handle_member_summary(args: argparse.Namespace) -> None:  # noqa: ARG001
    config = AppConfig.from_env()
    _run_timed(MemberSummaryReport(ChessComClient(), config))


def _handle_prospects(args: argparse.Namespace) -> None:  # noqa: ARG001
    config = AppConfig.from_env()
    _run_timed(ProspectReport(ChessComClient(), config))


def _handle_match_eligibility(args: argparse.Namespace) -> None:
    config = AppConfig.from_env()
    # --match-id CLI flag overrides (or supplies) the MATCH_ID env var
    if args.match_id:
        config = dataclasses.replace(config, match_id=args.match_id)
    _run_timed(MatchEligibilityReport(ChessComClient(), config))


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

_HANDLERS = {
    "match-participation": _handle_match_participation,
    "member-summary": _handle_member_summary,
    "prospects": _handle_prospects,
    "match-eligibility": _handle_match_eligibility,
}


def build_parser() -> argparse.ArgumentParser:
    """Construct and return the top-level :class:`argparse.ArgumentParser`.

    Returns:
        Fully configured parser with all four subcommands registered.
    """
    parser = argparse.ArgumentParser(
        prog="chesscom",
        description="Chess.com club management tools.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "All options are read from environment variables.\n"
            "Copy .env.template to .env and fill in the values before running."
        ),
    )

    sub = parser.add_subparsers(
        dest="subcommand",
        required=True,
        metavar="<subcommand>",
    )

    sub.add_parser(
        "match-participation",
        help="Export club contribution / match-participation report.",
        description=(
            "Analyses member participation and win rates across all team matches "
            "completed in DATA_ANALYSIS_YEAR and writes a two-sheet Excel workbook."
        ),
    )

    sub.add_parser(
        "member-summary",
        help="Export a roster of all current club members with key stats.",
        description=(
            "Fetches every club member's profile and stats from the Chess.com API "
            "and writes a single-sheet Excel workbook."
        ),
    )

    sub.add_parser(
        "prospects",
        help="Export a de-duplicated prospect list from multiple clubs.",
        description=(
            "Collects members from LIST_OF_CLUBS, removes anyone already in "
            "EXCLUSION_CLUB, de-duplicates, and exports to Excel."
        ),
    )

    me_parser = sub.add_parser(
        "match-eligibility",
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
