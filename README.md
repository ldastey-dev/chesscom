# chesscom

Python tools for managing a Chess.com club. Generates Excel reports covering
member statistics, match participation, prospect identification, match
eligibility, and timeout monitoring.

[![CI](https://github.com/ldastey-dev/chesscom/actions/workflows/ci.yml/badge.svg)](https://github.com/ldastey-dev/chesscom/actions/workflows/ci.yml)

---

## Reports

| Subcommand | Output file | Description |
|---|---|---|
| `member-summary` | `Club Member Summary Report.xlsx` | Roster of all club members with ratings, Chess960 ratings, FIDE titles, join dates, and last-online dates. |
| `match-participation` | `<Club> Club Contribution Report <Year>.xlsx` | Two-sheet workbook: per-member win rate, timeout rate, and participation %; plus a match-by-match breakdown. |
| `prospects` | `Member Prospects.xlsx` | De-duplicated prospect list sourced from one or more target clubs, with current members excluded. |
| `match-eligibility` | `Match Eligibility.xlsx` | Club members eligible for a specific match (within its rating cap), showing sign-up status. |
| `timeout-check` | `Timeout Check Report.xlsx` | Two-sheet workbook: timeout alerts grouped by match; player timeout summary. Also prints a concise summary to stdout. |

---

## Prerequisites

- Python 3.11 or higher
- A [Chess.com](https://www.chess.com) club (you must have access to your club's URL slug)
- `git`

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/ldastey-dev/chesscom.git
cd chesscom
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -e .
```

### 4. Configure environment variables

```bash
cp .env.template .env
```

Open `.env` and fill in your values — see [Environment Variables](#environment-variables) below.

---

## Usage

All subcommands read configuration from environment variables (`.env` file) **and**
CLI arguments. CLI arguments take precedence over environment variables when both
are provided.

### Common flags (available on all subcommands)

| Flag | Overrides | Description |
|---|---|---|
| `--club-ref SLUG` | `CLUB_REF` | Club URL slug for API paths |
| `--club-name NAME` | `CLUB_NAME` | Club display name |

---

### Club Member Summary

```bash
# Using .env (CLUB_REF and CLUB_NAME set):
python -m chesscom member-summary

# Using CLI args only:
python -m chesscom member-summary --club-ref team-scotland --club-name "Team Scotland"
```

**Required:** `CLUB_REF`, `CLUB_NAME`

---

### Match Participation Report

```bash
# Using .env (CLUB_REF, CLUB_NAME, DATA_ANALYSIS_YEAR set):
python -m chesscom match-participation

# Using CLI args:
python -m chesscom match-participation --club-ref team-scotland --club-name "Team Scotland" --year 2025

# Mixed — override year only:
python -m chesscom match-participation --year 2025
```

**Required:** `CLUB_REF`, `CLUB_NAME`, `DATA_ANALYSIS_YEAR` (or `--year`)

---

### Prospect Report

```bash
# Using .env (LIST_OF_CLUBS set):
python -m chesscom prospects

# Using CLI args:
python -m chesscom prospects --clubs team-ireland team-england --exclusion-club team-scotland

# Mixed — override exclusion club only:
python -m chesscom prospects --exclusion-club team-scotland
```

**Required:** `LIST_OF_CLUBS` (or `--clubs`)  
**Optional:** `EXCLUSION_CLUB` (or `--exclusion-club`)

---

### Match Eligibility Report

```bash
# Using .env (MATCH_ID set):
python -m chesscom match-eligibility

# Using CLI args:
python -m chesscom match-eligibility --match-id 12345

# Mixed — override match ID only:
python -m chesscom match-eligibility --match-id 67890
```

**Required:** `CLUB_REF`, `CLUB_NAME`, `MATCH_ID` (or `--match-id`)

---

### Timeout Check

```bash
# Using .env (TIMEOUT_MATCH_IDS set):
python -m chesscom timeout-check

# Using CLI args — specific matches:
python -m chesscom timeout-check 12345 67890

# Check all in-progress matches:
python -m chesscom timeout-check all

# Custom threshold (flag overrides TIMEOUT_THRESHOLD_HOURS):
python -m chesscom timeout-check all --threshold 24

# Full CLI args (no .env needed):
python -m chesscom timeout-check all \
  --club-ref team-scotland \
  --club-name "Team Scotland" \
  --threshold 10
```

**Required:** `CLUB_REF`, `CLUB_NAME`, plus match IDs via CLI or `TIMEOUT_MATCH_IDS`  
**Optional:** `TIMEOUT_THRESHOLD_HOURS` (or `--threshold`; default: 5 hours)

**Output:**
- **stdout** — concise per-match summary with flagged player counts
- **xlsx** — Tab 1: alerts grouped by match; Tab 2: player timeout counts (descending)

---

### Help

```bash
python -m chesscom --help
python -m chesscom timeout-check --help
```

---

## Environment Variables

Copy `.env.template` to `.env` and populate:

| Variable | Required by | Description |
|---|---|---|
| `CLUB_REF` | `member-summary`, `match-participation`, `match-eligibility`, `timeout-check` | Club URL slug, e.g. `team-scotland` |
| `CLUB_NAME` | `member-summary`, `match-participation`, `match-eligibility`, `timeout-check` | Display name, e.g. `Team Scotland` |
| `DATA_ANALYSIS_YEAR` | `match-participation` | Four-digit year to analyse, e.g. `2025` |
| `MATCH_ID` | `match-eligibility` | Chess.com match ID (also accepted via `--match-id`) |
| `LIST_OF_CLUBS` | `prospects` | Comma-separated club slugs to source prospects from |
| `EXCLUSION_CLUB` | `prospects` | Club slug whose members are excluded from the prospect list |
| `TIMEOUT_MATCH_IDS` | `timeout-check` | Comma-separated match IDs, or `all` for every in-progress match |
| `TIMEOUT_THRESHOLD_HOURS` | `timeout-check` | Hours remaining below which a game is flagged as at risk (default: `5`) |

All variables can also be supplied (or overridden) via CLI flags. Run any subcommand
with `--help` to see available options.

---

## Output

All Excel files are written to the `output/` directory (created automatically).
Filenames are unique — if a file already exists an incrementing counter suffix
is appended (`report_1.xlsx`, `report_2.xlsx`, …) to avoid overwriting
previous output.

The `output/` directory is excluded from version control.

---

## Project Structure

```
chesscom/
├── .env.template               # Environment variable template
├── pyproject.toml              # Dependencies and tooling configuration
├── src/
│   └── chesscom/
│       ├── __init__.py
│       ├── __main__.py         # Enables `python -m chesscom`
│       ├── cli.py              # argparse entry point (build_parser / main)
│       ├── config.py           # AppConfig dataclass + from_env()
│       ├── api/
│       │   └── client.py       # ChessComClient — all HTTP calls
│       ├── domain/
│       │   ├── models.py       # Member, Match, MatchResult, MemberParticipation, TimeoutAlert
│       │   └── services.py     # Pure calculation and filtering functions
│       ├── export/
│       │   └── excel.py        # ExcelReportWriter + SheetConfig
│       └── reports/
│           ├── base.py         # BaseReport ABC
│           ├── match_eligibility.py
│           ├── match_participation.py
│           ├── member_summary.py
│           ├── prospect.py
│           └── timeout_check.py
├── tests/
│   ├── integration/            # Live-API tests (require network)
│   └── unit/                   # Fast, dependency-free unit tests
└── output/                     # Generated Excel reports (git-ignored)
```

---

## Development

### Install dev dependencies

```bash
pip install -e ".[dev]"
```

### Run tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=src --cov-report=term-missing
```

### Lint

```bash
ruff check .
```

Auto-fix lint issues:

```bash
ruff check --fix .
```

### Format

```bash
ruff format .
```

### CI

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push and
pull request to `master`. It runs `ruff check` and `pytest --cov` against
Python 3.11 and 3.12, enforcing a minimum 90% test coverage threshold.

---

## Notes

- The Chess.com public API is rate-limited. Requests are retried automatically
  with exponential back-off on transient failures.
- A Chrome browser `User-Agent` header is used to ensure compatibility with
  the Chess.com API.
- The `timeout-check` command will warn if any boards could not be checked due
  to API errors.
