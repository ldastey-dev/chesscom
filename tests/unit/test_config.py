"""Unit tests for chesscom.config.AppConfig."""

from __future__ import annotations

import pytest

from chesscom.config import AppConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUIRED = {"CLUB_REF": "team-scotland", "CLUB_NAME": "Team Scotland"}


def _set_required(monkeypatch):
    for k, v in _REQUIRED.items():
        monkeypatch.setenv(k, v)


# ===========================================================================
# Happy path — required fields
# ===========================================================================


class TestRequiredFields:
    def test_club_ref_read(self, monkeypatch):
        _set_required(monkeypatch)
        cfg = AppConfig.from_env()
        assert cfg.club_ref == "team-scotland"

    def test_club_name_read(self, monkeypatch):
        _set_required(monkeypatch)
        cfg = AppConfig.from_env()
        assert cfg.club_name == "Team Scotland"

    def test_required_fields_stripped(self, monkeypatch):
        monkeypatch.setenv("CLUB_REF", "  team-scotland  ")
        monkeypatch.setenv("CLUB_NAME", "  Team Scotland  ")
        cfg = AppConfig.from_env()
        assert cfg.club_ref == "team-scotland"
        assert cfg.club_name == "Team Scotland"


# ===========================================================================
# Validation errors — missing required fields
# ===========================================================================


class TestValidationErrors:
    def test_missing_club_ref_raises(self, monkeypatch):
        monkeypatch.delenv("CLUB_REF", raising=False)
        monkeypatch.setenv("CLUB_NAME", "Team Scotland")
        with pytest.raises(ValueError, match="CLUB_REF"):
            AppConfig.from_env()

    def test_missing_club_name_raises(self, monkeypatch):
        monkeypatch.setenv("CLUB_REF", "team-scotland")
        monkeypatch.delenv("CLUB_NAME", raising=False)
        with pytest.raises(ValueError, match="CLUB_NAME"):
            AppConfig.from_env()

    def test_both_required_missing_lists_both(self, monkeypatch):
        monkeypatch.delenv("CLUB_REF", raising=False)
        monkeypatch.delenv("CLUB_NAME", raising=False)
        with pytest.raises(ValueError, match="CLUB_REF") as exc_info:
            AppConfig.from_env()
        assert "CLUB_NAME" in str(exc_info.value)

    def test_empty_string_club_ref_raises(self, monkeypatch):
        monkeypatch.setenv("CLUB_REF", "")
        monkeypatch.setenv("CLUB_NAME", "Team Scotland")
        with pytest.raises(ValueError, match="CLUB_REF"):
            AppConfig.from_env()

    def test_whitespace_only_club_ref_raises(self, monkeypatch):
        monkeypatch.setenv("CLUB_REF", "   ")
        monkeypatch.setenv("CLUB_NAME", "Team Scotland")
        with pytest.raises(ValueError, match="CLUB_REF"):
            AppConfig.from_env()


# ===========================================================================
# Optional field — data_analysis_year
# ===========================================================================


