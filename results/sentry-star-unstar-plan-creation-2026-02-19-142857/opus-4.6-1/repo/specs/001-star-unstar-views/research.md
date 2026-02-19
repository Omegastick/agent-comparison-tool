# Research: Star and Unstar Shared Issue Views

**Feature Branch**: `001-star-unstar-views`
**Date**: 2026-02-19

## Research Questions & Findings

### RQ-1: Does the `GroupSearchViewStarred` model already exist?

**Decision**: Yes — the model exists and is fully functional.

**Rationale**: `GroupSearchViewStarred` at `src/sentry/models/groupsearchviewstarred.py` already provides:

- `user_id` (HybridCloudForeignKey), `organization` (FlexibleForeignKey), `group_search_view` (FlexibleForeignKey), `position` (PositiveSmallIntegerField)
- A deferred unique constraint on `(user_id, organization_id, position)` to allow atomic reordering
- A custom manager with `reorder_starred_views()` for bulk position updates
- `DefaultFieldsModel` base providing `date_added` and `date_updated`

**Alternatives considered**: Creating a new model — rejected because the existing model covers all requirements.

---

### RQ-2: Does a dedicated star/unstar endpoint exist?

**Decision**: No — a dedicated star/unstar endpoint does NOT exist yet.

**Rationale**: The `__init__.py` at `src/sentry/issues/endpoints/__init__.py:57` exports `"OrganizationGroupSearchViewStarredEndpoint"` in `__all__`, but no corresponding file or import exists. This is a forward reference to the endpoint we need to create. Currently, starring only happens as a side effect of the bulk PUT endpoint (`OrganizationGroupSearchViewsEndpoint.put`) which creates `GroupSearchViewStarred` entries automatically when views are created/updated.

**Alternatives considered**: Using the existing bulk PUT endpoint — rejected because it requires sending the entire view list and is designed for frontend bulk sync, not individual star/unstar actions on shared views.

---

### RQ-3: What HTTP methods and URL pattern should the star/unstar endpoint use?

**Decision**: `PUT` for star (with optional position), `DELETE` for unstar, on URL `/{org}/group-search-views/{view_id}/starred/`.

**Rationale**:

- **PUT for star**: Follows the `DashboardFavoriteEndpoint` pattern which uses PUT. Star is idempotent (starring an already-starred view returns success). PUT with optional `position` in the request body.
- **DELETE for unstar**: Follows the `OrganizationPinnedSearchEndpoint` pattern. Unstar is idempotent (unstarring a non-starred view returns success).
- **URL pattern**: Nesting under `group-search-views/{view_id}/starred/` follows REST conventions for sub-resource actions and is consistent with the existing `group-search-views/{view_id}/visit/` pattern.

**Alternatives considered**:

1. Single PUT with `{"isStarred": true/false}` toggle — rejected for consistency; separate methods provide clearer semantics and match the pinned searches pattern.
2. POST for star — rejected because star is idempotent, making PUT more semantically correct.

---

### RQ-4: How should view access validation work for shared views?

**Decision**: A user can star a view if `view.user_id == request.user.id` OR `view.visibility == GroupSearchViewVisibility.ORGANIZATION` AND `view.organization == organization`.

**Rationale**: This matches the access check in `OrganizationGroupSearchViewStarredOrderEndpoint` (`organization_group_search_view_starred_order.py:33-36`) which validates that the user either owns the view or the view has organization visibility.

**Alternatives considered**: Checking project-level permissions — rejected because view access is determined by ownership or organization visibility, not project membership.

---

### RQ-5: How should position management work when starring at a specific position?

**Decision**: When starring with a position, shift existing starred views at that position and after by +1. When starring without a position, append to end (position = max + 1). When unstarring, close the gap by decrementing positions above the removed position.

**Rationale**: This matches the existing pattern in `organization_group_search_view_details.py:46-63` where deleting a view decrements positions of starred views above the deleted position. The insert-and-shift pattern is the natural complement.

**Alternatives considered**:

1. Sparse positioning (e.g., positions 10, 20, 30) — rejected; the codebase uses dense 0-indexed positions.
2. Only appending — rejected; the spec requires position management (FR-005, FR-006).

