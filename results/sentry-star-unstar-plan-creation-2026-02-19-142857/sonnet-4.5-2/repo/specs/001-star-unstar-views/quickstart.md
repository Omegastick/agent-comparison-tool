# Quickstart: Star and Unstar Shared Issue Views

**Feature Branch**: `001-star-unstar-views`  
**Date**: 2026-02-19

## Overview

This guide provides a quickstart for implementing the star/unstar endpoints for GroupSearchViews. The feature adds two new API endpoints that allow users to bookmark and organize shared issue views independently of view creation/deletion.

## Prerequisites

- Sentry development environment set up
- Python 3.13+
- PostgreSQL database running
- Familiarity with Django REST Framework

## What You'll Build

Two new API endpoints:

1. **Star Endpoint**: `POST /api/0/organizations/{org}/group-search-views/{view_id}/star/`
2. **Unstar Endpoint**: `DELETE /api/0/organizations/{org}/group-search-views/{view_id}/unstar/`

## Project Structure

```
src/sentry/
├── issues/endpoints/
│   ├── organization_group_search_view_star.py        # NEW
│   ├── organization_group_search_view_unstar.py      # NEW
│   └── __init__.py                                   # MODIFY (add exports)
├── api/
│   └── urls.py                                       # MODIFY (add routes)
└── models/
    ├── groupsearchview.py                            # EXISTING
    └── groupsearchviewstarred.py                     # EXISTING

tests/sentry/issues/endpoints/
├── test_organization_group_search_view_star.py       # NEW
└── test_organization_group_search_view_unstar.py     # NEW
```

## Implementation Steps

### Step 1: Create Star Endpoint

**File**: `src/sentry/issues/endpoints/organization_group_search_view_star.py`

**Key Components**:

```python
from django.db import transaction
from django.db.models import F, Max, Q
from rest_framework.request import Request
from rest_framework.response import Response
from sentry.api.base import region_silo_endpoint
from sentry.api.bases.organization import OrganizationEndpoint
from sentry.api.serializers.rest_framework import CamelSnakeSerializer
from sentry.db.postgres.roles import router
from sentry.models.groupsearchview import GroupSearchView
from sentry.models.groupsearchviewstarred import GroupSearchViewStarred

class StarRequestSerializer(CamelSnakeSerializer):
    position = serializers.IntegerField(required=False, min_value=1)

@region_silo_endpoint
class OrganizationGroupSearchViewStarEndpoint(OrganizationEndpoint):
    publish_status = {"POST": ApiPublishStatus.PUBLIC}

    def post(self, request: Request, organization, view_id: str) -> Response:
        # 1. Validate view exists and user has access
        # 2. Check if already starred (idempotency)
        # 3. Determine position (specified or append)
        # 4. Shift positions if inserting at specific position
        # 5. Create GroupSearchViewStarred entry
        # 6. Return 204
```

**Critical Logic**:

- Use atomic transaction for position updates
- Query with: `Q(visibility=ORGANIZATION) | Q(user_id=request.user.id)`
- Return 404 for both "not found" and "no access" (avoid leaking existence)

### Step 2: Create Unstar Endpoint

**File**: `src/sentry/issues/endpoints/organization_group_search_view_unstar.py`

**Key Components**:

```python
@region_silo_endpoint
class OrganizationGroupSearchViewUnstarEndpoint(OrganizationEndpoint):
    publish_status = {"DELETE": ApiPublishStatus.PUBLIC}

    def delete(self, request: Request, organization, view_id: str) -> Response:
        # 1. Delete starred entry (if exists)
        # 2. Capture deleted position
        # 3. Decrement positions of views with position > deleted
        # 4. Return 204
```

**Critical Logic**:

- Delete is idempotent (succeeds even if not starred)
- Use atomic transaction for position adjustments
- Pattern from existing delete endpoint (organization_group_search_view_details.py:65-72)

### Step 3: Add URL Routes

**File**: `src/sentry/api/urls.py`

Add two route entries:

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

**Location**: Add near other `group-search-views` routes (search for "group-search-views" in urls.py)

### Step 4: Export Endpoints

**File**: `src/sentry/issues/endpoints/__init__.py`

Add to exports:

```python
from .organization_group_search_view_star import OrganizationGroupSearchViewStarEndpoint
from .organization_group_search_view_unstar import OrganizationGroupSearchViewUnstarEndpoint

__all__ = [
    # ... existing exports ...
    "OrganizationGroupSearchViewStarEndpoint",
    "OrganizationGroupSearchViewUnstarEndpoint",
]
```

### Step 5: Write Tests

**File**: `tests/sentry/issues/endpoints/test_organization_group_search_view_star.py`

**Test Structure**:

```python
from sentry.testutils.cases import APITestCase

class OrganizationGroupSearchViewStarTest(APITestCase):
    endpoint = "sentry-api-0-organization-group-search-view-star"
    method = "post"

    def setUp(self):
        super().setUp()
        self.login_as(self.user)
        # Create test data with factory methods

    def test_star_organization_view(self):
        # Test starring a shared view

    def test_star_owned_view(self):
        # Test starring user's own view

    def test_star_at_position(self):
        # Test position insertion and shifting

    def test_star_already_starred(self):
        # Test idempotency

    def test_star_no_access(self):
        # Test 404 for unauthorized access
```

