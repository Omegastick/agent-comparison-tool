# Data Model: Star and Unstar Shared Issue Views

**Feature Branch**: `001-star-unstar-views`
**Date**: 2026-02-19

## Entities

### GroupSearchView (EXISTING — no changes)

The primary entity representing a saved issue search view. Can be owned by a user or shared with an organization.

**Source**: `src/sentry/models/groupsearchview.py:44-92`

| Field           | Type                             | Constraints                                          | Description                                                         |
| --------------- | -------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------- |
| id              | BigAutoField                     | PK                                                   | Auto-generated primary key                                          |
| name            | TextField                        | max_length=128                                       | Display name of the view                                            |
| user_id         | HybridCloudForeignKey(User)      | CASCADE                                              | Owner of the view                                                   |
| organization    | FlexibleForeignKey(Organization) | -                                                    | Owning organization                                                 |
| visibility      | CharField(16)                    | db_default="owner", choices=["organization","owner"] | Who can see/star the view                                           |
| query           | TextField                        | -                                                    | Search query string                                                 |
| query_sort      | CharField(16)                    | default="date"                                       | Sort order                                                          |
| position        | PositiveSmallIntegerField        | null=True                                            | Legacy position (being replaced by GroupSearchViewStarred.position) |
| is_all_projects | BooleanField                     | db_default=False                                     | Override to "All Projects"                                          |
| environments    | ArrayField(CharField)            | default=list                                         | Environment filters                                                 |
| time_filters    | JSONField                        | db_default={"period":"14d"}                          | Time range filters                                                  |
| date_added      | DateTimeField                    | null=True                                            | Creation timestamp                                                  |
| date_updated    | DateTimeField                    | auto_now                                             | Last update timestamp                                               |

**Constraints**:

- UniqueConstraint: `(user_id, organization_id, position)` — deferred

**Relationships**:

- M2M to `Project` through `GroupSearchViewProject`
- One-to-many to `GroupSearchViewStarred` (a view can be starred by many users)
- One-to-many to `GroupSearchViewLastVisited`

---

### GroupSearchViewStarred (EXISTING — no changes)

Junction table representing a user's starred (bookmarked) view with position ordering.

**Source**: `src/sentry/models/groupsearchviewstarred.py:52-75`

| Field             | Type                                | Constraints  | Description                                |
| ----------------- | ----------------------------------- | ------------ | ------------------------------------------ |
| id                | BigAutoField                        | PK           | Auto-generated primary key                 |
| user_id           | HybridCloudForeignKey(User)         | CASCADE      | User who starred the view                  |
| organization      | FlexibleForeignKey(Organization)    | -            | Organization scope                         |
| group_search_view | FlexibleForeignKey(GroupSearchView) | -            | The starred view                           |
| position          | PositiveSmallIntegerField           | NOT NULL     | Zero-based position in user's ordered list |
| date_added        | DateTimeField                       | auto_now_add | When the star was created                  |
| date_updated      | DateTimeField                       | auto_now     | Last update timestamp                      |

**Constraints**:

- UniqueConstraint: `(user_id, organization_id, position)` — deferred (allows temporary duplicates during reorder within a transaction)

**Custom Manager**: `GroupSearchViewStarredManager`

- `reorder_starred_views(organization, user_id, new_view_positions)` — bulk reorders positions

**Silo**: `@region_silo_model`
**Relocation scope**: `RelocationScope.Organization`

---

## Access Rules

A user can star a view if and only if:

1. The view belongs to the same organization as the user, AND
2. Either:
   - `view.user_id == request.user.id` (user owns the view), OR
   - `view.visibility == "organization"` (view is shared with the org)

This logic is codified in the existing `GroupSearchViewStarredOrderSerializer.validate_view_ids()` at `src/sentry/issues/endpoints/organization_group_search_view_starred_order.py:33-38`.

---

## State Transitions

### Star Operation

```
User has N starred views at positions [0..N-1]

Case 1: Star without position
  → Create GroupSearchViewStarred(position=N)
  → User now has N+1 starred views at [0..N]

Case 2: Star at position P (where 0 <= P <= N)
  → Shift all starred views with position >= P by +1
  → Create GroupSearchViewStarred(position=P)
  → User now has N+1 starred views at [0..N]

Case 3: Star at position P > N (clamped)
  → Treat as Case 1 (append to end)

Case 4: View already starred (idempotent)
  → No state change, return current state
```

### Unstar Operation

```
User has N starred views at positions [0..N-1]

Case 1: View is starred at position P
  → Delete GroupSearchViewStarred record
  → Shift all starred views with position > P by -1
  → User now has N-1 starred views at [0..N-2]

Case 2: View is not starred (idempotent)
  → No state change, return 204
```

---

## Entity Relationship Diagram

```
┌──────────────┐
│     User     │
└──────┬───────┘
       │ 1
       │
       │ *
┌──────┴───────────────┐        ┌──────────────────┐
│ GroupSearchViewStarred│───────►│  GroupSearchView  │
│                      │ *    1 │                   │
│ - user_id            │        │ - user_id (owner) │
│ - organization       │        │ - organization    │
│ - group_search_view  │        │ - visibility      │
│ - position           │        │ - query, name...  │
└──────────────────────┘        └──────────────────┘
                                        │ 1
                                        │
                                        │ *
                                ┌───────┴──────────┐
                                │GroupSearchView    │
                                │Project (M2M)     │
                                └──────────────────┘
```
