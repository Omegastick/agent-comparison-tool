# Research: Star and Unstar Shared Issue Views

**Date**: 2026-02-19  
**Feature Branch**: `001-star-unstar-views`

## Executive Summary

This feature adds two dedicated API endpoints (`star` and `unstar`) for GroupSearchViews. The underlying infrastructure (model, serializers, position management) already exists in the codebase but is only accessible through bulk create/update/delete operations. This research validates the technical approach and documents the existing patterns to follow.

## Existing Infrastructure Analysis

### 1. Data Model (Already Exists)

**File**: `/workspace/repo/src/sentry/models/groupsearchviewstarred.py`

The `GroupSearchViewStarred` model is complete and production-ready:

```python
@region_silo_model
class GroupSearchViewStarred(DefaultFieldsModel):
    user_id = HybridCloudForeignKey(settings.AUTH_USER_MODEL, on_delete="CASCADE")
    organization = FlexibleForeignKey("sentry.Organization", db_constraint=False)
    group_search_view = FlexibleForeignKey("sentry.GroupSearchView", on_delete="CASCADE")
    position = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "organization_id", "position"],
                name="sentry_groupsearchviewstarred_unique_view_position_per_org_user",
                deferrable=models.Deferrable.DEFERRED  # Critical for atomic reordering
            )
        ]
```

**Key Features**:

- Deferrable constraint allows bulk position updates within a transaction
- Position field enables ordered list of starred views
- Proper foreign key relationships with cascade deletion
- Region silo model (user data lives in region silo)

### 2. Manager Methods (Already Exists)

**File**: `/workspace/repo/src/sentry/models/groupsearchviewstarred.py` (lines 20-50)

`GroupSearchViewStarredManager.reorder_starred_views()` provides atomic reordering:

```python
def reorder_starred_views(self, organization, user_id, new_view_positions):
    """
    Reorders existing starred views to new positions.

    Args:
        organization: Organization scope
        user_id: User performing reorder
        new_view_positions: List of (view_id, new_position) tuples

    Uses bulk_update for efficiency and atomic transactions.
    """
```

**Usage Pattern**: Called by existing reorder endpoint, can be leveraged for position shifting in star operation.

### 3. Existing Endpoints

#### A. Bulk Create/Update: `OrganizationGroupSearchViewsEndpoint`

**File**: `/workspace/repo/src/sentry/issues/endpoints/organization_group_search_views.py`

- **GET**: Returns user's starred views (queries `GroupSearchViewStarred`)
- **PUT**: Creates/updates views AND automatically stars them
- **Limitation**: Cannot star existing views without modifying them

#### B. Delete: `OrganizationGroupSearchViewDetailsEndpoint`

**File**: `/workspace/repo/src/sentry/issues/endpoints/organization_group_search_view_details.py`

- **DELETE**: Deletes view and unstars it, then decrements positions of higher views
- **Limitation**: Cannot unstar without deleting the view itself

#### C. Reorder: `OrganizationGroupSearchViewStarredOrderEndpoint`

**File**: `/workspace/repo/src/sentry/issues/endpoints/organization_group_search_view_starred_order.py`

- **PUT**: Reorders existing starred views
- **Limitation**: Cannot add/remove stars, only reorder

### 4. Gap Analysis

**What's Missing**:

1. **Independent Star Operation**: Cannot star a view without creating/updating it
2. **Independent Unstar Operation**: Cannot unstar without deleting the view
3. **Position Insertion Logic**: No logic to insert at specific position and shift others
4. **Access Validation for Starring**: Need to validate user can access view before starring

**What Exists**:

- Model and database schema ✅
- Serializers (`GroupSearchViewStarredSerializer`) ✅
- Position management utilities ✅
- Permission checking base classes ✅
- Test infrastructure ✅

## Technical Decisions

### Decision 1: Endpoint Design Pattern

**Chosen**: Resource-nested POST/DELETE endpoints

