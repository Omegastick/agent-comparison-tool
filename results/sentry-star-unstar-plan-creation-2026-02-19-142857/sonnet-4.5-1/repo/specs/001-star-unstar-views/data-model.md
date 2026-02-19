# Data Model: Star and Unstar Shared Issue Views

**Feature**: 001-star-unstar-views  
**Date**: 2026-02-19  
**Status**: Complete

## Overview

This document describes the data model for the star/unstar feature. **Note**: The core models already exist in Sentry. This feature adds dedicated star/unstar API endpoints to complement the existing bulk operations.

---

## Entities

### 1. GroupSearchView (Existing)

**Description**: Represents a saved issue search view with filters and display preferences. Can be owned by a user or shared with an organization.

**Location**: `/workspace/repo/src/sentry/models/groupsearchview.py`

**Scope**: Region silo, organization-scoped

**Fields**:

| Field           | Type                      | Required | Constraints                                      | Description                          |
| --------------- | ------------------------- | -------- | ------------------------------------------------ | ------------------------------------ |
| id              | BigAutoField              | Yes      | Primary key                                      | Unique identifier                    |
| name            | TextField                 | Yes      | max_length=128                                   | Display name of the view             |
| user_id         | HybridCloudForeignKey     | Yes      | FK to User, CASCADE                              | Creator/owner of the view            |
| organization    | FlexibleForeignKey        | Yes      | FK to Organization                               | Organization scope                   |
| visibility      | CharField                 | Yes      | choices: "owner"/"organization", default="owner" | Access control                       |
| query           | TextField                 | Yes      | -                                                | Lucene-style search query            |
| query_sort      | CharField                 | Yes      | choices from SortOptions, default="date"         | Sort order for results               |
| position        | PositiveSmallIntegerField | No       | Nullable                                         | View's position in user's list       |
| projects        | ManyToManyField           | No       | Through GroupSearchViewProject                   | Filtered projects                    |
| is_all_projects | BooleanField              | Yes      | default=False                                    | Whether view applies to all projects |
| environments    | ArrayField                | Yes      | default=[]                                       | Filtered environments                |
| time_filters    | JSONField                 | Yes      | default={"period": "14d"}                        | Time range filters                   |
| date_added      | DateTimeField             | Yes      | Auto                                             | Creation timestamp                   |
| date_updated    | DateTimeField             | Yes      | Auto-updated                                     | Last modification timestamp          |

**Relationships**:

- Belongs to one User (creator)
- Belongs to one Organization
- Has many Projects (via GroupSearchViewProject through table)
- Has many GroupSearchViewStarred entries (users who starred it)
- Has many GroupSearchViewLastVisited entries (users who visited it)

**Constraints**:

- UniqueConstraint(["user_id", "organization_id", "position"], deferrable=DEFERRED)

**Validation Rules**:

- Name must not be empty
- Query must be valid Lucene syntax (validated at API layer)
- Projects must belong to the organization
- Maximum 50 views per user per organization

**State Transitions**: N/A (simple CRUD entity)

---

### 2. GroupSearchViewStarred (Existing)

**Description**: Many-to-many relationship between users and views, representing which views a user has starred/bookmarked. Includes position for ordered display.

**Location**: `/workspace/repo/src/sentry/models/groupsearchviewstarred.py`

**Scope**: Region silo, organization + user scoped

**Fields**:

| Field             | Type                      | Required | Constraints           | Description                                |
| ----------------- | ------------------------- | -------- | --------------------- | ------------------------------------------ |
| id                | BigAutoField              | Yes      | Primary key           | Unique identifier                          |
| user_id           | HybridCloudForeignKey     | Yes      | FK to User, CASCADE   | User who starred the view                  |
| organization      | FlexibleForeignKey        | Yes      | FK to Organization    | Organization scope (for efficient queries) |
| group_search_view | FlexibleForeignKey        | Yes      | FK to GroupSearchView | The starred view                           |
| position          | PositiveSmallIntegerField | Yes      | 0-indexed             | Position in user's ordered starred list    |
| date_added        | DateTimeField             | Yes      | Auto                  | When view was starred                      |
| date_updated      | DateTimeField             | Yes      | Auto-updated          | Last position update                       |

