# Benchmark Analysis: Plan Generation Quality

**Experiment**: basic-greenfield-plan-creation
**Date**: 2026-02-12
**Agents**: Claude Sonnet 4.5, Claude Opus 4.6, GPT-5
**Runs per agent**: 3
**Task**: Generate an implementation plan for a Todo CRUD API spec using `/speckit.plan`

---

## Executive Summary

Claude Opus 4.6 delivered the highest-quality plans with the most complete artifact generation (plan + research + data model + quickstart + 7 API contracts), excellent spec fidelity, and near-perfect consistency across all 3 runs. Claude Sonnet 4.5 produced comprehensive standalone plans with good spec coverage but did not generate the supporting Phase 0/1 artifacts (research.md, data-model.md, contracts/). GPT-5 was the least consistent agent, with one run (gpt-5-1) producing a fundamentally incorrect plan that used the wrong technology stack (Node.js/Express instead of Python/FastAPI) and was placed in the wrong file location; the other two runs were adequate but produced notably thinner artifacts than the other agents.

---

## Agent-by-Agent Analysis

### Claude Sonnet 4.5

**Runs analyzed**: sonnet-4.5-1, sonnet-4.5-2, sonnet-4.5-3

#### Completeness (7/10)

Sonnet 4.5 generated plan.md files in the correct `.specify/specs/001-todo-crud/` location in all 3 runs. The plans themselves are thorough and cover all spec requirements: all 7 API endpoints, all functional requirements (FR-001 through FR-012), the Todo data model with correct fields, validation rules, HTTP status codes, and performance targets. However, Sonnet 4.5 **only produced the plan.md file** -- it did not generate the supporting artifacts that the plan template workflow calls for (research.md, data-model.md, quickstart.md, contracts/ directory). The plan references these as future deliverables rather than creating them. This is a significant gap: the `/speckit.plan` command is expected to produce Phase 0 and Phase 1 outputs, not just the plan scaffold.

#### Accuracy (9/10)

All three plans correctly identify:
- Python 3.11+ with FastAPI, Pydantic v2, SQLite
- All 7 endpoints with correct HTTP methods and status codes
- The Todo entity with all 6 fields (id, title, description, completed, created_at, completed_at)
- UUID v4 for IDs, UTC timestamps, validation constraints (title 1-500 chars, description max 2000)
- TDD methodology with pytest + httpx
- Constitutional compliance (simplicity, type safety, code standards)

Minor variation: Run 3 included a separate `validation/` module in its project structure, slightly over-engineering beyond what the constitution's simplicity principle suggests. Run 1 proposed a 4-layer architecture (Routes -> Service -> Repository -> Database) while Run 2 had a slightly different module layout. These differences are within acceptable bounds.

#### Consistency (7/10)

The three plans share the same core content but differ meaningfully in structure and depth:
- **Line counts**: 291, 266, 403 lines (significant variance, 1.5x spread)
- **Run 1**: Most detailed with explicit layered architecture diagram, 4-layer pattern (routes/service/repository/database)
- **Run 2**: More concise, includes explicit `pyproject.toml` dependency listing and risk assessment table
- **Run 3**: Longest plan, includes database schema table, API response format examples, error handling strategy table, security and performance sections, future enhancements list

The structural inconsistency suggests Sonnet 4.5 is somewhat sensitive to its generation path, though all plans arrive at equivalent technical conclusions.

#### Quality (7/10)

The plans are well-written and technically sound. The constitution checks are thorough. Project structures are sensible and follow Python best practices. However, the plans read more as "planning documents about what will be planned" rather than complete deliverables -- they describe Phases 0-2 as future work rather than executing them. For a command that's supposed to produce actionable Phase 0 and Phase 1 outputs, this is an incomplete interpretation of the task.

---

### Claude Opus 4.6

**Runs analyzed**: opus-4.6-1, opus-4.6-2, opus-4.6-3

#### Completeness (10/10)

Opus 4.6 produced the most complete artifact sets across all runs. Every run generated:
- `plan.md` - Implementation plan
- `research.md` - Phase 0 technology research
- `data-model.md` - Phase 1 database schema and Pydantic models with SQL queries
- `quickstart.md` - Phase 1 development setup guide
- `contracts/` directory with 7 individual API contract files (create-todo.md, list-todos.md, get-todo.md, update-todo.md, delete-todo.md, complete-todo.md, incomplete-todo.md)

Total: 12 files per run (~1091 lines in run 1). This is the complete set of deliverables expected by the `/speckit.plan` workflow. Opus 4.6 was the only agent that understood it needed to run the setup-plan.sh script, create the `specs/` directory at the repo root (rather than `.specify/specs/`), and produce all Phase 0 and Phase 1 outputs.

#### Accuracy (10/10)

All plans demonstrate precise spec interpretation:
- Correctly identifies all 7 endpoints with exact HTTP methods, paths, and status codes
- Todo model has all 6 fields with correct types and constraints
- Data model includes actual SQL CREATE TABLE statements with CHECK constraints
- Research documents justify each technology choice against constitutional principles (e.g., no ORM because "Constitution Principle I: An ORM adds abstraction without justification for 1 table and 7 queries")
- Contract files include request/response examples, Pydantic model references, and acceptance scenario mappings
- Correctly notes edge cases from spec (invalid UUID returns 400 not 404, empty title validation, etc.)

