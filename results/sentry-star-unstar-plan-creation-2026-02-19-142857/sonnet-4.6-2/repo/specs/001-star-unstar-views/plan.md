# Implementation Plan: Star and Unstar Shared Issue Views

**Branch**: `001-star-unstar-views` | **Date**: 2026-02-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-star-unstar-views/spec.md`

## Summary

Add a dedicated endpoint for starring and unstarring individual `GroupSearchView` records per user,
with optional position insertion. The `GroupSearchViewStarred` model already exists; what is
missing is a per-view star/unstar endpoint (POST/DELETE on
`/group-search-views/{view_id}/star/`) that is decoupled from the existing bulk-PUT flow.

## Technical Context

**Language/Version**: Python 3.13+
**Primary Dependencies**: Django 5.2+, Django REST Framework, `sentry.api.bases.organization.OrganizationEndpoint`
**Storage**: PostgreSQL (region silo) — `sentry_groupsearchviewstarred` table already exists
**Testing**: pytest via `sentry.testutils.cases.APITestCase`
**Target Platform**: Linux server (region silo)
**Project Type**: Web application — backend API only (Django + DRF)
**Performance Goals**: Consistent with other issue-view endpoints; single-row write on each call
**Constraints**: Deferred unique constraint on `(user_id, organization_id, position)` must be respected; all writes within `transaction.atomic`
**Scale/Scope**: Per-user, per-org star list; bounded by practical UI limits (≤50 starred views, consistent with `MAX_VIEWS = 50`)

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                        | Status | Notes                                                                                                                                             |
| -------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| I. Convention Over Configuration | PASS   | New endpoint mirrors `organization_group_search_view_visit.py`; reuses `MemberPermission`, `@region_silo_endpoint`, existing model manager        |
| II. Security by Default          | PASS   | All queries scoped to `organization` + `request.user.id`; view access validated before star/unstar                                                |
| III. Framework Trust             | PASS   | Inherits `OrganizationEndpoint`; uses DRF for input validation; no custom auth reimplementation                                                   |
| IV. Batch-Aware Data Access      | PASS   | Star/unstar are single-row writes; no serialization path has N+1 risk                                                                             |
| V. Test-Driven with Factories    | PASS   | Tests use `self.create_*` factories; test file at `tests/sentry/issues/endpoints/test_organization_group_search_view_star.py` mirrors source path |
| VI. Incremental Delivery         | PASS   | Guarded by existing `organizations:issue-view-sharing` feature flag                                                                               |

**Constitution Check Result**: ALL GATES PASS. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-star-unstar-views/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── star-unstar.yaml
└── tasks.md             # Phase 2 output (created by /speckit.tasks — NOT this command)
```

### Source Code (repository root)

```text
src/sentry/issues/endpoints/
└── organization_group_search_view_star.py   # NEW — star/unstar endpoint

src/sentry/issues/endpoints/__init__.py      # MODIFY — add import + __all__ entry

src/sentry/api/urls.py                       # MODIFY — add URL pattern for /star/

tests/sentry/issues/endpoints/
└── test_organization_group_search_view_star.py   # NEW — full test coverage
```

**Structure Decision**: Single Django/DRF backend feature. No frontend changes. No new models or
migrations needed — `GroupSearchViewStarred` already has the schema required by all acceptance
scenarios.

## Complexity Tracking

> No constitution violations — this section is not required.