**Relationships**:

- Belongs to one User (the one who starred)
- Belongs to one Organization (denormalized for query efficiency)
- Belongs to one GroupSearchView (the starred view)

**Constraints**:

- UniqueConstraint(["user_id", "organization_id", "position"], deferrable=DEFERRED)
  - **Note**: Deferred constraint is critical - allows atomic reordering within transactions
- Implicit unique constraint on ["user_id", "group_search_view"] via idempotent star logic

**Validation Rules**:

- User must have access to the view (own it OR view is organization-shared)
- Position must be non-negative
- Position must be within range [0, N-1] where N is count of user's starred views

**State Transitions**:

```
[Non-existent] --star()--> [Starred at position P]
[Starred at position P] --unstar()--> [Non-existent]
[Starred at position P] --reorder()--> [Starred at position Q]
[Starred at position P] --star(same view)--> [Starred at position P] (idempotent)
```

**Lifecycle**:

1. Created when user stars a view (via star endpoint or bulk PUT)
2. Position updated when user reorders starred views
3. Position adjusted when other starred views are deleted
4. Deleted when user unstars the view OR when referenced view is deleted (CASCADE)

---

### 3. GroupSearchViewProject (Existing Through Table)

**Description**: Many-to-many through table linking views to projects.

**Location**: `/workspace/repo/src/sentry/models/groupsearchview.py` (inline)

**Fields**:

- group_search_view (FK to GroupSearchView, CASCADE)
- project (FK to Project, CASCADE)
- date_added, date_updated (from DefaultFieldsModel)

---

### 4. GroupSearchViewLastVisited (Existing)

**Description**: Tracks when users last visited/viewed each view (for UI "last visited" display).

**Location**: `/workspace/repo/src/sentry/models/groupsearchviewlastvisited.py`

**Fields**:

- user_id (HybridCloudForeignKey to User, CASCADE)
- organization (FlexibleForeignKey to Organization)
- group_search_view (FlexibleForeignKey to GroupSearchView)
- last_visited (DateTimeField, default=now)

**Constraints**:

- UniqueConstraint(["user_id", "organization_id", "group_search_view_id"])

---

## Entity Relationship Diagram

```
┌─────────────────────┐
│   Organization      │
│                     │
└──────────┬──────────┘
           │
           │ 1:N
           │
┌──────────▼──────────┐         ┌─────────────────────┐
│   GroupSearchView   │◄────────┤      Project        │
│  - id               │  M:N    │                     │
│  - name             │ (via    └─────────────────────┘
│  - user_id          │  through)
│  - organization     │
│  - visibility       │
│  - query            │
│  - query_sort       │
│  - position         │
└──────────┬──────────┘
           │
           │ 1:N
           │
           ├───────────────────────────────────┐
           │                                   │
┌──────────▼──────────────┐     ┌─────────────▼──────────────┐
│ GroupSearchViewStarred  │     │ GroupSearchViewLastVisited │
│  - id                   │     │  - user_id                 │
│  - user_id              │     │  - group_search_view       │
│  - organization         │     │  - last_visited            │
│  - group_search_view    │     └────────────────────────────┘
│  - position             │
└─────────────────────────┘


Relationships:
- User ---1:N---> GroupSearchView (creator/owner)
- User ---M:N---> GroupSearchView (via GroupSearchViewStarred)
- User ---1:N---> GroupSearchViewLastVisited
- Organization ---1:N---> GroupSearchView
- GroupSearchView ---M:N---> Project (via GroupSearchViewProject)
```

---

## Data Access Patterns

### 1. Star a View

**Use case**: User bookmarks a view they find useful

**Query pattern**:

```python
# Validate view access
view = GroupSearchView.objects.get(
    id=view_id,
    organization=organization
)
if view.user_id != user.id and view.visibility != "organization":
    raise PermissionDenied

# Determine position
if position is None:
    max_pos = GroupSearchViewStarred.objects.filter(
        user_id=user.id,
        organization=organization
    ).aggregate(Max("position"))["position__max"]
    position = (max_pos + 1) if max_pos is not None else 0

# Star (idempotent)
GroupSearchViewStarred.objects.update_or_create(
    user_id=user.id,
    organization=organization,
    group_search_view=view,
    defaults={"position": position}
)

# If position specified, shift existing items
if position_specified:
    GroupSearchViewStarred.objects.filter(
        user_id=user.id,
        organization=organization,
        position__gte=position
    ).exclude(group_search_view=view).update(position=F("position") + 1)
```

**Indexes used**:

- (user_id, organization_id, position) - UNIQUE constraint index
- (user_id, group_search_view_id) - Implicit for idempotency check

---

### 2. Unstar a View

**Use case**: User removes a bookmarked view from their list

**Query pattern**:

```python
# Get starred entry
try:
    starred = GroupSearchViewStarred.objects.get(
        user_id=user.id,
        organization=organization,
        group_search_view_id=view_id
    )
    deleted_position = starred.position
    starred.delete()

    # Adjust positions of remaining items
    GroupSearchViewStarred.objects.filter(
        user_id=user.id,
        organization=organization,
        position__gt=deleted_position
    ).update(position=F("position") - 1)
except GroupSearchViewStarred.DoesNotExist:
    pass  # Idempotent - already unstarred
```

**Indexes used**:

- (user_id, organization_id, group_search_view_id) - for lookup
- (user_id, organization_id, position) - for position adjustment

---

### 3. List Starred Views

**Use case**: Retrieve all starred views for a user in order

**Query pattern**:

```python
starred_views = GroupSearchViewStarred.objects.filter(
    user_id=user.id,
    organization=organization
).select_related(
    "group_search_view"
).prefetch_related(
    "group_search_view__projects"
).order_by("position")
```

**Indexes used**:

- (user_id, organization_id) - for filtering
- (position) - for sorting

**Serialization**: Uses `GroupSearchViewStarredSerializer` with batch-fetched `lastVisited` data

---

### 4. Reorder Starred Views

**Use case**: User changes the order of their starred views

**Query pattern**:

```python
with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
    starred_views = GroupSearchViewStarred.objects.filter(
        user_id=user.id,
        organization=organization
    )

    # Validate: new order must match existing starred views
    existing_ids = {v.group_search_view_id for v in starred_views}
    if existing_ids != set(new_order):
        raise ValueError("Mismatch")

    # Create position map
    position_map = {view_id: idx for idx, view_id in enumerate(new_order)}

    # Update positions in memory
    views_to_update = list(starred_views)
    for view in views_to_update:
        view.position = position_map[view.group_search_view_id]

    # Bulk update (single query)
    GroupSearchViewStarred.objects.bulk_update(views_to_update, ["position"])
```

**Indexes used**:

- (user_id, organization_id, position) - DEFERRED constraint allows temporary duplicates during transaction

---

### 5. Check if View is Starred

**Use case**: Determine if a view is starred by the current user (for UI display)

**Query pattern**:

```python
# In serializer get_attrs() to avoid N+1
starred_ids = set(
    GroupSearchViewStarred.objects.filter(
        user_id=user.id,
        group_search_view_id__in=[view.id for view in view_list]
    ).values_list("group_search_view_id", flat=True)
)

# Return {view: {"is_starred": view.id in starred_ids}}
```

---

### 6. Delete View (Cascade to Starred)

**Use case**: View owner deletes a view

**Query pattern**:

```python
view = GroupSearchView.objects.get(
    id=view_id,
    user_id=user.id,
    organization=organization
)

# Delete view (cascades to GroupSearchViewStarred due to FK)
view.delete()

# Adjust positions for all users who had starred it
# (This is handled automatically by CASCADE, but positions need adjustment)
# Note: Current implementation does NOT adjust positions across users
# Each user's starred list may have gaps, which are handled by serializer
```

**Note**: In production, position adjustment on cascade deletion is not implemented for cross-user cleanup. This is acceptable because positions are user-scoped and gaps can be normalized by the reorder endpoint.

