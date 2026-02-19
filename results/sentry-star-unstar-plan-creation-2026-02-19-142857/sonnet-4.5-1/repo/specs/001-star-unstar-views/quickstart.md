# Quickstart: Star and Unstar Shared Issue Views

**Feature**: 001-star-unstar-views  
**Last Updated**: 2026-02-19

## Overview

This guide helps developers implement and use the star/unstar endpoints for group search views (saved issue views). These endpoints complement the existing bulk operations by providing dedicated actions for starring and unstarring views.

**Important**: The underlying data model (`GroupSearchView` and `GroupSearchViewStarred`) already exists in Sentry. This feature adds new API endpoints to the existing infrastructure.

---

## For API Consumers

### Quick Reference

| Operation             | Method | Endpoint                                                        | Status               |
| --------------------- | ------ | --------------------------------------------------------------- | -------------------- |
| Star a view           | POST   | `/api/0/organizations/{org}/group-search-views/{view_id}/star/` | ⚠️ To be implemented |
| Unstar a view         | DELETE | `/api/0/organizations/{org}/group-search-views/{view_id}/star/` | ⚠️ To be implemented |
| List starred views    | GET    | `/api/0/organizations/{org}/group-search-views/`                | ✅ Exists            |
| Reorder starred views | PUT    | `/api/0/organizations/{org}/group-search-views-starred-order/`  | ✅ Exists            |

### Authentication

All endpoints require authentication via Bearer token:

```bash
curl -H "Authorization: Bearer YOUR_SENTRY_TOKEN" \
  https://sentry.io/api/0/organizations/my-org/group-search-views/
```

### Star a View

**Endpoint**: `POST /api/0/organizations/{org}/group-search-views/{view_id}/star/`

**Use case**: Bookmark a useful view created by a teammate

```bash
# Star at end of list (default)
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  https://sentry.io/api/0/organizations/my-org/group-search-views/123/star/

# Star at specific position
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"position": 2}' \
  https://sentry.io/api/0/organizations/my-org/group-search-views/123/star/
```

**Response (201 Created or 200 OK)**:

```json
{
  "id": "123",
  "name": "High Priority Bugs",
  "query": "is:unresolved priority:high",
  "querySort": "date",
  "position": 2,
  "projects": ["backend-api"],
  "isAllProjects": false,
  "environments": ["production"],
  "timeFilters": {
    "period": "14d"
  },
  "lastVisited": null,
  "dateCreated": "2026-02-01T08:00:00Z",
  "dateUpdated": "2026-02-19T10:30:00Z"
}
```

**Idempotency**: Starring an already-starred view returns 200 OK with the existing data.

### Unstar a View

**Endpoint**: `DELETE /api/0/organizations/{org}/group-search-views/{view_id}/star/`

**Use case**: Remove a view from your bookmarks

```bash
curl -X DELETE \
  -H "Authorization: Bearer YOUR_TOKEN" \
  https://sentry.io/api/0/organizations/my-org/group-search-views/123/star/
```

**Response (204 No Content)**: Empty body

**Idempotency**: Unstarring a non-starred view returns 204 with no error.

### List Starred Views

**Endpoint**: `GET /api/0/organizations/{org}/group-search-views/`

**Use case**: Retrieve all bookmarked views in order

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://sentry.io/api/0/organizations/my-org/group-search-views/
```

**Response (200 OK)**:

```json
[
  {
    "id": "456",
    "name": "My Daily View",
    "position": 0,
    ...
  },
  {
    "id": "789",
    "name": "Critical Errors",
    "position": 1,
    ...
  },
  {
    "id": "123",
    "name": "High Priority Bugs",
    "position": 2,
    ...
  }
]
```

### Reorder Starred Views

**Endpoint**: `PUT /api/0/organizations/{org}/group-search-views-starred-order/`

**Use case**: Change the order of bookmarked views

```bash
curl -X PUT \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"viewIds": [123, 456, 789]}' \
  https://sentry.io/api/0/organizations/my-org/group-search-views-starred-order/
