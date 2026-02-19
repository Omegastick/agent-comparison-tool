# Research: Star and Unstar Shared Issue Views

**Feature**: `001-star-unstar-views`
**Date**: 2026-02-19

---

## 1. Does the data model already exist?

**Decision**: `GroupSearchViewStarred` already exists and is the correct model — no new model or migration is needed.

**Evidence**:

- `src/sentry/models/groupsearchviewstarred.py` defines `GroupSearchViewStarred` with `user_id`, `organization`, `group_search_view` (FK), and `position` (PositiveSmallIntegerField).
- Migration `0836_create_groupsearchviewstarred_table.py` has already been applied.
- The model has a deferred unique constraint on `(user_id, organization_id, position)`, which enables safe position shifting within a single transaction.
- A custom manager `GroupSearchViewStarredManager.reorder_starred_views()` handles bulk reorder, but does NOT handle add/remove — that gap is what this feature fills.

**Rationale**: The model was created for the bulk-PUT flow in `OrganizationGroupSearchViewsEndpoint`. It already satisfies every field required by the spec.

**Alternatives considered**: Adding a boolean `is_starred` field to `GroupSearchView` — rejected because `GroupSearchViewStarred` cleanly separates per-user star state from the view definition, and already exists.

---

## 2. Is there already a star/unstar endpoint?

**Decision**: No dedicated star/unstar endpoint exists. One must be created.

**Evidence**:

- `src/sentry/api/urls.py` lists only four group-search-view patterns: `GET/PUT /group-search-views/`, `DELETE /group-search-views/{view_id}/`, `POST /group-search-views/{view_id}/visit/`, and `PUT /group-search-views-starred-order/`.
- `src/sentry/issues/endpoints/__init__.py` already declares `OrganizationGroupSearchViewStarredEndpoint` in `__all__` but the class does not yet exist (the import is absent).
- Starring/unstarring is currently only possible as a side-effect of the bulk-PUT to `/group-search-views/`, which replaces the entire view set and is not suitable for toggling a single view.

**Rationale**: The `__all__` stub confirms this endpoint is planned. The feature spec maps directly to a new file: `organization_group_search_view_star.py`.

---

## 3. Which HTTP methods are correct for star/unstar?

**Decision**: `POST` to star, `DELETE` to unstar, both at `/group-search-views/{view_id}/star/`.

**Rationale**:

- `POST` for star mirrors the `visit` endpoint pattern (`POST /group-search-views/{view_id}/visit/`).
- `DELETE` for unstar is semantically correct (removing a resource).
- Both are idempotent in their effect (per FR-003, FR-004), even though `DELETE` is formally idempotent and `POST` is not; the implementation enforces idempotency explicitly.
- Using a sub-resource `/star/` keeps the URL self-documenting and consistent with `/visit/`.

**Alternatives considered**:

- Single `PUT` with `{"isStarred": true/false}` — used by Dashboard favorites (`OrganizationDashboardFavoriteEndpoint`). Rejected because it conflates two distinct operations into one payload field, making it harder to express position on star.
- `PUT` with toggle semantics — rejected as ambiguous for idempotent callers.

---

## 4. How should position insertion work?

**Decision**: Accept an optional `position` integer in the POST request body. If omitted, append to end (position = current count). Shift all existing entries at `position >=` new position up by 1 within `transaction.atomic`.

**Evidence** — existing shift pattern from `organization_group_search_view_details.py`:

```python
# On delete, compact downward:
GroupSearchViewStarred.objects.filter(
    organization=organization,
    user_id=request.user.id,
    position__gt=deleted_position,
).update(position=F("position") - 1)
```

The complement for insertion is an upward shift before inserting:

```python
GroupSearchViewStarred.objects.filter(
    organization=organization,
    user_id=request.user.id,
    position__gte=insert_position,
).update(position=F("position") + 1)
# then create with position=insert_position
```

**Rationale**: The deferred unique constraint on `(user_id, organization_id, position)` allows the shift + create to occur within a single transaction without transient uniqueness violations.

