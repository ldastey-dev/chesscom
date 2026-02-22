"""Integration tests for ChessComClient.

All HTTP calls are intercepted and mocked using the ``responses`` library
so no real network traffic is generated.
"""

from __future__ import annotations

import pytest
import requests
import responses as resp

from chesscom.api.client import BASE_URL, ChessComClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_client(**kwargs) -> ChessComClient:
    """Return a client with zero backoff so retry tests run fast."""
    kwargs.setdefault("backoff_factor", 0)
    return ChessComClient(**kwargs)


# ---------------------------------------------------------------------------
# get_club_members
# ---------------------------------------------------------------------------


class TestGetClubMembers:
    @resp.activate
    def test_merges_all_three_buckets(self, club_members_response):
        resp.add(
            resp.GET,
            f"{BASE_URL}/club/team-scotland/members",
            json=club_members_response,
            status=200,
        )
        client = make_client()
        members = client.get_club_members("team-scotland")
        assert len(members) == 3
        usernames = [m["username"] for m in members]
        assert "player_weekly" in usernames
        assert "player_monthly" in usernames
        assert "player_alltime" in usernames

    @resp.activate
    def test_empty_buckets_returns_empty_list(self):
        resp.add(
            resp.GET,
            f"{BASE_URL}/club/empty-club/members",
            json={"weekly": [], "monthly": [], "all_time": []},
            status=200,
        )
        client = make_client()
        assert client.get_club_members("empty-club") == []

    @resp.activate
    def test_missing_buckets_tolerated(self):
        """Response with only one bucket present should not raise."""
        resp.add(
            resp.GET,
            f"{BASE_URL}/club/test-club/members",
            json={"weekly": [{"username": "solo"}]},
            status=200,
        )
        client = make_client()
        members = client.get_club_members("test-club")
        assert members == [{"username": "solo"}]

    @resp.activate
    def test_http_error_raises(self):
        resp.add(
            resp.GET,
            f"{BASE_URL}/club/bad-club/members",
            status=404,
        )
        client = make_client(retries=1)
        with pytest.raises(requests.HTTPError):
            client.get_club_members("bad-club")

    @resp.activate
    def test_uses_club_ref_in_url(self, club_members_response):
        resp.add(
            resp.GET,
            f"{BASE_URL}/club/my-custom-club/members",
            json=club_members_response,
            status=200,
        )
        client = make_client()
        client.get_club_members("my-custom-club")
        assert resp.calls[0].request.url == f"{BASE_URL}/club/my-custom-club/members"


# ---------------------------------------------------------------------------
# get_player_stats
# ---------------------------------------------------------------------------


class TestGetPlayerStats:
    @resp.activate
    def test_returns_stats_dict(self, player_stats_response):
        resp.add(
            resp.GET,
            f"{BASE_URL}/player/testplayer/stats",
            json=player_stats_response,
            status=200,
        )
        client = make_client()
        stats = client.get_player_stats("testplayer")
        assert stats["chess_daily"]["last"]["rating"] == 1200
        assert stats["chess960_daily"]["last"]["rating"] == 1100

    @resp.activate
    def test_unrated_player_returns_empty_dict(self, player_stats_response_unrated):
        resp.add(
            resp.GET,
            f"{BASE_URL}/player/newcomer/stats",
            json=player_stats_response_unrated,
            status=200,
        )
        client = make_client()
        stats = client.get_player_stats("newcomer")
        assert stats == {}

    @resp.activate
    def test_http_error_raises(self):
        resp.add(resp.GET, f"{BASE_URL}/player/ghost/stats", status=410)
        client = make_client(retries=1)
        with pytest.raises(requests.HTTPError):
            client.get_player_stats("ghost")

    @resp.activate
    def test_username_is_lowercased_in_url(self, player_stats_response):
        """URL should use the username as-is (Chess.com is case-insensitive)."""
        resp.add(
            resp.GET,
            f"{BASE_URL}/player/TestPlayer/stats",
            json=player_stats_response,
            status=200,
        )
        client = make_client()
        client.get_player_stats("TestPlayer")
        assert "/player/TestPlayer/stats" in resp.calls[0].request.url


# ---------------------------------------------------------------------------
# get_player_profile
# ---------------------------------------------------------------------------


class TestGetPlayerProfile:
    @resp.activate
    def test_returns_profile(self, player_profile_response):
        resp.add(
            resp.GET,
            f"{BASE_URL}/player/testplayer",
            json=player_profile_response,
            status=200,
        )
        client = make_client()
        profile = client.get_player_profile("testplayer")
        assert profile["username"] == "testplayer"
        assert profile["name"] == "Test Player"
        assert profile["title"] == "FM"

    @resp.activate
    def test_http_error_raises(self):
        resp.add(resp.GET, f"{BASE_URL}/player/nobody", status=404)
        client = make_client(retries=1)
        with pytest.raises(requests.HTTPError):
            client.get_player_profile("nobody")

    @resp.activate
    def test_profile_url_distinct_from_stats_url(self, player_profile_response):
        resp.add(
            resp.GET,
            f"{BASE_URL}/player/testplayer",
            json=player_profile_response,
            status=200,
        )
        client = make_client()
        client.get_player_profile("testplayer")
        assert resp.calls[0].request.url == f"{BASE_URL}/player/testplayer"


