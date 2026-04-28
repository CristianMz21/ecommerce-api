# Skill Registry — ecommerce-api

**Project**: ecommerce-api
**Generated**: 2026-04-27 (updated with autoskills)
**Persistence**: engram + local file

## Project-Level Skills

Located in `.agents/skills/`:

| Skill | Trigger | Path |
|-------|---------|------|
| `seo` | "improve SEO", "optimize search", "structured data" | `.agents/skills/seo/SKILL.md` |
| `accessibility` | "improve accessibility", "a11y audit", "WCAG" | `.agents/skills/accessibility/SKILL.md` |
| `frontend-design` | "build web components", "styling", "dashboard" | `.agents/skills/frontend-design/SKILL.md` |
| `django-expert` | Django models, views, DRF, ORM, migrations | `.agents/skills/django-expert/SKILL.md` |
| `django-patterns` | Django architecture, DRF API design, caching, signals | `.agents/skills/django-patterns/SKILL.md` |
| `django-security` | Django auth, CSRF, SQL injection, XSS, secure config | `.agents/skills/django-security/SKILL.md` |
| `python-executor` | Execute Python code in sandbox (inference.sh) | `.agents/skills/python-executor/SKILL.md` |
| `python-testing-patterns` | pytest, fixtures, mocking, TDD patterns | `.agents/skills/python-testing-patterns/SKILL.md` |

## SDD Workflow Skills

Located in `~/.config/opencode/skills/`:

| Command | Purpose |
|---------|---------|
| `/sdd-init` | Initialize SDD context |
| `/sdd-explore` | Investigate codebase |
| `/sdd-propose` | Create change proposal |
| `/sdd-spec` | Write specifications |
| `/sdd-design` | Technical design |
| `/sdd-tasks` | Break into tasks |
| `/sdd-apply` | Implement code |
| `/sdd-verify` | Validate against specs |
| `/sdd-archive` | Archive completed change |
| `/sdd-onboard` | Guided SDD walkthrough |

## Available Agents

| Agent | Description |
|-------|-------------|
| `sdd-orchestrator` | SDD workflow coordinator |
| `sdd-apply` | Implement code from tasks |
| `sdd-design` | Create technical design |
| `sdd-explore` | Investigate codebase |
| `sdd-propose` | Create change proposals |
| `sdd-spec` | Write specifications |
| `sdd-tasks` | Break down specs into tasks |
| `sdd-verify` | Validate implementation |
| `sdd-archive` | Archive completed changes |
| `backend-dev` | Django/DRF specialist |
| `db-dev` | Database/Django ORM specialist |
| `sec-auditor` | Security vulnerability scanner |

## OpenCode Configuration

| Component | Path |
|-----------|------|
| Project config | `.opencode/opencode.json` |
| **AGENTS.md** | `.opencode/AGENTS.md` |
| Architecture rules | `.opencode/rules/architecture.md` |
| Security rules | `.opencode/rules/security.md` |
| Quality rules | `.opencode/rules/quality_and_testing.md` |
| Django rules | `.opencode/rules/backend-django.md` |
| **Pre-commit config** | `.pre-commit-config.yaml` |
| **Env template** | `.env.example` |
| **Suppression checker** | `scripts/check_suppressions.py` (PROTECTED) |

## Quality Tools

| Tool | Config | Command |
|------|--------|---------|
| **check-suppressions** | `scripts/check_suppressions.py` | `python scripts/check_suppressions.py --strict` |
| ruff | `pyproject.toml` | `ruff check store/ ecommerce_api/` |
| ruff format | `pyproject.toml` | `ruff format store/ ecommerce_api/` |
| mypy | `pyproject.toml` | `mypy store/ ecommerce_api/` |
| pre-commit | `.pre-commit-config.yaml` | `pre-commit run --all-files` |
| pip-audit | `pyproject.toml` | `pip-audit` |

## Testing

- **Framework**: Django `APITestCase`
- **Command**: `python manage.py test store`
- **Location**: `store/tests.py`
- **Test count**: 28 tests

## Protected Files

| File | Reason |
|------|--------|
| `scripts/check_suppressions.py` | Enforces ZERO SUPPRESSIONS rule. Must never be modified. |