class TestDataAnalysisYear:
    def test_year_absent_defaults_to_none(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.delenv("DATA_ANALYSIS_YEAR", raising=False)
        cfg = AppConfig.from_env()
        assert cfg.data_analysis_year is None

    def test_year_parsed_to_int(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.setenv("DATA_ANALYSIS_YEAR", "2024")
        cfg = AppConfig.from_env()
        assert cfg.data_analysis_year == 2024

    def test_year_whitespace_stripped_then_parsed(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.setenv("DATA_ANALYSIS_YEAR", "  2025  ")
        cfg = AppConfig.from_env()
        assert cfg.data_analysis_year == 2025

    def test_year_empty_string_normalised_to_none(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.setenv("DATA_ANALYSIS_YEAR", "")
        cfg = AppConfig.from_env()
        assert cfg.data_analysis_year is None

    def test_year_non_integer_raises(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.setenv("DATA_ANALYSIS_YEAR", "twenty-twenty")
        with pytest.raises(ValueError, match="DATA_ANALYSIS_YEAR"):
            AppConfig.from_env()


# ===========================================================================
# Optional field — match_id
# ===========================================================================


class TestMatchId:
    def test_match_id_absent_defaults_to_none(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.delenv("MATCH_ID", raising=False)
        cfg = AppConfig.from_env()
        assert cfg.match_id is None

    def test_match_id_read(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.setenv("MATCH_ID", "12345")
        cfg = AppConfig.from_env()
        assert cfg.match_id == "12345"

    def test_match_id_stripped(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.setenv("MATCH_ID", "  67890  ")
        cfg = AppConfig.from_env()
        assert cfg.match_id == "67890"

    def test_match_id_empty_string_normalised_to_none(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.setenv("MATCH_ID", "")
        cfg = AppConfig.from_env()
        assert cfg.match_id is None


# ===========================================================================
# Optional field — prospect_clubs
# ===========================================================================


class TestProspectClubs:
    def test_absent_defaults_to_empty_list(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.delenv("LIST_OF_CLUBS", raising=False)
        cfg = AppConfig.from_env()
        assert cfg.prospect_clubs == []

    def test_single_club_parsed(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.setenv("LIST_OF_CLUBS", "team-ireland")
        cfg = AppConfig.from_env()
        assert cfg.prospect_clubs == ["team-ireland"]

    def test_multiple_clubs_split_on_comma(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.setenv("LIST_OF_CLUBS", "team-ireland,team-england,team-wales")
        cfg = AppConfig.from_env()
        assert cfg.prospect_clubs == ["team-ireland", "team-england", "team-wales"]

    def test_clubs_whitespace_stripped(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.setenv("LIST_OF_CLUBS", " team-ireland , team-england ")
        cfg = AppConfig.from_env()
        assert cfg.prospect_clubs == ["team-ireland", "team-england"]

    def test_empty_entries_discarded(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.setenv("LIST_OF_CLUBS", "team-ireland,,team-england,")
        cfg = AppConfig.from_env()
        assert cfg.prospect_clubs == ["team-ireland", "team-england"]

    def test_empty_string_produces_empty_list(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.setenv("LIST_OF_CLUBS", "")
        cfg = AppConfig.from_env()
        assert cfg.prospect_clubs == []


# ===========================================================================
# Optional field — exclusion_club
# ===========================================================================


class TestExclusionClub:
    def test_absent_defaults_to_none(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.delenv("EXCLUSION_CLUB", raising=False)
        cfg = AppConfig.from_env()
        assert cfg.exclusion_club is None

    def test_exclusion_club_read(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.setenv("EXCLUSION_CLUB", "team-scotland")
        cfg = AppConfig.from_env()
        assert cfg.exclusion_club == "team-scotland"

    def test_exclusion_club_stripped(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.setenv("EXCLUSION_CLUB", "  team-scotland  ")
        cfg = AppConfig.from_env()
        assert cfg.exclusion_club == "team-scotland"

    def test_empty_string_normalised_to_none(self, monkeypatch):
        _set_required(monkeypatch)
        monkeypatch.setenv("EXCLUSION_CLUB", "")
        cfg = AppConfig.from_env()
        assert cfg.exclusion_club is None


# ===========================================================================
# Full happy path
# ===========================================================================


class TestFullHappyPath:
    def test_all_fields_present(self, monkeypatch):
        monkeypatch.setenv("CLUB_REF", "team-scotland")
        monkeypatch.setenv("CLUB_NAME", "Team Scotland")
        monkeypatch.setenv("DATA_ANALYSIS_YEAR", "2024")
        monkeypatch.setenv("MATCH_ID", "99999")
        monkeypatch.setenv("LIST_OF_CLUBS", "team-ireland,team-england")
        monkeypatch.setenv("EXCLUSION_CLUB", "team-scotland")
        cfg = AppConfig.from_env()
        assert cfg.club_ref == "team-scotland"
        assert cfg.club_name == "Team Scotland"
        assert cfg.data_analysis_year == 2024
        assert cfg.match_id == "99999"
        assert cfg.prospect_clubs == ["team-ireland", "team-england"]
        assert cfg.exclusion_club == "team-scotland"

    def test_returns_appconfig_instance(self, monkeypatch):
        _set_required(monkeypatch)
        assert isinstance(AppConfig.from_env(), AppConfig)
