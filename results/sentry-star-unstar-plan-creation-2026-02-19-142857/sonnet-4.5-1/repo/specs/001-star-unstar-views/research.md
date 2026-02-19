# Research: Star and Unstar Shared Issue Views

**Feature**: 001-star-unstar-views  
**Date**: 2026-02-19  
**Status**: Complete

## Executive Summary

Research reveals that **the starring feature for GroupSearchView already exists and is fully implemented** in Sentry. The `GroupSearchViewStarred` model, endpoints, and position management system are already in production. This feature request may be asking for:

1. Additional star/unstar-specific endpoints (currently handled via bulk PUT operations)
2. Documentation or refinement of existing functionality
3. Extension of the existing starred views system

## Research Findings

### 1. GroupSearchView Model - RESOLVED

**Decision**: Use existing GroupSearchView model  
**Location**: `/workspace/repo/src/sentry/models/groupsearchview.py`

**Key characteristics**:

- **Silo**: `@region_silo_model` - Region silo (project/issue data)
- **Relocation scope**: `RelocationScope.Organization`
- **Tenant boundaries**: Organization + User scoped
- **Visibility modes**:
  - `GroupSearchViewVisibility.OWNER` (default) - Private to creator
  - `GroupSearchViewVisibility.ORGANIZATION` - Shared with org (gated by `organizations:issue-view-sharing` feature flag)

**Model structure**:

```python
@region_silo_model
class GroupSearchView(DefaultFieldsModelExisting):
    name = models.TextField(max_length=128)
    user_id = HybridCloudForeignKey("sentry.User", on_delete="CASCADE")
    organization = FlexibleForeignKey("sentry.Organization")
    visibility = models.CharField(max_length=16, db_default="owner")
    query = models.TextField()
    query_sort = models.CharField(max_length=16, default=SortOptions.DATE)
    position = models.PositiveSmallIntegerField(null=True)
    projects = models.ManyToManyField("sentry.Project", through="GroupSearchViewProject")
    is_all_projects = models.BooleanField(db_default=False)
    environments = ArrayField(models.CharField(max_length=64), default=list)
    time_filters = models.JSONField(null=False, db_default={"period": "14d"})
```

**Rationale**: Model already exists with proper silo architecture, relocation support, and security boundaries. No changes needed.

**Alternatives considered**: Creating a new view model → Rejected because GroupSearchView already exists with all required functionality.

---

### 2. GroupSearchViewStarred Model - ALREADY IMPLEMENTED

**Decision**: The starred views feature is already fully implemented  
**Location**: `/workspace/repo/src/sentry/models/groupsearchviewstarred.py`

**Current implementation**:

```python
@region_silo_model
class GroupSearchViewStarred(DefaultFieldsModel):
    __relocation_scope__ = RelocationScope.Organization

    user_id = HybridCloudForeignKey("sentry.User", on_delete="CASCADE")
    organization = FlexibleForeignKey("sentry.Organization")
    group_search_view = FlexibleForeignKey("sentry.GroupSearchView")
    position = models.PositiveSmallIntegerField()

    objects = GroupSearchViewStarredManager()

    class Meta:
        db_table = "sentry_groupsearchviewstarred"
        constraints = [
            UniqueConstraint(
                fields=["user_id", "organization_id", "position"],
                name="unique_view_position_per_org_user",
                deferrable=models.Deferrable.DEFERRED,  # Critical for safe reordering
            )
        ]
```

**Manager includes**:

- `reorder_starred_views(organization, user_id, new_view_positions)` - Atomic reordering with validation

**Rationale**: Comprehensive starring system already exists with:

- Position ordering
- Atomic reordering via deferred constraints
- Automatic position adjustment on deletion
- Idempotent operations
- Organization + user scoping

**Alternatives considered**: Creating new star/unstar endpoints → May be valid if dedicated star/unstar actions are desired separate from bulk operations.

---

### 3. Existing Endpoints - COMPREHENSIVE API EXISTS

**Decision**: Use existing endpoint patterns as reference  
**Base class**: `OrganizationEndpoint` with `@region_silo_endpoint` decorator  
**Permission**: Custom `MemberPermission` class with `member:read` and `member:write` scopes

**Current endpoints** (all in `/workspace/repo/src/sentry/issues/endpoints/`):

#### **OrganizationGroupSearchViewsEndpoint**

- **URL**: `/organizations/{org}/group-search-views/`
- **Methods**: GET (list starred views), PUT (bulk create/update/delete views)
- **File**: `organization_group_search_views.py`
- **Pattern**: Bulk operations with automatic starring of created/updated views