The plans make no errors in spec interpretation. No invented requirements, no missed requirements.

#### Consistency (10/10)

Opus 4.6 produced remarkably consistent plans across all 3 runs:
- **Plan line counts**: 91, 95, 94 (minimal variance, ~4% spread)
- **Artifact structure**: Identical file sets in all 3 runs (12 files each)
- **Technical decisions**: Identical across runs (no ORM, flat src/ layout, tests per user story, WAL mode for SQLite)
- **Project structure**: Virtually identical module layout (main.py, models.py, database.py, routes.py, errors/exceptions.py)
- **Constitution check format**: Same table format with same pass/fail assessments

The only minor differences are cosmetic (e.g., "errors.py" vs "exceptions.py" naming, slight wording variations in summaries). The core technical substance is nearly identical across all runs.

#### Quality (10/10)

The plans are concise, focused, and actionable. Key quality indicators:
- **Research.md**: Substantive technology justifications (not boilerplate), with clear rationale for each decision linked to constitutional principles
- **Data-model.md**: Includes actual SQL schema, Pydantic model code, SQL query table, data flow diagram, and integrity rules
- **Contracts**: Each contract file specifies request format, response format per status code, Pydantic models, invariants, error triggers, and acceptance scenarios
- **Plan.md**: Tightly scoped, no unnecessary sections, constitution check is a clean table format

The plans are the shortest in line count but the most information-dense. Opus avoided padding and focused on delivering actionable artifacts that could directly guide implementation.

---

### GPT-5

**Runs analyzed**: gpt-5-1, gpt-5-2, gpt-5-3

#### Completeness (4/10)

GPT-5 showed the most uneven completeness:
- **Run 1 (gpt-5-1)**: Created a file called `speckit.plan` (not `plan.md`) at the repo root (not in specs/ or .specify/). Did NOT generate research.md, data-model.md, quickstart.md, or contracts/. The plan itself is a generic project plan, not a speckit-format plan.
- **Run 2 (gpt-5-2)**: Created `specs/001-todo-crud/plan.md` plus research.md, data-model.md, quickstart.md (but no contracts/). 5 files total.
- **Run 3 (gpt-5-3)**: Same artifact set as Run 2. 5 files total.

No run produced the contracts/ directory with individual API contract files, which is a Phase 1 deliverable. Runs 2 and 3 produced supporting artifacts but they were notably thin (research.md was 8 lines in run 2, data-model.md was 14 lines in run 2 and 11 lines in run 3).

#### Accuracy (4/10)

This is where GPT-5 had its most critical failure:
- **Run 1**: Proposed Node.js + Express + TypeScript + Prisma ORM + React frontend -- entirely wrong technology stack. The spec and constitution clearly mandate Python 3.11+, FastAPI, SQLite via stdlib, and Pydantic v2. This plan also invented features not in the spec: frontend UI, Docker, CI/CD, E2E testing with Playwright, status enum with "pending/in_progress/done", priority field, due_date field.
- **Run 2**: Correctly identified Python/FastAPI/SQLite stack but deviated from the spec in several ways: used `PUT` instead of `PATCH` for updates, added `status` enum (pending/in_progress/done) instead of the spec's boolean `completed`, added `priority` (0-5) and `due_date` fields not in the spec, added pagination (limit/offset) and filtering (status, due_before, due_after) not in the spec, used integer auto-increment IDs instead of UUID v4, set title max length to 200 instead of 500, and added a `/health` endpoint not specified. It also mentions `sqlalchemy` as an alternative, which contradicts the constitution's simplicity principle.
- **Run 3**: More accurate than Run 2 but still had the short plan format. It correctly used UUID v4, FastAPI, and parameterized queries, and was closer to the spec, but the plan was very terse (71 lines) with minimal design detail.

#### Consistency (2/10)

GPT-5 showed the worst consistency of any agent:
- **Plan line counts**: 97, 117, 71 (moderate variance in size but massive variance in content)
- **Technology stack**: Run 1 chose Node.js/Express/TypeScript; Runs 2 and 3 chose Python/FastAPI (correct)
- **Data model**: Run 1 used Prisma/Postgres-ready; Run 2 invented status enum, priority, due_date fields; Run 3 was closest to spec
- **File location**: Run 1 used `speckit.plan` at repo root; Runs 2-3 used `specs/001-todo-crud/plan.md`
- **Artifact generation**: Run 1 produced 1 file; Runs 2-3 produced 5 files each
- **Plan format**: Run 1 used a custom non-markdown format; Runs 2-3 used markdown with headers

The agent showed fundamental instability in task interpretation, sometimes ignoring the repository's constitution and spec entirely.

#### Quality (4/10)