```

**Response (204 No Content)**: Empty body

**Important**: The `viewIds` array must include ALL currently starred view IDs. Missing or extra IDs will cause a 400 error.

---

## For Sentry Developers

### Prerequisites

- Python 3.13+
- Django 5.2+
- PostgreSQL (existing Sentry database)
- Sentry development environment set up

### Development Workflow

#### 1. Create Endpoint Files

Create two new endpoint files in `/workspace/repo/src/sentry/issues/endpoints/`:

**File**: `organization_group_search_view_star.py`

```python
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.api_owners import ApiOwner
from sentry.api.api_publish_status import ApiPublishStatus
from sentry.api.base import region_silo_endpoint
from sentry.api.bases.organization import OrganizationEndpoint
from sentry.api.serializers import serialize
from sentry.models.groupsearchview import GroupSearchView, GroupSearchViewVisibility
from sentry.models.groupsearchviewstarred import GroupSearchViewStarred

# MemberPermission allows regular org members to manage their stars
class MemberPermission(OrganizationPermission):
    scope_map = {
        "POST": ["member:read", "member:write"],
        "DELETE": ["member:read", "member:write"],
    }

@region_silo_endpoint
class OrganizationGroupSearchViewStarEndpoint(OrganizationEndpoint):
    publish_status = {
        "POST": ApiPublishStatus.EXPERIMENTAL,
        "DELETE": ApiPublishStatus.EXPERIMENTAL,
    }
    owner = ApiOwner.ISSUES
    permission_classes = (MemberPermission,)

    def post(self, request: Request, organization, view_id: str) -> Response:
        """Star a group search view"""
        # Implementation details in Phase 2
        pass

    def delete(self, request: Request, organization, view_id: str) -> Response:
        """Unstar a group search view"""
        # Implementation details in Phase 2
        pass
```

#### 2. Register URL Routes

Add routes to `/workspace/repo/src/sentry/api/urls.py`:

```python
# Star/unstar endpoint
re_path(
    r"^organizations/(?P<organization_id_or_slug>[^\/]+)/group-search-views/(?P<view_id>\d+)/star/$",
    OrganizationGroupSearchViewStarEndpoint.as_view(),
    name="sentry-api-0-organization-group-search-view-star",
),
```

#### 3. Write Tests

Create test file at `/workspace/repo/tests/sentry/issues/endpoints/test_organization_group_search_view_star.py`:

```python
from sentry.models.groupsearchview import GroupSearchView, GroupSearchViewVisibility
from sentry.models.groupsearchviewstarred import GroupSearchViewStarred
from sentry.testutils.cases import APITestCase
from sentry.testutils.helpers.features import with_feature

@with_feature("organizations:issue-stream-custom-views")
class OrganizationGroupSearchViewStarTest(APITestCase):
    endpoint = "sentry-api-0-organization-group-search-view-star"

    def setUp(self):
        super().setUp()
        self.login_as(self.user)

        # Create a test view
        self.view = GroupSearchView.objects.create(
            organization=self.organization,
            user_id=self.user.id,
            name="Test View",
            query="is:unresolved",
            query_sort="date",
            visibility=GroupSearchViewVisibility.ORGANIZATION,
        )

    def test_star_view_at_end(self):
        """Test starring a view without position (appends to end)"""
        response = self.get_success_response(
            self.organization.slug,
            self.view.id,
            method="post",
            status_code=201,
        )
        assert response.data["id"] == str(self.view.id)
        assert response.data["position"] == 0

        # Verify database
        starred = GroupSearchViewStarred.objects.get(
            user_id=self.user.id,
            group_search_view=self.view,
        )
        assert starred.position == 0

    def test_star_view_idempotent(self):
        """Test starring an already-starred view (idempotent)"""
        # Star first time
        self.get_success_response(
            self.organization.slug,
            self.view.id,
            method="post",
            status_code=201,
        )

        # Star second time - should return 200 OK (not 201)
        response = self.get_success_response(
            self.organization.slug,
            self.view.id,
            method="post",
            status_code=200,
        )
        assert response.data["position"] == 0

    def test_unstar_view(self):
        """Test unstarring a starred view"""
        # Star first
        GroupSearchViewStarred.objects.create(
            user_id=self.user.id,
            organization=self.organization,
            group_search_view=self.view,
            position=0,
        )

        # Unstar
        self.get_success_response(
            self.organization.slug,
            self.view.id,
            method="delete",
            status_code=204,
        )

        # Verify deleted
        assert not GroupSearchViewStarred.objects.filter(
            user_id=self.user.id,
            group_search_view=self.view,
        ).exists()

    def test_unstar_view_idempotent(self):
        """Test unstarring a non-starred view (idempotent)"""
        # Unstar without starring first
        self.get_success_response(
            self.organization.slug,
            self.view.id,
            method="delete",
            status_code=204,
        )

    def test_star_view_no_access(self):
        """Test starring a view the user doesn't have access to"""
        # Create private view owned by another user
        other_user = self.create_user()
        private_view = GroupSearchView.objects.create(
            organization=self.organization,
            user_id=other_user.id,
            name="Private View",
            query="is:unresolved",
            query_sort="date",
            visibility=GroupSearchViewVisibility.OWNER,  # Private!
        )

        # Attempt to star
        self.get_error_response(
            self.organization.slug,
            private_view.id,
            method="post",
            status_code=403,
        )
