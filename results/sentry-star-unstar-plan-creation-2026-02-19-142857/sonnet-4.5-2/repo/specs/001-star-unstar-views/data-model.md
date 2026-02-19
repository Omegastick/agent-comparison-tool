# Data Model: Star and Unstar Shared Issue Views

**Feature Branch**: `001-star-unstar-views`  
**Date**: 2026-02-19

## Overview

This feature leverages existing data models in the Sentry codebase. No new models or migrations are required. This document describes the entities involved and their relationships for reference.

## Entities

### GroupSearchView (Existing)

**File**: `/workspace/repo/src/sentry/models/groupsearchview.py`

Represents a saved issue search configuration that can be owned by a user or shared with an organization.

**Fields**:

- `id` (BigAutoField): Primary key
- `user_id` (HybridCloudForeignKey): Owner of the view
- `organization` (FlexibleForeignKey): Organization scope
- `name` (TextField, max_length=128): Display name
- `visibility` (CharField): `OWNER` or `ORGANIZATION`
- `query` (TextField): Search query string
- `query_sort` (CharField): Sort order
- `position` (PositiveSmallIntegerField, nullable): Position in user's view list
- `projects` (ManyToManyField): Associated projects (through `GroupSearchViewProject`)
- `is_all_projects` (BooleanField): Override to include all projects
- `environments` (ArrayField): List of environment names
- `time_filters` (JSONField): Time range filters
- `date_added` (DateTimeField): Creation timestamp
- `date_updated` (DateTimeField): Last modification timestamp

**Constraints**:

```python
UniqueConstraint(
    fields=["user_id", "organization_id", "position"],
    name="sentry_issueviews_unique_view_position_per_org_user",
    deferrable=models.Deferrable.DEFERRED
)
```

**Access Control**:

- Views with `visibility=OWNER` are only accessible to the owner
- Views with `visibility=ORGANIZATION` are accessible to all members of the organization

### GroupSearchViewStarred (Existing)

**File**: `/workspace/repo/src/sentry/models/groupsearchviewstarred.py`

Junction table representing a user's starred/favorited views with position ordering.

**Fields**:

- `id` (BigAutoField): Primary key
- `user_id` (HybridCloudForeignKey): User who starred the view
- `organization` (FlexibleForeignKey): Organization scope (denormalized for performance)
- `group_search_view` (FlexibleForeignKey): The starred view
- `position` (PositiveSmallIntegerField): Order in user's starred list (1-indexed)
- `date_added` (DateTimeField): When the view was starred
- `date_updated` (DateTimeField): Last modification timestamp

**Constraints**:

```python
UniqueConstraint(
    fields=["user_id", "organization_id", "position"],
    name="sentry_groupsearchviewstarred_unique_view_position_per_org_user",
    deferrable=models.Deferrable.DEFERRED
)

UniqueConstraint(
    fields=["user_id", "organization_id", "group_search_view_id"],
    name="sentry_groupsearchviewstarred_unique_view_per_org_user"
)
```

**Manager Methods**:

- `reorder_starred_views(organization, user_id, new_view_positions)`: Atomic reordering of starred views

**Deferrable Constraints**:
The position constraint uses `deferrable=DEFERRED`, which allows temporary violations during a transaction. This is critical for atomic position updates (e.g., shifting positions when inserting a view at a specific position).

## Entity Relationships

```
User (HybridCloud)
  |
  |---< owns >---< GroupSearchView
  |                     |
  |                     v
  |              Organization
  |                     |
  |---< stars >----< GroupSearchViewStarred >---< references >---< GroupSearchView
                        |
                        v
                    position (ordering)
```

**Key Relationships**:

1. **User → GroupSearchView** (1:N)
   - A user can own multiple views
   - Field: `GroupSearchView.user_id`
   - Cascade: Delete view when user is deleted

2. **Organization → GroupSearchView** (1:N)
   - An organization contains multiple views
   - Field: `GroupSearchView.organization`
   - Scope: All queries must filter by organization

3. **User → GroupSearchViewStarred** (1:N)
   - A user can star multiple views
   - Field: `GroupSearchViewStarred.user_id`
   - Cascade: Delete starred entries when user is deleted

4. **GroupSearchView → GroupSearchViewStarred** (1:N)
   - A view can be starred by multiple users
   - Field: `GroupSearchViewStarred.group_search_view`
   - Cascade: Delete starred entries when view is deleted

