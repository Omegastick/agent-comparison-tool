# Research: Star and Unstar Shared Issue Views

**Feature Branch**: `001-star-unstar-views`
**Date**: 2026-02-19

## Research Tasks & Findings

### R1: Does the GroupSearchViewStarred model already exist?

**Decision**: Yes, the model already exists and is fully functional.

**Rationale**: `GroupSearchViewStarred` is defined in `/workspace/repo/src/sentry/models/groupsearchviewstarred.py` (lines 52-75). It is a `@region_silo_model` with fields: `user_id` (HybridCloudForeignKey), `organization` (FlexibleForeignKey), `group_search_view` (FlexibleForeignKey), and `position` (PositiveSmallIntegerField). It has a deferred UniqueConstraint on `(user_id, organization_id, position)`. A custom manager `GroupSearchViewStarredManager` provides `reorder_starred_views()`. No new model or migration is needed.

**Alternatives considered**: Creating a new model was unnecessary since the existing one satisfies all spec requirements (FR-001 through FR-010).

---

### R2: What is the current starring mechanism?

**Decision**: Starring is currently embedded within the bulk PUT endpoint, not available as a standalone action.

**Rationale**: The existing `OrganizationGroupSearchViewsEndpoint` (PUT method in `src/sentry/issues/endpoints/organization_group_search_views.py`) creates `GroupSearchViewStarred` records as a side effect of bulk view creation/update. There is no dedicated star/unstar endpoint. The `__init__.py` at `src/sentry/issues/endpoints/__init__.py` line 57 references `OrganizationGroupSearchViewStarredEndpoint` in `__all__` but this class does not exist (stale forward reference). This confirms the star/unstar endpoint needs to be built.

**Alternatives considered**: Extending the existing PUT endpoint was rejected because the spec calls for single-action star/unstar operations (SC-001, SC-002), and the bulk endpoint is not suitable for starring a shared view the user doesn't own.

---

### R3: What endpoint pattern should star/unstar follow?

**Decision**: A single endpoint at `group-search-views/<view_id>/star/` supporting PUT (star) and DELETE (unstar).

**Rationale**: This follows the existing convention in the codebase:

- `group-search-views/<view_id>/visit/` uses POST for a similar user-specific action (visit tracking)
- PUT for star (with optional `position` body param) aligns with the dashboard favorite pattern (`OrganizationDashboardFavoriteEndpoint`)
- DELETE for unstar is natural REST semantics for removing a relationship
- The visit endpoint (`organization_group_search_view_visit.py`) is the closest template to follow

**Alternatives considered**:

- POST/DELETE pair: Rejected because PUT is more idempotent-friendly (FR-003) and the dashboard favorite endpoint sets the precedent
- Toggle endpoint (PUT with `isFavorited` boolean): Rejected because the spec has different semantics for star (with position) vs unstar

---

### R4: What access control rules apply?

**Decision**: A user can star any view they have access to: their own views (any visibility) OR organization-shared views (`visibility = "organization"`).

**Rationale**: The existing `GroupSearchViewStarredOrderSerializer` (in `organization_group_search_view_starred_order.py`, lines 33-38) validates access with:

```python
if gsv.user_id != self.context["user"].id and gsv.visibility != GroupSearchViewVisibility.ORGANIZATION:
    raise serializers.ValidationError("You do not have access to one or more views")
```

This same access check must be applied for the star endpoint (FR-008, FR-010).

**Alternatives considered**: None - the existing pattern is the canonical access check.

---

### R5: What feature flag should gate the new endpoint?

**Decision**: Use `organizations:issue-view-sharing` feature flag.

**Rationale**: The starred order endpoint already uses this flag (`organization_group_search_view_starred_order.py`, line 50). The star/unstar feature is part of the view sharing capability - it lets users star shared views. Using the same flag ensures consistent feature rollout.

**Alternatives considered**: `organizations:issue-stream-custom-views` was considered but that gates the base views CRUD, not the sharing/starring extensions.

