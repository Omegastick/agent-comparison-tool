# Implementation Plan: Star and Unstar Shared Issue Views

**Branch**: `001-star-unstar-views` | **Date**: 2026-02-19 | **Spec**: [/workspace/repo/specs/001-star-unstar-views/spec.md](spec.md)
**Input**: Feature specification from `/specs/001-star-unstar-views/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Add dedicated star and unstar API endpoints for GroupSearchViews to allow users to bookmark and organize shared issue views independently of view creation/deletion. The infrastructure (GroupSearchViewStarred model, serializers, position management) already exists but is only accessible through bulk operations. This feature exposes individual star/unstar operations with optional position management.

## Technical Context

**Language/Version**: Python 3.13+  
**Primary Dependencies**: Django 5.2+, Django REST Framework, drf-spectacular (OpenAPI docs)  
**Storage**: PostgreSQL (with deferrable constraints for position management)  
**Testing**: pytest with APITestCase framework  
**Target Platform**: Linux server (Sentry backend application)  
**Project Type**: Web application backend (Django REST API)  
**Performance Goals**: <200ms p95 response time for single star/unstar operations  
**Constraints**: Multi-tenant security (organization/user scoping), atomic position updates, idempotent operations  
**Scale/Scope**: 2 new API endpoints (star, unstar) leveraging existing GroupSearchViewStarred model and manager

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

### I. Convention Over Configuration ✅

**Assessment**: PASS  
**Evidence**: Feature will follow established Sentry patterns:

- Use `OrganizationEndpoint` base class for automatic permission checking
- Mirror structure of existing GroupSearchView endpoints in `src/sentry/issues/endpoints/`
- Follow naming convention: `organization_group_search_view_star.py` and `organization_group_search_view_unstar.py`
- Leverage existing `GroupSearchViewStarred` model and `GroupSearchViewStarredManager`
- Use established serializers (`GroupSearchViewStarredSerializer`)

**No new patterns required** - all infrastructure exists.

### II. Security by Default ✅

**Assessment**: PASS  
**Evidence**: Security will be enforced through:

- Inherit from `OrganizationEndpoint` - automatic org scoping
- Query scoping: `GroupSearchView.objects.filter(organization=organization)` before starring
- Validate view access: check `visibility == ORGANIZATION` OR `user_id == request.user.id`
- All starred view queries scoped: `GroupSearchViewStarred.objects.filter(organization=organization, user_id=request.user.id)`
- Use `publish_status = {"POST": ApiPublishStatus.PUBLIC}` for API documentation

**Follows existing pattern** from `organization_group_search_view_starred_order.py` lines 30-43.

### III. Framework Trust ✅

**Assessment**: PASS  
**Evidence**:

- Use `OrganizationEndpoint` base class (not reimplementing permission logic)
- Use `@region_silo_endpoint` decorator (views are region-scoped data)
- Use Django ORM directly (no custom abstractions)
- Use DRF `Response` and `Request` objects
- Use `transaction.atomic(router.db_for_write(GroupSearchViewStarred))` for position updates

**No framework wrapping** - direct Django/DRF usage.

### IV. Batch-Aware Data Access ✅

**Assessment**: PASS  
**Evidence**:

- Star/unstar operations are single-item operations (no batch concerns in endpoint)
- Serializers already implement two-phase pattern in `GroupSearchViewStarredSerializer.get_attrs()`
- GET endpoints (existing) use `get_attrs()` for batch fetching of last_visited, projects
- Position updates use `bulk_update()` when shifting multiple positions

**No N+1 queries** - existing serializers handle batching correctly.

### V. Test-Driven with Factories ✅

**Assessment**: PASS  
**Evidence**: Tests will use:

- `APITestCase` base class
- `self.create_user()`, `self.create_organization()`, `self.create_project()`
- `self.login_as(user)` for authentication
- `self.get_success_response()` and `self.get_error_response()` for assertions
- Test file location: `tests/sentry/issues/endpoints/test_organization_group_search_view_star.py`
- Mirror structure of `tests/sentry/issues/endpoints/test_organization_group_search_view_starred_order.py`

**No direct model construction** - use factory methods only.

### VI. Incremental Delivery ✅

**Assessment**: PASS (optional - feature is small enough)  
**Evidence**:

- Feature can be delivered without feature flag (small, isolated change)
- Two endpoints can be merged independently (star first, then unstar)
- Existing functionality unaffected (additive change only)
- If gating desired, use: `features.has('organizations:issue-views-starring', organization)`

**Optional gating** - feature is safe to deploy directly.

### Architectural Constraints ✅

**Silo boundaries**: PASS

- Feature is region-scoped (`@region_silo_endpoint`)
- Uses `HybridCloudForeignKey` for user_id (already in model)
- No cross-silo communication required

**Migrations**: PASS

- No new migrations required (model exists since migration 0836)
- No schema changes needed

**API contracts**: PASS

- Request/response use camelCase (e.g., `viewId`, `groupSearchView`)
- IDs returned as strings (`str(view.id)`)
- Errors use `"detail"` key
- Follows OpenAPI documentation standards with drf-spectacular

### Summary

**GATE STATUS: PASS** ✅

All constitution principles satisfied. No violations. No complexity justification required.

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

```text
src/sentry/
├── issues/
│   └── endpoints/
│       ├── organization_group_search_view_star.py        # NEW: Star endpoint
│       ├── organization_group_search_view_unstar.py      # NEW: Unstar endpoint
│       ├── organization_group_search_views.py            # EXISTING: Bulk operations
│       ├── organization_group_search_view_details.py     # EXISTING: Delete
│       └── organization_group_search_view_starred_order.py  # EXISTING: Reorder
├── models/
│   ├── groupsearchview.py                                # EXISTING: Main model
│   └── groupsearchviewstarred.py                         # EXISTING: Star relationship model
├── api/
│   ├── urls.py                                           # MODIFY: Add new routes
│   └── serializers/
│       └── models/
│           └── groupsearchview.py                        # EXISTING: Serializers
└── testutils/
    └── cases.py                                          # EXISTING: Test base classes

tests/sentry/issues/endpoints/
├── test_organization_group_search_view_star.py           # NEW: Star tests
├── test_organization_group_search_view_unstar.py         # NEW: Unstar tests
├── test_organization_group_search_views.py               # EXISTING
├── test_organization_group_search_view_details.py        # EXISTING
└── test_organization_group_search_view_starred_order.py  # EXISTING
```

**Structure Decision**: Follows Sentry's established pattern where issue-related endpoints live in `src/sentry/issues/endpoints/` rather than `src/sentry/api/endpoints/`. This matches the existing GroupSearchView endpoints. Test files mirror the source structure in `tests/sentry/issues/endpoints/`.

## Complexity Tracking

**Status**: No violations - section not applicable.