**Edge case — position out of range**: If the requested position exceeds the current count, clamp to `count` (append). This matches the spec edge case: "What happens when a user tries to star a view at a position larger than their current list size?"

---

## 5. How should access control work?

**Decision**: A user may star any `GroupSearchView` that is either:

1. Owned by the user (`user_id = request.user.id`), OR
2. Shared with the organization (`visibility = GroupSearchViewVisibility.ORGANIZATION`)

The view must also belong to the same `organization`. Requests outside these bounds return `404` (not `403`) to avoid leaking information about existence.

**Evidence** — same logic already used in `GroupSearchViewStarredOrderSerializer.validate_view_ids()`:

```python
if any(
    gsv.user_id != self.context["user"].id
    and gsv.visibility != GroupSearchViewVisibility.ORGANIZATION
    for gsv in gsvs
):
    raise serializers.ValidationError("You do not have access to one or more views")
```

**Rationale**: Consistent with FR-008, FR-010, SC-005, and the existing starred-order endpoint. Returns `404` rather than `403` to avoid leaking private view existence to unauthorized users (constitution principle II: Security by Default).

---

## 6. Which feature flag should gate the endpoint?

**Decision**: Gate on `organizations:issue-view-sharing`.

**Evidence**: The starred-order endpoint (`OrganizationGroupSearchViewStarredOrderEndpoint`) uses `organizations:issue-view-sharing`. Star/unstar is in the same feature family (sharing-aware view management).

**Rationale**: The basic custom-views flag (`organizations:issue-stream-custom-views`) gates view CRUD. Starring is only meaningful when views can be shared (you star shared views). Using `issue-view-sharing` is consistent with the existing starred-order endpoint.

---

## 7. What is the correct permission scope?

**Decision**: `POST` and `DELETE` both require `["member:read", "member:write"]`.

**Evidence**: `OrganizationGroupSearchViewStarredOrderEndpoint` uses the same scopes for `PUT`. The visit endpoint uses only `member:read` for `POST` because visiting is read-only in effect; starring writes a row.

---

## 8. Concurrency: what if two requests star at the same position simultaneously?

**Decision**: The deferred unique constraint + `transaction.atomic` is sufficient. The second transaction will either see the shifted rows or fail with `IntegrityError` (which is caught and returned as `400`).

**Evidence**: This is the same concurrency model used throughout the existing star/reorder code. The `Deferrable.DEFERRED` constraint means the uniqueness check happens at commit time, not at each individual UPDATE, which prevents false conflicts during the shift phase.

---

## 9. Idempotency implementation

**Decision**:

- **Star (POST)**: Use `get_or_create` on `GroupSearchViewStarred` keyed by `(user_id, organization, group_search_view)`. If the row already exists, return `204` immediately without modifying position.
- **Unstar (DELETE)**: Use `filter(...).delete()`. If no row exists, `delete()` returns `(0, {})` — no error, return `204`.

**Rationale**: Matches FR-003 and FR-004 precisely. Consistent with `handle_is_bookmarked()` in `api/helpers/group_index/update.py` which uses `get_or_create` for bookmarking.

---

## 10. All NEEDS CLARIFICATION items resolved

| Item                            | Resolution                                                       |
| ------------------------------- | ---------------------------------------------------------------- |
| Does the model exist?           | Yes — `GroupSearchViewStarred`                                   |
| Is there an existing endpoint?  | No — must be created                                             |
| HTTP method design              | POST to star, DELETE to unstar at `/star/` sub-resource          |
| Position insertion algorithm    | Shift ≥ position up by 1, then insert; clamp out-of-range to end |
| Access control for shared views | Same as starred-order: owner OR org-visibility                   |
| Feature flag                    | `organizations:issue-view-sharing`                               |
| Permission scopes               | `member:read`, `member:write`                                    |
| Concurrency                     | Deferred constraint + `transaction.atomic`                       |
| Idempotency                     | `get_or_create` (star), `filter().delete()` (unstar)             |
