# AGENTS.md

> Single source of truth for all coding standards, architecture decisions, and
> workflow conventions. Read by Devin, Cursor, Windsurf, GitHub Copilot, and
> other coding agents.

## Project Overview

A Python CLI tool for Chess.com club administrators. It fetches data from the
Chess.com public API and generates Excel workbooks covering four report types:
club member summaries, match participation analysis, prospect identification,
and match eligibility checking. Club admins use it to manage rosters, track
member contributions, and identify new member candidates — delivering the kind
of structured reporting that the Chess.com UI does not provide out of the box.

---

## Tech Stack

- **Language:** Python 3.11+
- **CLI:** `argparse` (stdlib)
- **Data:** `pandas ~3.0`, `numpy ~2.4`
- **Excel output:** `openpyxl ~3.1`
- **HTTP:** `requests ~2.32` (with exponential back-off retry)
- **Config:** `python-dotenv ~1.2` (`.env` file loader)
- **Testing:** `pytest ~9.0`, `pytest-cov ~7.0`, `responses ~0.26` (HTTP mocking)
- **Linting / Formatting:** `ruff ~0.15` (lint, format, isort)
- **Package Manager:** `pip` with `pyproject.toml`
- **Database:** None — all data fetched from the Chess.com public API at runtime

---

## Commands

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=term-missing

# Lint
ruff check .

# Auto-fix lint issues
ruff check --fix .

# Format
ruff format .

# Build / install (production)
pip install -e .
```

> There is no type-checker or security-audit tool configured. Do not assume
> `mypy`, `bandit`, or similar tools are available.

---

## Architecture

- **Style:** Clean/Layered (four layers — see below)
- **Deployment:** Local CLI tool; run manually or in a scheduled script
- **Service boundaries:** Single Python package; no microservices or network services

### Dependency Direction

Dependencies point inward. This is non-negotiable.

```text
Presentation   cli.py, __main__.py
    ↓