#### **OrganizationGroupSearchViewDetailsEndpoint**

- **URL**: `/organizations/{org}/group-search-views/{view_id}/`
- **Methods**: DELETE
- **File**: `organization_group_search_view_details.py`
- **Pattern**: Deletes view and automatically adjusts positions of remaining starred views

#### **OrganizationGroupSearchViewStarredOrderEndpoint**

- **URL**: `/organizations/{org}/group-search-views-starred-order/`
- **Methods**: PUT
- **File**: `organization_group_search_view_starred_order.py`
- **Pattern**: Reorders starred views using manager method with transaction

#### **OrganizationGroupSearchViewVisitEndpoint**

- **URL**: `/organizations/{org}/group-search-views/{view_id}/visit/`
- **Methods**: POST
- **File**: `organization_group_search_view_visit.py`
- **Pattern**: Updates last visited timestamp

**Rationale**: All CRUD and position management operations already exist. The bulk PUT endpoint handles creation and automatically stars views.

**Alternatives considered**:

- Creating dedicated POST `/star/` and DELETE `/unstar/` endpoints
- Using a toggle endpoint like Dashboard favorites (PUT with `isFavorited` boolean)

**Gap analysis**: The spec requests explicit star/unstar endpoints, but current implementation uses:

- **Starring**: Implicit via PUT bulk update (creates view + starred entry)
- **Unstarring**: Could be achieved via DELETE (removes entire view) OR by omitting from bulk update list

**Recommendation**: Add dedicated star/unstar endpoints if the spec requires actions on existing views without full CRUD operations.

---

### 4. Authorization Patterns - RESOLVED

**Decision**: Use existing authorization pattern from GroupSearchView endpoints

**Pattern**:

```python
@region_silo_endpoint
class MyEndpoint(OrganizationEndpoint):
    owner = ApiOwner.ISSUES
    permission_classes = (MemberPermission,)

    def post(self, request: Request, organization: Organization, view_id: str) -> Response:
        # Validate view access
        try:
            view = GroupSearchView.objects.get(
                id=view_id,
                organization=organization  # Organization scoping
            )
        except GroupSearchView.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Check user access: owner OR organization-shared
        if view.user_id != request.user.id and view.visibility != GroupSearchViewVisibility.ORGANIZATION:
            return Response({"detail": "You do not have access to this view"}, status=status.HTTP_403_FORBIDDEN)

        # Perform star operation...
```

**Authorization rules**:

- User can access a view IF:
  - They own it (`view.user_id == request.user.id`), OR
  - It's organization-shared (`visibility == ORGANIZATION`) AND user is in the organization
- Always scope by organization first (tenant boundary)
- Return 404 for non-existent views
- Return 403 for unauthorized access to existing views

**Feature flag**: `organizations:issue-view-sharing` - Required for ORGANIZATION visibility mode

**Rationale**: Follows Sentry's security-first principles. Similar to `SavedSearch` authorization pattern.

**Alternatives considered**: Using object-level permissions class → Rejected because endpoint-level validation is clearer and matches existing patterns.

---

### 5. Position Management Strategy - RESOLVED

**Decision**: Use separate position field with deferred unique constraints (already implemented)

**Implementation details**:

- **Field type**: `models.PositiveSmallIntegerField()`
- **Constraint**: `UniqueConstraint(["user_id", "organization_id", "position"], deferrable=Deferrable.DEFERRED)`
- **Key insight**: Deferred constraints allow temporary duplicate positions during atomic reordering
- **Positions**: Zero-indexed (0 = first item)

**Atomic reordering pattern** (already in `GroupSearchViewStarredManager`):

```python
def reorder_starred_views(self, organization, user_id, new_view_positions: list[int]):
    # 1. Fetch existing starred views
    existing_starred_views = self.filter(organization=organization, user_id=user_id)

    # 2. Validate: new list must match existing starred views
    existing_ids = {v.group_search_view_id for v in existing_starred_views}
    if existing_ids != set(new_view_positions):
        raise ValueError("Mismatch between existing and provided starred views.")

    # 3. Create position mapping
    position_map = {view_id: idx for idx, view_id in enumerate(new_view_positions)}

    # 4. Update positions in memory
    views_to_update = list(existing_starred_views)
    for view in views_to_update:
        view.position = position_map[view.group_search_view_id]

    # 5. Bulk update database (within transaction from endpoint)
    if views_to_update:
        self.bulk_update(views_to_update, ["position"])
```

**Usage in endpoint**:

