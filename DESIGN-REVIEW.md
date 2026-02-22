# Design Review — `chesscom` Repository

**Date:** 2026-02-22
**Reviewer:** Principal Engineer (Python / Clean Architecture)
**Scope:** Full codebase review against SOLID, Clean Code, and Clean Architecture principles

---

## 1. Executive Summary

This repository contains four Python scripts that interact with the Chess.com public API to generate Excel reports for club management. While the code is functional, it exhibits significant structural and design deficiencies: duplicated logic across scripts, no abstraction layers, no tests, no documentation, inconsistent naming, side-effects at import time, and tight coupling between data access, business logic, and presentation. The codebase is fragile and would resist any safe refactoring without a test harness.

**Severity rating: High** — the codebase needs foundational restructuring before feature work continues.

---

## 2. Critical Findings

### 2.1 Naming — Scripts Have Unclear, Inconsistent Names

| Current Name | Problem | Recommended Name |
|---|---|---|
| `club_contribution_report.py` | "Contribution" is vague; the script measures match participation and win rates | `club_match_participation_report.py` |
| `generate_club_member_report.py` | "Generate" prefix is redundant (all scripts generate something); "report" is too generic | `club_member_summary.py` |
| `generate_prospect_data.py` | "Generate" prefix is redundant; "data" is meaningless — it produces an exclusion-filtered prospect report | `club_prospect_report.py` |
| `match_strengthening_extract.py` | "Strengthening extract" is domain jargon that doesn't describe the action; it produces a match eligibility report | `match_eligibility_report.py` |

### 2.2 Architecture — No Layered Structure (Violation of Separation of Concerns)

Every script mixes three responsibilities in flat functions:

1. **Data access** — HTTP calls to Chess.com API
2. **Business logic** — filtering, aggregation, percentage calculations
3. **Presentation** — Excel formatting, hyperlinks, sheet naming

There is no separation between these layers. This makes it impossible to test business logic without making HTTP calls, and impossible to change the output format without touching data-fetching code.

### 2.3 Massive Code Duplication (DRY Violation)

The following logic is duplicated across 2–4 scripts:

| Duplicated Concern | Files |
|---|---|
| Fetching club members (`weekly + monthly + all_time`) | All 4 scripts |
| Fetching player profile (name, joined date, last online) | `club_contribution_report.py`, `generate_club_member_report.py`, `generate_prospect_data.py`, `match_strengthening_extract.py` |
| Fetching player stats (rating, timeout %) | All 4 scripts |
| Timestamp → formatted date conversion | All 4 scripts |
| Excel export with hyperlinks | `club_contribution_report.py`, `match_strengthening_extract.py` |

### 2.4 `utils/__init__.py` — God Module with Side Effects at Import Time

- `load_dotenv()` executes on import, causing side effects for any module that imports `utils`.
- `headers` is a module-level mutable global — any importer shares state.
- `install_requirements()` exists but is never called — dead code.
- `disable_system_sleep()` / `enable_system_sleep()` invoke `sudo` and system-level commands from a utility module — dangerous, untestable, and unrelated to chess data.
- `print_line()` wraps `print()` with `\n\r` — non-standard line ending (should be `\r\n` if CR+LF is intended) and the abstraction adds no value.
- `get_unique_filename()` uses nested f-string quotes that are fragile and path construction uses string concatenation mixed with `os.path.join`.
- `calculate_execution_time` decorator silently swallows exceptions (returns `None` on error) which hides bugs.

### 2.5 `generate_prospect_data.py` — Bypasses `utils.request_handler`

This script imports `requests` directly and makes raw `requests.get()` calls, bypassing the retry/error-handling wrapper in `utils.request_handler`. This means network failures in prospect generation have no retry logic and inconsistent error handling compared to other scripts.

### 2.6 No Tests Exist

- Zero test files in the repository.
- `settings.json` configures pytest but there are no tests to run.
- No test directory structure.
- No mocking strategy for the HTTP layer.
- **This is the single biggest blocker to safe refactoring.** Without behavioural tests pinning current behaviour, any structural change risks introducing regressions with no safety net.

### 2.7 No Documentation

- No `README.md` exists.
- No docstrings on most functions (only `match_strengthening_extract.py` has docstrings — and those were likely added recently).
- `.env.template` references `club_member_data.py` which doesn't exist — stale documentation.
- No architecture decision records (ADRs).
- No usage instructions for any script.

### 2.8 No Dependency Pinning

