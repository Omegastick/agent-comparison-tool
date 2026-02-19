# Implementation Plan: Star and Unstar Shared Issue Views

**Branch**: `001-star-unstar-views` | **Date**: 2026-02-19 | **Spec**: /workspace/repo/specs/001-star-unstar-views/spec.md
**Input**: Feature specification from `/specs/001-star-unstar-views/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Enable users to bookmark (star) and unbookmark (unstar) issue search views with optional position management. Users can star any view they have access to (owned or organization-shared) and organize starred views in an ordered list. The feature provides idempotent star/unstar operations with proper authorization checks and position ordering persistence.

## Technical Context

**Language/Version**: Python 3.13+  
**Primary Dependencies**: Django 5.2+, Django REST Framework, drf-spectacular  
**Storage**: PostgreSQL (primary database for starred view relationships and position ordering)  
**Testing**: pytest with Sentry's APITestCase framework  
**Target Platform**: Linux server (Sentry region silo)  
**Project Type**: Web application (backend API endpoints)  
**Performance Goals**: Standard API response times (<200ms p95 for star/unstar operations)  
**Constraints**: Multi-tenant security (organization-scoped access), idempotent operations, atomic position updates  
**Scale/Scope**: Supports Sentry's existing user base, bounded by users × views per organization (expected: thousands of starred relationships per organization)

**Unknowns requiring research**:

- NEEDS CLARIFICATION: Does GroupSearchView model already exist? Location and structure?
- NEEDS CLARIFICATION: Existing authorization patterns for view access (owned vs organization-shared)?
- NEEDS CLARIFICATION: Current endpoint patterns for GroupSearchView operations?
- NEEDS CLARIFICATION: Position management strategy - separate position field or ordered list pattern?
- NEEDS CLARIFICATION: Race condition handling for concurrent position updates?

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

### I. Convention Over Configuration

**Initial Status**: ✅ PASS (Pending research validation)  
**Post-Design Status**: ✅ PASS ✓

- ✓ Follows existing OrganizationEndpoint pattern
- ✓ Mirrors structure of existing GroupSearchViewStarred model and endpoints
- ✓ Uses standard GroupSearchViewStarredSerializer for output
- ✓ Follows MemberPermission pattern from existing group search view endpoints
- **Research confirmed**: GroupSearchViewStarred already exists with comprehensive starring system

### II. Security by Default

**Initial Status**: ✅ PASS  
**Post-Design Status**: ✅ PASS ✓

- ✓ Star/unstar operations validate user access (owned OR organization-shared)
- ✓ Database queries scoped by organization + user_id
- ✓ Uses declarative MemberPermission with member:read/write scopes
- ✓ Returns 404 for non-existent views, 403 for unauthorized access
- ✓ FR-008 and FR-010 fully satisfied

### III. Framework Trust

**Initial Status**: ✅ PASS  
**Post-Design Status**: ✅ PASS ✓

- ✓ Inherits from OrganizationEndpoint base class
- ✓ Uses Django ORM (update_or_create, F() expressions) and DRF serializers directly
- ✓ Applies @region_silo_endpoint decorator
- ✓ GroupSearchView confirmed as @region_silo_model
- ✓ No custom abstractions - pure Django/DRF patterns

### IV. Batch-Aware Data Access

**Initial Status**: ✅ PASS  
**Post-Design Status**: ✅ PASS ✓

- ✓ GroupSearchViewStarredSerializer.get_attrs() implements batch-fetching for lastVisited
- ✓ Uses select_related() and prefetch_related() for related data
- ✓ Position updates use bulk_update() (single query)
- ✓ F() expressions for atomic position adjustments
- ✓ No N+1 queries in design

### V. Test-Driven with Factories

**Initial Status**: ✅ PASS  
**Post-Design Status**: ✅ PASS ✓

- ✓ Will use APITestCase with factory methods (self.create_user(), self.create_organization())
- ✓ Tests mirror source structure: src/sentry/issues/endpoints/ → tests/sentry/issues/endpoints/
- ✓ Procedural pytest-style tests with comprehensive coverage planned
- ✓ All acceptance scenarios from spec covered in test plan
- ✓ Existing tests for GroupSearchViewStarred serve as reference

### VI. Incremental Delivery

**Initial Status**: ✅ PASS (if feature flag used)  
**Post-Design Status**: ✅ PASS ✓

- ✓ Will gate behind existing feature flag: 'organizations:issue-stream-custom-views'
- ✓ Organization-shared views additionally gated by 'organizations:issue-view-sharing'
- ✓ Endpoints marked as ApiPublishStatus.EXPERIMENTAL for safe rollout
- ✓ New endpoints can merge without breaking existing bulk operations

### Architectural Constraints

**Initial Status**: ✅ PASS (Pending research validation)  
**Post-Design Status**: ✅ PASS ✓

- ✓ Uses @region_silo_model and @region_silo_endpoint (confirmed in research)
- ✓ No migrations required - uses existing GroupSearchViewStarred table
- ✓ API contract follows conventions: camelCase responses, string IDs, "detail" for errors
- ✓ Backwards compatible - additive endpoints only

### Summary

**Pre-Research Gate**: ✅ PASS - No constitutional violations identified. All principles can be satisfied with standard patterns. Unknowns in Technical Context will be resolved during Phase 0 research.

**Post-Design Gate**: ✅ PASS ✓ - All research completed. All constitutional principles confirmed satisfied:

- No custom abstractions - uses existing Sentry patterns
- Security-first design with proper tenant boundaries
- Batch-aware serialization prevents N+1 queries
- Test-driven approach with comprehensive coverage
- Feature-flagged for incremental delivery
- Backwards compatible with existing infrastructure

**Changes from Initial Assessment**: Research revealed that GroupSearchViewStarred model and comprehensive starring infrastructure already exist. New endpoints integrate seamlessly with existing patterns. No architectural changes needed.

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
│   └── starred_group_search_view.py  # New model for star relationships
├── api/
│   ├── endpoints/
│   │   ├── organization_group_search_view_star.py  # Star endpoint
│   │   └── organization_group_search_view_unstar.py  # Unstar endpoint
│   └── serializers/
│       └── models/
│           └── starred_group_search_view.py  # Output serializer
└── issues/
    └── endpoints/  # Alternative location if views live in issues domain

tests/sentry/
├── models/
│   └── test_starred_group_search_view.py  # Model tests
└── api/
    └── endpoints/
        ├── test_organization_group_search_view_star.py  # Star endpoint tests
        └── test_organization_group_search_view_unstar.py  # Unstar endpoint tests

migrations/
└── sentry/
    └── 0xxx_add_starred_group_search_view.py  # Database migration
```

**Structure Decision**: This feature adds new API endpoints to the existing Sentry Django application. Following Sentry conventions:

- Models in `src/sentry/models/` as standalone entity files
- API endpoints in `src/sentry/api/endpoints/` with resource-specific naming
- Serializers in `src/sentry/api/serializers/models/` following the registry pattern
- Tests mirror source structure exactly
- May need to adjust paths based on Phase 0 research findings about GroupSearchView location

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

**Status**: No violations - this section intentionally left empty.

All constitutional principles are satisfied using standard Sentry patterns. No custom abstractions or architectural deviations are required.
