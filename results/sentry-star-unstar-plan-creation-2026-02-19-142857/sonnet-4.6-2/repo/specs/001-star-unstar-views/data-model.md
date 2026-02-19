# Data Model: Star and Unstar Shared Issue Views

**Feature**: `001-star-unstar-views`
**Date**: 2026-02-19

---

## Summary

No new models or migrations are required. All storage needs are satisfied by the pre-existing
`GroupSearchViewStarred` model and its migration chain through `0836_create_groupsearchviewstarred_table.py`.

---

## Entities

### GroupSearchView (existing, read-only for this feature)

**File**: `src/sentry/models/groupsearchview.py`
**Table**: `sentry_groupsearchview`

| Field             | Type                                 | Notes                                           |
| ----------------- | ------------------------------------ | ----------------------------------------------- |
| `id`              | BigAutoField (PK)                    |                                                 |
| `name`            | TextField(max_length=128)            | Display name                                    |
| `user_id`         | HybridCloudForeignKey → User         | Owner                                           |
| `organization`    | FlexibleForeignKey → Organization    | Tenant boundary                                 |
| `visibility`      | CharField                            | `"owner"` or `"organization"`                   |
| `query`           | TextField                            | Search query                                    |
| `query_sort`      | CharField                            | Sort option                                     |
| `position`        | PositiveSmallIntegerField(null=True) | Owner's tab order (distinct from star position) |
| `projects`        | ManyToManyField → Project            | Via `GroupSearchViewProject`                    |
| `is_all_projects` | BooleanField                         |                                                 |
| `environments`    | ArrayField                           |                                                 |
| `time_filters`    | JSONField                            | e.g. `{"period": "14d"}`                        |

**Access rule for this feature**: A user may star a view iff:

- `view.organization == request.organization`, AND
- `view.user_id == request.user.id` OR `view.visibility == "organization"`

---

### GroupSearchViewStarred (existing — the target entity)

**File**: `src/sentry/models/groupsearchviewstarred.py`
**Table**: `sentry_groupsearchviewstarred`

| Field               | Type                                 | Nullable | Notes                                   |
| ------------------- | ------------------------------------ | -------- | --------------------------------------- |
| `id`                | BigAutoField (PK)                    |          |                                         |
| `user_id`           | HybridCloudForeignKey → User         | No       | Star owner                              |
| `organization`      | FlexibleForeignKey → Organization    | No       | Tenant boundary                         |
| `group_search_view` | FlexibleForeignKey → GroupSearchView | No       | The starred view                        |
| `position`          | PositiveSmallIntegerField            | No       | Zero-based order in user's starred list |
| `date_added`        | DateTimeField                        | No       | Inherited from `DefaultFieldsModel`     |
| `date_updated`      | DateTimeField                        | No       | Inherited from `DefaultFieldsModel`     |

**Constraints**:

```sql
UNIQUE (user_id, organization_id, position) DEFERRABLE INITIALLY DEFERRED
-- name: sentry_groupsearchviewstarred_unique_view_position_per_org_user
```

The `DEFERRABLE DEFERRED` constraint is critical: it allows position shift operations
(UPDATE position + 1) and the subsequent INSERT to both be checked at transaction commit time,
avoiding transient violations.

There is no `UNIQUE (user_id, organization_id, group_search_view_id)` constraint at the DB level,
but the application enforces "one star per user per view" idempotently via `get_or_create`.

**Custom manager**: `GroupSearchViewStarredManager` (existing) — provides `reorder_starred_views()`.
This feature adds no new manager methods; the insert/delete logic is handled inline in the endpoint.

---

## State Transitions

```
[not starred]
     │
     │ POST /group-search-views/{id}/star/
     │ body: { "position": N }  (optional)
     ▼
[starred at position N]
     │
     │ DELETE /group-search-views/{id}/star/
     ▼
[not starred]
```

**Position invariant**: For a given `(user_id, organization_id)` pair, positions form a
zero-based, contiguous sequence `[0, 1, 2, ..., count-1]` at all times (maintained by the
shift-up-on-star / shift-down-on-unstar operations).

---

## Write Operations

### Star (POST)

```
1. Fetch view scoped to org; return 404 if not found or inaccessible
2. If GroupSearchViewStarred already exists for (user, org, view) → return 204 (idempotent)
3. Within transaction.atomic:
   a. count = GroupSearchViewStarred.objects.filter(user, org).count()
   b. insert_position = min(requested_position ?? count, count)
   c. UPDATE position = position + 1 WHERE (user, org, position >= insert_position)
   d. INSERT GroupSearchViewStarred(user, org, view, position=insert_position)
4. Return 204
```

### Unstar (DELETE)

```
1. Fetch view scoped to org; return 404 if not found or inaccessible
2. Within transaction.atomic:
   a. try: starred = GroupSearchViewStarred.get(user, org, view)
   b. if not found → return 204 (idempotent)
   c. deleted_position = starred.position
   d. starred.delete()
   e. UPDATE position = position - 1 WHERE (user, org, position > deleted_position)
3. Return 204
```

---

## Validation Rules

| Rule                                                             | Source            |
| ---------------------------------------------------------------- | ----------------- |
| View must belong to the request organization                     | FR-008, FR-010    |
| View must be owned by user OR have visibility="organization"     | FR-008, FR-010    |
| Position must be a non-negative integer if provided              | FR-005            |
| Position is clamped to `[0, count]` if out of range              | Edge case in spec |
| Starring an already-starred view returns success without changes | FR-003            |
| Unstarring a non-starred view returns success without changes    | FR-004            |

---

## No Migration Required

The `sentry_groupsearchviewstarred` table was created by migration
`0836_create_groupsearchviewstarred_table.py` and already contains all required columns and
constraints. This feature does not alter any schema.