`requirements.txt` has no version pins. Builds are non-reproducible. A breaking change in `pandas`, `requests`, or `openpyxl` would silently break the application.

### 2.9 GitHub Actions Workflow is Broken

`.github/workflows/main.yml` uses Jinja-style `{{ }}` instead of GitHub Actions `${{ }}` for secrets. This workflow will fail on every run.

### 2.10 Configuration is Scattered and Inconsistent

- `club_contribution_report.py` reads env vars at module level.
- `generate_club_member_report.py` reads env vars inside `__main__`.
- `generate_prospect_data.py` reads env vars inside `__main__`.
- `match_strengthening_extract.py` reads env vars at module level.
- `utils/__init__.py` calls `load_dotenv()` at import time.

There is no single configuration object or pattern.

---

## 3. SOLID Violations

| Principle | Violation |
|---|---|
| **Single Responsibility** | Every script handles API calls, business logic, and Excel generation. `utils/__init__.py` handles HTTP, file I/O, sleep management, requirement installation, and printing. |
| **Open/Closed** | Adding a new report type requires copying an entire script and duplicating API call patterns. No extension points exist. |
| **Liskov Substitution** | Not applicable (no inheritance hierarchy). |
| **Interface Segregation** | `utils` is a monolith — any consumer gets sleep management, requirement installation, HTTP handling, and printing whether they need it or not. |
| **Dependency Inversion** | All scripts depend directly on concrete HTTP implementations. Business logic cannot be tested without network access. |

---

## 4. Missing Behavioural Tests (Test Strategy)

The following tests must be written **before** any refactoring begins, to pin current behaviour:

### 4.1 Unit Tests (Pure Logic)

| Test | Module | Behaviour to Pin |
|---|---|---|
| `test_calculate_participation_percentage` | `club_contribution_report` | Returns 0 when no matches; correct percentage otherwise |
| `test_calculate_participation_percentage_division_by_zero` | `club_contribution_report` | Handles zero total matches gracefully |
| `test_calculate_win_rate` | `club_contribution_report` | Correct win rate; returns 0 when no games |
| `test_calculate_win_rate_all_draws` | `club_contribution_report` | Win rate is 0% when all draws |
| `test_get_unique_filename_no_conflict` | `utils` | Returns base filename when no file exists |
| `test_get_unique_filename_with_conflict` | `utils` | Appends incrementing counter when file exists |
| `test_request_handler_retries_on_failure` | `utils` | Retries the configured number of times with backoff |
| `test_request_handler_raises_after_max_retries` | `utils` | Raises after exhausting retries |

### 4.2 Integration Tests (Mocked HTTP)

| Test | Behaviour to Pin |
|---|---|
| `test_get_all_club_members_combines_categories` | Members from weekly, monthly, and all_time are merged |
| `test_get_member_daily_rating_missing_stats` | Returns 'N/A' or 'Unrated' when stats are absent |
| `test_get_match_data_identifies_correct_team` | Correctly identifies the club's team regardless of team1/team2 position |
| `test_get_match_participants_returns_lowercase` | All usernames are lowercased for comparison |
| `test_get_eligible_members_filters_by_rating` | Members above max rating are excluded |
| `test_get_eligible_members_by_variant_chess960` | Chess960 variant uses chess960 rating field |
| `test_get_match_variant_detects_chess960` | Correctly identifies chess960 from rules/variant fields |
| `test_fetch_club_members_prospect_exclusion` | Members in exclusion club are filtered out |
| `test_prospect_deduplication` | Duplicate usernames across clubs are deduplicated |

### 4.3 End-to-End Tests (Mocked HTTP, Real Excel Output)

| Test | Behaviour to Pin |
|---|---|
| `test_club_contribution_report_generates_valid_excel` | Excel file is created with correct sheets and columns |
| `test_club_member_summary_generates_valid_excel` | Excel file is created with expected member data |
| `test_match_eligibility_report_generates_valid_excel` | Excel contains variant info and hyperlinks |
| `test_prospect_report_generates_valid_excel` | Excel file contains only non-excluded members |

---

## 5. Proposed Target Architecture