```

#### 4. Run Tests

```bash
# Run specific test file
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_star.py -v

# Run all group search view tests
pytest tests/sentry/issues/endpoints/test_organization_group_search_view*.py -v

# Run with coverage
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_star.py --cov=src/sentry/issues/endpoints --cov-report=html
```

#### 5. Database Transactions

**Important**: Always use `transaction.atomic()` with proper DB routing:

```python
from django.db import IntegrityError, router, transaction

with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
    # Perform database writes here
    starred, created = GroupSearchViewStarred.objects.update_or_create(
        user_id=request.user.id,
        organization=organization,
        group_search_view=view,
        defaults={"position": position}
    )
```

#### 6. Serialization Pattern

Use existing serializers with batch-fetching:

```python
from sentry.api.serializers import serialize
from sentry.api.serializers.models.groupsearchview import GroupSearchViewStarredSerializer

# Single object
serialized = serialize(
    starred_view,
    request.user,
    serializer=GroupSearchViewStarredSerializer()
)

# Batch (avoids N+1 queries)
starred_views = GroupSearchViewStarred.objects.filter(
    user_id=request.user.id,
    organization=organization
).select_related("group_search_view").prefetch_related("group_search_view__projects")

serialized = serialize(
    list(starred_views),
    request.user,
    serializer=GroupSearchViewStarredSerializer()
)
```

---

## Key Implementation Details

### Authorization Pattern

```python
# 1. Fetch view (organization-scoped)
try:
    view = GroupSearchView.objects.get(
        id=view_id,
        organization=organization
    )
except GroupSearchView.DoesNotExist:
    return Response(status=status.HTTP_404_NOT_FOUND)

# 2. Check user access
if view.user_id != request.user.id and view.visibility != GroupSearchViewVisibility.ORGANIZATION:
    return Response(
        {"detail": "You do not have access to this view"},
        status=status.HTTP_403_FORBIDDEN
    )
```

### Position Management

**Appending to end**:

```python
max_pos = GroupSearchViewStarred.objects.filter(
    user_id=request.user.id,
    organization=organization
).aggregate(Max("position"))["position__max"]

position = (max_pos + 1) if max_pos is not None else 0
```

**Inserting at specific position**:

```python
# Shift existing items
GroupSearchViewStarred.objects.filter(
    user_id=request.user.id,
    organization=organization,
    position__gte=position
).exclude(group_search_view=view).update(position=F("position") + 1)

# Create/update starred entry
GroupSearchViewStarred.objects.update_or_create(
    user_id=request.user.id,
    organization=organization,
    group_search_view=view,
    defaults={"position": position}
)
```

**Adjusting positions on delete**:

```python
try:
    starred = GroupSearchViewStarred.objects.get(
        user_id=request.user.id,
        organization=organization,
        group_search_view_id=view_id
    )
    deleted_position = starred.position
    starred.delete()

    # Decrement positions of items after deleted one
    GroupSearchViewStarred.objects.filter(
        user_id=request.user.id,
        organization=organization,
        position__gt=deleted_position
    ).update(position=F("position") - 1)
