# Research: Star and Unstar Shared Issue Views

**Feature**: 001-star-unstar-views  
**Date**: 2026-02-19  
**Status**: Complete

## Overview

This document consolidates research findings for implementing star/unstar functionality for GroupSearchView (issue views). The research focused on understanding existing patterns, identifying reusable components, and determining best practices for the implementation.

## Key Decisions

### Decision 1: Reuse Existing GroupSearchViewStarred Model

**Decision**: Use the existing `GroupSearchViewStarred` model without modifications.

**Rationale**:

- Model already exists in the codebase (`src/sentry/models/groupsearchviewstarred.py`)
- Designed specifically for this use case (many-to-many relationship with position tracking)
- Includes all necessary fields: `user_id`, `organization`, `group_search_view`, `position`
- Has custom manager with reordering logic already implemented
- Follows Sentry conventions (region silo, proper constraints, RelocationScope)

**Alternatives Considered**:

- **Create new StarredView model**: Rejected because GroupSearchViewStarred already exists and serves the exact purpose
- **Add starred flag to GroupSearchView**: Rejected because it wouldn't support multiple users starring the same view with different positions
- **Use separate UserPreference system**: Rejected because it's less type-safe and doesn't support the relationship model needed

**Implementation Notes**:

- Table: `sentry_groupsearchviewstarred`
- Unique constraint: `(user_id, organization_id, position)` with DEFERRED deferrable
- Custom manager: `GroupSearchViewStarredManager` with `reorder_starred_views()` method
- No database migrations required

---

### Decision 2: Create Separate Star/Unstar Endpoint Pattern

**Decision**: Implement star/unstar as operations on the view details endpoint pattern, using POST/DELETE methods on a sub-resource.

**Rationale**:

- Follows REST principles (star/unstar are actions on a specific resource)
- Consistent with Sentry's existing bookmark patterns (ProjectBookmark, GroupBookmark)
- Allows for future extensibility (e.g., adding metadata to starred views)
- Clear, discoverable API surface
- Supports idempotent operations naturally

**URL Pattern**:

```
POST   /organizations/{org}/group-search-views/{view_id}/star/
DELETE /organizations/{org}/group-search-views/{view_id}/star/
```

**Alternatives Considered**:

- **PATCH on view details with `isStarred` field**: Rejected because it couples starring to view updates and doesn't fit the operational nature of star/unstar
- **Bulk star endpoint**: Rejected for initial implementation (can be added later if needed)
- **Single toggle endpoint**: Rejected because separate POST/DELETE is more RESTful and clearer about intent

**Related Existing Patterns**:

- `ProjectBookmark`: Uses PUT on project details with `isBookmarked` field
- `DashboardFavoriteUser`: No dedicated endpoint, managed through dashboard CRUD
- **Chosen approach** is more explicit and follows modern REST practices

---

### Decision 3: Position Management Strategy

**Decision**: Support optional position parameter on star, default to end-of-list if not provided. Use existing reorder endpoint for bulk reordering.

**Rationale**:

- Matches feature requirements (FR-005, FR-006, FR-007)
- Leverages existing `OrganizationGroupSearchViewStarredOrderEndpoint` for reordering
- Keeps star/unstar operations simple (single-item focus)
- Automatic position adjustment on unstar maintains list integrity
- Follows established pattern in the codebase

**Position Handling**:

1. **Star without position**: Append to end (max position + 1)
2. **Star with position**: Insert at position, shift others down
3. **Unstar**: Remove and decrement positions > deleted position
4. **Bulk reorder**: Use existing `/group-search-views-starred-order/` endpoint

**Implementation Details**:

```python
# On star with position
with transaction.atomic():
    # Shift existing positions >= target position
    GroupSearchViewStarred.objects.filter(
        organization=org,
        user_id=user_id,
        position__gte=target_position,
    ).update(position=F("position") + 1)

    # Create new starred entry
    GroupSearchViewStarred.objects.create(
        organization=org,
        user_id=user_id,
        group_search_view=view,
        position=target_position,
    )

# On unstar
with transaction.atomic():
    deleted_position = starred.position
    starred.delete()

    # Decrement positions after deleted item
    GroupSearchViewStarred.objects.filter(
        organization=org,
        user_id=user_id,
        position__gt=deleted_position,
    ).update(position=F("position") - 1)
```

**Alternatives Considered**:

- **No position management**: Rejected because it's a core requirement (P2 priority)
- **Rebuild positions on every operation**: Rejected because it's inefficient and unnecessary
- **Fractional positions**: Rejected because it complicates queries and has edge cases

---

### Decision 4: Permission and Access Control Strategy

**Decision**: Validate view access before allowing star/unstar operations. Use existing view visibility rules.

**Rationale**:

- Security requirement (FR-008, FR-010)
- Prevents users from discovering private views by attempting to star them
- Consistent with Sentry's multi-tenant security model (Constitution Principle II)
- Reuses existing GroupSearchView access logic

**Access Rules**:

1. User must be authenticated
2. User must be member of the view's organization
3. View must be accessible to user based on visibility:
   - `OWNER`: Only the owner can access
   - `ORGANIZATION`: Any org member can access
4. View must exist and not be deleted

**Implementation Pattern**:

```python
# Get view with organization scoping
try:
    view = GroupSearchView.objects.get(
        id=view_id,
        organization=organization,  # From OrganizationEndpoint
    )
except GroupSearchView.DoesNotExist:
    return Response({"detail": "View not found"}, status=404)

# Check visibility
if view.visibility == GroupSearchViewVisibility.OWNER:
    if view.user_id != request.user.id:
        return Response({"detail": "Permission denied"}, status=403)
# ORGANIZATION visibility allows all org members (already validated by endpoint base class)
```

**Alternatives Considered**:

- **Separate permission class**: Rejected because the logic is simple enough to inline
- **Allow starring any view ID**: Rejected due to security concerns (information disclosure)
- **Only allow starring organization views**: Rejected because users should be able to star their own views (FR-004)

---

### Decision 5: Idempotency Handling

**Decision**: Make star and unstar operations fully idempotent. Return success (200/204) even if state doesn't change.

**Rationale**:

- Explicit requirement (FR-003, FR-004)
- Improves reliability for clients (network retries safe)
- Simplifies client-side logic (no need to check current state)
- Follows Sentry's existing bookmark patterns (ProjectBookmark uses try/except IntegrityError)

**Implementation**:

```python
# Star (idempotent)
starred, created = GroupSearchViewStarred.objects.get_or_create(
    organization=organization,
    user_id=request.user.id,
    group_search_view=view,
    defaults={"position": calculated_position},
)
if not created:
    # Already starred - no-op, still return success
    return Response(status=204)

# Unstar (idempotent)
deleted_count = GroupSearchViewStarred.objects.filter(
    organization=organization,
    user_id=request.user.id,
    group_search_view=view,
).delete()
# Always return success, regardless of deleted_count
return Response(status=204)
```

**Alternatives Considered**:

- **Return 409 Conflict for duplicate star**: Rejected because it breaks idempotency and complicates clients
- **Return different status codes**: Rejected because it adds unnecessary complexity
- **Update position on duplicate star**: Considered but rejected to keep star operation simple (use reorder endpoint for position changes)

---

## Technology Stack Summary

| Component     | Technology            | Version | Notes                       |
| ------------- | --------------------- | ------- | --------------------------- |
| Language      | Python                | 3.13+   | Sentry requirement          |
| Framework     | Django                | 5.2+    | Core framework              |
| API Framework | Django REST Framework | Latest  | With drf-spectacular        |
| Database      | PostgreSQL            | Latest  | Primary database            |
| Task Queue    | Celery                | 5.5+    | Not needed for this feature |
| Testing       | pytest                | Latest  | With APITestCase            |
| Architecture  | Region Silo           | N/A     | All models and endpoints    |