```
chesscom/
├── README.md
├── DESIGN-REVIEW.md
├── pyproject.toml                  # Replace requirements.txt
├── .env.template
├── .github/
│   └── workflows/
│       └── ci.yml                  # Fixed CI pipeline
├── src/
│   └── chesscom/
│       ├── __init__.py
│       ├── config.py               # Centralised configuration
│       ├── api/
│       │   ├── __init__.py
│       │   └── client.py           # Single Chess.com API client class
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── models.py           # Dataclasses: Member, Match, MatchResult
│       │   └── services.py         # Pure business logic (calculations, filtering)
│       ├── reports/
│       │   ├── __init__.py
│       │   ├── base.py             # Abstract report class
│       │   ├── match_participation.py
│       │   ├── member_summary.py
│       │   ├── prospect.py
│       │   └── match_eligibility.py
│       ├── export/
│       │   ├── __init__.py
│       │   └── excel.py            # Generic Excel export utilities
│       └── cli.py                  # Entry points for each report
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Shared fixtures, mock API responses
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_services.py
│   │   └── test_config.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_api_client.py
│   │   └── test_reports.py
│   └── e2e/
│       ├── __init__.py
│       └── test_excel_output.py
└── output/
```

---

## 6. Remedial Actions (Execution Order)

Each action below is a self-contained prompt that should be executed sequentially. Later actions depend on earlier ones.

---

### Action 1: Create Project Documentation

**Prompt:**
> Create a `README.md` in the repository root for the `chesscom` project. It should include: a project description (tools for managing a Chess.com club — generating member reports, match participation reports, prospect lists, and match eligibility reports), prerequisites (Python 3.10+, a Chess.com club), setup instructions (clone, create venv, install dependencies, copy `.env.template` to `.env` and configure), usage instructions showing how to run each of the four scripts with a brief description of what each produces, and a section on environment variables referencing the `.env.template`. Also fix the `.env.template` — replace the stale reference to `club_member_data.py` with the correct current filenames (`club_contribution_report.py` and `generate_club_member_report.py`). Use clean Markdown formatting.

---

### Action 2: Pin Dependency Versions and Migrate to `pyproject.toml`

**Prompt:**
> Replace `requirements.txt` with a `pyproject.toml` using a `[project]` table (PEP 621). Pin all current dependencies to their currently installed major.minor versions (run `pip freeze` to determine versions). Add `[project.optional-dependencies]` with a `dev` group containing `pytest`, `pytest-cov`, `responses` (for HTTP mocking), and `ruff` (for linting). Include `[tool.ruff]` and `[tool.pytest.ini_options]` configuration sections. Set the project name to `chesscom`, version `0.1.0`, and require Python `>=3.10`. Remove the old `requirements.txt` file.

---

### Action 3: Create Test Infrastructure and Pin Current Behaviour

**Prompt:**
> Create the test directory structure: `tests/__init__.py`, `tests/conftest.py`, `tests/unit/__init__.py`, `tests/unit/test_calculations.py`, `tests/integration/__init__.py`, `tests/integration/test_api_calls.py`.
>
> In `tests/conftest.py`, create pytest fixtures that provide sample JSON responses mimicking the Chess.com API for: club members endpoint (with weekly/monthly/all_time arrays), player stats endpoint (with chess_daily and chess960_daily), player profile endpoint, club matches endpoint, and single match endpoint. Use the `responses` library to mock HTTP calls.
>
> In `tests/unit/test_calculations.py`, write tests for `calculate_participation_percentage` and `calculate_win_rate` from `club_contribution_report.py` — cover zero-division, normal cases, edge cases (all wins, all losses, all draws).
>
> In `tests/unit/test_calculations.py`, also write tests for `get_unique_filename` from `utils` — mock `os.path.exists` to test the counter-incrementing logic.
>
> In `tests/integration/test_api_calls.py`, use the `responses` library to mock HTTP and write tests for: `get_all_club_members` (verifies weekly+monthly+all_time merge), `get_match_data` (verifies correct team identification when club is team1 vs team2), `get_match_participants` (verifies lowercase normalisation), `get_eligible_members` (verifies rating filtering). Import these from their current modules.
>
> Ensure all tests pass with `pytest -v`.

---

### Action 4: Fix `utils/__init__.py` — Remove Side Effects and Dead Code

