# CLAUDE.md

Read and apply `AGENTS.md` for project conventions and workflow rules.

## Context System

Before starting any task, read `.context/index.md` and load files matching the current task's domain. Standards, playbooks, and conventions are all available on demand.

## Skills (Claude Code)

Assessment, review, planning, and refactoring playbooks are available as Claude Code skills. Type `/` to see all available commands, or describe your task and the relevant skill will be suggested.

---

## Project-Specific Rules

- **British English** in all written output (docs, comments, commit messages) — see `.context/conventions/communication.md`.
- **Plan mode for non-trivial tasks** — if a task has 3+ steps or architectural impact, write a plan to `tasks/todo.md` before implementing. See `.context/conventions/workflow.md`.
- **No type-checker or security-audit tool** — `mypy` and `bandit` are not configured. Do not assume they exist or add them without discussion.
- **Chess.com API domain knowledge** — the public API (`api.chess.com/pub`) is unauthenticated. All endpoint methods live in `ChessComClient`. The Chrome `User-Agent` header is required and must not be removed.
- **Four report types only** — `member-summary`, `match-participation`, `prospects`, `match-eligibility`. New report types must follow the `BaseReport` subclass pattern and be registered in `cli.py`.
- **Environment variables drive all configuration** — every setting is in `.env.template`. New settings must be added to `AppConfig` in `config.py` first; never use `os.getenv()` directly.
- **Verify tests pass before marking work complete** — run `pytest` after any behaviour change.
