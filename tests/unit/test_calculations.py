"""
Unit tests for pure calculation functions in club_contribution_report and utils.

These tests have no I/O or HTTP dependencies — they test logic only.
"""

from unittest.mock import patch

import pytest
import requests
import responses as responses_lib

import club_contribution_report as ccr
import utils

# ---------------------------------------------------------------------------
# calculate_participation_percentage
# ---------------------------------------------------------------------------


class TestCalculateParticipationPercentage:
    def test_normal_participation(self):
        assert ccr.calculate_participation_percentage(10, 7) == 70.0

    def test_full_participation(self):
        assert ccr.calculate_participation_percentage(5, 5) == 100.0

    def test_zero_participation(self):
        assert ccr.calculate_participation_percentage(10, 0) == 0.0

    def test_division_by_zero_returns_zero(self):
        """When no matches have been played, result must be 0 not ZeroDivisionError."""
        assert ccr.calculate_participation_percentage(0, 0) == 0

    def test_single_match_participated(self):
        assert ccr.calculate_participation_percentage(1, 1) == 100.0

    def test_single_match_not_participated(self):
        assert ccr.calculate_participation_percentage(1, 0) == 0.0

    def test_result_is_rounded_to_two_decimal_places(self):
        # 1/3 * 100 = 33.333... → 33.33
        assert ccr.calculate_participation_percentage(3, 1) == 33.33


# ---------------------------------------------------------------------------
# calculate_win_rate
# ---------------------------------------------------------------------------


class TestCalculateWinRate:
    def test_all_wins(self):
        assert ccr.calculate_win_rate(10, 0, 0) == 100.0

    def test_all_losses(self):
        assert ccr.calculate_win_rate(0, 10, 0) == 0.0

    def test_all_draws(self):
        """Win rate is 0% when all games are draws."""
        assert ccr.calculate_win_rate(0, 0, 10) == 0.0

    def test_mixed_results(self):
        # 3 wins, 2 losses, 1 draw → 3/6 = 50.0%
        assert ccr.calculate_win_rate(3, 2, 1) == 50.0

    def test_no_games_returns_zero(self):
        """No ZeroDivisionError when all counts are 0."""
        assert ccr.calculate_win_rate(0, 0, 0) == 0

    def test_result_is_rounded_to_two_decimal_places(self):
        # 1 win, 2 losses, 0 draws → 1/3 = 33.33%
        assert ccr.calculate_win_rate(1, 2, 0) == 33.33

    def test_single_win(self):
        assert ccr.calculate_win_rate(1, 0, 0) == 100.0

    def test_majority_draws(self):
        # 1 win, 0 losses, 9 draws → 1/10 = 10.0%
        assert ccr.calculate_win_rate(1, 0, 9) == 10.0


# ---------------------------------------------------------------------------
# get_unique_filename
# ---------------------------------------------------------------------------


class TestGetUniqueFilename:
    def test_returns_base_filename_when_no_conflict(self):
        """When the target file does not exist, return the plain filename."""
        with (
            patch("utils.os.path.exists", return_value=False),
            patch("utils.os.makedirs"),
        ):
            result = utils.get_unique_filename("output", "MyReport", "xlsx")

        assert result.endswith("MyReport.xlsx")

    def test_appends_counter_when_file_exists_once(self):
        """When base name exists, append _1 to avoid overwrite."""
        # First call (base) returns True, second call (_1 suffix) returns False
        exists_side_effects = [True, False]
        with (
            patch("utils.os.path.exists", side_effect=exists_side_effects),
            patch("utils.os.makedirs"),
        ):
            result = utils.get_unique_filename("output", "MyReport", "xlsx")

        assert result.endswith("MyReport_1.xlsx")

    def test_increments_counter_until_free_slot(self):
        """Counter increments until a free filename is found."""
        # base, _1, _2 all exist; _3 is free
        exists_side_effects = [True, True, True, False]
        with (
            patch("utils.os.path.exists", side_effect=exists_side_effects),
            patch("utils.os.makedirs"),
        ):
            result = utils.get_unique_filename("output", "MyReport", "xlsx")

        assert result.endswith("MyReport_3.xlsx")

    def test_extension_is_preserved(self):
        with (
            patch("utils.os.path.exists", return_value=False),
            patch("utils.os.makedirs"),
        ):
            result = utils.get_unique_filename("output", "Report", "csv")

        assert result.endswith(".csv")

    def test_makedirs_is_called(self):
        """Ensures the output directory is created if it doesn't exist."""
        with (
            patch("utils.os.path.exists", return_value=False),
            patch("utils.os.makedirs") as mock_makedirs,
        ):
            utils.get_unique_filename("output", "Report", "xlsx")

        mock_makedirs.assert_called_once()


# ---------------------------------------------------------------------------
# request_handler — retry and error handling
# ---------------------------------------------------------------------------


class TestRequestHandler:
    BASE_URL = "https://api.chess.com/pub/test-endpoint"

    @responses_lib.activate
    def test_returns_response_on_success(self):
        responses_lib.add(responses_lib.GET, self.BASE_URL, json={"ok": True}, status=200)
        response = utils.request_handler(self.BASE_URL)
        assert response.json() == {"ok": True}

    @responses_lib.activate
    @patch("utils.time.sleep")
    def test_retries_on_connection_error_then_succeeds(self, mock_sleep):
        """Retries on ConnectionError and succeeds on the final attempt."""
        responses_lib.add(responses_lib.GET, self.BASE_URL, body=ConnectionError("Network down"))
        responses_lib.add(responses_lib.GET, self.BASE_URL, body=ConnectionError("Network down"))
        responses_lib.add(responses_lib.GET, self.BASE_URL, json={"ok": True}, status=200)

        response = utils.request_handler(self.BASE_URL, retries=3, backoff_factor=0.1)

        assert response.json() == {"ok": True}
        assert mock_sleep.call_count == 2  # slept between attempt 1→2 and 2→3

    @responses_lib.activate
    @patch("utils.time.sleep")
    def test_raises_after_max_retries_exhausted(self, mock_sleep):
        """Raises the underlying exception once all retries are consumed."""
        for _ in range(3):
            responses_lib.add(
                responses_lib.GET, self.BASE_URL, body=ConnectionError("Network down")
            )

        with pytest.raises(ConnectionError):
            utils.request_handler(self.BASE_URL, retries=3, backoff_factor=0.1)

        assert mock_sleep.call_count == 2  # sleep between attempts, not after last

    @responses_lib.activate
    @patch("utils.time.sleep")
    def test_raises_on_http_error_after_retries(self, mock_sleep):
        """HTTPError (e.g. 429) is retried and then raised."""
        for _ in range(3):
            responses_lib.add(responses_lib.GET, self.BASE_URL, status=429)

        with pytest.raises(requests.HTTPError):
            utils.request_handler(self.BASE_URL, retries=3, backoff_factor=0.1)

    @responses_lib.activate
    @patch("utils.time.sleep")
    def test_backoff_increases_exponentially(self, mock_sleep):
        """Sleep duration follows backoff_factor * 2^attempt pattern."""
        for _ in range(3):
            responses_lib.add(responses_lib.GET, self.BASE_URL, body=ConnectionError())

        with pytest.raises(ConnectionError):
            utils.request_handler(self.BASE_URL, retries=3, backoff_factor=1.0)

        # Attempt 0 → sleep(1.0 * 2^0 = 1.0), Attempt 1 → sleep(1.0 * 2^1 = 2.0)
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_calls == [1.0, 2.0]
