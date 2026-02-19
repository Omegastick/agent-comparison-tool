# Data Model: Star and Unstar Shared Issue Views

**Feature Branch**: `001-star-unstar-views`
**Date**: 2026-02-19

## Entities

### GroupSearchView (Existing — No Changes)

The saved issue search view entity. Can be owned by a user or shared with an organization.

| Field             | Type                               | Constraints                                   | Description                                            |
| ----------------- | ---------------------------------- | --------------------------------------------- | ------------------------------------------------------ |
| `id`              | `BigAutoField`                     | PK                                            | Primary key                                            |
| `name`            | `TextField`                        | max_length=128                                | Display name                                           |
| `user_id`         | `HybridCloudForeignKey(User)`      | NOT NULL, on_delete=CASCADE                   | Owner/creator                                          |
| `organization`    | `FlexibleForeignKey(Organization)` | NOT NULL, on_delete=CASCADE                   | Owning organization                                    |
| `visibility`      | `CharField(16)`                    | db_default="owner"                            | `"owner"` or `"organization"`                          |
| `query`           | `TextField`                        | NOT NULL                                      | Search query string                                    |
| `query_sort`      | `CharField(16)`                    | default="date"                                | Sort order                                             |
| `position`        | `PositiveSmallIntegerField`        | NULL, DEFERRED UNIQUE(user_id, org, position) | Legacy position (being superseded by starred position) |
| `is_all_projects` | `BooleanField`                     | db_default=False                              | Whether view spans all projects                        |
| `projects`        | `ManyToManyField(Project)`         | through=GroupSearchViewProject                | Associated projects                                    |
| `environments`    | `ArrayField(CharField)`            | default=list                                  | Environment filters                                    |
| `time_filters`    | `JSONField`                        | db_default={"period": "14d"}                  | Time range filters                                     |
| `date_added`      | `DateTimeField`                    | default=now, NULL                             | Creation timestamp                                     |
| `date_updated`    | `DateTimeField`                    | default=now                                   | Last update timestamp                                  |

**Location**: `src/sentry/models/groupsearchview.py`
**Table**: `sentry_groupsearchview`
**Silo**: `@region_silo_model`

---

### GroupSearchViewStarred (Existing — No Changes)

The join table between a user and a starred `GroupSearchView`. Maintains an ordered list of starred views per user per organization.

| Field               | Type                                  | Constraints                 | Description                                 |
| ------------------- | ------------------------------------- | --------------------------- | ------------------------------------------- |
| `id`                | `BigAutoField`                        | PK                          | Primary key                                 |
| `user_id`           | `HybridCloudForeignKey(User)`         | NOT NULL, on_delete=CASCADE | User who starred the view                   |
| `organization`      | `FlexibleForeignKey(Organization)`    | NOT NULL, on_delete=CASCADE | Organization scope                          |
| `group_search_view` | `FlexibleForeignKey(GroupSearchView)` | NOT NULL, on_delete=CASCADE | The starred view                            |
| `position`          | `PositiveSmallIntegerField`           | NOT NULL                    | User's ordering position (0-indexed, dense) |
| `date_added`        | `DateTimeField`                       | default=now, NULL           | When the view was starred                   |
| `date_updated`      | `DateTimeField`                       | default=now                 | Last update timestamp                       |

**Constraints**:

- `UniqueConstraint(fields=["user_id", "organization_id", "position"], deferrable=DEFERRED)` — prevents two starred views from occupying the same position; deferred to allow in-transaction position shifts.

**Location**: `src/sentry/models/groupsearchviewstarred.py`
**Table**: `sentry_groupsearchviewstarred`
**Silo**: `@region_silo_model`

**Custom Manager** (`GroupSearchViewStarredManager`):

- `reorder_starred_views(organization, user_id, new_view_positions)` — bulk reorders positions by mapping view IDs to indices.

---

## Relationships

```
User (control silo)
  │
  │ HybridCloudForeignKey (user_id)
  ├──────────────────────────────────► GroupSearchView (region silo)
  │                                      │
  │ HybridCloudForeignKey (user_id)      │ FlexibleForeignKey (group_search_view)
  ├──────────────────────────────────► GroupSearchViewStarred (region silo)
  │                                      │
  │                                      │ FlexibleForeignKey (organization)
  │                                      ▼
  └──────────────────────────────────► Organization (region silo)
```

**Key relationship**: A user can star many views. A view can be starred by many users. `GroupSearchViewStarred` is the many-to-many join table with an additional `position` attribute for per-user ordering.

---

## Validation Rules

| Rule                                           | Source         | Enforcement                                                                            |
| ---------------------------------------------- | -------------- | -------------------------------------------------------------------------------------- |
| View must belong to user's organization        | FR-008, FR-010 | Endpoint query: `GroupSearchView.objects.get(id=view_id, organization=organization)`   |
| View must be accessible (owned or org-visible) | FR-008, FR-010 | Endpoint check: `view.user_id == request.user.id or view.visibility == "organization"` |
| Position must be non-negative integer          | FR-005         | DRF serializer `IntegerField(min_value=0, required=False)`                             |
| Position clamped to list bounds                | Research R8    | Endpoint logic: `min(requested_position, current_count)`                               |
| Star is idempotent                             | FR-003         | Endpoint: check existing before creating                                               |
| Unstar is idempotent                           | FR-004         | Endpoint: handle `DoesNotExist` gracefully                                             |
| Positions remain dense (no gaps)               | Invariant      | On star-at-position: shift subsequent up by 1. On unstar: shift subsequent down by 1.  |

---

## State Transitions

### Starred View Lifecycle

```
                Star (PUT)
    ┌─────────────────────────────┐
    │                             ▼
[Not Starred] ──────────► [Starred at position N]
    ▲                             │
    │                             │ Unstar (DELETE)
    └─────────────────────────────┘
```

### Position Shift on Star (Insert at position P)

```
Before: [A:0] [B:1] [C:2]
Star X at position 1:
  1. Shift B(1→2), C(2→3)
  2. Insert X at 1
After:  [A:0] [X:1] [B:2] [C:3]
```

### Position Shift on Unstar (Remove from position P)

```
Before: [A:0] [X:1] [B:2] [C:3]
Unstar X (position 1):
  1. Delete X
  2. Shift B(2→1), C(3→2)
After:  [A:0] [B:1] [C:2]
```

---

## No New Migrations Required

Both `GroupSearchView` and `GroupSearchViewStarred` tables already exist with all required fields and constraints. This feature only adds a new API endpoint — no schema changes.