---

## Existing Patterns and References

### Similar Features in Codebase

1. **GroupBookmark** (`src/sentry/models/groupbookmark.py`)
   - Simple many-to-many relationship
   - No position management
   - Uses get_or_create/delete pattern

2. **ProjectBookmark** (`src/sentry/models/projectbookmark.py`)
   - Managed via PUT on project details
   - Uses IntegrityError handling for idempotency
   - No separate endpoint

3. **DashboardFavoriteUser** (`src/sentry/models/dashboard.py`)
   - Managed via property setter on Dashboard model
   - Bulk operations in setter
   - No dedicated endpoint

4. **GroupSearchViewStarred** (our target model)
   - Most sophisticated pattern
   - Position management with custom manager
   - Separate reorder endpoint
   - **This is the pattern we'll follow**

### Relevant Existing Endpoints

1. **OrganizationGroupSearchViewsEndpoint**
   - Location: `src/sentry/issues/endpoints/organization_group_search_views.py`
   - Methods: GET (list), PUT (bulk update)
   - Pattern: Organization-scoped, feature-flagged
   - Reference for error handling and serialization

2. **OrganizationGroupSearchViewDetailsEndpoint**
   - Location: `src/sentry/issues/endpoints/organization_group_search_view_details.py`
   - Methods: GET, PUT, DELETE
   - **This is where we'll add star/unstar**

3. **OrganizationGroupSearchViewStarredOrderEndpoint**
   - Location: `src/sentry/issues/endpoints/organization_group_search_view_starred_order.py`
   - Method: PUT
   - Handles bulk reordering of starred views
   - Reference for position management patterns

### Testing Patterns

**Location**: `tests/sentry/issues/endpoints/test_organization_group_search_view_starred_order.py`

**Key Patterns**:

- Use `APITestCase` with `endpoint` and `method` attributes
- `self.get_success_response()` and `self.get_error_response()` helpers
- Factory methods for test data setup
- `@with_feature` decorator for feature flags
- Atomic operations testing with transaction.atomic()
- Position verification after operations

---

## Best Practices Applied

### From Constitution

1. **Convention Over Configuration** (Principle I)
   - Using existing OrganizationEndpoint base class
   - Following established URL patterns
   - Mirroring existing bookmark implementations

2. **Security by Default** (Principle II)
   - Organization scoping on all queries
   - View access validation before operations
   - No trust of user-supplied IDs

3. **Framework Trust** (Principle III)
   - Using Django ORM directly
   - DRF serializers for validation
   - No custom abstractions

4. **Batch-Aware Data Access** (Principle IV)
   - Single-item operations don't require batching
   - Position updates use F() expressions for atomicity
   - List endpoints will use get_attrs() for related data

5. **Test-Driven with Factories** (Principle V)
   - APITestCase pattern
   - Factory methods for setup
   - Procedural tests

6. **Incremental Delivery** (Principle VI)
   - Feature flagged with `organizations:issue-view-sharing`
   - No schema changes required
   - Safe to merge incrementally

### From AGENTS.md

1. **API Design Rules**
   - snake_case for URL params (`view_id`)
   - camelCase for request/response bodies
   - String IDs in responses
   - "detail" key for errors

2. **Model Patterns**
   - @region_silo_model decorator
   - Proper RelocationScope
   - FlexibleForeignKey and HybridCloudForeignKey

3. **Endpoint Patterns**
   - @region_silo_endpoint decorator
   - publish_status with ApiPublishStatus
   - owner field for team ownership
   - permission_classes declaration

4. **Transaction Safety**
   - Use transaction.atomic(router.db_for_write(Model))
   - Handle IntegrityError gracefully
   - Atomic position adjustments with F() expressions

---

## Open Questions Resolved

### Q1: Should we allow starring deleted views?

**Answer**: No. Validate view exists before starring. If a starred view is deleted, the cascade delete on GroupSearchViewStarred will handle cleanup.