## State Transitions

### Star Operation

**Initial State**: User does not have a starred relationship with the view

**Preconditions**:

- View exists
- View belongs to the user's organization
- User has access to view (owned OR organization-shared)

**State Change**:

1. Validate preconditions
2. Check if already starred (idempotency)
   - If already starred → return success, no changes
3. Determine position:
   - If position specified → shift existing positions >= position
   - If position not specified → append to end (max position + 1)
4. Create `GroupSearchViewStarred` entry
5. Commit transaction

**Post-conditions**:

- `GroupSearchViewStarred` entry exists for (user, view)
- Position is unique within (user, organization)
- All starred views have contiguous or gapped positions (both valid)

**Failure Modes**:

- View not found → 404
- View not accessible → 404 (same response to avoid leaking existence)
- Position conflict (race condition) → Transaction rollback, retry or fail

### Unstar Operation

**Initial State**: User may or may not have a starred relationship with the view

**Preconditions**:

- View exists (optional - can unstar deleted view by ID)
- View belongs to the user's organization

**State Change**:

1. Delete `GroupSearchViewStarred` entry (if exists)
2. Capture deleted entry's position
3. Decrement positions of all views with position > deleted position
4. Commit transaction

**Post-conditions**:

- No `GroupSearchViewStarred` entry for (user, view)
- Positions of other starred views adjusted to close gap
- Positions remain unique and ordered

**Failure Modes**:

- None - operation is idempotent (succeeds even if not starred)

## Validation Rules

### Access Validation

**Rule**: User can only star views they have access to

**Implementation**:

```sql
SELECT * FROM sentry_groupsearchview
WHERE organization_id = ?
  AND id = ?
  AND (visibility = 'ORGANIZATION' OR user_id = ?)
```

**Enforcement**: Query filter before creating starred entry

### Position Validation

**Rule**: Position must be a positive integer

**Implementation**:

- Model field: `PositiveSmallIntegerField` (0-32767)
- Database constraint: `CHECK (position >= 0)`
- Convention: Use 1-indexed positions (start at 1, not 0)

**Optional Soft Limit**: Could add validation for reasonable range (e.g., 1-1000) but not required

### Uniqueness Validation

**Rule**: User cannot star the same view twice

**Implementation**:

- Database constraint: `UNIQUE (user_id, organization_id, group_search_view_id)`
- Application logic: Check existence before insert (for idempotency)

**Enforcement**: Database constraint + application-level idempotency check

## Denormalization

### Organization in GroupSearchViewStarred

**Why Denormalized**:

- `organization` is copied from `GroupSearchView` to `GroupSearchViewStarred`
- Allows efficient queries without joining to `GroupSearchView` table
- Critical for multi-tenant security (all queries scoped by organization)

**Consistency**:

- Organization is immutable (views cannot move between organizations)
- Copied at creation time, never updated
- If view changes organization (not possible in current design), starred entries would be invalid

## Performance Considerations

### Indexes

**Existing Indexes** (from constraints):

1. `(user_id, organization_id, position)` - Unique index for position ordering
2. `(user_id, organization_id, group_search_view_id)` - Unique index for starred relationship
3. `group_search_view_id` - Foreign key index (automatic)
4. `organization_id` - For tenant scoping queries

**Query Patterns**:

- List user's starred views: `WHERE user_id = ? AND organization_id = ? ORDER BY position`
  - **Index used**: (user_id, organization_id, position)
  - **Cost**: Index scan, very efficient
- Check if view is starred: `WHERE user_id = ? AND organization_id = ? AND group_search_view_id = ?`
  - **Index used**: (user_id, organization_id, group_search_view_id)
  - **Cost**: Index lookup, O(log n)
- Shift positions: `UPDATE ... WHERE user_id = ? AND organization_id = ? AND position >= ?`
  - **Index used**: (user_id, organization_id, position)
  - **Cost**: Index range scan + update, efficient for small sets

### Bulk Operations

**Shifting Positions** (when starring at specific position):

```python
GroupSearchViewStarred.objects.filter(
    user_id=user_id,
    organization=organization,
    position__gte=insert_position
).update(position=F("position") + 1)
```

**Efficiency**: Single bulk UPDATE query, not N individual updates

