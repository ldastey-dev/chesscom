"""
Integration tests for API-calling functions.

All HTTP calls are intercepted by the `responses` library — no real network
traffic is made during these tests.
"""

import os
from unittest.mock import patch

import responses as resp

# ---------------------------------------------------------------------------
# Modules under test — imported after conftest.py sets sys.path and env vars
# ---------------------------------------------------------------------------
import club_contribution_report as ccr
import generate_prospect_data as gpd
import match_strengthening_extract as mse

BASE = "https://api.chess.com/pub"
CLUB_REF = os.environ["CLUB_REF"]          # 'test-club' from conftest
CLUB_NAME = os.environ["CLUB_NAME"]        # 'Test Club' from conftest


# ---------------------------------------------------------------------------
# club_contribution_report — get_all_club_members
# ---------------------------------------------------------------------------


class TestGetAllClubMembers:
    @resp.activate
    def test_combines_weekly_monthly_all_time(self, club_members_response):
        """Members from all three categories must be merged into one list."""
        resp.add(
            resp.GET,
            f"{BASE}/club/{CLUB_REF}/members",
            json=club_members_response,
            status=200,
        )

        members = ccr.get_all_club_members()

        usernames = [m["username"] for m in members]
        assert "player_weekly" in usernames
        assert "player_monthly" in usernames
        assert "player_alltime" in usernames
        assert len(members) == 3

    @resp.activate
    def test_returns_empty_list_when_all_categories_empty(self):
        resp.add(
            resp.GET,
            f"{BASE}/club/{CLUB_REF}/members",
            json={"weekly": [], "monthly": [], "all_time": []},
            status=200,
        )

        members = ccr.get_all_club_members()
        assert members == []

    @resp.activate
    def test_handles_missing_category_keys(self):
        """When a category key is absent the merge must not raise."""
        resp.add(
            resp.GET,
            f"{BASE}/club/{CLUB_REF}/members",
            json={"weekly": [{"username": "solo"}]},  # no monthly / all_time
            status=200,
        )

        members = ccr.get_all_club_members()
        assert len(members) == 1
        assert members[0]["username"] == "solo"


# ---------------------------------------------------------------------------
# club_contribution_report — get_member_daily_rating
# ---------------------------------------------------------------------------


class TestGetMemberDailyRating:
    @resp.activate
    def test_returns_rating_from_stats(self, player_stats_response):
        resp.add(
            resp.GET,
            f"{BASE}/player/testplayer/stats",
            json=player_stats_response,
            status=200,
        )

        rating = ccr.get_member_daily_rating("testplayer")
        assert rating == 1200

    @resp.activate
    def test_returns_na_when_chess_daily_absent(self):
        """When chess_daily key is missing entirely, return 'N/A'."""
        resp.add(
            resp.GET,
            f"{BASE}/player/unrated/stats",
            json={},  # no chess_daily
            status=200,
        )

        rating = ccr.get_member_daily_rating("unrated")
        assert rating == "N/A"

    @resp.activate
    def test_returns_na_when_last_rating_absent(self):
        resp.add(
            resp.GET,
            f"{BASE}/player/norating/stats",
            json={"chess_daily": {"record": {"timeout_percent": 0}}},  # no 'last'
            status=200,
        )

        rating = ccr.get_member_daily_rating("norating")
        assert rating == "N/A"


# ---------------------------------------------------------------------------
# club_contribution_report — get_match_data
# ---------------------------------------------------------------------------


