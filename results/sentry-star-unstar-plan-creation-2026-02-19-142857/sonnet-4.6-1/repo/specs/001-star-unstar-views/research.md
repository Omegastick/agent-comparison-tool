# Research: Star and Unstar Shared Issue Views

**Feature**: 001-star-unstar-views  
**Date**: 2026-02-19  
**Status**: Complete — all NEEDS CLARIFICATION resolved

---

## 1. Does `GroupSearchViewStarred` already exist?

**Decision**: Yes — fully implemented.  
**Rationale**: `src/sentry/models/groupsearchviewstarred.py` contains `GroupSearchViewStarred`, a region-silo join-table model with fields `user_id`, `organization`, `group_search_view`, and `position`. A deferred `UniqueConstraint` on `(user_id, organization_id, position)` enforces ordered per-user lists within a transaction. The model also ships `GroupSearchViewStarredManager.reorder_starred_views()` for bulk position updates.  
**Alternatives considered**: N/A — the model already exists and is already in use by the bulk-PUT endpoint.

---

## 2. Current starring mechanism (how starring works today)

**Decision**: Starring is currently **implicit**. Every view created or updated via `PUT /group-search-views/` automatically creates or updates a `GroupSearchViewStarred` row. There is no explicit star/unstar toggle endpoint.  
**Rationale**: The bulk-PUT endpoint (`organization_group_search_views.py`) calls `GroupSearchViewStarred.objects.update_or_create(...)` for every view in the payload. The `GET` endpoint returns `GroupSearchViewStarred` rows ordered by `position`.  
**Gap**: The spec requires an explicit, standalone star/unstar action so that users can star/unstar any accessible view (including shared `visibility=organization` views they don't own) without going through the full bulk-PUT flow.

---

## 3. What endpoint pattern to follow for star/unstar?

**Decision**: Sub-resource action endpoint at `/group-search-views/{view_id}/star/`, using `PUT` for star and `DELETE` for unstar.  
**Rationale**:

- The `/visit/` sub-resource endpoint (`organization_group_search_view_visit.py`) is the direct precedent for a per-view action endpoint.
- `PUT` for star mirrors the pattern of `OrganizationDashboardFavoriteEndpoint` and avoids ambiguity when the state is idempotent.
- `DELETE` for unstar is semantically clear — it removes the starred relationship.
- Feature flag: `organizations:issue-view-sharing` (matches the sharing-aware starred-order endpoint; starring a shared view is the core use case unlocked by sharing).
- Alternative (`POST /star/` + `DELETE /star/`): Also acceptable and chosen over `PUT /star/` to align better with REST resource creation semantics. See contract for final choice.

---

## 4. Access control: who can star a view?

**Decision**: A user can star any `GroupSearchView` that belongs to their organization, provided it is either (a) owned by the user (`user_id == request.user.id`) or (b) has `visibility == GroupSearchViewVisibility.ORGANIZATION`.  
**Rationale**: FR-008 and FR-010 require access validation before starring. The existing `GroupSearchViewStarredOrderSerializer.validate_view_ids` already implements exactly this check and serves as the reference implementation.  
**Security (IDOR prevention)**: The query MUST always scope `GroupSearchView.objects.get(id=..., organization=organization)` first, then check the `user_id`/`visibility` condition. This satisfies the constitution's II (Security by Default).

---

## 5. Position management for star insertion

**Decision**: When starring without a position, append to end (`position = current_count`). When starring at a specific position, shift all existing entries at `position >= requested_position` up by 1 before inserting.  
**Rationale**: The deferred unique constraint on position allows bulk updates within a single transaction. The deletion path in `OrganizationGroupSearchViewDetailsEndpoint.delete` already demonstrates the shift pattern using `F("position") - 1`; the star path is the inverse.  
**Alternative**: Use a gap-based (sparse) position scheme — rejected because the existing model and all existing endpoints use dense 0-based positions.

---

## 6. Position management for unstar

**Decision**: Delete the `GroupSearchViewStarred` row; decrement `position` of all rows with `position > deleted_position` using `F("position") - 1`, all within an `atomic` transaction.  
**Rationale**: Mirrors the implementation already in `OrganizationGroupSearchViewDetailsEndpoint.delete` (lines 47-63 of `organization_group_search_view_details.py`).

---

## 7. Idempotency guarantees

**Decision**: Both star and unstar MUST be idempotent — duplicate operations return HTTP 200/204 without error.  
**Rationale**: FR-003 and FR-004 are explicit requirements. Starring an already-starred view simply returns the existing record unchanged. Unstarring a non-starred view is a no-op that returns 204.  
**Implementation**: Use `get_or_create` for starring (creating only if absent). For unstarring, catch `GroupSearchViewStarred.DoesNotExist` and return 204.

---

## 8. Feature flag selection

**Decision**: Use `organizations:issue-view-sharing`.  
**Rationale**: The star/unstar action is primarily meaningful for shared (organization-visibility) views — the whole point is to let users save shared views to their personal list. The `organizations:issue-view-sharing` flag gates the sharing feature and is already used by the related `starred-order` endpoint. `organizations:issue-stream-custom-views` gates the underlying view CRUD and remains unchanged.  
**Fallback**: Return `HTTP 404` when the flag is not enabled (consistent with `issue-stream-custom-views` endpoints) rather than `400` (which the starred-order endpoint uses — that appears to be an inconsistency in existing code).

---

## 9. `__init__.py` placeholder

**Decision**: `OrganizationGroupSearchViewStarredEndpoint` is already declared in `__all__` in `src/sentry/issues/endpoints/__init__.py` (line 57) but not yet imported or implemented. The new endpoint file must be named `organization_group_search_view_starred.py` and the import added.

---

## 10. What about the `GroupSearchView.position` field?

**Decision**: `GroupSearchView.position` is a legacy field from before `GroupSearchViewStarred` existed. The new star/unstar endpoint does NOT update `GroupSearchView.position` — it only manages `GroupSearchViewStarred.position`. The existing backfill migration (`0838`) synchronized the two; new code exclusively uses the starred table.

---

## 11. Response shape for star action

**Decision**: `PUT /star/` returns the created/existing `GroupSearchViewStarred` serialized via `GroupSearchViewStarredSerializer`, i.e., the full view data plus `position`.  
**Rationale**: Gives the client the position at which the view was inserted (important when position was omitted — client needs to know the auto-assigned position). Matches the shape already returned by the `GET /group-search-views/` list.  
**Alternative**: Return only `{ "position": N }` — rejected because returning the full object is more useful and reuses an existing serializer.

---

## 12. Transaction handling

**Decision**: All writes (star insertion + position shift, or star deletion + position decrement) MUST be wrapped in `transaction.atomic(using=router.db_for_write(GroupSearchViewStarred))`.  
**Rationale**: The deferred unique constraint only works within a transaction (it defers constraint check to commit time). Race conditions in concurrent starring are handled by catching `IntegrityError`.

---

## Summary Table

| Question                             | Answer                                         | Source                                        |
| ------------------------------------ | ---------------------------------------------- | --------------------------------------------- |
| Does `GroupSearchViewStarred` exist? | Yes                                            | `src/sentry/models/groupsearchviewstarred.py` |
| URL pattern                          | `/group-search-views/{view_id}/star/`          | Analogy to `/visit/`                          |
| HTTP methods                         | `PUT` (star), `DELETE` (unstar)                | REST convention                               |
| Feature flag                         | `organizations:issue-view-sharing`             | Matches starred-order endpoint                |
| Star position (no input)             | Append to end                                  | FR-007                                        |
| Star position (with input)           | Shift ≥ position up by 1                       | FR-006                                        |
| Unstar                               | Delete row, decrement higher positions         | Mirror of delete-view pattern                 |
| Idempotency                          | Yes — `get_or_create` / ignore DoesNotExist    | FR-003, FR-004                                |
| Access control                       | Own views + org-visibility views               | FR-008, FR-010                                |
| Response                             | Full `GroupSearchViewStarredSerializer` output | Reuse existing serializer                     |
| Endpoint file name                   | `organization_group_search_view_starred.py`    | `__init__.py` placeholder                     |
