# Quickstart: Implement Star/Unstar Views

**Feature**: 001-star-unstar-views  
**Branch**: `001-star-unstar-views`

This guide walks through implementing the star/unstar endpoint from scratch. Follow the steps in order.

---

## Prerequisites

- Python 3.13, Django 5.1
- The `GroupSearchViewStarred` model already exists (`src/sentry/models/groupsearchviewstarred.py`)
- No migrations required — the schema is complete

---

## Step 1: Create the endpoint file

Create `src/sentry/issues/endpoints/organization_group_search_view_starred.py`.

The endpoint class is `OrganizationGroupSearchViewStarredEndpoint`. It handles:

- `PUT /{view_id}/star/` — star a view
- `DELETE /{view_id}/star/` — unstar a view

Reference implementation patterns:

- `organization_group_search_view_visit.py` — per-view sub-resource action structure
- `organization_group_search_view_details.py` — position decrement pattern for delete
- `organization_group_search_view_starred_order.py` — `transaction.atomic` + `IntegrityError` handling

### Key implementation details

**Star (`PUT`)**:

```python
# 1. Check feature flag
if not features.has("organizations:issue-view-sharing", organization, actor=request.user):
    return Response(status=status.HTTP_404_NOT_FOUND)

# 2. Resolve + validate the view (scope to org, check visibility)
try:
    view = GroupSearchView.objects.get(id=view_id, organization=organization)
except GroupSearchView.DoesNotExist:
    return Response(status=status.HTTP_404_NOT_FOUND)

if view.user_id != request.user.id and view.visibility != GroupSearchViewVisibility.ORGANIZATION:
    return Response(status=status.HTTP_404_NOT_FOUND)  # do not reveal existence

# 3. Parse optional position from request body
serializer = StarViewSerializer(data=request.data)
if not serializer.is_valid():
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
position = serializer.validated_data.get("position")  # None means append

# 4. Idempotency check
existing = GroupSearchViewStarred.objects.filter(
    organization=organization, user_id=request.user.id, group_search_view=view
).first()
if existing:
    return Response(serialize(existing, request.user, serializer=...), status=status.HTTP_200_OK)

# 5. Atomic star with position management
with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
    current_count = GroupSearchViewStarred.objects.filter(
        organization=organization, user_id=request.user.id
    ).count()
    if position is None or position >= current_count:
        position = current_count
    else:
        GroupSearchViewStarred.objects.filter(
            organization=organization,
            user_id=request.user.id,
            position__gte=position,
        ).update(position=F("position") + 1)
    starred = GroupSearchViewStarred.objects.create(
        organization=organization,
        user_id=request.user.id,
        group_search_view=view,
        position=position,
    )

return Response(serialize(starred, request.user, serializer=...), status=status.HTTP_200_OK)
```

**Unstar (`DELETE`)**:

```python
# 1. Check feature flag (same as above)

# 2. Resolve + validate the view (same as above)

# 3. Idempotency check + delete
try:
    starred = GroupSearchViewStarred.objects.get(
        organization=organization, user_id=request.user.id, group_search_view=view
    )
except GroupSearchViewStarred.DoesNotExist:
    return Response(status=status.HTTP_204_NO_CONTENT)  # idempotent

with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
    deleted_position = starred.position
    starred.delete()
    GroupSearchViewStarred.objects.filter(
        organization=organization,
        user_id=request.user.id,
        position__gt=deleted_position,
    ).update(position=F("position") - 1)

return Response(status=status.HTTP_204_NO_CONTENT)
```

---

## Step 2: Register the endpoint in `__init__.py`

File: `src/sentry/issues/endpoints/__init__.py`

Add the import (line 19 area, alphabetically with other GSV imports):

```python
from .organization_group_search_view_starred import OrganizationGroupSearchViewStarredEndpoint
```

The `__all__` entry for `"OrganizationGroupSearchViewStarredEndpoint"` already exists at line 57.

---

## Step 3: Register the URL in `src/sentry/api/urls.py`

Add after the existing `/visit/` URL pattern (around line 1791):

```python
re_path(
    r"^(?P<organization_id_or_slug>[^\/]+)/group-search-views/(?P<view_id>[^\/]+)/star/$",
    OrganizationGroupSearchViewStarredEndpoint.as_view(),
    name="sentry-api-0-organization-group-search-view-starred",
),
```

Also add the import near the other `GroupSearchView` imports (around line 203):

```python
from sentry.issues.endpoints.organization_group_search_view_starred import (
    OrganizationGroupSearchViewStarredEndpoint,
)
```

---

## Step 4: Write tests

Test file: `tests/sentry/issues/endpoints/test_organization_group_search_view_starred.py`

Use `BaseGSVTestCase` from `tests/sentry/issues/endpoints/test_organization_group_search_views.py` as the base class.

### Test cases to cover

**Star (PUT)**:

1. `test_star_view_success` — Star an owned view; verify `GroupSearchViewStarred` row exists at correct position
2. `test_star_shared_view_success` — Star an org-visibility view; verify success
3. `test_star_view_idempotent` — Star already-starred view; verify 200 and no duplicate row
4. `test_star_view_appends_to_end_by_default` — No position → appended at `len(starred_views)`
5. `test_star_view_at_specific_position` — Position=1 with 3 existing views → view at pos 1, old pos 1 shifts to 2, old pos 2 shifts to 3
6. `test_star_view_position_out_of_range_appends` — Position > count → clamp to end
7. `test_star_view_from_another_org_returns_404` — Cross-org view → 404
8. `test_star_view_owned_by_other_user_with_owner_visibility_returns_404` — Non-shared, non-owned → 404
9. `test_star_without_feature_flag` — Missing `issue-view-sharing` flag → 404

**Unstar (DELETE)**:

1. `test_unstar_view_success` — Verify row deleted, succeeding positions decremented
2. `test_unstar_view_idempotent` — Unstar non-starred view → 204
3. `test_unstar_view_decrements_positions` — Delete middle entry; verify shift
4. `test_unstar_view_from_another_org_returns_404`
5. `test_unstar_without_feature_flag` → 404

---

## Step 5: Verify

```bash
# Run the new test file
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_starred.py -v

# Run the full GSV test suite to catch regressions
pytest tests/sentry/issues/endpoints/test_organization_group_search_views.py -v
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_details.py -v
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_starred_order.py -v
```

---

## File Checklist

| File                                                                           | Action                   |
| ------------------------------------------------------------------------------ | ------------------------ |
| `src/sentry/issues/endpoints/organization_group_search_view_starred.py`        | CREATE                   |
| `src/sentry/issues/endpoints/__init__.py`                                      | ADD import               |
| `src/sentry/api/urls.py`                                                       | ADD URL pattern + import |
| `tests/sentry/issues/endpoints/test_organization_group_search_view_starred.py` | CREATE                   |