---

### RQ-6: How should concurrency be handled for position conflicts?

**Decision**: Use `transaction.atomic()` with the deferred unique constraint on `(user_id, organization_id, position)`.

**Rationale**: The deferred constraint on `GroupSearchViewStarred` allows temporary position duplicates within a transaction, which is essential for shifting positions during insert. This is the same pattern used by `reorder_starred_views()`. Database-level serialization via `select_for_update()` or the atomic transaction block prevents concurrent star operations from creating inconsistent state.

**Alternatives considered**: Application-level locking — rejected; database transactions are the established pattern.

---

### RQ-7: What feature flag should gate this endpoint?

**Decision**: `organizations:issue-view-sharing`.

**Rationale**: The star/unstar feature is part of the view-sharing initiative. The existing `OrganizationGroupSearchViewStarredOrderEndpoint` uses this same flag. Starring shared views only makes sense when view sharing is enabled.

**Alternatives considered**: `organizations:issue-stream-custom-views` — rejected; that flag gates the basic custom views CRUD. Star/unstar of shared views is a sharing-specific feature.

---

### RQ-8: What response format should star/unstar use?

**Decision**: Both star and unstar return `204 No Content`.

**Rationale**: This matches the patterns used by:

- `OrganizationGroupSearchViewStarredOrderEndpoint` (204 on reorder)
- `OrganizationGroupSearchViewDetailsEndpoint` (204 on delete)
- `OrganizationDashboardFavoriteEndpoint` (204 on favorite toggle)
- `OrganizationGroupSearchViewVisitEndpoint` (204 on visit)

All user-preference toggle/action endpoints return 204 in the Sentry codebase.

**Alternatives considered**: Returning the starred view data — rejected for consistency with existing patterns.

---

### RQ-9: What edge cases need handling?

**Decision**: Handle these edge cases:

1. **Starring a deleted view**: Return 404 (view not found in organization).
2. **Starring at position > list size**: Clamp to end of list (position = max + 1). This is more user-friendly than rejecting.
3. **Concurrent star at same position**: The atomic transaction + deferred unique constraint handles this; one transaction will succeed, the other will either retry or fail gracefully.
4. **Starring a view from another organization**: Prevented by `OrganizationEndpoint` which resolves the org from the URL, and the query filters by `organization=organization`.
5. **Re-starring an already starred view**: Idempotent — return 204 without modification (FR-003). If position is specified and different from current, update the position.

**Rationale**: Each edge case maps to a requirement in the spec or a defensive coding best practice from the constitution (Security by Default).

---

## Summary of All Decisions

| #                 | Decision                                              | Pattern Source                                               |
| ----------------- | ----------------------------------------------------- | ------------------------------------------------------------ |
| Model             | Use existing `GroupSearchViewStarred`                 | Already exists                                               |
| Endpoint          | New `OrganizationGroupSearchViewStarredEndpoint`      | Forward-ref in `__init__.py:57`                              |
| HTTP Methods      | PUT (star) + DELETE (unstar)                          | `DashboardFavoriteEndpoint`, `PinnedSearchEndpoint`          |
| URL               | `/{org}/group-search-views/{view_id}/starred/`        | Matches `/{org}/group-search-views/{view_id}/visit/` pattern |
| Access Check      | Owner OR org-visibility                               | `StarredOrderEndpoint:33-36`                                 |
| Position (star)   | Optional; shift-and-insert or append                  | `view_details.py:46-63` (complement)                         |
| Position (unstar) | Close gap with decrement                              | `view_details.py:55-60`                                      |
| Concurrency       | `transaction.atomic()` + deferred constraint          | `starred_order.py:63`                                        |
| Feature Flag      | `organizations:issue-view-sharing`                    | `starred_order.py:50`                                        |
| Response          | 204 No Content                                        | All preference endpoints                                     |
| Permissions       | `MemberPermission` with `member:read`, `member:write` | `starred_order.py:16-19`                                     |
| Publish Status    | `ApiPublishStatus.EXPERIMENTAL`                       | `starred_order.py:45`                                        |
