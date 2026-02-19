# Quickstart: Star and Unstar Shared Issue Views

**Feature Branch**: `001-star-unstar-views`
**Date**: 2026-02-19

## Overview

This feature adds a dedicated API endpoint for starring and unstarring issue views (`GroupSearchView`). It reuses the existing `GroupSearchViewStarred` model — no new models or migrations are required.

## Files to Create

1. **`src/sentry/issues/endpoints/organization_group_search_view_star.py`** — New endpoint
2. **`tests/sentry/issues/endpoints/test_organization_group_search_view_star.py`** — Tests

## Files to Modify

1. **`src/sentry/issues/endpoints/__init__.py`** — Add import and `__all__` entry
2. **`src/sentry/api/urls.py`** — Add URL route

## Implementation Steps

### Step 1: Create the Endpoint

Create `src/sentry/issues/endpoints/organization_group_search_view_star.py`:

**Template** (mirrors `organization_group_search_view_visit.py`):

```python
from django.db import IntegrityError, router, transaction
from django.db.models import F, Max
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response

from sentry import features
from sentry.api.api_owners import ApiOwner
from sentry.api.api_publish_status import ApiPublishStatus
from sentry.api.base import region_silo_endpoint
from sentry.api.bases.organization import OrganizationEndpoint, OrganizationPermission
from sentry.api.serializers import serialize
from sentry.api.serializers.models.groupsearchview import GroupSearchViewStarredSerializer
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

    def put(self, request: Request, organization: Organization, view_id: str) -> Response:
        """Star an issue view for the current user."""
        if not features.has("organizations:issue-view-sharing", organization, actor=request.user):
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Validate the view exists in this org
        try:
            view = GroupSearchView.objects.get(id=view_id, organization=organization)
        except GroupSearchView.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Access check: user owns view OR view is org-visible
        if view.user_id != request.user.id and view.visibility != GroupSearchViewVisibility.ORGANIZATION:
            return Response(
                {"detail": "You do not have access to this view"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Idempotent: if already starred, return current state
        existing = GroupSearchViewStarred.objects.filter(
            organization=organization,
            user_id=request.user.id,
            group_search_view=view,
        ).first()
        if existing:
            return Response(
                serialize(existing, request.user, serializer=GroupSearchViewStarredSerializer(organization=organization)),
                status=status.HTTP_200_OK,
            )

        # Parse optional position
        serializer = StarGroupSearchViewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        requested_position = serializer.validated_data.get("position")

        try:
            with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
                # Get current max position
                max_pos = GroupSearchViewStarred.objects.filter(
                    organization=organization, user_id=request.user.id
                ).aggregate(max_pos=Max("position"))["max_pos"]

                next_position = (max_pos + 1) if max_pos is not None else 0

                if requested_position is None or requested_position >= next_position:
                    # Append to end
                    insert_position = next_position
                else:
                    # Shift existing views at >= requested_position
                    insert_position = requested_position
                    GroupSearchViewStarred.objects.filter(
                        organization=organization,
                        user_id=request.user.id,
                        position__gte=insert_position,
                    ).update(position=F("position") + 1)

                starred = GroupSearchViewStarred.objects.create(
                    organization=organization,
                    user_id=request.user.id,
                    group_search_view=view,
                    position=insert_position,
                )
        except IntegrityError:
            return Response(
                {"detail": "Failed to star view due to a conflict"},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            serialize(starred, request.user, serializer=GroupSearchViewStarredSerializer(organization=organization)),
            status=status.HTTP_200_OK,
        )

    def delete(self, request: Request, organization: Organization, view_id: str) -> Response:
        """Unstar an issue view for the current user."""
        if not features.has("organizations:issue-view-sharing", organization, actor=request.user):
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Validate the view exists in this org
        try:
            view = GroupSearchView.objects.get(id=view_id, organization=organization)
        except GroupSearchView.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Idempotent: if not starred, return 204
        try:
            starred = GroupSearchViewStarred.objects.get(
                organization=organization,
                user_id=request.user.id,
                group_search_view=view,
            )
        except GroupSearchViewStarred.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)

        deleted_position = starred.position

        with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
            starred.delete()
            # Decrement positions above the deleted one
            GroupSearchViewStarred.objects.filter(
                organization=organization,
                user_id=request.user.id,
                position__gt=deleted_position,
            ).update(position=F("position") - 1)

        return Response(status=status.HTTP_204_NO_CONTENT)
```

### Step 2: Register the Endpoint

In `src/sentry/issues/endpoints/__init__.py`, add:

```python
from .organization_group_search_view_star import OrganizationGroupSearchViewStarredEndpoint
```

The `__all__` entry already exists at line 57 (stale forward reference) — no change needed there.

### Step 3: Add URL Route

In `src/sentry/api/urls.py`, add after the existing `group-search-views` routes (near line 1797):

```python
re_path(
    r"^(?P<organization_id_or_slug>[^\/]+)/group-search-views/(?P<view_id>[^\/]+)/star/$",
    OrganizationGroupSearchViewStarredEndpoint.as_view(),
    name="sentry-api-0-organization-group-search-view-star",
),
```

Also add the import at the top of urls.py alongside other GroupSearchView imports.

### Step 4: Write Tests

Create `tests/sentry/issues/endpoints/test_organization_group_search_view_star.py`:

Test cases to cover:

1. **Star a shared view** — PUT returns 200 with starred view data
2. **Star at default position** — appends to end (position = N)
3. **Star at specific position** — inserts and shifts others
4. **Star at position > list size** — clamps to end
5. **Idempotent star** — starring already-starred view returns 200, no change
6. **Star own view** — user can star their own view
7. **Star inaccessible view** — returns 403 for `visibility=owner` view not owned by user
8. **Star non-existent view** — returns 404
9. **Unstar a starred view** — DELETE returns 204, positions gap-filled
10. **Idempotent unstar** — unstarring non-starred view returns 204
11. **Unstar non-existent view** — returns 404
12. **Feature flag disabled** — returns 404

## Running Tests

```bash
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_star.py -v
```

## Key References

| File                                                                                 | Purpose                   |
| ------------------------------------------------------------------------------------ | ------------------------- |
| `src/sentry/models/groupsearchviewstarred.py`                                        | Model (existing)          |
| `src/sentry/issues/endpoints/organization_group_search_view_visit.py`                | Template endpoint         |
| `src/sentry/issues/endpoints/organization_group_search_view_details.py`              | Position gap-fill pattern |
| `src/sentry/issues/endpoints/organization_group_search_view_starred_order.py`        | Access validation pattern |
| `src/sentry/api/serializers/models/groupsearchview.py`                               | Output serializer         |
| `tests/sentry/issues/endpoints/test_organization_group_search_view_starred_order.py` | Test pattern              |