- **Run 1**: Despite being well-structured as a generic project plan, it is a failure -- it completely ignores the repository's constitution, spec, and technology stack. The milestones (M1-M8) describe building a full-stack application with React, which has nothing to do with the spec.
- **Run 2**: The plan is reasonably structured but invents requirements. The research.md and data-model.md are extremely thin (8 and 14 lines respectively). The plan mixes in features from GPT-5's own interpretation rather than following the spec faithfully.
- **Run 3**: The most accurate of the three runs but also the tersest plan overall at 71 lines. It lacks the depth needed for an actionable implementation guide.

---

## Comparative Rankings

### Overall Ranking

| Rank | Agent | Completeness | Accuracy | Consistency | Quality | Overall |
|------|-------|-------------|----------|-------------|---------|---------|
| 1 | **Opus 4.6** | 10/10 | 10/10 | 10/10 | 10/10 | **10.0/10** |
| 2 | **Sonnet 4.5** | 7/10 | 9/10 | 7/10 | 7/10 | **7.5/10** |
| 3 | **GPT-5** | 4/10 | 4/10 | 2/10 | 4/10 | **3.5/10** |

### Category Breakdown

**Completeness** (artifact generation):
1. Opus 4.6 -- Full artifact set (plan + research + data model + quickstart + 7 contracts) in all runs
2. Sonnet 4.5 -- Plan only (no supporting Phase 0/1 artifacts)
3. GPT-5 -- One run failed entirely; other two had partial artifacts with no contracts

**Accuracy** (spec fidelity):
1. Opus 4.6 -- Zero spec deviations across all runs
2. Sonnet 4.5 -- Minor architectural variations but no spec misinterpretations
3. GPT-5 -- Run 1 wrong stack entirely; Run 2 invented multiple fields/features; Run 3 acceptable but thin

**Consistency** (cross-run stability):
1. Opus 4.6 -- Near-identical outputs (4% line count variance, identical structure and decisions)
2. Sonnet 4.5 -- Same conclusions but varying structure and depth (50% line count variance)
3. GPT-5 -- Fundamentally different outputs across runs (wrong stack, wrong data model, wrong file location)

**Quality** (actionability and depth):
1. Opus 4.6 -- Concise, information-dense, directly actionable with code examples
2. Sonnet 4.5 -- Well-written but describes future work rather than delivering it
3. GPT-5 -- Ranges from incorrect (Run 1) to thin but adequate (Run 3)

### Performance Metrics

| Agent | Avg Duration (s) | Duration Range (s) | Plans Generated | Artifacts per Run |
|-------|------------------|--------------------|-----------------|-------------------|
| Sonnet 4.5 | 142.3 | 133-154 | 3/3 | 1 (plan only) |
| Opus 4.6 | 321.7 | 280-344 | 3/3 | 12 (full set) |
| GPT-5 | 297.3 | 132-424 | 2/3 correct | 1-5 (variable) |

Opus 4.6 took ~2.3x longer than Sonnet 4.5 but produced ~12x more artifacts. GPT-5 had the widest duration variance (3.2x between fastest and slowest runs), correlating with its inconsistent output quality.

---

## Notable Observations

### 1. Opus 4.6 understood the full workflow
Opus 4.6 was the only agent that ran the `setup-plan.sh` script, correctly set up the `specs/` directory structure at the repo root (separate from `.specify/specs/`), and produced all expected Phase 0 and Phase 1 deliverables. This demonstrates superior understanding of the speckit toolchain and the repository's conventions.

### 2. GPT-5 Run 1 is a critical failure
GPT-5's first run proposed Node.js/Express/TypeScript/React when the project constitution explicitly specifies Python/FastAPI/SQLite/Pydantic. It also placed the plan in a `speckit.plan` file at the repo root instead of the expected location. This represents a fundamental failure to read and adhere to repository context -- the constitution.md file was present and accessible.

### 3. GPT-5 consistently invented requirements
Across Runs 2 and 3, GPT-5 added features not in the spec: pagination, filtering, status enums, priority fields, due dates, and health endpoints. This "creative enhancement" behavior is problematic for plan generation where spec fidelity is essential.

### 4. Sonnet 4.5 was reliable but incomplete
Sonnet 4.5 consistently produced good plans but treated the task as "write a plan document" rather than "execute the speckit planning workflow and produce all deliverables." It described what research.md, data-model.md, and contracts/ would contain but did not create them.

### 5. Metrics.json undercounts actual output
All metrics.json files show `plan.total_lines: 0` and `has_commits: false`, despite plans being generated and (in some cases) committed. This appears to be a metrics collection issue -- the benchmark harness may be looking for plans in `.specify/specs/*/plan.md` while some agents wrote to `specs/*/plan.md`.

### 6. Git identity issues affected all agents
Every agent encountered `Author identity unknown` errors on first commit attempt. Opus 4.6 and Sonnet 4.5 resolved this cleanly on first retry; GPT-5 Run 2 needed three attempts before finding the right git config syntax.

### 7. Duration correlates with thoroughness, not quality
GPT-5 Run 2 was the slowest (424s) but produced only 5 thin artifacts. Opus 4.6 averaged 322s and produced 12 high-quality artifacts. Sonnet 4.5 was fastest (avg 142s) but only produced 1 artifact. Speed alone is not a useful quality predictor.
