"""
Shared pytest configuration, path setup, and fixtures.

Environment variables are set at module level so they are in place before any
test module imports the src scripts (which read env vars at module level).
"""

import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Path setup — make src/ importable without installing as a package first
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ---------------------------------------------------------------------------
# Test environment variables
# Set these BEFORE any script is imported so module-level os.getenv() calls
# resolve to test values. load_dotenv() in utils/__init__.py will not override
# variables that are already set.
# ---------------------------------------------------------------------------
os.environ.setdefault("CLUB_REF", "test-club")
os.environ.setdefault("CLUB_NAME", "Test Club")
os.environ.setdefault("DATA_ANALYSIS_YEAR", "2025")
os.environ.setdefault("MATCH_ID", "99999")
os.environ.setdefault("LIST_OF_CLUBS", "prospect-club-a,prospect-club-b")


# ---------------------------------------------------------------------------
# Sample API response fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def club_members_response():
    """Sample JSON response from /club/{club}/members."""
    return {
        "weekly": [{"username": "player_weekly", "joined": 1700000000}],
        "monthly": [{"username": "player_monthly", "joined": 1700000001}],
        "all_time": [{"username": "player_alltime", "joined": 1700000002}],
    }


@pytest.fixture()
def player_stats_response():
    """Sample JSON response from /player/{username}/stats."""
    return {
        "chess_daily": {
            "last": {"rating": 1200},
            "record": {"timeout_percent": 5.0},
        },
        "chess960_daily": {
            "last": {"rating": 1100},
            "record": {"timeout_percent": 5.0},
        },
    }


@pytest.fixture()
def player_stats_response_unrated():
    """Stats response where chess_daily is absent (unrated player)."""
    return {}


@pytest.fixture()
def player_profile_response():
    """Sample JSON response from /player/{username}."""
    return {
        "username": "testplayer",
        "name": "Test Player",
        "title": "FM",
        "last_online": 1700000000,
        "joined": 1690000000,
    }


@pytest.fixture()
def club_matches_response():
    """Sample JSON response from /club/{club}/matches."""
    return {
        "finished": [
            {
                "name": "Test Match 2025",
                "@id": "https://api.chess.com/pub/match/11111",
                "start_time": 1704067200,  # 2024-01-01 — within 2025 filter range
            }
        ],
        "in_progress": [],
    }


@pytest.fixture()
def match_detail_response_team1():
    """Match where Test Club is team1."""
    return {
        "name": "Test Match",
        "settings": {"max_rating": 1400, "rules": "chess", "variant": ""},
        "teams": {
            "team1": {
                "name": "Test Club",
                "players": [
                    {"username": "Alice", "played_as_white": "win", "played_as_black": "checkmated"},
                    {"username": "Bob", "played_as_white": "in progress", "played_as_black": "timeout"},
                ],
            },
            "team2": {
                "name": "Opponent Club",
                "players": [
                    {"username": "Charlie", "played_as_white": "win", "played_as_black": "win"},
                ],
            },
        },
    }


@pytest.fixture()
def match_detail_response_team2():
    """Match where Test Club is team2 (verifies team detection regardless of position)."""
    return {
        "name": "Test Match",
        "settings": {"max_rating": 1400, "rules": "chess", "variant": ""},
        "teams": {
            "team1": {
                "name": "Opponent Club",
                "players": [
                    {"username": "Charlie", "played_as_white": "win", "played_as_black": "win"},
                ],
            },
            "team2": {
                "name": "Test Club",
                "players": [
                    {"username": "Alice", "played_as_white": "win", "played_as_black": "checkmated"},
                ],
            },
        },
    }


@pytest.fixture()
def match_detail_response_chess960():
    """Match with Chess960 variant indicators in settings."""
    return {
        "name": "Chess960 Match",
        "settings": {"max_rating": 1400, "rules": "chess960", "variant": ""},
        "teams": {
            "team1": {
                "name": "Test Club",
                "players": [{"username": "Alice", "played_as_white": "win", "played_as_black": "win"}],
            },
            "team2": {
                "name": "Opponent Club",
                "players": [],
            },
        },
    }