except GroupSearchViewStarred.DoesNotExist:
    pass  # Idempotent - already unstarred
```

### Idempotency

- **Star**: Use `update_or_create()` - returns existing entry if already starred
- **Unstar**: Use `filter().delete()` - returns 0 if not found (no error)

---

## Common Patterns

### Checking if View is Starred (in Serializers)

```python
# In get_attrs() to batch-fetch
def get_attrs(self, item_list, user, **kwargs):
    starred_ids = set(
        GroupSearchViewStarred.objects.filter(
            user_id=user.id,
            group_search_view_id__in=[item.id for item in item_list]
        ).values_list("group_search_view_id", flat=True)
    )

    return {
        item: {"is_starred": item.id in starred_ids}
        for item in item_list
    }
```

### Feature Flags

Check feature flags in endpoints:

```python
from sentry import features

# Check if custom views are enabled
if not features.has("organizations:issue-stream-custom-views", organization):
    return Response({"detail": "Feature not enabled"}, status=404)

# Check if view sharing is enabled (for org-shared views)
if view.visibility == GroupSearchViewVisibility.ORGANIZATION:
    if not features.has("organizations:issue-view-sharing", organization):
        return Response({"detail": "View sharing not enabled"}, status=403)
```

---

## Debugging

### Check Database State

```python
# Check starred views for a user
from sentry.models.groupsearchviewstarred import GroupSearchViewStarred
from sentry.models.organization import Organization
from sentry.models.user import User

user = User.objects.get(email="user@example.com")
org = Organization.objects.get(slug="my-org")

starred = GroupSearchViewStarred.objects.filter(
    user_id=user.id,
    organization=org
).order_by("position")

for s in starred:
    print(f"Position {s.position}: {s.group_search_view.name}")
```

### Enable Query Logging

```python
import logging
logging.getLogger("django.db.backends").setLevel(logging.DEBUG)

# Now all SQL queries are logged
```

### Check Constraints

```bash
# Connect to PostgreSQL
psql sentry

# Check constraint
\d sentry_groupsearchviewstarred

# Should show constraint:
# "unique_view_position_per_org_user" UNIQUE CONSTRAINT, btree (user_id, organization_id, position) DEFERRABLE INITIALLY DEFERRED
```

---

## Performance Tips

1. **Use select_related()**: Fetch related GroupSearchView in one query
2. **Use prefetch_related()**: Fetch M2M projects efficiently
3. **Batch operations**: Use bulk_update() for reordering
4. **Avoid N+1**: Always implement get_attrs() in serializers
5. **Use F() expressions**: For atomic position increments/decrements

---

## Related Resources

- **API Specification**: `/workspace/repo/specs/001-star-unstar-views/contracts/openapi.yaml`
- **Data Model**: `/workspace/repo/specs/001-star-unstar-views/data-model.md`
- **Research**: `/workspace/repo/specs/001-star-unstar-views/research.md`
- **Feature Spec**: `/workspace/repo/specs/001-star-unstar-views/spec.md`

**Existing similar endpoints**:

- `organization_group_search_views.py` - Bulk operations
- `organization_group_search_view_starred_order.py` - Reordering
- `organization_group_search_view_details.py` - Delete view

**Models**:

- `/workspace/repo/src/sentry/models/groupsearchview.py`
- `/workspace/repo/src/sentry/models/groupsearchviewstarred.py`

---

## Next Steps

After implementing endpoints:

1. ✅ Write comprehensive tests (see test template above)
2. ✅ Run tests: `pytest tests/sentry/issues/endpoints/test_organization_group_search_view_star.py -v`
3. ✅ Manual testing via API client (curl, Postman, or Sentry's internal tools)
4. ✅ Update OpenAPI documentation with drf-spectacular decorators
5. ✅ Add feature flag checks if needed
6. ✅ Update AGENTS.md with any new patterns

---

## Questions or Issues?

Refer to:

- **Constitution**: `/workspace/repo/.specify/memory/constitution.md` - Architectural principles
- **AGENTS.md**: `/workspace/repo/AGENTS.md` - Sentry development patterns
- **Existing tests**: `/workspace/repo/tests/sentry/issues/endpoints/test_organization_group_search_view*.py`