---

## Indexing Strategy

**Existing indexes** (created by constraints and foreign keys):

1. **Primary keys**:
   - groupsearchview.id
   - groupsearchviewstarred.id

2. **Unique constraints** (create indexes):
   - groupsearchview: (user_id, organization_id, position) [DEFERRED]
   - groupsearchviewstarred: (user_id, organization_id, position) [DEFERRED]

3. **Foreign keys** (automatic indexes in PostgreSQL):
   - groupsearchview: user_id, organization_id
   - groupsearchviewstarred: user_id, organization_id, group_search_view_id

**Query performance**:

- List starred views: O(log N) lookup by (user_id, org_id), then sequential scan of user's starred items
- Star/unstar: O(log N) lookup by (user_id, org_id, view_id)
- Reorder: O(N) bulk update where N = count of user's starred views
- Position adjustment: O(K) where K = count of items after deleted position

**Expected scale**:

- Thousands of views per organization
- Hundreds of starred views per user
- Millions of starred relationships total

---

## Data Integrity Rules

### Database Level

1. **Foreign key constraints**: ON DELETE CASCADE
   - Deleting a User cascades to GroupSearchView and GroupSearchViewStarred
   - Deleting an Organization cascades to all related entities
   - Deleting a GroupSearchView cascades to GroupSearchViewStarred

2. **Unique constraints**:
   - (user_id, organization_id, position) - No duplicate positions for a user
   - DEFERRED - Checked at transaction commit, not per statement

3. **Check constraints**: None (validation at application layer)

### Application Level

1. **Access control**: User can only star views they have access to (owned or org-shared)
2. **Position bounds**: Position must be in range [0, N-1]
3. **Organization membership**: User must be member of organization
4. **View limit**: Maximum 50 views per user (enforced in bulk PUT endpoint)
5. **Idempotency**: Star/unstar operations are idempotent

---

## Migration Considerations

**Current state**: All tables exist with proper constraints

**No migrations required** for adding dedicated star/unstar endpoints (uses existing schema)

**If schema changes needed in future**:

- Use `SeparateDatabaseAndState` for DEFERRED constraints
- Create indexes with `CONCURRENTLY` to avoid locking
- Use `RangeQuerySetWrapperWithProgressBar` for data backfills
- Ensure backwards compatibility (additive changes only)

---

## Data Validation Examples

### Valid Star Operation

```json
POST /organizations/acme/group-search-views/123/star/
{
  "position": 2
}

// Result: View 123 starred at position 2
// Existing items at positions 2+ shift to 3+
```

### Invalid Star Operation (No Access)

```json
POST /organizations/acme/group-search-views/456/star/

// User doesn't own view 456, and it's visibility="owner"
// Result: 403 Forbidden
{
  "detail": "You do not have access to this view"
}
```

### Valid Unstar Operation (Idempotent)

```json
DELETE /organizations/acme/group-search-views/123/star/

// Result: 204 No Content
// If view was starred: removed from starred list, positions adjusted
// If view was not starred: no-op, still returns 204
```

### Valid Reorder Operation

```json
PUT /organizations/acme/group-search-views-starred-order/
{
  "viewIds": [789, 456, 123]
}

// Result: 204 No Content
// Starred views reordered to positions 0, 1, 2
```

### Invalid Reorder Operation (Missing View)

```json
PUT /organizations/acme/group-search-views-starred-order/
{
  "viewIds": [789, 456]  // Missing view 123 that user has starred
}

// Result: 400 Bad Request
{
  "detail": "Mismatch between existing and provided starred views."
}
```

---

## Summary

The data model leverages existing Sentry entities:

- **GroupSearchView**: Represents saved issue search views
- **GroupSearchViewStarred**: Many-to-many relationship with position ordering
- **Deferred unique constraints**: Enable atomic reordering within transactions
- **Foreign key cascades**: Maintain referential integrity
- **Application-level validation**: Enforce access control and business rules

The model is production-ready and already battle-tested. New star/unstar endpoints will use the existing schema with no migrations required.
