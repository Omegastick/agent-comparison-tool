# Data Model: Star and Unstar Shared Issue Views

**Feature**: 001-star-unstar-views  
**Date**: 2026-02-19

---

## Existing Entities (no new models required)

The data model for this feature is **fully covered by existing schema**. No migrations are needed.

---

### Entity 1: `GroupSearchView`

**Table**: `sentry_groupsearchview`  
**File**: `src/sentry/models/groupsearchview.py`

| Field             | Type                                       | Notes                                                                         |
| ----------------- | ------------------------------------------ | ----------------------------------------------------------------------------- |
| `id`              | auto PK                                    |                                                                               |
| `name`            | `TextField(max_length=128)`                | Display name                                                                  |
| `user_id`         | `HybridCloudForeignKey → sentry.User`      | Owner                                                                         |
| `organization`    | `FlexibleForeignKey → sentry.Organization` | Tenant boundary                                                               |
| `visibility`      | `CharField(max_length=16)`                 | `"owner"` (default) or `"organization"`                                       |
| `query`           | `TextField`                                | Issue stream filter query                                                     |
| `query_sort`      | `CharField(max_length=16)`                 | Sort option (e.g. `"date"`, `"new"`)                                          |
| `position`        | `PositiveSmallIntegerField(null=True)`     | Legacy position (owned views); deferred unique per `(user_id, org, position)` |
| `projects`        | M2M via `GroupSearchViewProject`           | Associated projects                                                           |
| `is_all_projects` | `BooleanField(db_default=False)`           | Whether the view applies to all projects                                      |
| `environments`    | `ArrayField(CharField)`                    | Selected environments                                                         |
| `time_filters`    | `JSONField`                                | Time range filter (default `{"period": "14d"}`)                               |
| `date_added`      | auto                                       | Creation timestamp                                                            |
| `date_updated`    | auto                                       | Last update timestamp                                                         |

**Relevant class constants**:

- `GroupSearchViewVisibility.ORGANIZATION = "organization"`
- `GroupSearchViewVisibility.OWNER = "owner"`

**Access rule for star/unstar**: A user may star/unstar a view `V` in organization `O` if and only if:

```
V.organization_id == O.id
AND (V.user_id == request.user.id OR V.visibility == "organization")
```

---

### Entity 2: `GroupSearchViewStarred` ← **primary join table for starring**

**Table**: `sentry_groupsearchviewstarred`  
**File**: `src/sentry/models/groupsearchviewstarred.py`

| Field               | Type                                          | Notes                                            |
| ------------------- | --------------------------------------------- | ------------------------------------------------ |
| `id`                | auto PK                                       |                                                  |
| `user_id`           | `HybridCloudForeignKey → sentry.User`         | The user who starred the view                    |
| `organization`      | `FlexibleForeignKey → sentry.Organization`    | Tenant boundary                                  |
| `group_search_view` | `FlexibleForeignKey → sentry.GroupSearchView` | The starred view                                 |
| `position`          | `PositiveSmallIntegerField`                   | 0-based position in user's personal starred list |
| `date_added`        | auto                                          | When starred                                     |
| `date_updated`      | auto                                          | Last updated                                     |

**Constraints**:

- `DEFERRED UNIQUE (user_id, organization_id, position)` — uniqueness enforced at transaction commit, allowing bulk position shifts within a transaction.

**Semantics**:

- A row in this table means "user X has starred view V at position N in org O".
- Absence of a row means the view is not starred by that user.
- `position` is 0-based, dense (no gaps).

**Manager methods** (`GroupSearchViewStarredManager`):

- `reorder_starred_views(organization, user_id, new_view_positions: list[int])` — bulk-reorders all positions; raises `ValueError` on set mismatch. Used by the starred-order endpoint (not used by star/unstar).

---

### Entity 3: `GroupSearchViewLastVisited` (read reference only)

**Table**: `sentry_groupsearchviewlastvisited`  
**File**: `src/sentry/models/groupsearchviewlastvisited.py`

Not modified by this feature. Referenced by serializers to populate `lastVisited` in responses.

---

## State Transitions

### Star a view (FR-001, FR-003, FR-005, FR-006, FR-007)

```
PRECONDITION: View accessible to user (own or org-visibility, same org)

IF GroupSearchViewStarred(user, org, view) already exists:
    → no-op, return existing record  [idempotent per FR-003]

ELSE:
    resolve_position:
        IF position param provided AND 0 <= position <= current_count:
            shift: UPDATE sentry_groupsearchviewstarred
                   SET position = position + 1
                   WHERE user_id=user AND org=org AND position >= requested_position
        ELSE (no position or out-of-range):
            position = COUNT(*) WHERE user_id=user AND org=org

    INSERT INTO sentry_groupsearchviewstarred
        (user_id, org, group_search_view, position)
        VALUES (user, org, view, position)
```

### Unstar a view (FR-002, FR-004)

```
PRECONDITION: View accessible to user (own or org-visibility, same org)

IF GroupSearchViewStarred(user, org, view) does not exist:
    → no-op, return 204  [idempotent per FR-004]

ELSE:
    deleted_position = starredView.position
    DELETE FROM sentry_groupsearchviewstarred
        WHERE user_id=user AND org=org AND group_search_view=view

    UPDATE sentry_groupsearchviewstarred
        SET position = position - 1
        WHERE user_id=user AND org=org AND position > deleted_position
```

---

## Validation Rules

| Rule                                                   | FR             | Details                                                                                                                                                                                                   |
| ------------------------------------------------------ | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| View must exist and be accessible                      | FR-008, FR-010 | `GroupSearchView.objects.get(id=view_id, organization=organization)` then check `user_id == request.user.id OR visibility == "organization"`. Return `404` if not found, `403` if found but inaccessible. |
| `position` must be a non-negative integer, if provided | FR-005         | Validated by serializer `PositiveIntegerField(allow_null=True)`. Out-of-range values silently clamp to end of list.                                                                                       |
| All writes must be atomic                              | FR-009         | `transaction.atomic(using=router.db_for_write(GroupSearchViewStarred))`                                                                                                                                   |

---

## No New Models

The `GroupSearchViewStarred` model was introduced in migration `0836` and backfilled from existing `GroupSearchView.position` values in migration `0838`. This feature adds no new database tables or columns.