**Prompt:**
> Refactor `src/utils/__init__.py` with the following changes:
>
> 1. Remove the `install_requirements()` function — it is dead code, never called.
> 2. Move `load_dotenv()` out of module-level scope. Instead, create a function `init()` that calls `load_dotenv()` and is explicitly called from each script's `__main__` block.
> 3. Remove `disable_system_sleep()` and `enable_system_sleep()` — these are dangerous system-level operations. Remove their calls from the `calculate_execution_time` decorator.
> 4. Fix `print_line()` — change `\n\r` to `\r\n` or simply remove the function and use standard `print()` everywhere. If keeping it, add a note that it exists for terminal compatibility.
> 5. Fix `get_unique_filename()` — replace the mixed string concatenation and `os.path.join` with consistent `os.path.join` usage throughout. Replace the nested f-string with a clean variable assignment.
> 6. Fix `calculate_execution_time` — log the exception but re-raise it instead of silently returning `None`.
> 7. Update each script's `__main__` block to call `utils.init()` before any env var access.
>
> Run the existing tests after changes to verify nothing breaks.

---

### Action 5: Create a Centralised API Client

**Prompt:**
> Create `src/chesscom/` as a proper Python package. Create `src/chesscom/__init__.py` and `src/chesscom/api/__init__.py`.
>
> Create `src/chesscom/api/client.py` containing a `ChessComClient` class that:
> - Accepts `base_url` (default: `https://api.chess.com/pub`) and `headers` in its constructor
> - Has a private `_get(endpoint)` method wrapping the retry logic currently in `utils.request_handler`
> - Exposes these public methods, each returning parsed JSON dicts or domain-appropriate Python types:
>   - `get_club_members(club_ref) -> list[dict]` — merges weekly/monthly/all_time
>   - `get_player_stats(username) -> dict`
>   - `get_player_profile(username) -> dict`
>   - `get_club_matches(club_ref) -> list[dict]`
>   - `get_match(match_id_or_url) -> dict`
>
> This class must be the **single point of API access** for the entire codebase. All existing direct HTTP calls in the four scripts and `utils` should eventually route through this client.
>
> Write tests in `tests/integration/test_chess_com_client.py` using the `responses` library to verify each method. Ensure all tests pass.

---

### Action 6: Extract Domain Models

**Prompt:**
> Create `src/chesscom/domain/__init__.py` and `src/chesscom/domain/models.py`.
>
> Define the following `@dataclass` classes:
> - `Member`: username, name, fide_title, daily_rating (int | None), chess960_rating (int | None), timeout_percent (float), joined_chess_com (datetime), last_online (datetime), joined_club (datetime | None)
> - `MatchResult`: username, result_white (str), result_black (str)
> - `Match`: match_id, name, url, start_time (datetime), max_rating (int | None), variant (str), participants (list[MatchResult])
> - `MemberParticipation`: username, daily_rating, matches_played (int), matches_participated (int), wins (int), losses (int), draws (int), timeouts (int), participation_pct (float), win_rate_pct (float)
>
> Add a factory classmethod `from_api_response` on `Member` and `Match` that constructs the dataclass from the raw API JSON dicts. This decouples the API response shape from the domain model.
>
> Write unit tests in `tests/unit/test_models.py` for the factory methods, covering happy paths and missing/malformed data.

---

### Action 7: Extract Business Logic into a Services Layer

**Prompt:**
> Create `src/chesscom/domain/services.py` containing pure functions (no I/O, no HTTP):
>
> - `calculate_participation_percentage(total_matches: int, participated: int) -> float`
> - `calculate_win_rate(wins: int, losses: int, draws: int) -> float`
> - `filter_members_by_rating(members: list[Member], max_rating: int, variant: str) -> list[Member]`
> - `exclude_members(all_members: list[Member], exclusion_set: set[str]) -> list[Member]`
> - `deduplicate_members(members: list[Member]) -> list[Member]`
> - `classify_result(result: str) -> Literal['win', 'loss', 'draw', 'timeout', 'unknown']`
> - `build_participation_stats(member: Member, matches: list[Match]) -> MemberParticipation`
>
> Migrate the logic currently in `club_contribution_report.py` (`calculate_participation_percentage`, `calculate_win_rate`, result classification), `generate_prospect_data.py` (exclusion filtering, deduplication), and `match_strengthening_extract.py` (rating filtering by variant) into these functions.
>
> Write comprehensive unit tests in `tests/unit/test_services.py`. These are pure functions so tests require no mocking — just input/output assertions. Cover edge cases: zero division, empty lists, unknown result strings, members with `None` ratings.

---

### Action 8: Extract Excel Export Module