**File**: `tests/sentry/issues/endpoints/test_organization_group_search_view_unstar.py`

**Test Structure**:

```python
class OrganizationGroupSearchViewUnstarTest(APITestCase):
    endpoint = "sentry-api-0-organization-group-search-view-unstar"
    method = "delete"

    def test_unstar_view(self):
        # Test unstarring and position adjustment

    def test_unstar_not_starred(self):
        # Test idempotency
```

## Key Patterns to Follow

### 1. Access Control

**Always scope to organization**:

```python
view = GroupSearchView.objects.filter(
    Q(visibility=GroupSearchView.Visibility.ORGANIZATION) | Q(user_id=request.user.id),
    id=view_id,
    organization=organization
).first()
```

### 2. Atomic Position Updates

**Use transactions with deferrable constraints**:

```python
with transaction.atomic(router.db_for_write(GroupSearchViewStarred)):
    # Shift positions
    GroupSearchViewStarred.objects.filter(...).update(position=F("position") + 1)
    # Create entry
    GroupSearchViewStarred.objects.create(...)
```

### 3. Idempotency

**Check before acting**:

```python
# Star: check if already starred
if GroupSearchViewStarred.objects.filter(...).exists():
    return Response(status=204)

# Unstar: delete returns count, always return 204
GroupSearchViewStarred.objects.filter(...).delete()
return Response(status=204)
```

### 4. Error Responses

**Always use "detail" key**:

```python
return Response({"detail": "View not found"}, status=404)
return Response({"detail": "Invalid position"}, status=400)
```

### 5. Test Factory Methods

**Never use Model.objects.create() directly**:

```python
# GOOD
self.create_user()
self.create_organization()
self.create_project()

# BAD
User.objects.create(...)
```

## Reference Examples

Study these existing files for patterns:

1. **Reorder Endpoint** (position management):
   - `/workspace/repo/src/sentry/issues/endpoints/organization_group_search_view_starred_order.py`

2. **Delete Endpoint** (position decrementing):
   - `/workspace/repo/src/sentry/issues/endpoints/organization_group_search_view_details.py`

3. **Model with Manager**:
   - `/workspace/repo/src/sentry/models/groupsearchviewstarred.py`

4. **Test Structure**:
   - `/workspace/repo/tests/sentry/issues/endpoints/test_organization_group_search_view_starred_order.py`

## Running Tests

```bash
# Run all star/unstar tests
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_star.py
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_unstar.py

# Run specific test
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_star.py::OrganizationGroupSearchViewStarTest::test_star_organization_view

# Run with verbose output
pytest -vv tests/sentry/issues/endpoints/test_organization_group_search_view_star.py
```

## Testing Manually

```bash
# Start Sentry development server
sentry devserver

# Star a view
curl -X POST \
  http://localhost:8000/api/0/organizations/my-org/group-search-views/123/star/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"position": 2}'

# Unstar a view
curl -X DELETE \
  http://localhost:8000/api/0/organizations/my-org/group-search-views/123/unstar/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# List starred views (existing endpoint)
curl http://localhost:8000/api/0/organizations/my-org/group-search-views/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Common Pitfalls

1. **Forgetting organization scoping** → IDOR vulnerability
2. **Not using atomic transactions** → Race conditions in position updates
3. **Using wrong status codes** → Use 204 for success, 404 for not found
4. **Direct model creation in tests** → Use factory methods
5. **Not handling idempotency** → Operations should be safe to retry
6. **Returning 403 instead of 404** → Leaks view existence

## Success Criteria

Before considering the feature complete:

- [ ] Star endpoint returns 204 for successful star
- [ ] Star endpoint is idempotent (re-starring succeeds)
- [ ] Unstar endpoint returns 204 for successful unstar
- [ ] Unstar endpoint is idempotent (re-unstarring succeeds)
- [ ] Position insertion shifts existing positions correctly
- [ ] Position deletion adjusts remaining positions
- [ ] Access control enforced (404 for unauthorized views)
- [ ] All tests pass
- [ ] OpenAPI documentation generated correctly

## Next Steps

After completing implementation:

1. **Code Review**: Submit PR with all changes
2. **Manual Testing**: Test with various position scenarios
3. **Performance Testing**: Verify query performance with large starred lists
4. **Documentation**: Update API documentation if needed
5. **Monitoring**: Add metrics for star/unstar operations (optional)

## Questions?

Refer to:

- **Research Document**: `/workspace/repo/specs/001-star-unstar-views/research.md`
- **Data Model**: `/workspace/repo/specs/001-star-unstar-views/data-model.md`
- **API Contracts**: `/workspace/repo/specs/001-star-unstar-views/contracts/`
- **AGENTS.md**: `/workspace/repo/AGENTS.md`
