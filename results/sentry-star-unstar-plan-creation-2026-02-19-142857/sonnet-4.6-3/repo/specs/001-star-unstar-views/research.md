# Research: Star and Unstar Shared Issue Views

**Feature**: `001-star-unstar-views`
**Phase**: 0 — Research
**Date**: 2026-02-19

---

## Summary

All research questions are resolved. The `GroupSearchViewStarred` model, its manager, and all related serializers/migrations already exist in the codebase. The feature requires **new API endpoints** to expose star and unstar operations; the storage layer is already in place.

---

## Findings

### Finding 1: GroupSearchViewStarred Model Already Exists

**Decision**: Use the existing `GroupSearchViewStarred` model as-is.

**Rationale**: The model (`src/sentry/models/groupsearchviewstarred.py`) was introduced in migration `0836` and is fully schema-ready:

- `user_id` (HybridCloudForeignKey → User, CASCADE)
- `organization` (FlexibleForeignKey → Organization)
- `group_search_view` (FlexibleForeignKey → GroupSearchView)
- `position` (PositiveSmallIntegerField)
- Deferred UniqueConstraint on `(user_id, organization_id, position)` — safe for in-transaction reordering

**Alternatives considered**: Adding an `is_starred` boolean field to `GroupSearchView` itself — rejected because a junction table correctly represents a per-user relationship (one view can be starred by many users independently).

---

### Finding 2: GroupSearchViewStarredManager Handles Reordering

**Decision**: Use `GroupSearchViewStarred.objects.reorder_starred_views(organization, user_id, new_view_positions)` for bulk reordering.

**Rationale**: The custom manager method (lines 15–49 of `groupsearchviewstarred.py`) performs a `bulk_update` inside a validated set comparison. It raises `ValueError` if the provided IDs do not match the user's current starred set exactly. Used by `OrganizationGroupSearchViewStarredOrderEndpoint`.

**Alternatives considered**: Manual loop with `.save()` — rejected due to N+1 writes.

---

### Finding 3: No Star/Unstar Toggle Endpoint Exists Yet

**Decision**: Create a new endpoint `OrganizationGroupSearchViewStarEndpoint` at `/organizations/{slug}/group-search-views/{view_id}/star/` supporting `POST` (star) and `DELETE` (unstar).

**Rationale**: Auditing all URLs in `src/sentry/api/urls.py` (lines 1779–1797), the only existing group-search-view endpoints are:

- `GET/PUT /group-search-views/` — list/bulk-replace
- `DELETE /group-search-views/{view_id}/` — delete a view
- `POST /group-search-views/{view_id}/visit/` — record last visit
- `PUT /group-search-views-starred-order/` — reorder starred views

None expose a star/unstar toggle for a single view.

**Alternatives considered**:

- `PUT /group-search-views/{view_id}/` with `isStarred` body — rejects existing `DELETE` endpoint's pattern and mixes concern.
- Overloading `PUT /group-search-views/` (bulk replace) to handle single-star — too coarse, would require full list transmission for a single toggle.
- Using `PUT /group-search-views/{view_id}/star/` — a sub-resource with `POST/DELETE` mirrors the `/visit/` and `/favorite/` patterns exactly and is cleaner REST.

---

### Finding 4: Access Control — Visibility Scope

**Decision**: The star endpoint must validate that the user can access the view being starred: either `user_id = request.user.id` (owned) or `visibility = GroupSearchViewVisibility.ORGANIZATION` and `organization = organization`.

**Rationale**: The spec (FR-008, FR-010) requires rejecting stars on views the user cannot access. The existing `organization_group_search_view_starred_order.py` endpoint at line 29–38 demonstrates the canonical access check pattern:

```python
GroupSearchView.objects.filter(organization=self.context["organization"], id__in=view_ids)
# then verify user_id or visibility == ORGANIZATION
```

Cross-org access is prevented by always scoping the `GroupSearchView.objects.get()` call to `organization=organization`.

**Alternatives considered**: A separate permission class — unnecessary because the check is a data-level ownership query, not a scope-level permission.

---

### Finding 5: Idempotency Pattern — create_or_update

**Decision**: Use `GroupSearchViewStarred.objects.create_or_update(...)` for starring (idempotent upsert), and a no-op-on-missing delete for unstarring.

**Rationale**:

- `create_or_update` (Sentry's own race-safe upsert, `src/sentry/db/models/query.py` lines 180–235) handles the "already starred" case atomically — it updates the position if the row exists.
- `GroupSearchViewLastVisited` at `/visit/` uses this exact pattern (line 45 of `organization_group_search_view_visit.py`).
- For unstar: filter with `organization=organization, user_id=request.user.id, group_search_view=view` and delete if found; if absent, return 204 (idempotent). Mirror the DELETE pattern from `organization_group_search_view_details.py` lines 47–63.

**Alternatives considered**: `get_or_create` + `IntegrityError` catch (`ProjectBookmark` pattern) — works but less elegant than `create_or_update`.

---

### Finding 6: Position Management

**Decision**: When no position is specified, append to end (position = current count of starred views). When a position is specified, shift all rows at that position and beyond upward first, then insert.

**Rationale**: The spec requires FR-005 (optional position) and FR-006 (shift on insert). The deferred unique constraint on `position` allows in-transaction shifts without violating uniqueness mid-operation. The existing `DELETE` endpoint (lines 56–60 of `organization_group_search_view_details.py`) demonstrates the shift pattern using `F("position") - 1`. The insertion shift is the inverse.

**Implementation approach**:

```python
with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
    count = GroupSearchViewStarred.objects.filter(
        organization=organization, user_id=user_id
    ).count()
    insert_position = position if position is not None else count
    insert_position = min(insert_position, count)  # clamp to valid range
    # Shift existing views at >= insert_position upward
    GroupSearchViewStarred.objects.filter(
        organization=organization,
        user_id=user_id,
        position__gte=insert_position,
    ).update(position=F("position") + 1)
    # Insert at position
    GroupSearchViewStarred.objects.create(
        organization=organization,
        user_id=user_id,
        group_search_view=view,
        position=insert_position,
    )
```

**Alternatives considered**: Python-side loop to shift — rejected due to N+1 writes and race conditions.

---

### Finding 7: Feature Flag

**Decision**: Gate the new endpoint behind `organizations:issue-view-sharing` (the same flag used by `OrganizationGroupSearchViewStarredOrderEndpoint`).

**Rationale**: Starring is part of the sharing/personalization feature set. The `issue-stream-custom-views` flag gates the older list/create/delete endpoints; the newer starred-order endpoint uses `issue-view-sharing`. Since this is a new capability aligned with the sharing flow, `issue-view-sharing` is the right gate.

**Alternatives considered**: `issue-stream-custom-views` — used by the older, lower-level endpoints; using it would conflate this feature with the basic view management feature.

---

### Finding 8: Serializer — No New Output Shape Needed

**Decision**: The `POST` (star) response should return the `GroupSearchViewStarredSerializer` output for the created entry. The `DELETE` (unstar) returns `204 No Content`.

**Rationale**: `GroupSearchViewStarredSerializer` (lines 84–105 of `src/sentry/api/serializers/models/groupsearchview.py`) already produces the correct shape including `position`. No new serializer is required.

**Alternatives considered**: Return the full starred list on star — too heavy; let the client refresh if needed.

---

### Finding 9: Concurrent Star Requests (Edge Case)

**Decision**: Wrap the position-shift + create operation in `transaction.atomic(using=router.db_for_write(GroupSearchViewStarred))`. Catch `IntegrityError` and return `409 Conflict` if concurrent inserts collide.

**Rationale**: The deferred unique constraint on `(user_id, organization_id, position)` will raise `IntegrityError` at commit time if two concurrent inserts attempt the same position. Wrapping in `transaction.atomic` with `IntegrityError` catching mirrors the `OrganizationGroupSearchViewStarredOrderEndpoint` pattern (lines 62–70 of `organization_group_search_view_starred_order.py`).

**Alternatives considered**: `select_for_update()` on the starred set — provides serialization but at cost of locking the entire user's starred list; overkill given expected usage frequency.

---

### Finding 10: URL Convention for Sub-resource Toggle

**Decision**: URL: `^(?P<organization_id_or_slug>[^\/]+)/group-search-views/(?P<view_id>[^\/]+)/star/$`
Route name: `sentry-api-0-organization-group-search-view-star`

**Rationale**: Mirrors `/visit/` sub-resource pattern exactly. The `view_id` regex `[^\/]+` matches both integer IDs and slugs, consistent with all other group-search-view endpoints.

---

## Resolved Clarifications

| Original Question                             | Resolution                                                           |
| --------------------------------------------- | -------------------------------------------------------------------- |
| Does `GroupSearchViewStarred` exist?          | Yes — fully migrated, no new model needed                            |
| What feature flag to use?                     | `organizations:issue-view-sharing`                                   |
| How to handle "already starred" idempotently? | `create_or_update` — upserts position                                |
| How to handle position insertion?             | Atomic shift-up + insert in `transaction.atomic`                     |
| Out-of-bounds position?                       | Clamp to `count` (append)                                            |
| Cross-org access rejection?                   | Scope `GroupSearchView.objects.get()` to `organization=organization` |
| Which visibility values allow starring?       | `OWNER` (own views) or `ORGANIZATION` (shared)                       |
| New serializer needed?                        | No — `GroupSearchViewStarredSerializer` is sufficient                |
| New migration needed?                         | No — schema already exists                                           |
| What `publish_status`?                        | `EXPERIMENTAL` for both POST and DELETE                              |
