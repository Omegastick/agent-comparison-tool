# Implementation Plan: Star and Unstar Shared Issue Views

**Branch**: `001-star-unstar-views` | **Date**: 2026-02-19 | **Spec**: /workspace/repo/specs/001-star-unstar-views/spec.md
**Input**: Feature specification from `/workspace/repo/specs/001-star-unstar-views/spec.md`

This plan implements per-user starring and unstarring of GroupSearchView entities with stable, position-aware ordering. The implementation follows Sentry backend conventions (Django + DRF, region-silo), uses transactional position management to avoid races, and preserves backward-compatible migrations.

## Technical Context

**Language/Version**: Python 3.13 (Django 5.2+ codebase)  
**Primary Dependencies**: Django 5.2+, Django REST Framework, sentry internal libs (FlexibleForeignKey, HybridCloudForeignKey), celery (if async work needed)  
**Storage**: PostgreSQL (primary), Redis for cache/locking (optional)  
**Testing**: pytest with sentry.testutils, factory-based fixtures (use provided factories)  
**Target Platform**: Linux server (region silo)  
**Project Type**: backend (Django app inside `src/sentry/`)  
**Performance Goals**: Typical user operations should be low-latency; target p95 < 200ms for star/unstar endpoints under normal load. Position reordering operations should scale to users with hundreds of starred views with acceptable latency (sub-second).  
**Constraints**: Migrations must be backwards compatible; all DB queries scoped by organization and user; follow batch-aware data access and avoid N+1 queries; changes must be feature-flag gated for incremental rollout.  
**Scale/Scope**: Per-user starred lists are expected to be small (dozens to a few hundred items). System must support orgs with millions of views but per-user operations remain bounded by the user's starred list size.

## Constitution Check

Gates (all must pass to proceed):

- Conform to Sentry conventions (endpoints, serializers, tests): WILL COMPLY — Implementation will mirror existing endpoints for saved views and use OrganizationEndpoint / region_silo_endpoint patterns.
- Security by Default (tenant scoping): WILL COMPLY — All queries will include organization/user scoping and use existing permission classes.
- Framework Trust (use DRF/Django primitives): WILL COMPLY — Use OrganizationEndpoint, DRF serializers, and Sentry serializers where appropriate.
- Batch-Aware Data Access: WILL COMPLY — List endpoints will batch-fetch related GroupSearchView data in serializers' get_attrs to avoid N+1.
- Test-Driven with Factories: WILL COMPLY — Tests will use provided factory helpers and follow existing test patterns.
- Incremental Delivery: WILL COMPLY — Feature will be gate-flagged and safe to merge behind a feature flag.

All gates are satisfied by design and do not require exceptions. Proceeding to research and design.

## Project Structure

Documentation (this feature):

```text
/workspace/repo/specs/001-star-unstar-views/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
└── tasks.md (Phase 2)
```

Source code (implementation targets inside repository):

```text
src/sentry/models/starred.py             # new model (region_silo_model)
src/sentry/api/endpoints/starred_views.py# endpoints for star/unstar/list
src/sentry/api/serializers/starred.py    # DRF input serializers + Sentry serializers
tests/sentry/api/endpoints/test_starred_views.py
```

**Structure Decision**: Implement as a small, self-contained region-silo Django app module inside `src/sentry/` so it integrates with existing models (`GroupSearchView`) and permission helpers.

## Complexity Tracking

No constitution violations detected that require justification.
