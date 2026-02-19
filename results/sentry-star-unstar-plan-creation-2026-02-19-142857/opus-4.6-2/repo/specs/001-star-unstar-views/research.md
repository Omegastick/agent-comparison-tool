# Research: Star and Unstar Shared Issue Views

**Feature Branch**: `001-star-unstar-views`
**Date**: 2026-02-19

## Research Tasks

### R1: Existing Model for Starred Views

**Question**: Does a model for starring views already exist, or does one need to be created?

**Decision**: Use the existing `GroupSearchViewStarred` model.

**Rationale**: The model already exists at `src/sentry/models/groupsearchviewstarred.py` with all required fields: `user_id`, `organization`, `group_search_view`, and `position`. It has a deferred unique constraint on `(user_id, organization_id, position)` and a custom manager with `reorder_starred_views()`. No new model or migration is needed.

**Alternatives considered**:

- Creating a new join model: Rejected — `GroupSearchViewStarred` already serves this exact purpose.
- Adding a boolean `is_starred` field to `GroupSearchView`: Rejected — starring is per-user, not per-view. A join table is the correct pattern.

---

### R2: Missing Endpoint for Independent Star/Unstar

**Question**: How do users currently star/unstar views, and what gap exists?

**Decision**: A new dedicated endpoint is needed at `PUT/DELETE /organizations/{org}/group-search-views/{view_id}/starred/`.

**Rationale**: Currently, starring happens implicitly:

- **Starring via bulk PUT**: `PUT /organizations/{org}/group-search-views/` creates `GroupSearchViewStarred` entries as a side effect of creating/updating views (`_create_view()` and `_update_existing_view()` in `organization_group_search_views.py`).
- **Unstarring via delete**: `DELETE /organizations/{org}/group-search-views/{view_id}/` removes the starred entry as a side effect of deleting the view entirely.

There is **no way** to:

1. Star a shared view (one created by another user with `visibility=organization`) without the bulk PUT endpoint, which only manages the user's own views.
2. Unstar a view without deleting it entirely.

The `__init__.py` in `src/sentry/issues/endpoints/` already lists `OrganizationGroupSearchViewStarredEndpoint` in `__all__` (line 57) but doesn't import it — confirming this endpoint is planned but not yet implemented.

**Alternatives considered**:

- Extending the existing bulk PUT endpoint: Rejected — the bulk PUT is designed for managing owned views, not for starring arbitrary shared views. Adding star/unstar semantics would conflate two different operations.
- Adding to the details endpoint: Rejected — the details endpoint manages view CRUD, not the starring relationship. A user should be able to unstar without deleting.

---

### R3: Position Management Strategy for Star Operation

**Question**: How should position be assigned when starring a view, and how should positions shift?

**Decision**:

- **Without position**: Append at end (`max(position) + 1` or `0` if no starred views).
- **With position**: Insert at specified position, shift all views at `position >= specified` up by 1 using `F("position") + 1`.

**Rationale**: This mirrors the existing delete pattern in `organization_group_search_view_details.py` (lines 55-60) which decrements positions after removal. The insert is the inverse operation. The deferred unique constraint on `(user_id, organization_id, position)` allows position shifts within a `transaction.atomic` block without violating uniqueness mid-transaction.

**Alternatives considered**:

- Sparse positioning (e.g., positions 10, 20, 30): Rejected — the codebase uses dense sequential positions everywhere. Would require rewriting the reorder endpoint and all existing logic.
- Fractional positioning: Rejected — existing `PositiveSmallIntegerField` only supports integers. All existing code assumes dense integer positions.

---

### R4: Access Control for Shared Views

**Question**: What access control is needed to star shared views from other users?

**Decision**: A user can star a view if:

1. The view belongs to the same organization, AND
2. The view is owned by the user (`user_id == request.user.id`), OR the view has `visibility = GroupSearchViewVisibility.ORGANIZATION`.

**Rationale**: This matches the access validation in `OrganizationGroupSearchViewStarredOrderEndpoint` (lines 33-38 in `organization_group_search_view_starred_order.py`), which checks `gsv.user_id != user.id and gsv.visibility != GroupSearchViewVisibility.ORGANIZATION`. A user should not be able to star another user's private view.

