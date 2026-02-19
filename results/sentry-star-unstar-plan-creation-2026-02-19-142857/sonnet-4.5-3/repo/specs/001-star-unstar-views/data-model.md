# Data Model: Star and Unstar Shared Issue Views

**Feature**: 001-star-unstar-views  
**Date**: 2026-02-19  
**Status**: Design Complete

## Overview

This document describes the data model for the star/unstar feature. The implementation reuses the existing `GroupSearchViewStarred` model without modifications, following Sentry's established patterns for many-to-many relationships with ordering.

## Entity Relationship Diagram

```
┌─────────────────────────────────────┐
│         Organization                │
│  (Existing - Multi-tenant boundary) │
└────────────┬────────────────────────┘
             │
             │ 1:N
             │
             ├──────────────────────────────────┐
             │                                  │
             │                                  │
┌────────────▼────────────────┐    ┌───────────▼──────────────┐
│      GroupSearchView         │    │         User             │
│      (Existing Model)        │    │  (HybridCloudForeignKey) │
│                              │    │                          │
│ - id: bigint (PK)           │    │ - id: int                │
│ - name: text                │    │ - [other user fields]    │
│ - query: text               │    │                          │
│ - organization_id: bigint   │    └───────────┬──────────────┘
│ - user_id: int (owner)      │                │
│ - visibility: varchar(16)   │                │
│ - position: smallint        │                │
│ - [other fields...]         │                │
└────────────┬────────────────┘                │
             │                                  │
             │                                  │
             │ N:M with ordering                │
             │                                  │
             │    ┌─────────────────────────────▼──────────┐
             │    │    GroupSearchViewStarred             │
             │    │        (Join Table)                   │
             │    │                                       │
             │    │ - id: bigint (PK)                    │
             └────┼─▶ group_search_view_id: bigint (FK) │
                  │ - user_id: int (FK, HybridCloud)    │
                  │ - organization_id: bigint (FK)       │
                  │ - position: smallint (NOT NULL)      │
                  │ - date_added: timestamp              │
                  │ - date_updated: timestamp            │
                  │                                       │
                  │ UNIQUE(user_id, org_id, position)    │
                  │   DEFERRED constraint                │
                  └───────────────────────────────────────┘
```

## Entities

### 1. GroupSearchView (Existing)

**Purpose**: Represents a saved issue search view. Can be owned by a user or shared with an organization.

**Table**: `sentry_groupsearchview`

**Silo**: Region

**Key Fields**:

| Field             | Type                      | Constraints                     | Description                       |
| ----------------- | ------------------------- | ------------------------------- | --------------------------------- |
| `id`              | BigAutoField              | Primary Key                     | Unique identifier                 |
| `name`            | TextField                 | max_length=128                  | Display name of the view          |
| `query`           | TextField                 | NOT NULL                        | Search query string               |
| `organization_id` | BigInteger                | Foreign Key, NOT NULL           | Organization boundary             |
| `user_id`         | Integer                   | HybridCloudForeignKey, NOT NULL | Owner of the view                 |
| `visibility`      | CharField(16)             | NOT NULL, default=OWNER         | OWNER or ORGANIZATION             |
| `position`        | PositiveSmallIntegerField | Nullable                        | Position in owner's personal list |
| `query_sort`      | CharField(16)             | default=DATE                    | Sort order for query results      |
| `date_added`      | DateTimeField             | default=now                     | Creation timestamp                |
| `date_updated`    | DateTimeField             | default=now                     | Last update timestamp             |

**Constraints**:

- `UNIQUE(user_id, organization_id, position)` - DEFERRED (for owner's personal list)
- `CHECK(visibility IN ('owner', 'organization'))`

**State Transitions**:

- Created with `visibility=OWNER` by default
- Can be changed to `visibility=ORGANIZATION` to share
- Position managed separately from starred position

**Validation Rules**:

1. `name` must be 1-128 characters
2. `query` must be valid issue search syntax
3. `visibility` must be OWNER or ORGANIZATION
4. If `visibility=OWNER`, only owner can access
5. If `visibility=ORGANIZATION`, all org members can access

**No Changes Required**: This model exists and is used as-is.

---

### 2. GroupSearchViewStarred (Existing - Core to this Feature)

**Purpose**: Many-to-many join table tracking which views a user has starred, with position ordering per user.

**Table**: `sentry_groupsearchviewstarred`

**Silo**: Region

**Key Fields**:

| Field                  | Type                      | Constraints                              | Description                     |
| ---------------------- | ------------------------- | ---------------------------------------- | ------------------------------- |
| `id`                   | BigAutoField              | Primary Key                              | Unique identifier               |
| `group_search_view_id` | BigInteger                | Foreign Key, NOT NULL, CASCADE           | The starred view                |
| `user_id`              | Integer                   | HybridCloudForeignKey, NOT NULL, CASCADE | User who starred it             |
| `organization_id`      | BigInteger                | Foreign Key, NOT NULL                    | Organization boundary           |
| `position`             | PositiveSmallIntegerField | NOT NULL                                 | Position in user's starred list |
| `date_added`           | DateTimeField             | default=now                              | When starred                    |
| `date_updated`         | DateTimeField             | default=now                              | Last update                     |

**Constraints**:

- `UNIQUE(user_id, organization_id, position)` - DEFERRED
  - Allows temporary duplicates within transaction
  - Enforces contiguous positions at commit time
- `FOREIGN KEY(group_search_view_id)` with CASCADE delete
  - When view is deleted, starred records auto-deleted
- `FOREIGN KEY(organization_id)` for tenant boundary

**Position Semantics**:

- 0-indexed: First starred view has position=0
- Contiguous: No gaps (0, 1, 2, 3, ...)
- Unique per user per organization
- Managed explicitly on star/unstar operations

**State Transitions**:

1. **Star (without position)**:

   ```
   [Empty] → [position = max(existing_positions) + 1]
   ```

2. **Star (with position P)**:

   ```
   Positions [0,1,2,3] + Star at P=1
   → [0, 1, 2, 3]
   → [0, 2, 3, 4]  (shift positions >= 1)
   → [0, 1, 2, 3, 4]  (insert at 1)
   ```

3. **Unstar at position P**:

   ```
   Positions [0,1,2,3] - Unstar at P=1
   → [0, _, 2, 3]  (delete at 1)
   → [0, 1, 2]  (decrement positions > 1)
   ```

4. **Reorder** (bulk operation via separate endpoint):
   ```
   [view_1:0, view_2:1, view_3:2]
   → Reorder to [view_3, view_1, view_2]
   → [view_3:0, view_1:1, view_2:2]
   ```

**Validation Rules**:

1. `position` must be >= 0
2. `position` must be < 32767 (PositiveSmallIntegerField max)
3. User must have access to the view being starred
4. User and view must be in the same organization
5. No duplicate (user, view) pairs (natural uniqueness from star operation)

**Custom Manager**: `GroupSearchViewStarredManager`

Methods:

- `reorder_starred_views(organization, user_id, new_view_positions)`: Bulk reorder

**No Changes Required**: This model exists and is used as-is.

---

### 3. User (Existing - HybridCloudForeignKey)

**Purpose**: Represents authenticated users in Sentry.

**Silo**: Control (accessed via HybridCloudForeignKey from Region)

**Relevant Fields**:

- `id` (int): Primary key
- Authentication and profile fields

**Usage in this Feature**:

- `user_id` in GroupSearchView (owner)
- `user_id` in GroupSearchViewStarred (who starred)
- Accessed via `request.user` in endpoints

**No Changes Required**: Existing entity, used via foreign keys.

---

### 4. Organization (Existing)

**Purpose**: Multi-tenant boundary. All data scoped to organizations.

**Silo**: Control (with Region foreign keys)

**Usage in this Feature**:

- `organization_id` in both models enforces tenant isolation
- Provided by `OrganizationEndpoint` base class
- All queries must include `organization_id` filter

**No Changes Required**: Existing entity, used for scoping.

---

## Relationships

### 1. User → GroupSearchViewStarred (1:N)

- **Type**: One user can star many views
- **FK**: `user_id` (HybridCloudForeignKey)
- **Cascade**: DELETE - when user is deleted, their stars are removed
- **Uniqueness**: User can star each view only once (enforced by idempotent star operation)

### 2. GroupSearchView → GroupSearchViewStarred (1:N)

- **Type**: One view can be starred by many users
- **FK**: `group_search_view_id` (FlexibleForeignKey)
- **Cascade**: DELETE - when view is deleted, all stars are removed
- **Note**: A view being starred doesn't prevent its deletion

### 3. Organization → GroupSearchView (1:N)

- **Type**: One organization has many views
- **FK**: `organization_id` (FlexibleForeignKey)
- **Cascade**: CASCADE - when org deleted, views deleted
- **Boundary**: All queries scoped by organization

### 4. Organization → GroupSearchViewStarred (1:N)

- **Type**: One organization has many starred relationships
- **FK**: `organization_id` (FlexibleForeignKey)
- **Cascade**: CASCADE - when org deleted, starred records deleted
- **Boundary**: All queries scoped by organization

### 5. User → GroupSearchView (1:N as owner)

- **Type**: One user owns many views
- **FK**: `user_id` in GroupSearchView
- **Cascade**: CASCADE via HybridCloudForeignKey
- **Note**: Ownership is separate from starring (can star own views)

---

## Position Management Algorithms

### Algorithm 1: Star Without Position (Append)

**Goal**: Add view to end of user's starred list

**Steps**:

```sql
-- 1. Get max position
SELECT COALESCE(MAX(position), -1) + 1 AS next_position
FROM sentry_groupsearchviewstarred
WHERE user_id = ? AND organization_id = ?;

-- 2. Insert (idempotent with get_or_create)
INSERT INTO sentry_groupsearchviewstarred
  (user_id, organization_id, group_search_view_id, position, date_added, date_updated)
VALUES (?, ?, ?, next_position, NOW(), NOW())
ON CONFLICT DO NOTHING;  -- Simplified; actual implementation uses get_or_create
```

**Complexity**: O(1) - constant time, no shifting needed

**Example**:

```
Before: [view_A:0, view_B:1, view_C:2]
Star view_D: max(2) + 1 = 3
After:  [view_A:0, view_B:1, view_C:2, view_D:3]
```

---

### Algorithm 2: Star With Position (Insert)

**Goal**: Insert view at specific position, shift others down

**Steps**:

```sql
BEGIN TRANSACTION;

  -- 1. Shift positions >= target position down
  UPDATE sentry_groupsearchviewstarred
  SET position = position + 1, date_updated = NOW()
  WHERE user_id = ? AND organization_id = ? AND position >= target_position;

  -- 2. Insert at target position
  INSERT INTO sentry_groupsearchviewstarred
    (user_id, organization_id, group_search_view_id, position, date_added, date_updated)
  VALUES (?, ?, ?, target_position, NOW(), NOW());

COMMIT;
```

**Complexity**: O(N) where N = number of positions >= target

**Example**:

```
Before: [view_A:0, view_B:1, view_C:2]
Star view_D at position 1:
  - Shift: view_B:1→2, view_C:2→3
  - Insert: view_D:1
After:  [view_A:0, view_D:1, view_B:2, view_C:3]
```

**Edge Cases**:

- Position > current max: Clamp to max+1 (append)
- Position < 0: Reject (validation error)
- Position = 0: Shift all existing positions

---

### Algorithm 3: Unstar (Remove and Compact)

**Goal**: Remove view from starred list, close the gap

**Steps**:

```sql
BEGIN TRANSACTION;

  -- 1. Get position of starred view
  SELECT position INTO deleted_position
  FROM sentry_groupsearchviewstarred
  WHERE user_id = ? AND organization_id = ? AND group_search_view_id = ?;

  -- 2. Delete the starred record
  DELETE FROM sentry_groupsearchviewstarred
  WHERE user_id = ? AND organization_id = ? AND group_search_view_id = ?;

  -- 3. Decrement positions after deleted position
  UPDATE sentry_groupsearchviewstarred
  SET position = position - 1, date_updated = NOW()
  WHERE user_id = ? AND organization_id = ? AND position > deleted_position;

COMMIT;
```

**Complexity**: O(N) where N = number of positions > deleted

**Example**:

```
Before: [view_A:0, view_B:1, view_C:2, view_D:3]
Unstar view_B (position 1):
  - Delete: view_B removed
  - Decrement: view_C:2→1, view_D:3→2
After:  [view_A:0, view_C:1, view_D:2]
```

**Idempotency**: If view not starred, DELETE affects 0 rows, UPDATE does nothing. Still returns success.

---

### Algorithm 4: Reorder (Bulk Update)

**Goal**: Rearrange all starred views to match new order

**Steps** (from existing `GroupSearchViewStarredManager.reorder_starred_views`):

```python
# 1. Validate input matches existing starred views
existing_views = set(
    GroupSearchViewStarred.objects
    .filter(organization=org, user_id=user_id)
    .values_list('group_search_view_id', flat=True)
)
if set(new_view_positions) != existing_views:
    raise ValueError("Mismatch between existing and provided views")

# 2. Fetch all starred records
views_to_update = list(
    GroupSearchViewStarred.objects
    .filter(organization=org, user_id=user_id)
)

# 3. Update positions in memory
position_map = {view_id: idx for idx, view_id in enumerate(new_view_positions)}
for view in views_to_update:
    view.position = position_map[view.group_search_view_id]

# 4. Bulk update (atomic)
with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
    GroupSearchViewStarred.objects.bulk_update(views_to_update, ["position", "date_updated"])
```

**Complexity**: O(N) where N = total starred views for user

**Example**:

```
Before: [view_A:0, view_B:1, view_C:2]
Reorder to [view_C, view_A, view_B]:
After:  [view_C:0, view_A:1, view_B:2]
```

**Note**: This feature only implements star/unstar. Reordering uses the existing endpoint at `/group-search-views-starred-order/`.

---

## Database Indexes

### Existing Indexes (via constraints):

1. **Primary Keys**:
   - `sentry_groupsearchview.id`
   - `sentry_groupsearchviewstarred.id`

2. **Unique Constraints** (create implicit indexes):
   - `(user_id, organization_id, position)` on GroupSearchView
   - `(user_id, organization_id, position)` on GroupSearchViewStarred (DEFERRED)

3. **Foreign Keys** (typically auto-indexed):
   - `group_search_view_id` on GroupSearchViewStarred
   - `organization_id` on both tables
   - `user_id` on both tables (HybridCloudForeignKey)

### Query Patterns:

**Star operation**:

```sql
-- Check view exists and accessible
SELECT * FROM sentry_groupsearchview
WHERE id = ? AND organization_id = ?;

-- Get max position
SELECT MAX(position) FROM sentry_groupsearchviewstarred
WHERE user_id = ? AND organization_id = ?;

-- Index used: (user_id, organization_id, position)
```

**Unstar operation**:

```sql
-- Delete starred record
DELETE FROM sentry_groupsearchviewstarred
WHERE user_id = ? AND organization_id = ? AND group_search_view_id = ?;

-- Index used: (user_id, organization_id, position) + group_search_view_id
```

**List starred views** (existing endpoint):

```sql
-- Get user's starred views
SELECT gsv.* FROM sentry_groupsearchview gsv
JOIN sentry_groupsearchviewstarred gsvs ON gsv.id = gsvs.group_search_view_id
WHERE gsvs.user_id = ? AND gsvs.organization_id = ?
ORDER BY gsvs.position;

-- Index used: (user_id, organization_id, position)
```

### Performance Assessment:

- All queries use existing indexes effectively
- No new indexes required
- Position-based ordering is efficient (indexed)
- Compound index on (user_id, organization_id, position) covers most queries

---

## Data Integrity Rules

### Enforced by Database:

1. **Referential Integrity**:
   - `group_search_view_id` must reference valid GroupSearchView (FK constraint)
   - CASCADE delete on view deletion removes all stars
   - CASCADE delete on user deletion removes all stars

2. **Uniqueness**:
   - `(user_id, organization_id, position)` must be unique (DEFERRED constraint)
   - Positions must be contiguous (enforced by application logic)

3. **NOT NULL**:
   - All foreign keys are NOT NULL
   - `position` is NOT NULL (required field)

### Enforced by Application:

1. **Access Control**:
   - User must be in organization to star views in that org
   - User must have view access based on visibility rules
   - OWNER views: only owner can star (or view at all)
   - ORGANIZATION views: any org member can star

2. **Position Validation**:
   - Position must be >= 0
   - Position > max is clamped to max+1
   - Negative positions rejected with 400 error

3. **Idempotency**:
   - Starring an already-starred view is a no-op (returns success)
   - Unstarring a non-starred view is a no-op (returns success)

4. **Organization Scoping**:
   - All queries filtered by organization_id
   - No cross-organization starring allowed
   - Enforced at endpoint level (OrganizationEndpoint base class)

### Transaction Boundaries:

All star/unstar operations wrapped in atomic transactions:

```python
with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
    # Position shifting + insert/delete
    pass
```

This ensures:

- All-or-nothing semantics
- DEFERRED constraint validation at commit
- No partial position updates
- Isolation from concurrent operations

---

## Edge Cases and Handling

### 1. Deleted View

**Scenario**: User tries to star a view that was just deleted

**Handling**:

```python
try:
    view = GroupSearchView.objects.get(id=view_id, organization=org)
except GroupSearchView.DoesNotExist:
    return Response({"detail": "View not found"}, status=404)
```

**Cascade Cleanup**: When a view is deleted, all `GroupSearchViewStarred` records are auto-deleted via CASCADE.

---

### 2. Already Starred

**Scenario**: User stars a view they've already starred

**Handling**:

```python
starred, created = GroupSearchViewStarred.objects.get_or_create(
    organization=org,
    user_id=user.id,
    group_search_view=view,
    defaults={"position": calculated_position}
)
if not created:
    # Already starred - no-op, return success
    return Response(status=204)
```

**Result**: Idempotent - returns 204 No Content without changing state.

---

### 3. Position Out of Bounds

**Scenario**: User tries to star at position 100 when they only have 5 starred views

**Handling**:

```python
max_position = GroupSearchViewStarred.objects.filter(
    organization=org, user_id=user.id
).aggregate(Max('position'))['position__max'] or -1

if target_position > max_position + 1:
    target_position = max_position + 1  # Clamp to end
```

**Result**: Position is clamped to end of list (append behavior).

---

### 4. Concurrent Position Conflicts

**Scenario**: Two requests try to star different views at position 1 simultaneously

**Handling**:

- DEFERRED constraint allows temporary duplicates within transaction
- At commit time, one transaction succeeds, the other fails with IntegrityError
- Failed transaction is caught and returns 400 error

```python
try:
    with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
        # Position shifting + insert
        pass
except IntegrityError as e:
    return Response({"detail": "Position conflict. Please retry."}, status=400)
```

**Result**: Client retries request, succeeds on second attempt with updated positions.

---

### 5. Non-Starred View Unstar

**Scenario**: User tries to unstar a view they haven't starred

**Handling**:

```python
deleted_count, _ = GroupSearchViewStarred.objects.filter(
    organization=org,
    user_id=user.id,
    group_search_view=view
).delete()

# Always return success, regardless of deleted_count
return Response(status=204)
```

**Result**: Idempotent - returns 204 No Content without error.

---

### 6. Owner-Only View Access

**Scenario**: User tries to star an OWNER-visibility view they don't own

**Handling**:

```python
if view.visibility == GroupSearchViewVisibility.OWNER:
    if view.user_id != request.user.id:
        return Response({"detail": "Permission denied"}, status=403)
```

**Result**: 403 Forbidden - prevents information disclosure.

---

### 7. Maximum Starred Views

**Scenario**: User has 32,767 starred views (PositiveSmallIntegerField max)

**Handling**:

```python
# position is PositiveSmallIntegerField (0-32767)
if calculated_position > 32767:
    return Response({"detail": "Maximum starred views limit reached"}, status=400)
```

**Result**: Explicit error message. (In practice, this limit is unlikely to be reached.)

---

### 8. Organization Mismatch

**Scenario**: User tries to star a view from a different organization

**Handling**:

- OrganizationEndpoint validates user is member of org in URL
- Query filters by organization: `view = GroupSearchView.objects.get(id=view_id, organization=org)`
- If view is in different org, query returns DoesNotExist

**Result**: 404 Not Found - prevents cross-organization leakage.

---

## Migration Plan

**Required Migrations**: None

**Reason**: All models exist in production. This feature only adds new API endpoints.

**Schema Changes**: None

**Data Migration**: None

**Backwards Compatibility**: Full - no breaking changes to existing data or APIs.

---

## Testing Strategies

### Unit Tests (Model Level)

1. **Position Calculation**:
   - Test max position calculation on empty list
   - Test max position calculation with existing stars
   - Test position clamping for out-of-bounds values

2. **Cascade Deletes**:
   - Delete view, verify starred records removed
   - Delete user, verify starred records removed

3. **Constraint Validation**:
   - Test unique position constraint
   - Test DEFERRED constraint behavior in transaction

### Integration Tests (Endpoint Level)

1. **Star Operations**:
   - Star view without position (append)
   - Star view with position (insert and shift)
   - Star already-starred view (idempotent)
   - Star with position > max (clamp to end)
   - Star deleted view (404)
   - Star view from different org (404)
   - Star OWNER view as non-owner (403)

2. **Unstar Operations**:
   - Unstar starred view (remove and compact)
   - Unstar non-starred view (idempotent)
   - Unstar with position adjustment verification

3. **Position Management**:
   - Verify position shifting on star at middle position
   - Verify position compacting on unstar at middle position
   - Verify positions remain contiguous after operations

4. **Concurrency**:
   - Simulate concurrent star requests at same position
   - Verify transaction isolation and conflict handling

5. **Feature Flag**:
   - Test with feature flag enabled (success)
   - Test with feature flag disabled (400 error)

### Test Data Fixtures

```python
# Typical test setup
class StarUnstarViewTest(APITestCase):
    def setUp(self):
        super().setUp()
        self.login_as(user=self.user)

        # Create test views
        self.view_owner = GroupSearchView.objects.create(
            name="My Private View",
            organization=self.organization,
            user_id=self.user.id,
            query="is:unresolved",
            visibility=GroupSearchViewVisibility.OWNER,
            position=0,
        )

        self.view_shared = GroupSearchView.objects.create(
            name="Shared Team View",
            organization=self.organization,
            user_id=self.other_user.id,
            query="is:unresolved assigned:me",
            visibility=GroupSearchViewVisibility.ORGANIZATION,
            position=0,
        )

        # Pre-star some views for testing
        GroupSearchViewStarred.objects.create(
            organization=self.organization,
            user_id=self.user.id,
            group_search_view=self.view_owner,
            position=0,
        )
```

---

## Summary

The data model for star/unstar functionality is **complete and ready for implementation**:

- ✅ **Reuses existing models** (GroupSearchView, GroupSearchViewStarred)
- ✅ **No schema changes required** (no migrations)
- ✅ **Position management algorithms defined** (star, unstar, reorder)
- ✅ **Data integrity rules established** (database + application level)
- ✅ **Edge cases documented and handled** (idempotency, concurrency, access control)
- ✅ **Testing strategies defined** (unit, integration, fixtures)

**Next Steps**: Generate API contracts (OpenAPI spec) in Phase 1.