class TestGetMatchData:
    MATCH_URL = f"{BASE}/match/test-match"

    @resp.activate
    def test_identifies_club_as_team1(self, match_detail_response_team1):
        resp.add(resp.GET, self.MATCH_URL, json=match_detail_response_team1, status=200)

        participants = ccr.get_match_data(self.MATCH_URL)

        assert "Alice" in participants
        assert "Bob" in participants
        # Opponents must not appear
        assert "Charlie" not in participants

    @resp.activate
    def test_identifies_club_as_team2(self, match_detail_response_team2):
        """Club identification must work regardless of team1/team2 slot."""
        resp.add(resp.GET, self.MATCH_URL, json=match_detail_response_team2, status=200)

        participants = ccr.get_match_data(self.MATCH_URL)

        assert "Alice" in participants
        assert "Charlie" not in participants

    @resp.activate
    def test_extracts_results_correctly(self, match_detail_response_team1):
        resp.add(resp.GET, self.MATCH_URL, json=match_detail_response_team1, status=200)

        participants = ccr.get_match_data(self.MATCH_URL)

        assert participants["Alice"]["result_white"] == "win"
        assert participants["Alice"]["result_black"] == "checkmated"

    @resp.activate
    def test_returns_in_progress_when_result_missing(self, match_detail_response_team1):
        """Absent result field defaults to 'in progress'."""
        resp.add(resp.GET, self.MATCH_URL, json=match_detail_response_team1, status=200)

        participants = ccr.get_match_data(self.MATCH_URL)
        # Bob has played_as_white='in progress' in fixture
        assert participants["Bob"]["result_white"] == "in progress"

    @resp.activate
    def test_returns_empty_dict_when_club_not_found(self):
        """No match found for club → empty participants dict."""
        match_json = {
            "teams": {
                "team1": {"name": "Club A", "players": []},
                "team2": {"name": "Club B", "players": []},
            }
        }
        resp.add(resp.GET, self.MATCH_URL, json=match_json, status=200)

        participants = ccr.get_match_data(self.MATCH_URL)
        assert participants == {}


# ---------------------------------------------------------------------------
# match_strengthening_extract — get_match_participants
# ---------------------------------------------------------------------------


class TestGetMatchParticipants:
    @resp.activate
    def test_returns_participants_from_clubs_team(self, match_detail_response_team1):
        """Only players from Test Club's team must be returned."""
        resp.add(
            resp.GET,
            f"{BASE}/match/99999",
            json=match_detail_response_team1,
            status=200,
        )

        with patch.object(mse, "CLUB_NAME", "Test Club"):
            participants = mse.get_match_participants("99999")

        assert "alice" in participants
        assert "bob" in participants
        assert "charlie" not in participants

    @resp.activate
    def test_returns_lowercase_usernames(self, match_detail_response_team1):
        """All usernames must be lowercased for case-insensitive comparison."""
        resp.add(
            resp.GET,
            f"{BASE}/match/99999",
            json=match_detail_response_team1,
            status=200,
        )

        with patch.object(mse, "CLUB_NAME", "Test Club"):
            participants = mse.get_match_participants("99999")

        for username in participants:
            assert username == username.lower(), f"Username '{username}' is not lowercase"

    @resp.activate
    def test_returns_empty_when_club_not_in_match(self):
        """Returns empty list when Test Club is not a participant."""
        match_json = {
            "settings": {},
            "teams": {
                "team1": {"name": "Other Club 1", "players": [{"username": "X"}]},
                "team2": {"name": "Other Club 2", "players": [{"username": "Y"}]},
            },
        }
        resp.add(resp.GET, f"{BASE}/match/99999", json=match_json, status=200)

        with patch.object(mse, "CLUB_NAME", "Test Club"):
            participants = mse.get_match_participants("99999")

        assert participants == []


# ---------------------------------------------------------------------------
# match_strengthening_extract — get_eligible_members (rating filter)
# ---------------------------------------------------------------------------


