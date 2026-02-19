# Implementation Plan: Star and Unstar Shared Issue Views

**Branch**: `001-star-unstar-views` | **Date**: 2026-02-19 | **Spec**: `/specs/001-star-unstar-views/spec.md`
**Input**: Feature specification from `/specs/001-star-unstar-views/spec.md`

## Summary

Add a dedicated star/unstar endpoint for `GroupSearchView` that allows users to star any view they have access to (owned or organization-shared) and unstar previously starred views, with optional position management. The implementation uses the existing `GroupSearchViewStarred` model and follows established patterns from the `DashboardFavoriteEndpoint` and `OrganizationGroupSearchViewStarredOrderEndpoint`.

## Technical Context

**Language/Version**: Python 3.13+
**Primary Dependencies**: Django 5.2+, Django REST Framework, Celery 5.5+
**Storage**: PostgreSQL (via `GroupSearchViewStarred` model, table `sentry_groupsearchviewstarred`)
**Testing**: pytest with `APITestCase` and `TransactionTestCase` base classes
**Target Platform**: Linux server (Sentry backend)
**Project Type**: Web application (Django backend)
**Performance Goals**: Standard API response times (<200ms p95)
**Constraints**: Silo architecture (region silo), backwards-compatible migrations, camelCase API responses
**Scale/Scope**: Per-user per-organization starred views list, bounded by existing MAX_VIEWS (50)

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| #   | Principle                     | Status | Evidence                                                                                                                                                                                                                                                |
| --- | ----------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I   | Convention Over Configuration | PASS   | New endpoint mirrors existing `OrganizationGroupSearchViewStarredOrderEndpoint` and `OrganizationGroupSearchViewDetailsEndpoint` patterns. Uses same `MemberPermission`, `ApiOwner.ISSUES`, `ApiPublishStatus.EXPERIMENTAL`, and feature flag checking. |
| II  | Security by Default           | PASS   | All queries scoped by `organization` + `user_id`. View access validated by checking `user_id` ownership or `visibility == ORGANIZATION`. Uses `OrganizationEndpoint` base class for automatic org resolution and permission checking.                   |
| III | Framework Trust               | PASS   | Inherits from `OrganizationEndpoint`, uses DRF serializers for validation, `@region_silo_endpoint` decorator, standard `Response` objects. No custom framework wrappers.                                                                                |
| IV  | Batch-Aware Data Access       | PASS   | No new serializer needed for star/unstar (returns 204). Existing `GroupSearchViewStarredSerializer` already batch-fetches in `get_attrs()` for list operations.                                                                                         |
| V   | Test-Driven with Factories    | PASS   | Tests will use `self.create_user()`, `self.create_organization()`, `self.create_project()` factories. Test file mirrors source: `tests/sentry/issues/endpoints/test_organization_group_search_view_starred.py`.                                         |
| VI  | Incremental Delivery          | PASS   | Gated behind `organizations:issue-view-sharing` feature flag (same as the starred order endpoint). Safe to merge without activating.                                                                                                                    |

**Architectural Constraints:**

- Silo: Region silo (views and stars are project/issue data) — PASS
- Migrations: No schema changes needed (`GroupSearchViewStarred` model already exists) — PASS
- API contracts: Responses use 204 No Content for star/unstar, camelCase for any body — PASS

**Gate Result: ALL PASS — Proceeding to Phase 0.**

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
└── tasks.md             # Phase 2 output (NOT created by plan)
```

### Source Code (repository root)

```text
src/sentry/issues/endpoints/
├── organization_group_search_view_starred.py       # NEW: Star/Unstar endpoint
├── organization_group_search_view_starred_order.py # EXISTING: Reorder endpoint
├── organization_group_search_views.py              # EXISTING: List/Bulk update
├── organization_group_search_view_details.py       # EXISTING: Delete
└── __init__.py                                     # UPDATE: Add import + __all__ entry

src/sentry/api/
├── urls.py              # UPDATE: Add star/unstar URL route

tests/sentry/issues/endpoints/
└── test_organization_group_search_view_starred.py  # NEW: Tests
```

**Structure Decision**: Follows existing Sentry pattern — endpoint in `src/sentry/issues/endpoints/`, test file mirrors source path in `tests/`. No new models or serializers needed.

## Constitution Check — Post-Design Re-evaluation

_Re-checked after Phase 1 design completion._

| #   | Principle                     | Status | Evidence                                                                                                                                                                                                                    |
| --- | ----------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I   | Convention Over Configuration | PASS   | Endpoint follows exact same structure as `OrganizationGroupSearchViewStarredOrderEndpoint`. Same `MemberPermission`, `ApiOwner.ISSUES`, `ApiPublishStatus.EXPERIMENTAL`. URL mirrors `group-search-views/{view_id}/visit/`. |
| II  | Security by Default           | PASS   | All queries scoped by `organization` (resolved by `OrganizationEndpoint`). View access validated by `user_id` match OR `visibility == ORGANIZATION`.                                                                        |
| III | Framework Trust               | PASS   | Inherits `OrganizationEndpoint`. Uses DRF serializer for input. `@region_silo_endpoint`. Standard `Response`.                                                                                                               |
| IV  | Batch-Aware Data Access       | PASS   | No serializer needed (204 responses). Position shift uses bulk `.update()`.                                                                                                                                                 |
| V   | Test-Driven with Factories    | PASS   | Uses `self.create_user()`, `self.create_organization()`. Test path mirrors source.                                                                                                                                          |
| VI  | Incremental Delivery          | PASS   | Gated behind `organizations:issue-view-sharing` feature flag.                                                                                                                                                               |

**Post-Design Gate Result: ALL PASS.**

## Complexity Tracking

> No violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --------- | ---------- | ------------------------------------ |
| —         | —          | —                                    |
