# Implementation Plan: Star and Unstar Shared Issue Views

**Branch**: `001-star-unstar-views` | **Date**: 2026-02-19 | **Spec**: `/specs/001-star-unstar-views/spec.md`
**Input**: Feature specification from `/specs/001-star-unstar-views/spec.md`

## Summary

Add a dedicated API endpoint to star and unstar `GroupSearchView` instances independently of the bulk PUT endpoint. The `GroupSearchViewStarred` model already exists with position management. This feature adds a `PUT` (star) and `DELETE` (unstar) endpoint at `/organizations/{org}/group-search-views/{view_id}/starred/` that creates/removes `GroupSearchViewStarred` rows with proper position management, idempotent behavior, and access control for both owned and organization-shared views.

## Technical Context

**Language/Version**: Python 3.13+
**Primary Dependencies**: Django 5.2+, Django REST Framework, Celery 5.5+
**Storage**: PostgreSQL (via Django ORM, `GroupSearchViewStarred` table already exists)
**Testing**: pytest with `APITestCase` and `TransactionTestCase` base classes
**Target Platform**: Linux server (Sentry backend)
**Project Type**: Web application (Django backend API)
**Performance Goals**: Standard API response times; position updates are bounded by user's starred view count (max ~50)
**Constraints**: Must use `transaction.atomic` with deferred unique constraints for position management; region silo boundary
**Scale/Scope**: Per-user starred list, bounded by `MAX_VIEWS = 50`

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

**Pre-Phase 0 check: PASS** | **Post-Phase 1 re-check: PASS** — No new violations introduced by design.

| #    | Principle                       | Status | Evidence                                                                                                                                                      |
| ---- | ------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I    | Convention Over Configuration   | PASS   | Mirrors existing `OrganizationGroupSearchViewDetailsEndpoint` and `OrganizationGroupSearchViewVisitEndpoint` patterns exactly                                 |
| II   | Security by Default             | PASS   | Queries scoped to `organization` + validates view access (owned or organization-visibility); uses `MemberPermission` with `member:read`/`member:write` scopes |
| III  | Framework Trust                 | PASS   | Inherits `OrganizationEndpoint`, uses `@region_silo_endpoint`, DRF serializer for input validation                                                            |
| IV   | Batch-Aware Data Access         | PASS   | Position updates use bulk `filter().update()` with `F()` expressions, not per-row queries                                                                     |
| V    | Test-Driven with Factories      | PASS   | Tests use `BaseGSVTestCase` with factory-created data; procedural assertions                                                                                  |
| VI   | Incremental Delivery            | PASS   | Gated behind `organizations:issue-view-sharing` feature flag                                                                                                  |
| AC-1 | Silo boundaries                 | PASS   | All models are `@region_silo_model`; endpoint is `@region_silo_endpoint`; user referenced via `HybridCloudForeignKey`                                         |
| AC-2 | Backwards-compatible migrations | PASS   | No new migrations required; `GroupSearchViewStarred` table already exists                                                                                     |
| AC-3 | API contract stability          | PASS   | Response uses `camelCase`, IDs as strings, errors via `"detail"` key                                                                                          |

**Gate result: PASS** — No violations detected.

## Project Structure

### Documentation (this feature)

```text
specs/001-star-unstar-views/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (NOT created by plan)
```

### Source Code (repository root)

```text
src/sentry/
├── models/
│   └── groupsearchviewstarred.py          # Existing model (no changes needed)
├── issues/endpoints/
│   ├── __init__.py                        # Add import for new endpoint
│   └── organization_group_search_view_starred.py  # NEW: Star/unstar endpoint
├── api/
│   ├── urls.py                            # Add URL route for new endpoint
│   └── serializers/
│       └── models/groupsearchview.py      # Existing serializer (no changes needed)
└── ...

tests/sentry/issues/endpoints/
└── test_organization_group_search_view_starred.py  # NEW: Tests for star/unstar
```

**Structure Decision**: Follows existing Sentry convention. New endpoint file in `src/sentry/issues/endpoints/` mirrors existing `organization_group_search_view_details.py` and `organization_group_search_view_visit.py` patterns. Test file mirrors source path in `tests/`.

## Complexity Tracking

> No violations detected. Table intentionally left empty.
