# Data Model: Star and Unstar Shared Issue Views

**Feature**: `001-star-unstar-views`
**Phase**: 1 — Design
**Date**: 2026-02-19

---

## Overview

No new models or migrations are required. The complete persistence layer was introduced in migrations `0836`–`0841`. This document describes the entities relevant to the feature and their roles.

---

## Existing Entities (No Changes)

### GroupSearchView

**File**: `src/sentry/models/groupsearchview.py`
**Table**: `sentry_groupsearchview`
**Silo**: `@region_silo_model`

Represents a saved issue search view. A view is owned by one user in one organization, but may be shared organization-wide via `visibility`.

| Field             | Type                                   | Notes                                 |
| ----------------- | -------------------------------------- | ------------------------------------- |
| `id`              | `BoundedBigAutoField`                  | PK                                    |
| `name`            | `TextField(max_length=128)`            | Display name                          |
| `user_id`         | `HybridCloudForeignKey(User)`          | Creator/owner                         |
| `organization`    | `FlexibleForeignKey(Organization)`     | Tenant boundary                       |
| `visibility`      | `CharField(max_length=16)`             | `"owner"` or `"organization"`         |
| `query`           | `TextField`                            | Issue search query string             |
| `query_sort`      | `CharField`                            | Sort order (e.g., `"date"`)           |
| `position`        | `PositiveSmallIntegerField(null=True)` | Legacy ordering (nullable since 0843) |
| `projects`        | M2M via `GroupSearchViewProject`       | Scoped projects                       |
| `is_all_projects` | `BooleanField`                         | Override to all-projects              |
| `environments`    | `ArrayField(CharField)`                | Scoped environments                   |
| `time_filters`    | `JSONField`                            | Default: `{"period": "14d"}`          |
| `date_added`      | `DateTimeField`                        | Auto from base                        |
| `date_updated`    | `DateTimeField`                        | Auto from base                        |

**Access rule for starring**: A user may star a view if:

- `view.user_id == request.user.id` (they own it), **OR**
- `view.visibility == GroupSearchViewVisibility.ORGANIZATION` AND `view.organization == organization`

---

### GroupSearchViewStarred

**File**: `src/sentry/models/groupsearchviewstarred.py`
**Table**: `sentry_groupsearchviewstarred`
**Silo**: `@region_silo_model`
**Migration**: `0836_create_groupsearchviewstarred_table.py`

The junction table representing the "starred" relationship between a user and a view within an organization. Its existence records a star; its `position` field encodes the user's custom ordering.

| Field               | Type                                   | Notes                             |
| ------------------- | -------------------------------------- | --------------------------------- |
| `id`                | `BoundedBigAutoField`                  | PK                                |
| `user_id`           | `HybridCloudForeignKey(User, CASCADE)` | The starring user                 |
| `organization`      | `FlexibleForeignKey(Organization)`     | Tenant boundary                   |
| `group_search_view` | `FlexibleForeignKey(GroupSearchView)`  | The starred view                  |
| `position`          | `PositiveSmallIntegerField`            | 0-indexed position in user's list |
| `date_added`        | `DateTimeField`                        | Auto from base                    |
| `date_updated`      | `DateTimeField`                        | Auto from base                    |

**Constraints**:

- `UniqueConstraint(fields=["user_id", "organization_id", "position"], deferrable=DEFERRED)` — ensures no two starred views share a position per user per org; deferrable enables in-transaction swaps without violating the constraint mid-operation.
- No explicit unique constraint on `(user_id, organization_id, group_search_view_id)` — but `create_or_update` semantics enforce at most one entry per (user, view).

**State transitions**:

```
View not starred
      │
      │ POST /star/ (no position or position=N)
      ▼
GroupSearchViewStarred row created at position N
      │                        │
      │ DELETE /star/           │ PATCH /starred-order/ (reorder)
      ▼                        ▼
Row deleted,             position updated,
positions shifted down   other rows shifted
```

**Custom manager method** (used by reorder endpoint):

```python
GroupSearchViewStarred.objects.reorder_starred_views(
    organization, user_id, new_view_positions=[list[int]]
)
```

---

### GroupSearchViewProject (Through Table)

**File**: `src/sentry/models/groupsearchview.py` (lines 19–29)
**Table**: `sentry_groupsearchviewproject`

Junction between `GroupSearchView` and `Project`. Read-only for this feature.

---

### GroupSearchViewLastVisited

**File**: `src/sentry/models/groupsearchviewlastvisited.py`
**Table**: `sentry_groupsearchviewlastvisited`

Tracks when a user last visited a view. Read-only for this feature (managed by the `/visit/` endpoint).

---

## Position Management Rules

### Starring without position (append)

```
current starred list: [A@0, B@1, C@2]
star D (no position specified)
→ insert D at position = count = 3
result: [A@0, B@1, C@2, D@3]
```

### Starring at a specific position

```
current starred list: [A@0, B@1, C@2]
star D at position=1
→ shift: B→2, C→3  (UPDATE position = position+1 WHERE position >= 1)
→ insert D at position=1
result: [A@0, D@1, B@2, C@3]
```

### Starring at out-of-bounds position

```
current starred list: [A@0, B@1]  (count=2)
star D at position=99
→ clamp: insert_position = min(99, 2) = 2
→ no shift needed (position >= 2 only if count > 2)
result: [A@0, B@1, D@2]
```

### Unstarring

```
current starred list: [A@0, B@1, C@2]
unstar B (position=1)
→ delete GroupSearchViewStarred for B
→ shift down: C→1  (UPDATE position = position-1 WHERE position > 1)
result: [A@0, C@1]
```

### Already-starred idempotency

```
POST /star/ for a view already in user's starred list
→ create_or_update finds existing row, no-ops (same position)
→ returns 200 with existing starred view data
```

### Unstar-when-not-starred idempotency

```
DELETE /star/ for a view not in user's starred list
→ filter returns no rows, nothing deleted
→ returns 204 No Content
```

---

## Validation Rules

| Rule                     | Condition                                                              | Error             |
| ------------------------ | ---------------------------------------------------------------------- | ----------------- |
| View exists              | `GroupSearchView.objects.get(id=view_id, organization=organization)`   | `404 Not Found`   |
| User has access          | `view.user_id == request.user.id OR view.visibility == "organization"` | `403 Forbidden`   |
| Position is non-negative | `position >= 0` (if supplied)                                          | `400 Bad Request` |
| Position is integer      | DRF serializer field validation                                        | `400 Bad Request` |
| Idempotent star          | Already starred → 200 with existing data                               | —                 |
| Idempotent unstar        | Not starred → 204                                                      | —                 |

---

## No Migration Required

The `sentry_groupsearchviewstarred` table was created in migration `0836` and is production-ready. No DDL changes are needed for this feature.