Application    reports/*.py  (BaseReport ABC + 4 concrete reports)
    ↓
Domain         domain/models.py, domain/services.py
    ↓
Infrastructure api/client.py, export/excel.py, config.py
```

### Key Design Decisions

1. **Centralised config** — all `os.getenv()` calls live exclusively in
   `AppConfig.from_env()` (`config.py`). No other module reads env vars
   directly.

2. **Single HTTP gateway** — `ChessComClient` (`api/client.py`) owns the
   Chess.com base URL, `User-Agent` header, and exponential back-off retry
   logic. All API calls must go through it.

3. **Domain isolation** — `Member`, `Match`, `MatchResult`, and
   `MemberParticipation` dataclasses in `domain/models.py` decouple raw
   Chess.com API JSON shapes from downstream business logic.

4. **Consistent report pipeline** — `BaseReport` ABC enforces the
   `collect_data() → build_sheet_configs() → ExcelReportWriter.write()`
   pipeline. Every report follows this contract.

5. **Safe output files** — `ExcelReportWriter` appends an incrementing
   counter suffix (`_1`, `_2`, …) if the target filename already exists,
   so previous reports are never silently overwritten.

6. **Pure domain logic** — functions in `domain/services.py` are
   side-effect-free (no I/O, no network). This makes them trivially
   unit-testable without mocking.

---

## Repository Structure

```text
chesscom/
├── .env.template                   # Environment variable template — copy to .env
├── .github/
│   ├── copilot-instructions.md     # GitHub Copilot instructions (defers here)
│   ├── dependabot.yml
│   ├── skills/                     # GitHub Copilot skills (assess, review, plan, refactor)
│   └── workflows/
│       └── ci.yml                  # CI: lint → test (py3.11 + py3.12) → coverage artifact
├── .claude/
│   └── skills/                     # Claude Code skills (mirrors .github/skills/)
├── .context/
│   ├── index.md                    # Context loader index — read before every task
│   ├── conventions/                # Code, workflow, and communication conventions
│   ├── playbooks/                  # Step-by-step procedures (assess/review/plan/refactor)
│   └── standards/                  # Domain standard references
├── pyproject.toml                  # Project metadata, dependencies, ruff config
├── src/
│   └── chesscom/
│       ├── __main__.py             # Entry point: `python -m chesscom`
│       ├── cli.py                  # argparse parser + subcommand handlers
│       ├── config.py               # AppConfig dataclass + from_env()
│       ├── api/
│       │   └── client.py           # ChessComClient — all HTTP calls
│       ├── domain/
│       │   ├── models.py           # Member, Match, MatchResult, MemberParticipation
│       │   └── services.py         # Pure calculation and filtering functions
│       ├── export/
│       │   └── excel.py            # ExcelReportWriter + SheetConfig
│       └── reports/
│           ├── base.py             # BaseReport ABC
│           ├── match_eligibility.py
│           ├── match_participation.py
│           ├── member_summary.py
│           └── prospect.py
├── tests/
│   ├── conftest.py
│   ├── integration/                # Live-API tests (require network access)
│   │   └── test_chess_com_client.py
│   └── unit/                       # Fast, dependency-free unit tests
│       ├── test_calculations.py
│       ├── test_cli.py
│       ├── test_config.py
│       ├── test_excel.py
│       ├── test_models.py
│       ├── test_reports.py
│       └── test_services.py
└── output/                         # Generated Excel reports (git-ignored)
```

---

## Code Conventions

### Naming

| Element | Convention | Example |
|---|---|---|
| Files | `snake_case.py` | `match_participation.py` |
| Classes | `PascalCase` | `ChessComClient`, `BaseReport` |
| Functions / methods | `snake_case` | `collect_data()`, `from_env()` |
| Private helpers | `_leading_underscore` | `_get()`, `_run_timed()` |
| Constants | `UPPER_SNAKE_CASE` | `BASE_URL`, `DEFAULT_HEADERS` |
| Output filenames | Defined per-report in `get_report_name()` | `Club Member Summary Report` |

### Patterns

- **Adding a report:** Subclass `BaseReport` in `src/chesscom/reports/`, implement
  `collect_data()` and `get_report_name()`, optionally override
  `build_sheet_configs()` for multi-sheet workbooks, then register the
  subcommand handler in `cli.py`.

- **Adding a config variable:** Add the field to `AppConfig` in `config.py` and
  parse it in `from_env()`. Never read env vars anywhere else.

- **Adding an API endpoint:** Add a method to `ChessComClient` in
  `api/client.py`. Route all HTTP calls through `_get()`.

- **Exporting data:** Instantiate `ExcelReportWriter` with one or more
  `SheetConfig` objects. Never write Excel files directly with openpyxl.

### Import Rules

| Layer | May import from | Must NOT import from |
|---|---|---|
| `cli.py` | `reports/`, `api/`, `config.py` | `domain/`, `export/` directly |
| `reports/` | `domain/`, `api/`, `export/`, `config.py` | `cli.py` |
| `domain/` | stdlib only | `api/`, `export/`, `reports/`, `cli.py` |
| `api/client.py` | stdlib, `requests` | `domain/`, `reports/`, `cli.py` |
| `export/excel.py` | stdlib, `pandas`, `openpyxl` | `api/`, `domain/`, `reports/`, `cli.py` |

No circular imports permitted.

---

## Context System

This repository uses on-demand context loading. Before starting any task, read `.context/index.md` and load files matching the current task's domain.

Available context types:

- **Standards** in `.context/standards/` — detailed reference for a specific concern (security, testing, performance, etc.)
- **Playbooks** in `.context/playbooks/` — step-by-step procedures for assessments, reviews, plans, and refactoring
- **Conventions** in `.context/conventions/` — workflow, communication, and coding style guidance

---

## Mandated Standards

The following standards are non-negotiable. Do not weaken them. Detailed guidance is in `.context/standards/`.

### Core Principles

- **Simplicity First:** Make every change as simple as possible. Impact minimal code.
- **No Laziness:** Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact:** Changes should only touch what's necessary. Avoid introducing bugs.
- **Security is Non-Negotiable:** Never log secrets, commit credentials, or introduce injection vectors.
- **Test What You Change:** If you modify behaviour, prove it works. If you refactor, prove nothing broke.
- **Evidence Over Opinion:** Reference specific code, config, or behaviour. No vague assertions.

### Standards Reference

| Standard | Key Rule | Detail |
| --- | --- | --- |
| Code Quality | SOLID, DRY, cyclomatic complexity < 10 | `.context/standards/code-quality.md` |
| Security | OWASP Top 10 compliance | `.context/standards/security.md` |
| Testing | >= 90% coverage, Test Trophy Model | `.context/standards/testing.md` |
| CI/CD | 7-stage pipeline, < 10 min full CI | `.context/standards/ci-cd.md` |
| Observability | OpenTelemetry, structured JSON logging | `.context/standards/observability.md` |
| Resilience | Circuit breakers, retries with backoff | `.context/standards/resilience.md` |
| Performance | No N+1, pagination, resource disposal | `.context/standards/performance.md` |
| Cost | Cache before network, FinOps principles | `.context/standards/cost-optimisation.md` |
| Operations | IaC, env vars, small focused PRs | `.context/standards/operational-excellence.md` |
| API Design | OpenAPI 3+, REST, RFC 7807 errors | `.context/standards/api-design.md` |
| AWS | 6 pillars: OpEx, Security, Reliability, Perf, Cost, Sustainability | `.context/standards/aws-well-architected.md` |
| GDPR | Lawful basis, data minimisation, subject rights | `.context/standards/gdpr.md` |
| PCI DSS | CDE scoping, AES-256, TLS 1.2+ | `.context/standards/pci-dss.md` |
| Accessibility | WCAG 2.2 AA, keyboard, ARIA, contrast | `.context/standards/accessibility.md` |
| Architecture | Clean Architecture, dependency direction, layer boundaries | `.context/standards/architecture.md` |
| IaC | State management, drift detection, container security | `.context/standards/iac.md` |
| Tech Debt | Debt taxonomy, impact scoring, paydown strategy | `.context/standards/tech-debt.md` |

---

## Project-Specific Rules

- **No `os.getenv()` outside `config.py`** — always read configuration through
  `AppConfig`. Violations break the single-source-of-truth pattern.

- **Integration tests require network access** — tests in `tests/integration/`
  make live calls to `api.chess.com`. Never run them in CI without a network.
  Unit tests in `tests/unit/` must be fully offline; use `responses` to mock
  HTTP, never `unittest.mock.patch` on `requests` directly.

- **Don't commit generated output** — the `output/` directory is git-ignored.
  Never add `.xlsx` files to version control.

- **`responses` for HTTP mocking** — the `responses` library is the approved
  way to stub the Chess.com API in tests. Do not use `unittest.mock` to patch
  `requests` directly.

- **Chess.com API is unauthenticated** — the public API requires no API key.
  The Chrome `User-Agent` header in `ChessComClient` is load-bearing; do not
  remove or change it without verifying compatibility.

- **Rate limiting** — the Chess.com API is rate-limited. The built-in
  exponential back-off in `ChessComClient._get()` handles transient failures;
  do not add additional `time.sleep()` calls around it.

- **Output uniqueness** — `ExcelReportWriter` auto-increments the filename
  suffix to avoid overwriting previous reports. Do not bypass this by
  hardcoding filenames or deleting files programmatically.