**Alternatives considered**:

- Organization membership check only: Rejected — private views (`visibility=owner`) should not be starrable by other users.
- Project-level access checks: Rejected — view access is org-level, not project-level. The existing pattern does not check project membership.

---

### R5: Feature Flag Gating

**Question**: Which feature flag should gate the new endpoint?

**Decision**: Gate behind `organizations:issue-view-sharing`.

**Rationale**: The star/unstar endpoint is most relevant in the context of shared views — users star views shared by others. The existing `OrganizationGroupSearchViewStarredOrderEndpoint` is also gated behind `organizations:issue-view-sharing`. Using the same flag ensures the feature is enabled/disabled as a cohesive unit.

**Alternatives considered**:

- `organizations:issue-stream-custom-views`: This is the base feature flag for custom views. The star/unstar endpoint is an extension of the sharing feature, not the base views feature. Using this broader flag would expose the endpoint before the sharing feature is ready.
- A new feature flag: Rejected — adding unnecessary feature flags increases operational complexity. The existing `issue-view-sharing` flag precisely covers this use case.

---

### R6: Idempotency Behavior

**Question**: How should the endpoint handle idempotent star/unstar requests?

**Decision**:

- **Star (PUT) when already starred**: Return `200 OK` with the current starred view data. Do not create a duplicate or change position.
- **Unstar (DELETE) when not starred**: Return `204 No Content`. No error.

**Rationale**: FR-003 and FR-004 explicitly require idempotent behavior. The `DashboardFavoriteEndpoint` (in `organization_dashboard_details.py` lines 226-234) returns `204` when already in the desired state. The star endpoint should return `200` on re-star to provide the caller with the current position data.

**Alternatives considered**:

- Return `409 Conflict` on duplicate star: Rejected — spec explicitly requires idempotent behavior.
- Return `404 Not Found` on unstar of non-starred: Rejected — spec requires idempotent success.

---

### R7: Edge Case - Starring a Deleted View

**Question**: What happens when a user tries to star a view that has been deleted?

**Decision**: Return `404 Not Found`. The view lookup (`GroupSearchView.objects.get(id=view_id, organization=organization)`) will raise `DoesNotExist`, and the endpoint returns 404.

**Rationale**: Consistent with `OrganizationGroupSearchViewDetailsEndpoint.delete()` which returns 404 for nonexistent views.

---

### R8: Edge Case - Position Exceeds List Size

**Question**: What happens if a user specifies a position larger than their current starred list size?

**Decision**: Clamp the position to the end of the list (i.e., `min(requested_position, current_count)`). This effectively appends the view.

**Rationale**: This is the least surprising behavior. Specifying position=100 when you have 3 items should add at position 3, not create a gap. The dense position scheme does not support gaps.

**Alternatives considered**:

- Return `400 Bad Request`: Rejected — overly strict for a convenience parameter. The intent is clear.
- Create gaps: Rejected — violates the dense position invariant maintained by all existing code.

---

### R9: Edge Case - Concurrent Star at Same Position

**Question**: What happens if two concurrent requests try to star different views at the same position?

**Decision**: The deferred unique constraint on `(user_id, organization_id, position)` will cause one transaction to fail with `IntegrityError`. The failing request returns `409 Conflict` or `400 Bad Request`. Client should retry.

**Rationale**: The existing starred order endpoint handles `IntegrityError` by returning `400`. This is a standard optimistic concurrency pattern. The deferred constraint ensures the check happens at commit time.

---

## Summary

All NEEDS CLARIFICATION items have been resolved. Key decisions:

1. **No new model** — `GroupSearchViewStarred` already exists
2. **No new migration** — table and constraints already exist
3. **New endpoint**: `PUT/DELETE /organizations/{org}/group-search-views/{view_id}/starred/`
4. **Feature flag**: `organizations:issue-view-sharing`
5. **Position management**: Append-at-end default, insert-at-position with shift, clamping for out-of-bounds
6. **Access control**: Organization-scoped + visibility check (owned or organization-visible)
7. **Idempotent**: Star returns success if already starred; unstar returns success if not starred