---

### R6: How should position management work for starring?

**Decision**: When no position is provided, append to the end (max position + 1). When a position is provided, shift existing views at that position and above by +1, then insert.

**Rationale**: This directly satisfies FR-005, FR-006, FR-007. The existing delete handler in `organization_group_search_view_details.py` (lines 55-60) shows the gap-filling pattern using `F("position") - 1`. The insert pattern is the inverse: shift using `F("position") + 1` for positions >= target, then insert.

**Alternatives considered**: Sparse position numbering (e.g., positions 0, 10, 20) was rejected because the existing codebase uses contiguous zero-based positions throughout.

---

### R7: How should idempotency be handled?

**Decision**: Starring an already-starred view returns success (200) with no state change. Unstarring a non-starred view returns success (204) with no state change.

**Rationale**: FR-003 and FR-004 explicitly require idempotent behavior. For star: check if `GroupSearchViewStarred` already exists for this user+view; if yes, return current state. For unstar: if no record found, return 204 silently. This matches patterns like `create_or_update` used throughout the codebase.

**Alternatives considered**: Returning 409 Conflict for duplicate stars was rejected because the spec explicitly says "does nothing and returns success."

---

### R8: What permission scope should the endpoint use?

**Decision**: `MemberPermission` with `scope_map = {"PUT": ["member:read", "member:write"], "DELETE": ["member:read", "member:write"]}`.

**Rationale**: All existing GroupSearchView mutation endpoints use `member:read` + `member:write` scopes because these are user-personal resources. The star/unstar endpoint modifies the user's own starred list, which is consistent with this scope level.

**Alternatives considered**: Using `org:write` was rejected because it's too restrictive for a personal preference action.

---

### R9: Edge case - starring a deleted view

**Decision**: Return 404 if the view doesn't exist.

**Rationale**: The visit endpoint (`organization_group_search_view_visit.py`, lines 39-42) uses `GroupSearchView.objects.get(id=view_id, organization=organization)` and returns 404 on `DoesNotExist`. The star endpoint should follow the same pattern.

---

### R10: Edge case - position larger than list size

**Decision**: Clamp to the end of the list (max position + 1). If position is 10 but only 3 views exist, insert at position 3.

**Rationale**: This is the most user-friendly behavior and avoids sparse position gaps. The deferred UniqueConstraint on position requires contiguous values.

---

### R11: Edge case - concurrent star requests at same position

**Decision**: Wrap in `transaction.atomic()` with `router.db_for_write()`. The deferred UniqueConstraint will catch any violations, returning a 409 or 400.

**Rationale**: The starred order endpoint (`organization_group_search_view_starred_order.py`, lines 62-63) uses this exact pattern: `transaction.atomic(using=router.db_for_write(GroupSearchViewStarred))`. IntegrityError is caught and returned as 400.

---

## Summary of Technical Decisions

| Aspect             | Decision                                                             |
| ------------------ | -------------------------------------------------------------------- |
| Model              | Reuse existing `GroupSearchViewStarred` - no new model needed        |
| Migration          | None required                                                        |
| Endpoint file      | `src/sentry/issues/endpoints/organization_group_search_view_star.py` |
| URL                | `group-search-views/<view_id>/star/`                                 |
| HTTP methods       | PUT (star with optional position), DELETE (unstar)                   |
| Feature flag       | `organizations:issue-view-sharing`                                   |
| Permission         | `MemberPermission` with `member:read`, `member:write`                |
| Publish status     | `EXPERIMENTAL`                                                       |
| Access check       | User owns view OR view visibility is `"organization"`                |
| Position on star   | Default to end; shift others if position specified                   |
| Position on unstar | Decrement positions above deleted position                           |
| Idempotency        | Star existing = no-op success; Unstar non-existing = no-op success   |
| Atomicity          | `transaction.atomic()` for position mutations                        |