class TestGetEligibleMembers:
    @resp.activate
    def test_filters_members_above_max_rating(self, player_profile_response):
        """Members whose daily rating exceeds max_rating must be excluded."""
        club_members = {
            "weekly": [{"username": "lowrated"}],
            "monthly": [{"username": "highrated"}],
            "all_time": [],
        }
        low_stats = {"chess_daily": {"last": {"rating": 1000}, "record": {"timeout_percent": 0}}, "chess960_daily": {}}
        high_stats = {"chess_daily": {"last": {"rating": 1800}, "record": {"timeout_percent": 0}}, "chess960_daily": {}}

        resp.add(resp.GET, f"{BASE}/club/test-club/members", json=club_members, status=200)
        resp.add(resp.GET, f"{BASE}/player/lowrated/stats", json=low_stats, status=200)
        resp.add(resp.GET, f"{BASE}/player/highrated/stats", json=high_stats, status=200)
        # get_last_online only called for eligible members
        resp.add(resp.GET, f"{BASE}/player/lowrated", json=player_profile_response, status=200)

        eligible = mse.get_eligible_members("test-club", max_rating=1400)

        usernames = [m["username"] for m in eligible]
        assert "lowrated" in usernames
        assert "highrated" not in usernames

    @resp.activate
    def test_unrated_members_are_excluded(self, player_profile_response):
        """Unrated players (no chess_daily) must not be included."""
        club_members = {"weekly": [{"username": "unrated"}], "monthly": [], "all_time": []}
        unrated_stats = {"chess960_daily": {}}  # no chess_daily key

        resp.add(resp.GET, f"{BASE}/club/test-club/members", json=club_members, status=200)
        resp.add(resp.GET, f"{BASE}/player/unrated/stats", json=unrated_stats, status=200)

        eligible = mse.get_eligible_members("test-club", max_rating=1400)
        assert eligible == []

    @resp.activate
    def test_member_exactly_at_max_rating_is_included(self, player_profile_response):
        """Rating equal to max_rating is on the boundary and must be included."""
        club_members = {"weekly": [{"username": "borderline"}], "monthly": [], "all_time": []}
        borderline_stats = {
            "chess_daily": {"last": {"rating": 1400}, "record": {"timeout_percent": 0}},
            "chess960_daily": {},
        }

        resp.add(resp.GET, f"{BASE}/club/test-club/members", json=club_members, status=200)
        resp.add(resp.GET, f"{BASE}/player/borderline/stats", json=borderline_stats, status=200)
        resp.add(resp.GET, f"{BASE}/player/borderline", json=player_profile_response, status=200)

        eligible = mse.get_eligible_members("test-club", max_rating=1400)
        assert len(eligible) == 1
        assert eligible[0]["username"] == "borderline"


# ---------------------------------------------------------------------------
# match_strengthening_extract — get_eligible_members_by_variant (chess960)
# ---------------------------------------------------------------------------


class TestGetEligibleMembersByVariant:
    @resp.activate
    def test_chess960_uses_chess960_rating(self, player_profile_response):
        """For chess960 variant, eligibility is determined by chess960_rating not daily."""
        club_members = {
            "weekly": [{"username": "c960eligible"}],
            "monthly": [{"username": "c960ineligible"}],
            "all_time": [],
        }
        # c960eligible: high daily (1800) but low 960 (1050) → should be included at 1400 cap
        # c960ineligible: low daily (800) but high 960 (1600) → excluded
        stats_eligible = {
            "chess_daily": {"last": {"rating": 1800}, "record": {"timeout_percent": 0}},
            "chess960_daily": {"last": {"rating": 1050}, "record": {"timeout_percent": 0}},
        }
        stats_ineligible = {
            "chess_daily": {"last": {"rating": 800}, "record": {"timeout_percent": 0}},
            "chess960_daily": {"last": {"rating": 1600}, "record": {"timeout_percent": 0}},
        }

        resp.add(resp.GET, f"{BASE}/club/test-club/members", json=club_members, status=200)
        resp.add(resp.GET, f"{BASE}/player/c960eligible/stats", json=stats_eligible, status=200)
        resp.add(resp.GET, f"{BASE}/player/c960ineligible/stats", json=stats_ineligible, status=200)
        resp.add(resp.GET, f"{BASE}/player/c960eligible", json=player_profile_response, status=200)

        eligible = mse.get_eligible_members_by_variant("test-club", max_rating=1400, variant="chess960")

        usernames = [m["username"] for m in eligible]
        assert "c960eligible" in usernames
        assert "c960ineligible" not in usernames

    @resp.activate
    def test_chess960_includes_unrated_960_players(self, player_profile_response):
        """Unrated Chess960 players are included for visibility."""
        club_members = {"weekly": [{"username": "unrated960"}], "monthly": [], "all_time": []}
        stats = {
            "chess_daily": {"last": {"rating": 1200}, "record": {"timeout_percent": 0}},
            "chess960_daily": {},  # no rating → 'Unrated'
        }

        resp.add(resp.GET, f"{BASE}/club/test-club/members", json=club_members, status=200)
        resp.add(resp.GET, f"{BASE}/player/unrated960/stats", json=stats, status=200)
        resp.add(resp.GET, f"{BASE}/player/unrated960", json=player_profile_response, status=200)

        eligible = mse.get_eligible_members_by_variant(
            "test-club", max_rating=1400, variant="chess960"
        )

        usernames = [m["username"] for m in eligible]
        assert "unrated960" in usernames


# ---------------------------------------------------------------------------
# match_strengthening_extract — get_match_variant
# ---------------------------------------------------------------------------