### Q2: Should we allow starring views from other organizations?

**Answer**: No. All operations scoped to the organization in the URL path. This is enforced by OrganizationEndpoint base class and explicit organization filtering.

### Q3: What happens on concurrent position conflicts?

**Answer**: PostgreSQL's DEFERRED constraint on `(user_id, organization_id, position)` handles this. Within a transaction, temporary duplicates are allowed, but they'll be resolved or fail at commit time. For this feature, we use atomic transactions with position shifting, minimizing conflict windows.

### Q4: Should unstar reorder remaining positions?

**Answer**: Yes. Decrement all positions > deleted position to maintain contiguous positions. This prevents gaps and simplifies list display logic.

### Q5: What's the maximum number of starred views?

**Answer**: No explicit limit. Position is PositiveSmallIntegerField (max 32767), which is more than sufficient. If needed, a soft limit can be added later via feature flag configuration.

### Q6: Should we support starring views at position 0?

**Answer**: No. Positions are 0-indexed internally, so position 0 is valid. The first view has position 0, second has position 1, etc.

### Q7: Do we need to handle view deletion specially?

**Answer**: No. GroupSearchViewStarred has `FlexibleForeignKey("sentry.GroupSearchView")` with default CASCADE delete. When a view is deleted, all stars are automatically removed. No special handling needed.

---

## Performance Considerations

### Database Queries

**Star operation** (without position):

1. SELECT to validate view exists and access (1 query)
2. SELECT MAX(position) for user's starred views (1 query)
3. INSERT starred record (1 query)
   **Total**: 3 queries

**Star operation** (with position):

1. SELECT to validate view exists and access (1 query)
2. UPDATE positions >= target (1 query, affects N records)
3. INSERT starred record (1 query)
   **Total**: 3 queries + O(N) for position shifting

**Unstar operation**:

1. SELECT to validate view exists and access (1 query)
2. DELETE starred record (1 query)
3. UPDATE positions > deleted (1 query, affects N records)
   **Total**: 3 queries + O(N) for position shifting

### Optimization Notes

- Position shifting uses F() expressions for atomic updates
- All operations wrapped in atomic transactions
- Unique constraint with DEFERRED allows temporary duplicates during transaction
- No N+1 queries (single-item operations)
- Could add index on `(user_id, organization_id, position)` if needed (may already exist via unique constraint)

### Scale Estimates

Assuming average user has 10-20 starred views:

- Star/unstar latency: 5-10ms (3 queries + position updates)
- 99th percentile: <20ms
- Well within <200ms p95 requirement

---

## Migration Strategy

**Required Migrations**: None

**Reason**: GroupSearchViewStarred model already exists in production. This feature only adds new endpoints to interact with the existing model.

**Deployment Plan**:

1. Merge star/unstar endpoint code (behind feature flag)
2. Test in staging with feature flag enabled
3. Gradually roll out feature flag to production organizations
4. Monitor error rates and performance
5. Enable for all organizations if metrics are good

**Rollback Plan**:

- Disable feature flag immediately if issues arise
- No data migration rollback needed (model unchanged)
- Can safely revert code changes

---

## Feature Flag

**Flag**: `organizations:issue-view-sharing`

**Status**: Already exists (used by existing GroupSearchView endpoints)

**Scope**: Organization-level feature flag

**No new flag needed** - reuse existing flag for consistency.

---

## Summary

All technical uncertainties have been resolved. The implementation plan can proceed with:

1. **Reuse** GroupSearchViewStarred model (no changes needed)
2. **Create** two new endpoints: POST/DELETE star sub-resource on view details
3. **Implement** position management with atomic transactions
4. **Validate** access before all operations
5. **Ensure** idempotency for star and unstar
6. **Test** using APITestCase pattern with existing feature flag
7. **Deploy** incrementally behind existing feature flag

No blockers identified. Ready for Phase 1 (Design & Contracts).