- **Star**: `POST /organizations/{org}/group-search-views/{view_id}/star/`
- **Unstar**: `DELETE /organizations/{org}/group-search-views/{view_id}/unstar/`

**Rationale**:

- RESTful: Star/unstar are actions on a specific view resource
- Consistent with Sentry's URL structure
- Clear intent: POST creates starred relationship, DELETE removes it
- Idempotent: Safe to retry

**Alternatives Considered**:

1. **PUT /organizations/{org}/group-search-views-starred/** with view_id in body
   - Rejected: Less RESTful, obscures which view is being starred
2. **POST with action in body** (`{"action": "star"}`)
   - Rejected: Not idiomatic REST, makes OpenAPI documentation awkward
3. **Single endpoint with toggle behavior**
   - Rejected: Not idempotent, unpredictable for concurrent requests

### Decision 2: Request Body for Star Endpoint

**Chosen**: Optional position parameter in request body

```json
{
  "position": 2 // Optional, defaults to appending at end
}
```

**Rationale**:

- Position is auxiliary data, not part of URL structure
- Allows future extensibility (e.g., add metadata, tags)
- Mirrors pattern in bulk PUT endpoint
- Clear separation: URL identifies resource, body provides parameters

**Alternatives Considered**:

1. **Query parameter** (`?position=2`)
   - Rejected: Query params typically for filtering/search, not resource creation
2. **No position support in star endpoint**
   - Rejected: Spec explicitly requires position management on starring

### Decision 3: Position Management Strategy

**Chosen**: Hybrid approach

- **No position specified**: Append to end (find max position + 1)
- **Position specified**: Insert at position, shift others up atomically

**Implementation**:

```python
with transaction.atomic(router.db_for_write(GroupSearchViewStarred)):
    if position is not None:
        # Increment positions >= specified position
        GroupSearchViewStarred.objects.filter(
            organization=organization,
            user_id=request.user.id,
            position__gte=position
        ).update(position=F("position") + 1)
    else:
        # Append: find max position
        max_pos = GroupSearchViewStarred.objects.filter(
            organization=organization,
            user_id=request.user.id
        ).aggregate(Max("position"))["position__max"]
        position = (max_pos or 0) + 1

    # Create starred entry
    GroupSearchViewStarred.objects.create(...)
```

**Rationale**:

- Atomic transaction prevents race conditions
- Deferrable constraint allows temporary position violations during transaction
- Follows pattern from delete endpoint (lines 67-72 in `organization_group_search_view_details.py`)
- Efficient: Single bulk update for shifting

**Alternatives Considered**:

1. **Always require position**
   - Rejected: Spec says position is optional, burdens simple use case
2. **Gap-based positioning** (e.g., position 1000, 2000, 3000)
   - Rejected: Adds complexity, eventual rebalancing needed, not Sentry's pattern

### Decision 4: Access Validation Logic

**Chosen**: Check both ownership and organization-level sharing

```python
# Validate view exists and user has access
view = GroupSearchView.objects.filter(
    Q(visibility=GroupSearchView.Visibility.ORGANIZATION) | Q(user_id=request.user.id),
    id=view_id,
    organization=organization
).first()

if not view:
    return Response({"detail": "View not found or access denied"}, status=404)
```

**Rationale**:

- Matches access pattern from reorder endpoint (lines 30-43)
- Single query with OR condition is efficient
- Returns 404 (not 403) to avoid leaking view existence
- Scoped to organization for multi-tenant security

**Alternatives Considered**:

1. **Separate queries for owned vs shared**
   - Rejected: Two database queries vs one
2. **Check permissions after fetching**
   - Rejected: Potential IDOR vulnerability if fetch not scoped

### Decision 5: Idempotency Handling

**Chosen**: Silent success for duplicate operations

**Star Idempotency**:

```python
# If already starred, return success without changes
if GroupSearchViewStarred.objects.filter(
    group_search_view=view,
    user_id=request.user.id,
    organization=organization
).exists():
    return Response(status=204)  # No content - idempotent success
```

**Unstar Idempotency**:

```python
# Delete returns number of deleted rows
deleted_count, _ = GroupSearchViewStarred.objects.filter(...).delete()
# Always return 204, regardless of whether anything was deleted
return Response(status=204)
```

**Rationale**:

- Matches HTTP idempotency semantics
- Safe for retries and race conditions
- Spec explicitly requires idempotent behavior (FR-003, FR-004)
- Consistent with REST best practices

**Alternatives Considered**:

1. **Return error on duplicate star**
   - Rejected: Violates spec, breaks retries
2. **Return different status for no-op vs actual change**
   - Rejected: Clients shouldn't need to distinguish, adds complexity

### Decision 6: Response Status Codes

**Chosen**:

- **Star success**: `204 No Content` (idempotent, no response body needed)
- **Unstar success**: `204 No Content`
- **View not found/no access**: `404 Not Found`
- **Invalid position**: `400 Bad Request`

**Rationale**:

- `204` is standard for successful DELETE with no response body
- Consistent with reorder endpoint (returns 204)
- Clear distinction: 404 for resource issues, 400 for input validation

**Alternatives Considered**:

1. **Return 200 with serialized starred view**
   - Rejected: Adds unnecessary data transfer, clients typically don't need response
2. **Return 201 Created for star**
   - Rejected: Awkward for idempotent operation (re-starring wouldn't be "created")

### Decision 7: URL Routing Pattern

**Chosen**: Add routes to `src/sentry/api/urls.py` with regex patterns

```python
re_path(
    r"^(?P<organization_id_or_slug>[^\/]+)/group-search-views/(?P<view_id>[0-9]+)/star/$",
    OrganizationGroupSearchViewStarEndpoint.as_view(),
    name="sentry-api-0-organization-group-search-view-star",
)
re_path(
    r"^(?P<organization_id_or_slug>[^\/]+)/group-search-views/(?P<view_id>[0-9]+)/unstar/$",
    OrganizationGroupSearchViewUnstarEndpoint.as_view(),
    name="sentry-api-0-organization-group-search-view-unstar",
)
```

**Rationale**:

- Matches existing GroupSearchView URL patterns
- Uses `[0-9]+` for numeric view_id (not slug)
- Name follows convention: `sentry-api-0-{resource}-{action}`
- Grouped with other group-search-view routes

**Alternatives Considered**:

1. **Place in issues-specific URL config**
   - Rejected: GroupSearchView routes are in main `api/urls.py`

## Best Practices from Existing Code

### 1. Endpoint Class Structure

**Reference**: `organization_group_search_view_starred_order.py`

```python
from sentry.api.base import region_silo_endpoint
from sentry.api.bases.organization import OrganizationEndpoint
from sentry.api.serializers import serialize

@region_silo_endpoint
class MyEndpoint(OrganizationEndpoint):
    publish_status = {
        "POST": ApiPublishStatus.PUBLIC,
    }

    def post(self, request: Request, organization) -> Response:
        # Implementation
        return Response(status=204)
```

**Key Elements**:

- `@region_silo_endpoint` decorator (views are region data)
- Inherit from `OrganizationEndpoint` (automatic permission/scoping)
- Declare `publish_status` for OpenAPI documentation
- Type hints: `request: Request`, `-> Response`

### 2. Transaction Safety

**Reference**: `organization_group_search_view_details.py` (lines 65-72)

```python
with transaction.atomic(router.db_for_write(GroupSearchViewStarred)):
    # Multiple database operations
    starred.delete()
    GroupSearchViewStarred.objects.filter(...).update(position=F("position") - 1)
```

**Critical**: Use `router.db_for_write(Model)` for correct silo routing.

### 3. Permission Checking Pattern

**Reference**: `organization_group_search_view_starred_order.py` (lines 30-43)

```python
# Fetch all views user is trying to operate on
views = GroupSearchView.objects.filter(
    Q(visibility=GroupSearchView.Visibility.ORGANIZATION) | Q(user_id=request.user.id),
    id__in=view_ids,
    organization=organization
)

# Validate user has access to ALL views
if len(views) != len(view_ids):
    return Response({"detail": "Invalid view IDs"}, status=400)
```

### 4. Error Response Format

**Critical**: Always use `"detail"` key for error messages (DRF convention)

```python
return Response({"detail": "View not found"}, status=404)
return Response({"detail": "Invalid position"}, status=400)
```

### 5. Testing Patterns

**Reference**: `test_organization_group_search_view_starred_order.py`

```python
class OrganizationGroupSearchViewStarTest(APITestCase):
    endpoint = "sentry-api-0-organization-group-search-view-star"
    method = "post"

    def setUp(self):
        super().setUp()
        self.login_as(self.user)
        self.view = self.create_group_search_view(
            organization=self.organization,
            user=self.user
        )

    def test_star_view(self):
        response = self.get_success_response(
            self.organization.slug,
            self.view.id,
            status_code=204
        )
```

**Key Elements**:

- Declare `endpoint` and `method` as class attributes
- Use factory methods: `self.create_*`
- Use `self.get_success_response()` for assertions
- Use `setUp()` for common test data

## Edge Cases and Validation

### 1. Deleted View

**Scenario**: User tries to star a view that has been deleted

**Handling**:

```python
view = GroupSearchView.objects.filter(...).first()
if not view:
    return Response({"detail": "View not found"}, status=404)
```

**Result**: 404 response, transaction not started

### 2. Position Out of Bounds

**Scenario**: User stars at position 100 when they only have 3 starred views

**Decision**: Allow it - creates gap in positions

- **Rationale**: Simplifies logic, gaps are harmless, user intent is clear
- **Alternative**: Clamp to max+1 (rejected: changes user intent)

### 3. Concurrent Star Requests

**Scenario**: Two requests try to star different views at same position simultaneously

**Handling**: Atomic transactions with deferrable constraints

- First transaction commits: succeeds
- Second transaction: position constraint violated, raises IntegrityError
- **Mitigation**: Retry with next available position? OR let it fail?

**Decision**: Let second request fail with 409 Conflict

- **Rationale**: Rare edge case, retry logic adds complexity, client can retry

### 4. Starring Owned vs Shared Views

**Scenario**: User stars their own view (which they created)

**Handling**: Allowed by design (spec Story 4)

- Access check: `Q(visibility=ORGANIZATION) | Q(user_id=request.user.id)`
- User's own views satisfy second condition

### 5. Organization Boundary

**Scenario**: User tries to star view from different organization

**Handling**: Filtered out by `organization=organization` in query

- Returns 404 (view not found in user's organization)
- Multi-tenant security maintained

## Performance Considerations

### 1. Position Shifting Cost

**Operation**: Starring at position 2 with 100 existing starred views

**Cost**:

- 1 SELECT (check if already starred)
- 1 SELECT (validate view access)
- 1 UPDATE (bulk shift positions >= 2)
- 1 INSERT (create starred entry)

**Total**: ~4 queries, all indexed

**Optimization**: Positions indexed as part of unique constraint

### 2. Append Cost

**Operation**: Starring without position (append to end)

**Cost**:

- 1 SELECT (check if already starred)
- 1 SELECT (validate view access)
- 1 SELECT with MAX aggregate (find highest position)
- 1 INSERT (create starred entry)

**Total**: ~4 queries

### 3. Idempotent Re-star Cost

**Operation**: Starring an already-starred view

**Cost**:

- 1 SELECT (check if already starred) → finds existing
- Early return, no further queries

**Total**: 1 query

**Optimization**: Most efficient path for common retry scenario

## Security Validation

### 1. IDOR Prevention

**Threat**: User manipulates view_id to star views from other organizations

**Mitigation**: All queries scoped to `organization=organization`

```python
view = GroupSearchView.objects.filter(
    organization=organization,  # Critical scoping
    id=view_id
)
```

### 2. Permission Validation

**Threat**: User stars private views owned by others

**Mitigation**: Access check with OR condition

```python
Q(visibility=ORGANIZATION) | Q(user_id=request.user.id)
```

### 3. Position Manipulation

**Threat**: User sets negative or extremely large position

**Mitigation**:

- Model field: `PositiveSmallIntegerField` (0-32767)
- Database enforces non-negative constraint
- Optional: Add serializer validation for reasonable range (0-1000)

## Open Questions - RESOLVED

### Q1: Should position be 0-indexed or 1-indexed?

**Decision**: 1-indexed (position starts at 1)

**Rationale**:

- Existing code uses 1-indexed (reorder endpoint expects positions starting at 1)
- More intuitive for non-technical users ("first position" = 1, not 0)
- Database constraint allows 0, but convention is to start at 1

**Evidence**: Test files show position values starting at 1

### Q2: What happens to position gaps?

**Decision**: Gaps are allowed and persist

**Rationale**:

- Simplifies insertion logic
- No harm in gaps (display layer can normalize)
- Automatic gap-filling adds complexity without clear benefit
- User can manually reorder to close gaps if desired

### Q3: Should there be a maximum number of starred views?

**Decision**: No explicit limit in v1

**Rationale**:

- No existing limit in GroupSearchViewStarred model
- Unlikely to hit practical limits (users rarely star >50 views)
- Can add soft limit later via feature flag if needed

**Alternative**: Could add validation like `if count > 100: return 400` but not required by spec

## Implementation Checklist

Based on research, these are the concrete tasks:

1. **Create Star Endpoint**
   - File: `src/sentry/issues/endpoints/organization_group_search_view_star.py`
   - Inherit from `OrganizationEndpoint`
   - Implement POST method with optional position parameter
   - Add to `__init__.py` exports

2. **Create Unstar Endpoint**
   - File: `src/sentry/issues/endpoints/organization_group_search_view_unstar.py`
   - Inherit from `OrganizationEndpoint`
   - Implement DELETE method
   - Add to `__init__.py` exports

3. **Update URL Routing**
   - File: `src/sentry/api/urls.py`
   - Add two `re_path` entries for star/unstar

4. **Create Star Tests**
   - File: `tests/sentry/issues/endpoints/test_organization_group_search_view_star.py`
   - Test all scenarios from spec (stories 1, 3, 4)

5. **Create Unstar Tests**
   - File: `tests/sentry/issues/endpoints/test_organization_group_search_view_unstar.py`
   - Test all scenarios from spec (story 2)

6. **Update OpenAPI Documentation**
   - Add drf-spectacular decorators to endpoints
   - Define request/response schemas

## References

### Existing Code to Study

1. **Model**: `/workspace/repo/src/sentry/models/groupsearchviewstarred.py`
2. **Reorder Endpoint**: `/workspace/repo/src/sentry/issues/endpoints/organization_group_search_view_starred_order.py`
3. **Delete Endpoint**: `/workspace/repo/src/sentry/issues/endpoints/organization_group_search_view_details.py`
4. **Serializer**: `/workspace/repo/src/sentry/api/serializers/models/groupsearchview.py`
5. **Test Example**: `/workspace/repo/tests/sentry/issues/endpoints/test_organization_group_search_view_starred_order.py`

### Documentation

- Django REST Framework: https://www.django-rest-framework.org/
- drf-spectacular: https://drf-spectacular.readthedocs.io/
- Sentry AGENTS.md: `/workspace/repo/AGENTS.md`

## Conclusion

All technical questions resolved. No remaining "NEEDS CLARIFICATION" items. Implementation can proceed directly to Phase 1 (design) and Phase 2 (implementation) with confidence.
