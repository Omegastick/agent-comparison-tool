# Quickstart: Star and Unstar Shared Issue Views

**Feature Branch**: `001-star-unstar-views`
**Date**: 2026-02-19

## What This Feature Does

Adds a dedicated API endpoint that allows users to star and unstar any `GroupSearchView` they have access to (owned or organization-shared). Starred views appear in the user's ordered list of views with position management.

## Files to Create

### 1. Endpoint: `src/sentry/issues/endpoints/organization_group_search_view_starred.py`

New endpoint class `OrganizationGroupSearchViewStarredEndpoint` with:

- **`PUT`** — Star a view (with optional `position` parameter)
  - Validate view exists in organization
  - Validate access: owned by user OR `visibility=organization`
  - If already starred: return existing starred view data (idempotent)
  - If position specified: clamp to bounds, shift subsequent positions up, insert
  - If no position: append at end
  - Use `transaction.atomic(using=router.db_for_write(GroupSearchViewStarred))`
  - Return `200` with serialized starred view

- **`DELETE`** — Unstar a view
  - Validate view exists in organization
  - If not starred: return `204` (idempotent)
  - If starred: delete starred entry, shift subsequent positions down
  - Return `204`

**Reference patterns**:

- Visit endpoint for structure: `src/sentry/issues/endpoints/organization_group_search_view_visit.py`
- Details endpoint for unstar + position logic: `src/sentry/issues/endpoints/organization_group_search_view_details.py:47-60`
- Starred order endpoint for transaction pattern: `src/sentry/issues/endpoints/organization_group_search_view_starred_order.py:62-72`

### 2. Tests: `tests/sentry/issues/endpoints/test_organization_group_search_view_starred.py`

Test cases covering:

**Star (PUT)**:

- Star a view successfully (appended at end)
- Star a view at specific position (shifts others)
- Star an already-starred view (idempotent, returns existing data)
- Star own view
- Star an organization-shared view
- Reject starring a private view owned by another user (403)
- Reject starring a nonexistent view (404)
- Reject starring a view from another organization (404)
- Position clamping (position > list size)
- Feature flag disabled (400)

**Unstar (DELETE)**:

- Unstar a starred view (positions adjusted)
- Unstar a non-starred view (idempotent, 204)
- Unstar a nonexistent view (404)
- Position decrement verification after unstar
- Feature flag disabled (400)

**Concurrency (TransactionTestCase)**:

- IntegrityError handling on concurrent position conflict

## Files to Modify

### 3. URL routing: `src/sentry/api/urls.py`

Add route (near line 1797, after the existing view routes):

```python
re_path(
    r"^(?P<organization_id_or_slug>[^\/]+)/group-search-views/(?P<view_id>[^\/]+)/starred/$",
    OrganizationGroupSearchViewStarredEndpoint.as_view(),
    name="sentry-api-0-organization-group-search-view-starred",
),
```

Add import at the top of the file alongside existing GroupSearchView imports.

### 4. Endpoints init: `src/sentry/issues/endpoints/__init__.py`

Add import for the new endpoint (line 57 in `__all__` already references it but import is missing):

```python
from .organization_group_search_view_starred import OrganizationGroupSearchViewStarredEndpoint
```

## Key Implementation Details

### Permission Class

```python
class MemberPermission(OrganizationPermission):
    scope_map = {
        "PUT": ["member:read", "member:write"],
        "DELETE": ["member:read", "member:write"],
    }
```

### Feature Flag

Gate behind `organizations:issue-view-sharing` — consistent with `OrganizationGroupSearchViewStarredOrderEndpoint`.

### Publish Status

```python
publish_status = {
    "PUT": ApiPublishStatus.EXPERIMENTAL,
    "DELETE": ApiPublishStatus.EXPERIMENTAL,
}
```

### Position Management (Star)

```python
# Inside transaction.atomic:
# 1. Get current max position
current_count = GroupSearchViewStarred.objects.filter(
    organization=organization, user_id=request.user.id
).count()

# 2. Determine insert position
if position is None:
    insert_position = current_count
else:
    insert_position = min(position, current_count)

# 3. Shift existing positions at or after insert point
GroupSearchViewStarred.objects.filter(
    organization=organization,
    user_id=request.user.id,
    position__gte=insert_position,
).update(position=F("position") + 1)

# 4. Create starred entry
starred = GroupSearchViewStarred.objects.create(
    organization=organization,
    user_id=request.user.id,
    group_search_view=view,
    position=insert_position,
)
```

### Position Management (Unstar)

```python
# Mirrors existing pattern in organization_group_search_view_details.py:47-60
deleted_position = starred_view.position
starred_view.delete()

GroupSearchViewStarred.objects.filter(
    organization=organization,
    user_id=request.user.id,
    position__gt=deleted_position,
).update(position=F("position") - 1)
```

### Access Validation

```python
# View must be in the organization
view = GroupSearchView.objects.get(id=view_id, organization=organization)

# View must be accessible to user
if view.user_id != request.user.id and view.visibility != GroupSearchViewVisibility.ORGANIZATION:
    return Response(
        status=status.HTTP_403_FORBIDDEN,
        data={"detail": "You do not have access to this view"},
    )
```

## Running Tests

```bash
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_starred.py -v
```

## Verification Checklist

- [ ] `PUT` returns 200 with starred view data (including position)
- [ ] `PUT` is idempotent (re-starring returns same data)
- [ ] `PUT` with position inserts correctly and shifts others
- [ ] `PUT` without position appends at end
- [ ] `DELETE` returns 204
- [ ] `DELETE` is idempotent (unstarring non-starred returns 204)
- [ ] `DELETE` decrements positions of subsequent starred views
- [ ] Access control rejects private views from other users
- [ ] Feature flag gating works
- [ ] All operations scoped to organization (IDOR prevention)
