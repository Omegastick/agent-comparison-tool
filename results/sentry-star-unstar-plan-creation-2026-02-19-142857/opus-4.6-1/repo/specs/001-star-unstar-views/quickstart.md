# Quickstart: Star and Unstar Shared Issue Views

**Feature Branch**: `001-star-unstar-views`
**Date**: 2026-02-19

## What to Build

A new API endpoint `OrganizationGroupSearchViewStarredEndpoint` that allows users to star and unstar issue views with position management. This endpoint fulfills the forward reference already in `src/sentry/issues/endpoints/__init__.py:57`.

## Files to Create

### 1. Endpoint: `src/sentry/issues/endpoints/organization_group_search_view_starred.py`

```python
from django.db import router, transaction
from django.db.models import F
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response

from sentry import features
from sentry.api.api_owners import ApiOwner
from sentry.api.api_publish_status import ApiPublishStatus
from sentry.api.base import region_silo_endpoint
from sentry.api.bases.organization import OrganizationEndpoint, OrganizationPermission
from sentry.models.groupsearchview import GroupSearchView, GroupSearchViewVisibility
from sentry.models.groupsearchviewstarred import GroupSearchViewStarred
from sentry.models.organization import Organization


class MemberPermission(OrganizationPermission):
    scope_map = {
        "PUT": ["member:read", "member:write"],
        "DELETE": ["member:read", "member:write"],
    }


class StarGroupSearchViewSerializer(serializers.Serializer):
    position = serializers.IntegerField(required=False, min_value=0)


@region_silo_endpoint
class OrganizationGroupSearchViewStarredEndpoint(OrganizationEndpoint):
    publish_status = {
        "PUT": ApiPublishStatus.EXPERIMENTAL,
        "DELETE": ApiPublishStatus.EXPERIMENTAL,
    }
    owner = ApiOwner.ISSUES
    permission_classes = (MemberPermission,)

    def _get_view(self, organization, request, view_id):
        """
        Get a view that the user has access to (owned or organization-visible).
        Returns the view or None.
        """
        try:
            view = GroupSearchView.objects.get(id=view_id, organization=organization)
        except GroupSearchView.DoesNotExist:
            return None

        # Check access: user owns the view OR view has organization visibility
        if view.user_id != request.user.id and view.visibility != GroupSearchViewVisibility.ORGANIZATION:
            return None

        return view

    def put(self, request: Request, organization: Organization, view_id: str) -> Response:
        """Star a group search view for the current user."""
        if not features.has("organizations:issue-view-sharing", organization, actor=request.user):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        view = self._get_view(organization, request, view_id)
        if view is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = StarGroupSearchViewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        requested_position = serializer.validated_data.get("position")

        with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
            # Check if already starred
            existing = GroupSearchViewStarred.objects.filter(
                organization=organization,
                user_id=request.user.id,
                group_search_view=view,
            ).first()

            if existing is not None:
                # Already starred — idempotent success
                return Response(status=status.HTTP_204_NO_CONTENT)

            # Determine position
            current_count = GroupSearchViewStarred.objects.filter(
                organization=organization,
                user_id=request.user.id,
            ).count()

            if requested_position is None:
                position = current_count  # Append to end
            else:
                position = min(requested_position, current_count)  # Clamp
                # Shift existing views at position and after
                GroupSearchViewStarred.objects.filter(
                    organization=organization,
                    user_id=request.user.id,
                    position__gte=position,
                ).update(position=F("position") + 1)

            GroupSearchViewStarred.objects.create(
                organization=organization,
                user_id=request.user.id,
                group_search_view=view,
                position=position,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request: Request, organization: Organization, view_id: str) -> Response:
        """Unstar a group search view for the current user."""
        if not features.has("organizations:issue-view-sharing", organization, actor=request.user):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        view = self._get_view(organization, request, view_id)
        if view is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
            try:
                starred = GroupSearchViewStarred.objects.get(
                    organization=organization,
                    user_id=request.user.id,
                    group_search_view=view,
                )
            except GroupSearchViewStarred.DoesNotExist:
                # Not starred — idempotent success
                return Response(status=status.HTTP_204_NO_CONTENT)

            deleted_position = starred.position
            starred.delete()

            # Close the gap
            GroupSearchViewStarred.objects.filter(
                organization=organization,
                user_id=request.user.id,
                position__gt=deleted_position,
            ).update(position=F("position") - 1)

        return Response(status=status.HTTP_204_NO_CONTENT)
```

### 2. Tests: `tests/sentry/issues/endpoints/test_organization_group_search_view_starred.py`

Test class structure (see `test_organization_group_search_view_starred_order.py` for pattern):

```python
class OrganizationGroupSearchViewStarredEndpointTest(APITestCase):
    endpoint = "sentry-api-0-organization-group-search-view-starred"

    # PUT tests:
    # - test_star_own_view
    # - test_star_shared_view
    # - test_star_already_starred_is_idempotent
    # - test_star_at_specific_position
    # - test_star_at_position_shifts_existing
    # - test_star_at_position_beyond_list_clamps
    # - test_star_without_position_appends
    # - test_star_nonexistent_view_returns_404
    # - test_star_inaccessible_view_returns_404
    # - test_star_cross_org_view_returns_404
    # - test_star_without_feature_flag_returns_400

    # DELETE tests:
    # - test_unstar_view
    # - test_unstar_not_starred_is_idempotent
    # - test_unstar_closes_position_gap
    # - test_unstar_nonexistent_view_returns_404
    # - test_unstar_without_feature_flag_returns_400
```

## Files to Modify

### 3. Update `src/sentry/issues/endpoints/__init__.py`

Add import (after line 19):

```python
from .organization_group_search_view_starred import OrganizationGroupSearchViewStarredEndpoint
```

(The `__all__` entry at line 57 already exists — no change needed there.)

### 4. Update `src/sentry/api/urls.py`

Add import to the issues endpoints import block (line 186-188 area) — the endpoint is imported via `__init__.py`, so add `OrganizationGroupSearchViewStarredEndpoint` to the existing import from `sentry.issues.endpoints`.

Add URL route after line 1791 (after the visit endpoint):

```python
re_path(
    r"^(?P<organization_id_or_slug>[^\/]+)/group-search-views/(?P<view_id>[^\/]+)/starred/$",
    OrganizationGroupSearchViewStarredEndpoint.as_view(),
    name="sentry-api-0-organization-group-search-view-starred",
),
```

## Key Patterns to Follow

| Pattern                         | Reference File                                         | Line  |
| ------------------------------- | ------------------------------------------------------ | ----- |
| MemberPermission class          | `organization_group_search_view_starred_order.py`      | 16-19 |
| Feature flag check              | `organization_group_search_view_starred_order.py`      | 50-51 |
| View access validation          | `organization_group_search_view_starred_order.py`      | 33-36 |
| Position gap closing on delete  | `organization_group_search_view_details.py`            | 46-63 |
| Atomic transaction for writes   | `organization_group_search_view_starred_order.py`      | 63    |
| Test setup with views + starred | `test_organization_group_search_view_starred_order.py` | 13-69 |

## Verification

Run tests:

```bash
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_starred.py -v
```

Run related tests to verify no regressions:

```bash
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_starred_order.py -v
pytest tests/sentry/issues/endpoints/test_organization_group_search_views.py -v
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_details.py -v
```