```python
try:
    with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
        GroupSearchViewStarred.objects.reorder_starred_views(
            organization=organization,
            user_id=request.user.id,
            new_view_positions=view_ids,
        )
except IntegrityError as e:
    return Response({"detail": str(e)}, status=400)
```

**Position adjustment on deletion** (already implemented):

```python
deleted_position = starred_view.position
starred_view.delete()

# Atomic decrement using F() expression
GroupSearchViewStarred.objects.filter(
    organization=organization,
    user_id=request.user.id,
    position__gt=deleted_position,
).update(position=F("position") - 1)
```

**Rationale**:

- Deferred constraints prevent race conditions during reordering
- Single bulk_update() call minimizes database round-trips
- F() expressions provide atomic position adjustments
- Already battle-tested in production

**Alternatives considered**:

- Linked list approach → Rejected (too complex, harder to query)
- Temporary high order numbers (like DashboardWidget) → Rejected (deferred constraints are cleaner)
- Fractional positions (e.g., 1.5, 2.5) → Rejected (requires eventual rebalancing, less predictable)

---

### 6. Race Condition Handling - RESOLVED

**Decision**: Use deferred unique constraints + atomic transactions (already implemented)

**Key mechanisms**:

1. **Deferred constraints**: Constraint is checked at transaction commit, not per statement

   ```python
   class Meta:
       constraints = [
           UniqueConstraint(
               fields=["user_id", "organization_id", "position"],
               deferrable=models.Deferrable.DEFERRED
           )
       ]
   ```

2. **Atomic transactions**: All position updates wrapped in transactions

   ```python
   with transaction.atomic(using=router.db_for_write(Model)):
       # Multiple position updates allowed here
       # Constraint checked only at commit
   ```

3. **F() expressions**: For single-item atomic updates

   ```python
   Model.objects.filter(...).update(position=F("position") - 1)
   ```

4. **Manager-level validation**: Validates entire operation before database writes
   ```python
   if existing_ids != set(new_positions):
       raise ValueError("Invalid reorder operation")
   ```

**Rationale**: Multi-layered approach prevents:

- Concurrent reordering conflicts (transaction isolation)
- Mid-transaction constraint violations (deferred checks)
- Invalid final states (validation before writes)

**Alternatives considered**:

- Row-level locking (`select_for_update()`) → Not needed with deferred constraints
- Optimistic locking with version fields → Adds complexity, deferred constraints sufficient

---

### 7. Idempotent Operations - RESOLVED

**Decision**: Use Django's `update_or_create()` for starring, no-op for unstarring non-existent

**Star operation pattern**:

```python
# Option 1: update_or_create (used in bulk PUT)
GroupSearchViewStarred.objects.update_or_create(
    organization=organization,
    user_id=user_id,
    group_search_view=view,
    defaults={"position": position}
)

# Option 2: create + IntegrityError catch (for simple bookmarks)
try:
    with transaction.atomic(router.db_for_write(Model)):
        GroupSearchViewStarred.objects.create(...)
except IntegrityError:
    pass  # Already starred - idempotent
```

**Unstar operation pattern**:

```python
# Idempotent delete - no error if not found
deleted_count, _ = GroupSearchViewStarred.objects.filter(
    organization=organization,
    user_id=request.user.id,
    group_search_view=view
).delete()

# Adjust positions if deleted
if deleted_count > 0:
    GroupSearchViewStarred.objects.filter(
        organization=organization,
        user_id=request.user.id,
        position__gt=deleted_position,
    ).update(position=F("position") - 1)
```

**Rationale**:

- `update_or_create()` handles "already starred" case gracefully
- `.delete()` returns 0 if nothing deleted (idempotent)
- Matches requirements FR-003 and FR-004

**Alternatives considered**:

- Boolean toggle endpoint (like Dashboard favorites) → Less RESTful, but valid alternative
- get_or_create → Less appropriate when position might change

---

### 8. Similar Reference Patterns in Sentry

**Patterns analyzed**:

| Feature                     | Model                  | Position Field | Idempotent Pattern   | File Location                    |
| --------------------------- | ---------------------- | -------------- | -------------------- | -------------------------------- |
| **GroupSearchView Starred** | GroupSearchViewStarred | ✅ Yes         | update_or_create     | models/groupsearchviewstarred.py |
| Project Bookmarks           | ProjectBookmark        | ❌ No          | IntegrityError catch | models/projectbookmark.py        |
| Group Bookmarks             | GroupBookmark          | ❌ No          | IntegrityError catch | models/groupbookmark.py          |
| Dashboard Favorites         | DashboardFavoriteUser  | ❌ No          | Property setter      | models/dashboard.py              |
| Dashboard Widgets           | DashboardWidget        | ✅ Yes         | Temp high orders     | models/dashboard_widget.py       |