**Prompt:**
> Create `src/chesscom/export/__init__.py` and `src/chesscom/export/excel.py`.
>
> Create a class `ExcelReportWriter` that:
> - Accepts a file path and a list of sheet configurations (sheet name, DataFrame, optional column hyperlink config)
> - Has a `write()` method that creates the Excel file using `openpyxl` as the engine
> - Handles hyperlink injection generically (given a column name and a URL template, apply hyperlinks)
> - Uses `get_unique_filename` logic to avoid overwrites
>
> This consolidates the duplicated Excel export code from `club_contribution_report.py` (xlsxwriter-based) and `match_strengthening_extract.py` (openpyxl-based) into a single consistent implementation.
>
> Write tests that verify: file creation, sheet naming, hyperlink injection, unique filename generation. Use temporary directories.

---

### Action 9: Create Centralised Configuration

**Prompt:**
> Create `src/chesscom/config.py` with a `@dataclass` called `AppConfig`:
> - `club_ref: str`
> - `club_name: str`
> - `data_analysis_year: int | None`
> - `match_id: str | None`
> - `prospect_clubs: list[str]`
> - `exclusion_club: str | None`
>
> Add a classmethod `from_env()` that reads from environment variables (using `os.getenv`) and validates that required fields are present. Raise `ValueError` with a clear message for missing required config.
>
> Replace all scattered `os.getenv()` calls in the four scripts with a single `AppConfig.from_env()` call. Pass config as a parameter to functions that need it — do not access globals.
>
> Write unit tests for `AppConfig.from_env()` using `monkeypatch` to set/unset env vars, verifying both happy path and validation errors.

---

### Action 10: Refactor Scripts into Report Classes

**Prompt:**
> Create `src/chesscom/reports/` with `__init__.py` and `base.py`.
>
> In `base.py`, define an abstract class `BaseReport` with:
> - Constructor accepting `ChessComClient` and `AppConfig`
> - Abstract method `collect_data() -> list[dict]`
> - Abstract method `get_report_name() -> str`
> - Concrete method `run()` that calls `collect_data()`, creates an `ExcelReportWriter`, and exports
>
> Create four concrete report classes, one per file:
> - `src/chesscom/reports/match_participation.py` → `MatchParticipationReport` (from `club_contribution_report.py`)
> - `src/chesscom/reports/member_summary.py` → `MemberSummaryReport` (from `generate_club_member_report.py`)
> - `src/chesscom/reports/prospect.py` → `ProspectReport` (from `generate_prospect_data.py`)
> - `src/chesscom/reports/match_eligibility.py` → `MatchEligibilityReport` (from `match_strengthening_extract.py`)
>
> Each report class should use `ChessComClient` for data access, domain `services` for logic, and `ExcelReportWriter` for output. No direct HTTP calls or raw `requests` usage in report classes.

---

### Action 11: Create CLI Entry Point

**Prompt:**
> Create `src/chesscom/cli.py` as the single entry point. Use `argparse` to provide subcommands:
> - `python -m chesscom match-participation` — runs `MatchParticipationReport`
> - `python -m chesscom member-summary` — runs `MemberSummaryReport`
> - `python -m chesscom prospects` — runs `ProspectReport`
> - `python -m chesscom match-eligibility` — runs `MatchEligibilityReport` (with optional `--match-id` argument)
>
> Create `src/chesscom/__main__.py` to enable `python -m chesscom` invocation.
>
> Each subcommand should: load config via `AppConfig.from_env()`, instantiate `ChessComClient`, instantiate the appropriate report, and call `report.run()`. Wrap in timing decorator.
>
> Remove the four old scripts from `src/` (`club_contribution_report.py`, `generate_club_member_report.py`, `generate_prospect_data.py`, `match_strengthening_extract.py`) and remove the old `src/utils/` package.

---

### Action 12: Fix GitHub Actions Workflow

**Prompt:**
> Replace `.github/workflows/main.yml` with a proper CI pipeline in `.github/workflows/ci.yml`:
> - Trigger on push and pull_request to `master`
> - Use a matrix strategy for Python 3.10 and 3.12
> - Steps: checkout, setup Python, install project with dev dependencies (`pip install -e ".[dev]"`), run `ruff check src/ tests/`, run `pytest --cov=src/chesscom --cov-report=term-missing`
> - Remove the broken AI Reviewer step or fix its secret references to use `${{ secrets.OPENAI_API_TOKEN }}` syntax
>
> Delete the old `main.yml`.

---

### Action 13: Update All Documentation