**Decrementing Positions** (when unstarring):

```python
GroupSearchViewStarred.objects.filter(
    user_id=user_id,
    organization=organization,
    position__gt=deleted_position
).update(position=F("position") - 1)
```

**Efficiency**: Single bulk UPDATE query

## Edge Cases

### Position Gaps

**Scenario**: User stars at position 10 when they only have 3 starred views

**Result**: Positions become [1, 2, 3, 10]

**Handling**: Allowed - gaps are harmless

- Display layer can renumber for UI if desired
- Database remains consistent
- Simplifies insertion logic

### Concurrent Starring

**Scenario**: Two requests try to star different views at position 2 simultaneously

**Handling**: Atomic transactions with deferrable constraints

- First transaction commits: positions shift, new view at 2
- Second transaction: attempts to insert at 2, but 2 is now taken
- **Result**: Second transaction may fail with constraint violation

**Mitigation Options**:

1. Let it fail (client retries) - CHOSEN APPROACH
2. Retry with next available position (adds complexity)
3. Advisory locks (not necessary for infrequent operation)

### Unstarring Non-existent Entry

**Scenario**: User calls unstar on a view they haven't starred

**Result**: `DELETE` returns 0 rows deleted, but operation succeeds (204)

**Rationale**: Idempotent - desired state achieved (view not starred)

### Starring Deleted View

**Scenario**: View is deleted after user initiates star request but before validation

**Result**: View validation fails → 404 response

**Handling**: `GroupSearchView.objects.filter(...).first()` returns None

### Orphaned Starred Entries

**Scenario**: View is deleted - what happens to starred entries?

**Handling**: Cascade deletion

- `GroupSearchViewStarred.group_search_view` has `on_delete=CASCADE`
- Database automatically deletes starred entries when view is deleted
- No manual cleanup needed

## Data Integrity Invariants

1. **Organization Consistency**:
   - `GroupSearchViewStarred.organization` always matches `GroupSearchView.organization`
   - Enforced by copying at creation time

2. **Position Uniqueness**:
   - Within (user, organization), each position appears at most once
   - Enforced by unique constraint

3. **View Uniqueness**:
   - Within (user, organization), each view is starred at most once
   - Enforced by unique constraint

4. **Referential Integrity**:
   - All `group_search_view` references point to existing views
   - Enforced by foreign key constraint with cascade deletion

5. **Access Boundary**:
   - Users can only star views in their organization
   - Enforced by application-level query scoping

## Migration History

**No new migrations required** - all models and constraints already exist.

**Relevant Migrations**:

- `0836`: Created `GroupSearchViewStarred` model
- `0838`: Added position field and unique constraints
- `0841`: Made constraints deferrable for atomic updates

## Schema Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ GroupSearchView                                             │
├─────────────────────────────────────────────────────────────┤
│ id (PK)                                                     │
│ user_id (FK → User)                                         │
│ organization_id (FK → Organization)                         │
│ name                                                        │
│ visibility: OWNER | ORGANIZATION                            │
│ query, query_sort, position                                 │
│ projects (M2M), environments, time_filters                  │
│ date_added, date_updated                                    │
└─────────────────────────────────────────────────────────────┘
                           ▲
                           │ group_search_view (FK, CASCADE)
                           │
┌─────────────────────────────────────────────────────────────┐
│ GroupSearchViewStarred                                      │
├─────────────────────────────────────────────────────────────┤
│ id (PK)                                                     │
│ user_id (FK → User, CASCADE)                                │
│ organization_id (FK → Organization)    [denormalized]       │
│ group_search_view_id (FK → GroupSearchView, CASCADE)        │
│ position (1-indexed ordering)                               │
│ date_added, date_updated                                    │
├─────────────────────────────────────────────────────────────┤
│ UNIQUE (user_id, organization_id, position) DEFERRABLE      │
│ UNIQUE (user_id, organization_id, group_search_view_id)     │
└─────────────────────────────────────────────────────────────┘
```

## Summary

- **No new entities required** - feature uses existing models
- **No schema changes** - all constraints and indexes exist
- **Key model**: `GroupSearchViewStarred` with position-based ordering
- **Access control**: Organization-scoped with visibility checks
- **Performance**: Optimized with proper indexing and bulk updates
- **Integrity**: Enforced by database constraints and cascade rules