**Best pattern match**: GroupSearchViewStarred itself - most recent, sophisticated implementation with position ordering.

---

### 9. Serialization Patterns - RESOLVED

**Decision**: Follow existing GroupSearchViewSerializer pattern with batch-fetching

**Output serializer** (already exists):

```python
# From: /workspace/repo/src/sentry/api/serializers/models/groupsearchview.py

@register(GroupSearchViewStarred)
class GroupSearchViewStarredSerializer(Serializer):
    def serialize(self, obj, attrs, user, **kwargs):
        # Wrap GroupSearchViewSerializer
        serialized_view = serialize(
            obj.group_search_view,
            user,
            serializer=GroupSearchViewSerializer(...)
        )
        return {
            **serialized_view,
            "position": obj.position,  # Add position field
        }

@register(GroupSearchView)
class GroupSearchViewSerializer(Serializer):
    def get_attrs(self, item_list, user, **kwargs):
        # Batch fetch last visited to avoid N+1
        last_visited = GroupSearchViewLastVisited.objects.filter(
            group_search_view__in=item_list,
            user_id=user.id,
        )
        last_visited_map = {lv.group_search_view_id: lv for lv in last_visited}

        return {
            item: {
                "last_visited": last_visited_map.get(item.id),
            }
            for item in item_list
        }

    def serialize(self, obj, attrs, user, **kwargs):
        return {
            "id": str(obj.id),
            "name": obj.name,
            "query": obj.query,
            "querySort": obj.query_sort,
            # ... other fields
            "lastVisited": attrs["last_visited"].last_visited if attrs.get("last_visited") else None,
        }
```

**Input validation** (already exists):

```python
# From: /workspace/repo/src/sentry/api/serializers/rest_framework/groupsearchview.py

class GroupSearchViewValidator(CamelSnakeSerializer):
    id = serializers.IntegerField(required=False)
    name = serializers.CharField(max_length=128, required=True)
    query = serializers.CharField(required=True)
    querySort = serializers.CharField(required=True)
    # ... other fields
```

**Rationale**:

- Uses Sentry's serializer registry pattern (`@register`)
- Implements `get_attrs()` for batch fetching (prevents N+1)
- Returns camelCase for API consistency
- Wraps related objects properly

---

## Design Decisions Summary

### What Already Exists

1. ✅ **GroupSearchView model** - Fully implemented with visibility controls
2. ✅ **GroupSearchViewStarred model** - Complete starred views system with position management
3. ✅ **Position ordering** - Deferred constraints + atomic reordering
4. ✅ **Bulk operations** - PUT endpoint for create/update/delete views
5. ✅ **Reordering endpoint** - PUT starred-order endpoint
6. ✅ **Serializers** - Input validation and output serialization with batch fetching
7. ✅ **Authorization** - Organization + user scoping with visibility controls
8. ✅ **Tests** - Comprehensive test suite for all operations

### What May Need to be Added (Based on Spec Requirements)

The spec requests explicit star/unstar operations. Current implementation handles these implicitly:

- **Starring**: Happens automatically when view is created/updated via bulk PUT
- **Unstarring**: Requires deleting the view OR omitting from bulk update

**Possible additions**:

1. **Dedicated star endpoint**: POST `/organizations/{org}/group-search-views/{view_id}/star/`
   - Stars an existing view (owned or org-shared)
   - Optional position parameter
   - Idempotent (no-op if already starred)

2. **Dedicated unstar endpoint**: DELETE `/organizations/{org}/group-search-views/{view_id}/star/`
   - Unstars a view (keeps the view itself)
   - Adjusts positions of remaining starred views
   - Idempotent (no-op if not starred)

**Rationale for additions**:

- Spec explicitly mentions "star and unstar" as distinct actions
- Current bulk operations conflate view management with starring
- Users may want to star/unstar existing views without modifying the view itself
- Matches user stories in spec (star a discovered shared view)

**Alternatives considered**:

- Keep current bulk-only approach → Rejected because spec explicitly requests star/unstar operations
- Use PUT toggle with boolean → Valid but less RESTful than separate endpoints

---

## Technology Choices

