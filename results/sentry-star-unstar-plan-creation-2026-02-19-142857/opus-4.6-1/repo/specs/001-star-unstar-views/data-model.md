# Data Model: Star and Unstar Shared Issue Views

**Feature Branch**: `001-star-unstar-views`
**Date**: 2026-02-19

## Entities

### GroupSearchView (EXISTING — no changes)

The core entity representing a saved issue search view.

**Source**: `src/sentry/models/groupsearchview.py`
**Table**: `sentry_groupsearchview`
**Silo**: Region (`@region_silo_model`)

| Field             | Type                             | Constraints              | Description                                            |
| ----------------- | -------------------------------- | ------------------------ | ------------------------------------------------------ |
| `id`              | BigAutoField                     | PK                       | Auto-generated primary key                             |
| `name`            | TextField                        | max_length=128           | Display name of the view                               |
| `user_id`         | HybridCloudForeignKey(User)      | CASCADE                  | Owning user (cross-silo)                               |
| `organization`    | FlexibleForeignKey(Organization) | FK                       | Owning organization                                    |
| `visibility`      | CharField(16)                    | default="owner"          | `"owner"` or `"organization"`                          |
| `query`           | TextField                        | —                        | Search query string                                    |
| `query_sort`      | CharField(16)                    | default=DATE             | Sort option                                            |
| `position`        | PositiveSmallIntegerField        | nullable                 | Legacy position (being superseded by starred position) |
| `is_all_projects` | BooleanField                     | default=False            | Override to "All Projects"                             |
| `environments`    | ArrayField(CharField)            | default=[]               | Environment filters                                    |
| `time_filters`    | JSONField                        | default={"period":"14d"} | Time range filters                                     |
| `date_added`      | DateTimeField                    | auto                     | Creation timestamp                                     |
| `date_updated`    | DateTimeField                    | auto                     | Last update timestamp                                  |

**Unique constraint** (deferred): `(user_id, organization_id, position)`

**Relationships**:

- Has many `GroupSearchViewProject` (through table for M2M with Project)
- Has many `GroupSearchViewStarred` (users who starred this view)
- Has many `GroupSearchViewLastVisited` (visit tracking)

**Visibility rules**:

- `"owner"`: Only the owning user can see/star this view
- `"organization"`: Any organization member can see/star this view

---

### GroupSearchViewStarred (EXISTING — no changes)

The join entity representing a user's star (bookmark) of a view with ordered positioning.

**Source**: `src/sentry/models/groupsearchviewstarred.py`
**Table**: `sentry_groupsearchviewstarred`
**Silo**: Region (`@region_silo_model`)

| Field               | Type                                | Constraints | Description                               |
| ------------------- | ----------------------------------- | ----------- | ----------------------------------------- |
| `id`                | BigAutoField                        | PK          | Auto-generated primary key                |
| `user_id`           | HybridCloudForeignKey(User)         | CASCADE     | User who starred (cross-silo)             |
| `organization`      | FlexibleForeignKey(Organization)    | FK          | Organization scope                        |
| `group_search_view` | FlexibleForeignKey(GroupSearchView) | FK          | The starred view                          |
| `position`          | PositiveSmallIntegerField           | NOT NULL    | 0-indexed position in user's starred list |
| `date_added`        | DateTimeField                       | auto        | When the star was created                 |
| `date_updated`      | DateTimeField                       | auto        | When the star was last modified           |

**Unique constraint** (deferred): `(user_id, organization_id, position)` — ensures no two starred views occupy the same position for a user in an organization. Deferred to allow temporary duplicates during atomic reordering.

**Custom manager**: `GroupSearchViewStarredManager`

- `reorder_starred_views(organization, user_id, new_view_positions)` — bulk reorders positions

---

## State Transitions

### Star Operation

```
[View exists, not starred by user]
    ├── Star without position → position = max(existing) + 1
    └── Star with position N →
        ├── Shift all starred views at position >= N by +1
        └── Create starred entry at position N

[View exists, already starred by user]
    └── Return 204 (idempotent, no change)
```

### Unstar Operation

```
[View starred by user at position N]
    ├── Delete starred entry
    └── Decrement all starred views with position > N by 1

[View not starred by user]
    └── Return 204 (idempotent, no change)
```

### Position Integrity Invariant

For a given `(user_id, organization_id)`, positions must always form a contiguous 0-indexed sequence: `0, 1, 2, ..., N-1` where N is the number of starred views. This invariant is maintained by:

- **Star (append)**: New position = count of existing starred views
- **Star (insert)**: Shift positions >= target, then insert
- **Unstar**: Delete entry, then decrement positions > deleted position

---

## Validation Rules

| Rule                                     | Field/Entity             | Enforcement                                                               |
| ---------------------------------------- | ------------------------ | ------------------------------------------------------------------------- |
| User must have access to view            | `GroupSearchView`        | Query checks `user_id == request.user.id OR visibility == "organization"` |
| View must belong to request organization | `GroupSearchView`        | Query filtered by `organization=organization`                             |
| Position must be non-negative            | `position`               | `PositiveSmallIntegerField` + serializer validation                       |
| Position clamped to valid range          | `position`               | Business logic: `min(position, count)`                                    |
| One star per user per view               | `GroupSearchViewStarred` | `get_or_create` pattern + unique constraint                               |

---

## Migration Impact

**No schema changes required.** All entities already exist with the needed fields and constraints. The feature only adds a new endpoint to operate on existing data.
