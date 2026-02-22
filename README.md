# chesscom

Python tools for managing a Chess.com club. Generates Excel reports covering
member statistics, match participation, prospect identification, and match
eligibility.

[![CI](https://github.com/ldastey-dev/chesscom/actions/workflows/ci.yml/badge.svg)](https://github.com/ldastey-dev/chesscom/actions/workflows/ci.yml)

---

## Reports

| Subcommand | Output file | Description |
|---|---|---|
| `member-summary` | `Club Member Summary Report.xlsx` | Roster of all club members with ratings, Chess960 ratings, FIDE titles, join dates, and last-online dates. |
| `match-participation` | `<Club> Club Contribution Report <Year>.xlsx` | Two-sheet workbook: per-member win rate, timeout rate, and participation %; plus a match-by-match breakdown. |
| `prospects` | `Member Prospects.xlsx` | De-duplicated prospect list sourced from one or more target clubs, with current members excluded. |
| `match-eligibility` | `Match Eligibility <match name>.xlsx` | Club members eligible for a specific match (within its rating cap), showing sign-up status. |

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

All subcommands read configuration from environment variables (or a `.env` file
in the project root).

### Club Member Summary

```bash
python -m chesscom member-summary
```

**Required:** `CLUB_REF`, `CLUB_NAME`

---

### Match Participation Report

```bash
python -m chesscom match-participation
```

**Required:** `CLUB_REF`, `CLUB_NAME`, `DATA_ANALYSIS_YEAR`

---

### Prospect Report

```bash
python -m chesscom prospects
```

**Required:** `LIST_OF_CLUBS`  
**Optional:** `EXCLUSION_CLUB`

---

### Match Eligibility Report

```bash
# Match ID from MATCH_ID env var:
python -m chesscom match-eligibility

# Or supply it directly:
python -m chesscom match-eligibility --match-id 12345
```

**Required:** `CLUB_REF`, `CLUB_NAME`  
**Optional:** `MATCH_ID` (can also be passed via `--match-id`)

---

### Help

```bash
python -m chesscom --help
python -m chesscom match-eligibility --help
```

---

## Environment Variables

Copy `.env.template` to `.env` and populate:

| Variable | Required by | Description |
|---|---|---|
| `CLUB_REF` | `member-summary`, `match-participation`, `match-eligibility` | Club URL slug, e.g. `team-scotland` |
| `CLUB_NAME` | `member-summary`, `match-participation`, `match-eligibility` | Display name, e.g. `Team Scotland` |
| `DATA_ANALYSIS_YEAR` | `match-participation` | Four-digit year to analyse, e.g. `2025` |
| `MATCH_ID` | `match-eligibility` | Chess.com match ID (optional — also accepted via `--match-id`) |
| `LIST_OF_CLUBS` | `prospects` | Comma-separated club slugs to source prospects from |
| `EXCLUSION_CLUB` | `prospects` | Optional club slug whose members are excluded from the prospect list |

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
│       │   ├── models.py       # Member, Match, MatchResult, MemberParticipation
│       │   └── services.py     # Pure calculation and filtering functions
│       ├── export/
│       │   └── excel.py        # ExcelReportWriter + SheetConfig
│       └── reports/
│           ├── base.py         # BaseReport ABC
│           ├── match_eligibility.py
│           ├── match_participation.py
│           ├── member_summary.py
│           └── prospect.py
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

### CI

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push and
pull request to `master`. It runs `ruff check` and `pytest --cov` against
Python 3.11 and 3.12.

---

## Notes

- The Chess.com public API is rate-limited. Requests are retried automatically
  with exponential back-off on transient failures.
- A Chrome browser `User-Agent` header is used to ensure compatibility with
  the Chess.com API.
