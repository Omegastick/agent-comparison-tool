# Implementation Plan: Star and Unstar Shared Issue Views

**Branch**: `001-star-unstar-views` | **Date**: 2026-02-19 | **Spec**: `/workspace/repo/specs/001-star-unstar-views/spec.md`
**Input**: Feature specification from `/specs/001-star-unstar-views/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Enable users to star and unstar GroupSearchView (issue views) with position management. This feature allows users to bookmark organization-shared or owned views, organizing them in a personally-ordered list for quick access. The implementation leverages the existing GroupSearchViewStarred model and follows Sentry's established patterns for many-to-many relationships with ordering.

## Technical Context

**Language/Version**: Python 3.13+  
**Primary Dependencies**: Django 5.2+, Django REST Framework, drf-spectacular  
**Storage**: PostgreSQL (primary database), region silo  
**Testing**: pytest with APITestCase pattern  
**Target Platform**: Linux server (Sentry backend API)  
**Project Type**: Web application (Django backend REST API)  
**Performance Goals**: Standard REST API latency (<200ms p95), support bulk operations efficiently  
**Constraints**: Multi-tenant security (organization scoping required), backwards-compatible migrations, silo architecture compliance  
**Scale/Scope**: Small feature addition - 2 new endpoints, reusing existing GroupSearchViewStarred model, approximately 200-300 lines of new code

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

### ✅ I. Convention Over Configuration

- **Status**: PASS
- **Analysis**: Feature follows existing GroupSearchView patterns. Star/unstar endpoints will mirror existing bookmark patterns (GroupBookmark, ProjectBookmark, DashboardFavoriteUser). The GroupSearchViewStarred model already exists and follows established conventions.

### ✅ II. Security by Default

- **Status**: PASS
- **Analysis**: All queries scoped to organization. Star/unstar operations require:
  - User authentication (enforced by endpoint base class)
  - Organization membership (OrganizationEndpoint)
  - View access validation (user must be able to view the GroupSearchView)
  - No direct ID trust - all queries filtered by organization_id and user_id

### ✅ III. Framework Trust

- **Status**: PASS
- **Analysis**: Using Django/DRF directly:
  - Inherit from OrganizationEndpoint (automatic permission checking)
  - Use @region_silo_endpoint decorator
  - Standard DRF serializers for input validation
  - Sentry serializer registry for output
  - No custom abstractions or framework wrappers

### ✅ IV. Batch-Aware Data Access

- **Status**: PASS
- **Analysis**:
  - Star/unstar are single-item operations by design
  - Position reordering uses bulk_update() (already exists in GroupSearchViewStarred manager)
  - List endpoints use get_attrs() pattern for batch fetching
  - No N+1 queries introduced

### ✅ V. Test-Driven with Factories

- **Status**: PASS
- **Analysis**:
  - Tests will use APITestCase pattern
  - Factory methods (self.create_user, self.create_organization)
  - Tests mirror source structure (tests/sentry/issues/endpoints/)
  - Procedural, assertion-heavy tests
  - Feature flag testing with @with_feature decorator

### ✅ VI. Incremental Delivery

- **Status**: PASS
- **Analysis**:
  - Feature gated behind existing "organizations:issue-view-sharing" flag
  - GroupSearchViewStarred model already exists (no schema changes needed)
  - Endpoints can be merged incrementally
  - Safe to deploy without activation

### Architectural Constraints

- **Silo boundaries**: ✅ All code in region silo (@region_silo_endpoint, @region_silo_model)
- **Migrations**: ✅ No migrations needed - reusing existing GroupSearchViewStarred model
- **API contracts**: ✅ camelCase responses, string IDs, "detail" key for errors

**Overall Assessment**: All gates PASS. No violations requiring justification.

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
├── models/
│   ├── groupsearchview.py              # Existing model
│   └── groupsearchviewstarred.py       # Existing model (reused)
├── issues/
│   ├── endpoints/
│   │   ├── organization_group_search_views.py                 # Existing (may need updates)
│   │   ├── organization_group_search_view_details.py          # New: Star/unstar endpoint
│   │   └── organization_group_search_view_starred_order.py    # Existing (reference)
│   └── serializers/
│       └── group_search_view.py        # Existing (may need updates)
└── api/
    ├── urls.py                         # Add new route
    └── serializers/
        └── models/
            └── groupsearchview.py      # Existing output serializer

tests/sentry/
└── issues/
    └── endpoints/
        ├── test_organization_group_search_views.py           # Existing (add tests)
        └── test_organization_group_search_view_details.py    # New: Star/unstar tests
```

**Structure Decision**: Single Django backend project. All code lives in the existing Sentry application under `src/sentry/`. Following the established pattern where GroupSearchView-related endpoints are in `src/sentry/issues/endpoints/` (region silo). Tests mirror the source structure in `tests/sentry/issues/endpoints/`.

## Complexity Tracking

> **No violations** - Constitution Check passed all gates. No additional complexity justification needed.