| Component        | Technology                                                | Rationale                                       |
| ---------------- | --------------------------------------------------------- | ----------------------------------------------- |
| Model base class | DefaultFieldsModel                                        | Provides date_added, date_updated automatically |
| Foreign keys     | HybridCloudForeignKey (User), FlexibleForeignKey (others) | Follows Sentry's silo architecture              |
| Position field   | PositiveSmallIntegerField                                 | Standard for ordered lists in Sentry            |
| Uniqueness       | UniqueConstraint with DEFERRED                            | Safe atomic reordering                          |
| Transactions     | transaction.atomic(router.db_for_write())                 | Proper DB routing in multi-silo setup           |
| Bulk updates     | QuerySet.bulk_update()                                    | Efficient batch operations                      |
| Atomic math      | F() expressions                                           | Race-condition-free increments/decrements       |
| Endpoints        | OrganizationEndpoint with @region_silo_endpoint           | Standard for org-scoped region data             |
| Permissions      | Custom MemberPermission with member:read/write            | Allows regular members to manage their stars    |
| Serialization    | Sentry registry pattern with get_attrs()                  | Prevents N+1 queries                            |
| Input validation | CamelSnakeSerializer (DRF)                                | Handles camelCase ↔ snake_case conversion       |
| Feature flags    | organizations:issue-view-sharing                          | Safe incremental rollout                        |

---

## Security Considerations

1. **Authorization**: All operations validate organization membership and view access
2. **Tenant isolation**: All queries scoped by organization + user
3. **Information disclosure**: Return 404 (not 403) for unauthorized views to prevent existence leakage
4. **SQL injection**: All queries use Django ORM (parameterized)
5. **IDOR prevention**: Always validate user has access before operations
6. **Race conditions**: Mitigated by deferred constraints + transactions

---

## Performance Considerations

1. **N+1 queries**: Prevented by `get_attrs()` batch fetching in serializers
2. **Index strategy**: Unique constraint creates index on (user_id, organization_id, position)
3. **Bulk operations**: Use `bulk_update()` for reordering (single query)
4. **Atomic updates**: F() expressions for position adjustments (single UPDATE)
5. **Query optimization**: `prefetch_related()` for M2M relationships (projects)

---

## Testing Strategy

Existing test coverage includes:

- ✅ Simple reordering
- ✅ Same order (idempotent)
- ✅ Empty list handling
- ✅ Duplicate IDs (error)
- ✅ Mismatch validation (error)
- ✅ Access control (can't reorder others' stars)
- ✅ Position adjustment on delete
- ✅ Automatic starring on view creation

Additional tests needed if new endpoints added:

- Star existing view at specific position
- Star already-starred view (idempotent)
- Unstar view and verify position adjustment
- Unstar non-starred view (idempotent)
- Star with position > list size
- Star deleted view (error)
- Concurrent star operations

---

## Migration Strategy

**Current state**: All tables and constraints already exist

- Migration 0836: Created `sentry_groupsearchviewstarred` table
- Migration 0838: Backfilled positions from GroupSearchView to GroupSearchViewStarred

**If new endpoints added**: No migrations required (uses existing tables)

---

## Open Questions for Implementation

1. **Spec alignment**: Does the spec require new dedicated star/unstar endpoints, or is documenting existing functionality sufficient?

2. **Starring behavior**: When starring an existing view without position parameter, should it:
   - Option A: Append to end of list (spec FR-007)
   - Option B: Use current view.position if available

3. **Feature flag**: Should new endpoints respect `organizations:issue-view-sharing` flag, or always be available?

4. **Bulk vs atomic**: Should star/unstar be exclusively atomic operations, or also support bulk starring multiple views?

5. **Response format**: Should star/unstar endpoints return:
   - 204 No Content (like reorder endpoint)
   - 200 with full starred view object
   - 201 Created (for new star entries)

---

## References

### Key Files

- **Models**: `/workspace/repo/src/sentry/models/groupsearchview.py`, `groupsearchviewstarred.py`
- **Endpoints**: `/workspace/repo/src/sentry/issues/endpoints/organization_group_search_view*.py`
- **Serializers**: `/workspace/repo/src/sentry/api/serializers/models/groupsearchview.py`
- **Tests**: `/workspace/repo/tests/sentry/issues/endpoints/test_organization_group_search_view*.py`
- **Migrations**: `/workspace/repo/src/sentry/migrations/0836_*.py`, `0838_*.py`

### Similar Patterns

- ProjectBookmark: `/workspace/repo/src/sentry/models/projectbookmark.py`
- DashboardFavoriteUser: `/workspace/repo/src/sentry/models/dashboard.py`
- SavedSearch: `/workspace/repo/src/sentry/models/savedsearch.py`

---

**Conclusion**: The starring feature is already comprehensively implemented. The spec may be requesting dedicated star/unstar endpoints that operate on existing views without full CRUD semantics, or documentation/refinement of the existing bulk operations.
