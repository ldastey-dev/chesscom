# chesscom

Python tools for managing a Chess.com club. Generates Excel reports covering member statistics, match participation, prospect identification, and match eligibility.

---

## Reports

| Script | Description |
|---|---|
| `club_contribution_report.py` | Generates a match participation report showing each member's win rate, timeout rate, and participation percentage across all club matches in a given year. |
| `generate_club_member_report.py` | Generates a full club member summary with ratings, Chess960 ratings, FIDE titles, join dates, and last-online dates. |
| `generate_prospect_data.py` | Generates a prospect list by aggregating members from a set of target clubs and excluding current club members. |
| `match_strengthening_extract.py` | Generates a match eligibility report listing club members who meet the rating threshold for a specific upcoming match, including sign-up status. |

---

## Prerequisites

- Python 3.10 or higher
- A [Chess.com](https://www.chess.com) club (you must have access to your club reference ID)
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

For development (includes `pytest`, `pytest-cov`, `responses`, `ruff`):

```bash
pip install -e ".[dev]"
```

### 4. Configure environment variables

Copy the template and fill in your values:

```bash
cp .env.template .env
```

Open `.env` and set each variable — see the [Environment Variables](#environment-variables) section below.

---

## Usage

All scripts are run from the `src/` directory.

```bash
cd src
```

### Club Member Summary

Produces an Excel file (`output/Club Member Summary Report.xlsx`) with one row per club member containing their rating, Chess960 rating, FIDE title, join date, and last-online date.

```bash
python generate_club_member_report.py
```

**Required env vars:** `CLUB_REF`

---

### Match Participation Report

Produces an Excel file (`output/<Club Name> Club Contribution Report <Year>.xlsx`) with two sheets: member metrics (participation %, win rate, timeout count) and a match-by-match breakdown.

```bash
python club_contribution_report.py
```

**Required env vars:** `CLUB_REF`, `CLUB_NAME`, `DATA_ANALYSIS_YEAR`

---

### Prospect Report

Produces an Excel file (`output/Member Prospects.xlsx`) listing players from specified clubs who are not already members of your club.

```bash
python generate_prospect_data.py
```

**Required env vars:** `LIST_OF_CLUBS` (comma-separated)

---

### Match Eligibility Report

Produces an Excel file (`output/Match Eligibility <match name>.xlsx`) listing club members who are eligible for a specific match based on its rating cap and chess variant, showing whether each member has already signed up.

```bash
python match_strengthening_extract.py
```

**Required env vars:** `CLUB_REF`, `CLUB_NAME`

`MATCH_ID` is optional — if not set, the script will prompt for it at runtime.

---

## Environment Variables

Copy `.env.template` to `.env` and populate the following variables:

| Variable | Required By | Description |
|---|---|---|
| `CLUB_REF` | `generate_club_member_report.py`, `club_contribution_report.py`, `match_strengthening_extract.py` | Your club's Chess.com URL slug (e.g. `team-scotland`) |
| `CLUB_NAME` | `club_contribution_report.py`, `match_strengthening_extract.py` | Your club's display name as it appears on Chess.com (e.g. `Team Scotland`) |
| `DATA_ANALYSIS_YEAR` | `club_contribution_report.py` | The year to analyse match participation for (e.g. `2025`) |
| `MATCH_ID` | `match_strengthening_extract.py` | The numeric Chess.com match ID (optional — prompted at runtime if absent) |
| `LIST_OF_CLUBS` | `generate_prospect_data.py` | Comma-separated list of club slugs to source prospects from |

---

## Output

All generated Excel files are written to the `output/` directory. The directory is created automatically if it does not exist. Filenames are unique — if a file with the same name already exists, an incrementing counter suffix is appended (e.g. `report_1.xlsx`, `report_2.xlsx`) to prevent overwriting local edits.

The `output/` directory is excluded from version control via `.gitignore`.

---

## Project Structure

```
chesscom/
├── .env.template          # Environment variable template
├── pyproject.toml         # Python dependencies and tooling configuration
├── src/
│   ├── club_contribution_report.py
│   ├── generate_club_member_report.py
│   ├── generate_prospect_data.py
│   ├── match_strengthening_extract.py
│   └── utils/
│       └── __init__.py    # Shared HTTP, file, and timing utilities
└── output/                # Generated Excel reports (git-ignored)
```

---

## Notes

- The Chess.com public API is rate-limited. Scripts include automatic retry logic with exponential backoff for transient failures.
- Scripts use a Chrome browser `User-Agent` header to ensure compatibility with the Chess.com API.
- Long-running scripts prevent the system from sleeping for the duration of execution (Windows and Linux supported).
