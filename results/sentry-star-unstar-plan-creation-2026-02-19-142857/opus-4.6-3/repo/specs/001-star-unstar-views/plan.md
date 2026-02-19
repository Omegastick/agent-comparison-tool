# Implementation Plan: Star and Unstar Shared Issue Views

**Branch**: `001-star-unstar-views` | **Date**: 2026-02-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-star-unstar-views/spec.md`

## Summary

Add a dedicated API endpoint for starring and unstarring issue views (GroupSearchView). The existing `GroupSearchViewStarred` model already supports the data requirements. The feature requires a new endpoint at `group-search-views/<view_id>/star/` with PUT (star) and DELETE (unstar) methods, supporting optional position management for ordered starred lists. No new model or migration is needed.

## Technical Context

**Language/Version**: Python 3.13+
**Primary Dependencies**: Django 5.2+, Django REST Framework, Celery (not directly used)
**Storage**: PostgreSQL (via existing `GroupSearchViewStarred` model)
**Testing**: pytest with `sentry.testutils.cases.APITestCase`
**Target Platform**: Linux server (Region silo)
**Project Type**: Web (backend-only for this feature)
**Performance Goals**: Standard API latency (<200ms p95), single DB transaction per request
**Constraints**: Must be idempotent (FR-003, FR-004), must enforce org-scoped access (FR-008, FR-010)
**Scale/Scope**: Per-user starred list, max ~50 views per user (existing MAX_VIEWS constant)

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                        | Status | Evidence                                                                                                                                                       |
| -------------------------------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I. Convention Over Configuration | PASS   | Mirrors `organization_group_search_view_visit.py` endpoint pattern exactly. Uses same base class, permission model, feature flag, and silo decorator.          |
| II. Security by Default          | PASS   | All queries scoped to `organization`. Access check validates user owns view OR view is org-visible. Uses `MemberPermission` with declarative scope map.        |
| III. Framework Trust             | PASS   | Inherits from `OrganizationEndpoint`, uses `@region_silo_endpoint`, relies on DRF serializer for input validation. No custom abstractions.                     |
| IV. Batch-Aware Data Access      | PASS   | Star/unstar operates on a single view. Position shift uses a single `filter().update()` call, not N+1.                                                         |
| V. Test-Driven with Factories    | PASS   | Tests will use `APITestCase` with factory methods (`self.create_*`). Test file at `tests/sentry/issues/endpoints/test_organization_group_search_view_star.py`. |
| VI. Incremental Delivery         | PASS   | Gated behind `organizations:issue-view-sharing` feature flag. Safe to merge inactive.                                                                          |
| Silo Boundaries                  | PASS   | `@region_silo_endpoint` + `@region_silo_model` — all data in region silo.                                                                                      |
| Backwards-Compatible Migrations  | PASS   | No new migrations required.                                                                                                                                    |
| API Contract Stability           | PASS   | Response uses camelCase, IDs as strings, errors use `"detail"` key.                                                                                            |

**Gate result: ALL PASS** — no violations, no complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-star-unstar-views/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── star-unstar-api.yaml
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/sentry/
├── models/
│   └── groupsearchviewstarred.py    # EXISTING - no changes needed
├── issues/endpoints/
│   ├── __init__.py                  # ADD import + __all__ entry
│   └── organization_group_search_view_star.py  # NEW endpoint
├── api/
│   ├── urls.py                      # ADD route
│   └── serializers/models/
│       └── groupsearchview.py       # EXISTING - no changes needed

tests/sentry/issues/endpoints/
└── test_organization_group_search_view_star.py  # NEW test file
```

**Structure Decision**: Backend-only change within existing `src/sentry/issues/endpoints/` directory, following the established pattern for GroupSearchView endpoints.

## Complexity Tracking

> No violations to justify — all constitution gates pass.
