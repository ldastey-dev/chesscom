"""
Unit tests for the pure calculation functions in chesscom.domain.services.

Originally these tested the duplicated functions in club_contribution_report.py
and utils. Now they test the canonical implementations in the services module.
"""


from chesscom.domain.services import calculate_participation_percentage, calculate_win_rate

# ---------------------------------------------------------------------------
# calculate_participation_percentage
# ---------------------------------------------------------------------------


class TestCalculateParticipationPercentage:
    def test_normal_participation(self):
        assert calculate_participation_percentage(10, 7) == 70.0

    def test_full_participation(self):
        assert calculate_participation_percentage(5, 5) == 100.0

    def test_zero_participation(self):
        assert calculate_participation_percentage(10, 0) == 0.0

    def test_division_by_zero_returns_zero(self):
        """When no matches have been played, result must be 0 not ZeroDivisionError."""
        assert calculate_participation_percentage(0, 0) == 0

    def test_single_match_participated(self):
        assert calculate_participation_percentage(1, 1) == 100.0

    def test_single_match_not_participated(self):
        assert calculate_participation_percentage(1, 0) == 0.0

    def test_result_is_rounded_to_two_decimal_places(self):
        # 1/3 * 100 = 33.333... -> 33.33
        assert calculate_participation_percentage(3, 1) == 33.33


# ---------------------------------------------------------------------------
# calculate_win_rate
# ---------------------------------------------------------------------------


class TestCalculateWinRate:
    def test_all_wins(self):
        assert calculate_win_rate(10, 0, 0) == 100.0

    def test_all_losses(self):
        assert calculate_win_rate(0, 10, 0) == 0.0

    def test_all_draws(self):
        """Win rate is 0% when all games are draws."""
        assert calculate_win_rate(0, 0, 10) == 0.0

    def test_mixed_results(self):
        # 3 wins, 2 losses, 1 draw -> 3/6 = 50.0%
        assert calculate_win_rate(3, 2, 1) == 50.0

    def test_no_games_returns_zero(self):
        """No ZeroDivisionError when all counts are 0."""
        assert calculate_win_rate(0, 0, 0) == 0

    def test_result_is_rounded_to_two_decimal_places(self):
        # 1 win, 2 losses, 0 draws -> 1/3 = 33.33%
        assert calculate_win_rate(1, 2, 0) == 33.33

    def test_single_win(self):
        assert calculate_win_rate(1, 0, 0) == 100.0

    def test_majority_draws(self):
        # 1 win, 0 losses, 9 draws -> 1/10 = 10.0%
        assert calculate_win_rate(1, 0, 9) == 10.0
