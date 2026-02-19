# Implementation Plan: Star and Unstar Shared Issue Views

**Branch**: `001-star-unstar-views` | **Date**: 2026-02-19 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/001-star-unstar-views/spec.md`

## Summary

Add an explicit star/unstar endpoint (`PUT`/`DELETE` on `/group-search-views/{view_id}/star/`) so users can bookmark any accessible view — including shared org-visibility views they don't own — into their personal ordered starred list. The `GroupSearchViewStarred` join table already exists in the schema; this feature exposes it via a dedicated REST endpoint with idempotent semantics and position management.

## Technical Context

**Language/Version**: Python 3.13  
**Primary Dependencies**: Django 5.1.7, Django REST Framework 3.15.2  
**Storage**: PostgreSQL (primary) — `sentry_groupsearchviewstarred` table (already exists, migration `0836`)  
**Testing**: pytest with `APITestCase` (`sentry.testutils.cases`)  
**Target Platform**: Linux server (Sentry region silo)  
**Project Type**: web (Django backend, no frontend changes in scope)  
**Performance Goals**: Single-row insert/delete + bounded position shift; p95 < 100ms  
**Constraints**: All writes in `transaction.atomic`; deferred unique constraint requires transactional writes; no new migrations  
**Scale/Scope**: Per-user, per-organization starred list; position shift affects at most ~50 rows (MAX_VIEWS limit)

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                        | Status | Notes                                                                                                                                                                                                                |
| -------------------------------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I. Convention Over Configuration | PASS   | Endpoint follows the `/visit/` sub-resource pattern exactly. `MemberPermission`, `@region_silo_endpoint`, `ApiOwner.ISSUES`, `publish_status` all match existing endpoints.                                          |
| II. Security by Default          | PASS   | Every query scopes `GroupSearchView` to `organization=organization`. Cross-org access returns 404 (not 403) to avoid revealing existence. Visibility check enforced before any write.                                |
| III. Framework Trust             | PASS   | Inherits `OrganizationEndpoint` for automatic org resolution and permission checking. No custom middleware or auth re-implementation.                                                                                |
| IV. Batch-Aware Data Access      | PASS   | Endpoint operates on a single view (not a list). The `GroupSearchViewStarredSerializer` delegates to `GroupSearchViewSerializer` which uses `get_attrs()` for batch-fetch of `lastVisited`. No N+1 in serialization. |
| V. Test-Driven with Factories    | PASS   | Tests use `BaseGSVTestCase` and `GroupSearchView.objects.create` / `GroupSearchViewStarred.objects.create` (same pattern as existing test files). No direct model construction outside the established test helpers. |
| VI. Incremental Delivery         | PASS   | Endpoint gated behind `organizations:issue-view-sharing` feature flag. Code merges safely without the flag enabled.                                                                                                  |

**Architectural constraints**:

| Constraint                      | Status | Notes                                                                                                                       |
| ------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------- |
| Silo boundaries                 | PASS   | Uses `@region_silo_endpoint` + `@region_silo_model` (existing). No control-silo data accessed.                              |
| Migrations backwards compatible | PASS   | No new migrations. Existing schema is complete.                                                                             |
| API contracts stable            | PASS   | Response uses `GroupSearchViewStarredSerializer` (existing, camelCase). IDs returned as strings. Errors use `"detail"` key. |

**Post-design re-check**: No violations introduced. The design adds one new file, one import, and one URL pattern — all following established patterns.

## Project Structure

### Documentation (this feature)

```text
specs/001-star-unstar-views/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── openapi.yaml     # Phase 1 output
└── tasks.md             # Phase 2 output (created by /speckit.tasks — NOT by /speckit.plan)
```

### Source Code

```text
src/sentry/issues/endpoints/
├── organization_group_search_view_starred.py    # NEW — OrganizationGroupSearchViewStarredEndpoint
├── organization_group_search_view_details.py    # existing (reference for position decrement)
├── organization_group_search_view_visit.py      # existing (reference for sub-resource structure)
└── __init__.py                                  # MODIFIED — add import

src/sentry/api/
└── urls.py                                      # MODIFIED — add URL pattern + import

tests/sentry/issues/endpoints/
└── test_organization_group_search_view_starred.py   # NEW
```

**Structure Decision**: Single web project (Django). Feature is backend-only. Existing `sentry_groupsearchviewstarred` table requires no schema changes.

## Complexity Tracking

> No constitution violations. Table intentionally left empty.