# ---------------------------------------------------------------------------
# get_club_matches
# ---------------------------------------------------------------------------


class TestGetClubMatches:
    @resp.activate
    def test_returns_full_payload(self, club_matches_response):
        resp.add(
            resp.GET,
            f"{BASE_URL}/club/team-scotland/matches",
            json=club_matches_response,
            status=200,
        )
        client = make_client()
        data = client.get_club_matches("team-scotland")
        assert "finished" in data
        assert len(data["finished"]) == 1
        assert data["finished"][0]["name"] == "Test Match 2025"

    @resp.activate
    def test_empty_matches_returned_as_is(self):
        resp.add(
            resp.GET,
            f"{BASE_URL}/club/new-club/matches",
            json={"finished": [], "in_progress": [], "registered": []},
            status=200,
        )
        client = make_client()
        data = client.get_club_matches("new-club")
        assert data["finished"] == []

    @resp.activate
    def test_http_error_raises(self):
        resp.add(resp.GET, f"{BASE_URL}/club/bad-club/matches", status=403)
        client = make_client(retries=1)
        with pytest.raises(requests.HTTPError):
            client.get_club_matches("bad-club")


# ---------------------------------------------------------------------------
# get_match
# ---------------------------------------------------------------------------


class TestGetMatch:
    @resp.activate
    def test_accepts_bare_match_id(self, match_detail_response_team1):
        resp.add(
            resp.GET,
            f"{BASE_URL}/match/12345",
            json=match_detail_response_team1,
            status=200,
        )
        client = make_client()
        data = client.get_match("12345")
        assert data["name"] == "Test Match"

    @resp.activate
    def test_accepts_full_url(self, match_detail_response_team1):
        full_url = f"{BASE_URL}/match/12345"
        resp.add(resp.GET, full_url, json=match_detail_response_team1, status=200)
        client = make_client()
        data = client.get_match(full_url)
        assert data["name"] == "Test Match"
        assert resp.calls[0].request.url == full_url

    @resp.activate
    def test_bare_id_builds_correct_url(self, match_detail_response_team1):
        resp.add(
            resp.GET,
            f"{BASE_URL}/match/99999",
            json=match_detail_response_team1,
            status=200,
        )
        client = make_client()
        client.get_match("99999")
        assert resp.calls[0].request.url == f"{BASE_URL}/match/99999"

    @resp.activate
    def test_http_error_raises(self):
        resp.add(resp.GET, f"{BASE_URL}/match/deleted", status=404)
        client = make_client(retries=1)
        with pytest.raises(requests.HTTPError):
            client.get_match("deleted")

    @resp.activate
    def test_chess960_match_settings_accessible(self, match_detail_response_chess960):
        resp.add(
            resp.GET,
            f"{BASE_URL}/match/chess960match",
            json=match_detail_response_chess960,
            status=200,
        )
        client = make_client()
        data = client.get_match("chess960match")
        assert data["settings"]["rules"] == "chess960"


# ---------------------------------------------------------------------------
# _get retry logic
# ---------------------------------------------------------------------------


class TestRetryLogic:
    @resp.activate
    def test_retries_on_connection_error_then_succeeds(self, club_members_response):
        """First attempt raises ConnectionError; second attempt succeeds."""
        resp.add(resp.GET, f"{BASE_URL}/club/retry-club/members", body=ConnectionError())
        resp.add(resp.GET, f"{BASE_URL}/club/retry-club/members", json=club_members_response)
        client = make_client(retries=2)
        members = client.get_club_members("retry-club")
        assert len(members) == 3
        assert len(resp.calls) == 2

    @resp.activate
    def test_raises_after_all_retries_exhausted(self):
        resp.add(resp.GET, f"{BASE_URL}/club/flaky/members", status=503)
        resp.add(resp.GET, f"{BASE_URL}/club/flaky/members", status=503)
        resp.add(resp.GET, f"{BASE_URL}/club/flaky/members", status=503)
        client = make_client(retries=3)
        with pytest.raises(requests.HTTPError):
            client.get_club_members("flaky")
        assert len(resp.calls) == 3

    @resp.activate
    def test_custom_base_url_is_used(self, club_members_response):
        custom_url = "https://mock.chess.test/pub"
        resp.add(
            resp.GET,
            f"{custom_url}/club/team/members",
            json=club_members_response,
        )
        client = make_client(base_url=custom_url)
        client.get_club_members("team")
        assert resp.calls[0].request.url == f"{custom_url}/club/team/members"

    @resp.activate
    def test_custom_headers_sent(self, club_members_response):
        resp.add(
            resp.GET,
            f"{BASE_URL}/club/test-club/members",
            json=club_members_response,
        )
        custom_headers = {"User-Agent": "TestAgent/1.0"}
        client = make_client(headers=custom_headers)
        client.get_club_members("test-club")
        assert resp.calls[0].request.headers["User-Agent"] == "TestAgent/1.0"
