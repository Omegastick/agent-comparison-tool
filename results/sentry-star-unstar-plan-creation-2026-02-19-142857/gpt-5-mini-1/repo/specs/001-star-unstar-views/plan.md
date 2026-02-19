# Implementation Plan: Star and Unstar Shared Issue Views

**Branch**: `001-star-unstar-views` | **Date**: 2026-02-19 | **Spec**: /workspace/repo/specs/001-star-unstar-views/spec.md
**Input**: Feature specification from `/workspace/repo/specs/001-star-unstar-views/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Add per-user starring for existing GroupSearchView entities. Provide idempotent star/unstar endpoints, support optional insertion position in a user's ordered starred list, and persist per-user ordering. The implementation will introduce a small normalized mapping model (`StarredSearchView`) persisted in PostgreSQL, provide organization-scoped API endpoints for star/unstar operations, and maintain ordering using an integer `position` with transactional updates (see research.md for alternatives considered). Concurrency will be handled with row-level locks within the user's starred set to ensure consistent shifts when inserting/removing entries.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.13 (Django 5.x, DRF)  
**Primary Dependencies**: Django, Django REST Framework, sentry base libraries (existing monorepo conventions)  
**Storage**: PostgreSQL (existing Sentry DB)  
**Testing**: pytest-based testutils and factory helpers (follow existing tests patterns)  
**Target Platform**: Linux server, region silo  
**Project Type**: Web backend (Django app within src/sentry)  
**Performance Goals**: Typical metadata operations; target p95 < 200ms for star/unstar under normal load. (TBD — see research)  
**Constraints**: Migrations must be backwards compatible; follow silo boundaries (@region_silo_model); permission checks must use Sentry permission system; use batch-aware serializers and avoid N+1 queries.  
**Scale/Scope**: Per-user metadata (expected low cardinality per user — typical users have <100 starred views), global userbase scale follows Sentry orgs and users.

**Open Questions / NEEDS CLARIFICATION**:

- Ordering strategy for inserts: integer positions with shifting vs fractional/float-positioning vs storing ordered array on user preferences — NEEDS CLARIFICATION (resolved in research.md)
- Concurrency handling: locking strategy for multi-request inserts at same position — NEEDS CLARIFICATION (resolved in research.md)
- Response shape: whether to return the entire updated starred list or a minimal success object — default to minimal serialized StarredSearchView (resolved in research.md)

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

Gates (derived from /workspace/repo/.specify/memory/constitution.md):

- Convention Over Configuration: Implementation must follow existing Django/DRF patterns and reuse sentry base classes and serializers. (COMPLIES — plan uses OrganizationEndpoint/DRF conventions)
- Security by Default: All queries must be scoped to organization and user; permission scopes must be declarative. (COMPLIES — plan uses OrganizationEndpoint and permission scopes; will validate in implementation)
- Framework Trust: Use Django ORM and DRF primitives; respect silo annotations (`@region_silo_model`, `@region_silo_endpoint`). (COMPLIES)
- Batch-Aware Data Access: Serializers must batch-fetch related GroupSearchView objects and user data. (COMPLIES — plan includes serializer with get_attrs)
- Test-Driven with Factories: Tests will use existing factory helpers and procedural test style. (COMPLIES)
- Incremental Delivery: Gate feature behind a feature flag so code can be merged safely. (COMPLIES — will add feature flag guard around endpoints)

No constitution violations identified. All requirements can be satisfied without changing silo boundaries or migration compatibility guarantees.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: Implement as a backend Django feature inside the existing Sentry region codebase. Concrete paths:

- Model: /workspace/repo/src/sentry/models/starred_search_view.py
- API Endpoint: /workspace/repo/src/sentry/api/endpoints/organization_starred_views.py
- Serializers: /workspace/repo/src/sentry/api/serializers/models/starred_search_view.py
- Migrations: /workspace/repo/src/sentry/migrations/<auto-generated>
- Tests: /workspace/repo/tests/sentry/api/endpoints/test_organization_starred_views.py

This mirrors existing Sentry patterns for entity models, organization-scoped endpoints, serializers and tests.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation                  | Why Needed         | Simpler Alternative Rejected Because |
| -------------------------- | ------------------ | ------------------------------------ |
| [e.g., 4th project]        | [current need]     | [why 3 projects insufficient]        |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient]  |