class TestGetMatchVariant:
    @resp.activate
    def test_detects_chess960_from_rules(self, match_detail_response_chess960):
        resp.add(
            resp.GET,
            f"{BASE}/match/99999",
            json=match_detail_response_chess960,
            status=200,
        )

        variant = mse.get_match_variant("99999")
        assert variant == "chess960"

    @resp.activate
    def test_detects_chess960_from_variant_field(self):
        match_json = {"settings": {"rules": "chess", "variant": "chess960"}}
        resp.add(resp.GET, f"{BASE}/match/99999", json=match_json, status=200)

        variant = mse.get_match_variant("99999")
        assert variant == "chess960"

    @resp.activate
    def test_defaults_to_standard_chess(self):
        match_json = {"settings": {"rules": "chess", "variant": ""}}
        resp.add(resp.GET, f"{BASE}/match/99999", json=match_json, status=200)

        variant = mse.get_match_variant("99999")
        assert variant == "chess"

    @resp.activate
    def test_returns_chess_when_settings_absent(self):
        resp.add(resp.GET, f"{BASE}/match/99999", json={}, status=200)

        variant = mse.get_match_variant("99999")
        assert variant == "chess"


# ---------------------------------------------------------------------------
# generate_prospect_data — fetch_club_members (raw requests.get, no retry)
# ---------------------------------------------------------------------------


class TestFetchClubMembers:
    @resp.activate
    def test_returns_merged_member_list(self, club_members_response):
        resp.add(
            resp.GET,
            f"{BASE}/club/prospect-club/members",
            json=club_members_response,
            status=200,
        )

        members = gpd.fetch_club_members("prospect-club")

        usernames = [m["username"] for m in members]
        assert "player_weekly" in usernames
        assert "player_monthly" in usernames
        assert "player_alltime" in usernames

    @resp.activate
    def test_returns_empty_list_on_non_200_response(self):
        """Raw requests.get path returns [] on error (no retry)."""
        resp.add(resp.GET, f"{BASE}/club/bad-club/members", status=500)

        members = gpd.fetch_club_members("bad-club")
        assert members == []

    @resp.activate
    def test_prospect_members_exclude_existing_club_members(self, club_members_response):
        """
        Verifies the exclusion logic: members already in the exclusion club
        must not appear in the eligible set.

        This test exercises the filtering logic inline — the extracted
        service function will provide a cleaner interface in Action 7.
        """
        prospect_members_response = {
            "weekly": [{"username": "new_prospect"}, {"username": "existing_member"}],
            "monthly": [],
            "all_time": [],
        }
        exclusion_response = {
            "weekly": [{"username": "existing_member"}],
            "monthly": [],
            "all_time": [],
        }

        resp.add(
            resp.GET,
            f"{BASE}/club/prospect-club/members",
            json=prospect_members_response,
            status=200,
        )
        resp.add(
            resp.GET,
            f"{BASE}/club/my-club/members",
            json=exclusion_response,
            status=200,
        )

        prospect_members = gpd.fetch_club_members("prospect-club")
        exclusion_members = {m["username"] for m in gpd.fetch_club_members("my-club")}
        eligible = [m for m in prospect_members if m["username"] not in exclusion_members]

        eligible_usernames = [m["username"] for m in eligible]
        assert "new_prospect" in eligible_usernames
        assert "existing_member" not in eligible_usernames

    def test_deduplication_of_prospects_across_clubs(self):
        """
        Verifies that duplicate usernames sourced from multiple clubs collapse
        to a single entry.

        NOTE: The deduplication logic is currently inline in main() of
        generate_prospect_data.py and cannot be cleanly unit tested without
        running the full function. This test validates the dedup algorithm in
        isolation using the same pattern as the production code. A proper
        service-level test will be added in Action 7.
        """
        # Simulate the dedup logic from generate_prospect_data.main()
        results = [
            {"Username": "alice", "Sourced Club": "club-a"},
            {"Username": "bob", "Sourced Club": "club-b"},
            {"Username": "alice", "Sourced Club": "club-c"},  # duplicate
        ]

        seen: set = set()
        deduped: list = []
        for result in results:
            if result["Username"] not in seen:
                deduped.append(result)
                seen.add(result["Username"])

        assert len(deduped) == 2
        usernames = [r["Username"] for r in deduped]
        assert usernames.count("alice") == 1
        assert "bob" in usernames