**Prompt:**
> Update the following documentation to reflect the completed refactoring:
>
> 1. **`README.md`** — Update usage instructions to show the new CLI interface (`python -m chesscom <subcommand>`). Document the new project structure. Add a "Development" section explaining how to run tests and linting.
> 2. **`.env.template`** — Update comments to reference the new CLI subcommands instead of old script filenames.
> 3. **`DESIGN-REVIEW.md`** — Add a "Resolution Status" section at the bottom tracking which actions have been completed.
> 4. Add docstrings to every public class and function in the new `src/chesscom/` package following Google-style docstring conventions.
> 5. Review and update `.vscode/settings.json` — remove deprecated `python.linting.*` settings (these moved to dedicated extensions in modern VS Code) and replace `python.formatting.provider` with a ruff formatter configuration.

---

## 7. Summary of Gaps

| Category | Count | Severity |
|---|---|---|
| Missing tests | 0 test files, ~20+ tests needed | **Critical** |
| Code duplication | ~5 patterns duplicated across 2–4 files | **High** |
| SOLID violations | 4 of 5 principles violated | **High** |
| Missing documentation | No README, stale .env.template | **High** |
| Security/safety | `sudo` system calls in utility code | **Medium** |
| Build reproducibility | Unpinned dependencies | **Medium** |
| Broken CI | GitHub Actions syntax error | **Medium** |
| Naming confusion | 4 of 4 scripts poorly named | **Low** |
| Inconsistent patterns | Mixed HTTP handling, mixed config loading | **Low** |

---

## 8. Prioritised Quick Wins (Can Be Done Immediately)

1. **Fix `.env.template` stale references** — 2 minutes
2. **Pin dependency versions** — 5 minutes
3. **Fix GitHub Actions `{{ }}` → `${{ }}`** — 2 minutes
4. **Remove `install_requirements()` dead code** — 1 minute
5. **Fix `\n\r` → standard `print()`** — 5 minutes
6. **Write tests for pure functions** (`calculate_participation_percentage`, `calculate_win_rate`) — 15 minutes

---

*This review recommends executing the 13 remedial actions in order. Actions 1–3 are preparatory (docs, deps, tests). Actions 4–10 are the core refactoring. Actions 11–13 are integration and finalisation. Do not skip Action 3 — tests must exist before refactoring begins.*

---

## 9. Resolution Status

All 13 remedial actions have been completed. The table below maps each action to
its corresponding pull request and the test count at the time of merge.

| Action | Title | PR | Tests at merge |
|---|---|---|---|
| 1 | Add README and pyproject.toml | [#2](https://github.com/ldastey-dev/chesscom/pull/2) | — |
| 2 | Pin dependencies in pyproject.toml | [#3](https://github.com/ldastey-dev/chesscom/pull/3) | — |
| 3 | Add initial test suite | [#4](https://github.com/ldastey-dev/chesscom/pull/4) | 27 |
| 4 | Add GitHub Actions CI workflow | [#5](https://github.com/ldastey-dev/chesscom/pull/5) | 27 |
| 5 | Extract shared utilities | [#6](https://github.com/ldastey-dev/chesscom/pull/6) | 27 |
| 6 | Add ChessComClient API wrapper | [#7](https://github.com/ldastey-dev/chesscom/pull/7) | 56 |
| 7 | Add domain models | [#8](https://github.com/ldastey-dev/chesscom/pull/8) / [#9](https://github.com/ldastey-dev/chesscom/pull/9) | 163 |
| 8 | Add ExcelReportWriter | [#10](https://github.com/ldastey-dev/chesscom/pull/10) | 185 |
| 9 | Add AppConfig | [#11](https://github.com/ldastey-dev/chesscom/pull/11) | 214 |
| 10 | Add report classes (BaseReport + 4 concrete reports) | [#12](https://github.com/ldastey-dev/chesscom/pull/12) | 255 |
| 11 | Add CLI entry point; remove legacy scripts | [#13](https://github.com/ldastey-dev/chesscom/pull/13) | 240 |
| 12 | Fix GitHub Actions workflow | Completed as part of Actions 4 & 11 | 240 |
| 13 | Update all documentation | [#14](https://github.com/ldastey-dev/chesscom/pull/14) | 240 |

### Final state (post Action 13)

- **240 tests** passing across Python 3.11 and 3.12
- **ruff** clean (0 errors)
- All legacy scripts removed; single `python -m chesscom <subcommand>` entry point
- Full Google-style docstrings on every public class and function
- README, `.env.template`, and `.vscode/settings.json` reflect the current codebase
