# Implementation Plan: Star and Unstar Shared Issue Views

**Branch**: `001-star-unstar-views` | **Date**: 2026-02-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-star-unstar-views/spec.md`

## Summary

Add `POST` and `DELETE` operations on a new `/organizations/{slug}/group-search-views/{view_id}/star/` endpoint that stars or unstars a `GroupSearchView` for the current user. The `GroupSearchViewStarred` model, migrations, and serializers are already in production; only the endpoint, URL registration, and tests are new.

## Technical Context

**Language/Version**: Python 3.13+
**Primary Dependencies**: Django 5.2+, Django REST Framework, Sentry base classes (`OrganizationEndpoint`, `region_silo_endpoint`)
**Storage**: PostgreSQL — `sentry_groupsearchviewstarred` table (exists, migration 0836); no new DDL required
**Testing**: pytest via `sentry.testutils.cases.APITestCase`
**Target Platform**: Linux server (region silo)
**Project Type**: Web application — Django backend only; no frontend changes in this feature
**Performance Goals**: Same as existing group-search-view endpoints — p95 < 200ms; operations are single-row upserts with an O(n) positional shift (bounded by user's starred list, typically < 50 views)
**Constraints**: Writes must be wrapped in `transaction.atomic(using=router.db_for_write(GroupSearchViewStarred))` to protect the deferred uniqueness constraint on position; feature flag `organizations:issue-view-sharing` must gate all new endpoints
**Scale/Scope**: Per-user per-org, very low cardinality writes; no bulk or cross-user operations

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                        | Assessment | Notes                                                                                                                                                                                                   |
| -------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I. Convention Over Configuration | **PASS**   | Endpoint mirrors `organization_group_search_view_visit.py` and `organization_group_search_view_details.py` in structure. No new patterns introduced.                                                    |
| II. Security by Default          | **PASS**   | All `GroupSearchView` queries are scoped to `organization=organization`. Access check verifies `user_id` match or `visibility == ORGANIZATION`. Cross-org access impossible via the existing ORM scope. |
| III. Framework Trust             | **PASS**   | Uses `OrganizationEndpoint`, `@region_silo_endpoint`, `MemberPermission(OrganizationPermission)`. No reimplementation of base class behavior.                                                           |
| IV. Batch-Aware Data Access      | **PASS**   | Positional shift uses a single bulk `UPDATE` via `.update(position=F("position") + 1)`, not a Python loop. `GroupSearchViewStarredSerializer.get_attrs()` already batch-fetches.                        |
| V. Test-Driven with Factories    | **PASS**   | Tests use `APITestCase` with `get_success_response`/`get_error_response`. Factory methods (`self.create_*`) required; no direct `Model.objects.create()` in test bodies.                                |
| VI. Incremental Delivery         | **PASS**   | Gated behind `organizations:issue-view-sharing`. Code can be merged and deployed without activating the feature.                                                                                        |
| Silo boundaries                  | **PASS**   | `@region_silo_endpoint` used. `GroupSearchViewStarred` is `@region_silo_model`. `HybridCloudForeignKey` used for `user_id` (correct pattern for cross-silo user reference).                             |
| Migrations backwards compatible  | **PASS**   | No new migrations.                                                                                                                                                                                      |
| API contracts stable             | **PASS**   | New endpoint with new route name. Response uses existing `GroupSearchViewStarredSerializer` shape — no breaking changes to existing responses. `camelCase` body, string IDs, `"detail"` error key.      |

**Post-design re-check**: All gates still pass. The design uses only established patterns, no new abstractions, and adds no migrations.

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
└── tasks.md             # Phase 2 output (not yet created)
```

### Source Code (repository root)

```text
src/sentry/issues/endpoints/
├── organization_group_search_view_star.py     # NEW: star/unstar endpoint

src/sentry/api/
└── urls.py                                    # MODIFY: add star route

tests/sentry/issues/endpoints/
└── test_organization_group_search_view_star.py  # NEW: test suite
```

**Structure Decision**: Single project (Django web application). No frontend changes. New endpoint file follows the existing naming convention of sibling files in `src/sentry/issues/endpoints/`. Tests mirror the source path per constitution §V.

## Complexity Tracking

_No constitution violations — section not applicable._
