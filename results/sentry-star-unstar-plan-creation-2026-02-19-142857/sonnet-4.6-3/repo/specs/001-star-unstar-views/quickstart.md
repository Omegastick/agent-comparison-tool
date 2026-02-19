# Quickstart: Star and Unstar Shared Issue Views

**Feature**: `001-star-unstar-views`
**Phase**: 1 — Design
**Date**: 2026-02-19

---

## What We're Building

A single new API endpoint exposing `POST` and `DELETE` on the sub-resource URL:

```
/api/0/organizations/{slug}/group-search-views/{view_id}/star/
```

This is the only code change. The model, migrations, serializer, and reorder endpoint already exist.

---

## Files to Create

| File                                                                        | Purpose            |
| --------------------------------------------------------------------------- | ------------------ |
| `src/sentry/issues/endpoints/organization_group_search_view_star.py`        | New endpoint class |
| `tests/sentry/issues/endpoints/test_organization_group_search_view_star.py` | Test suite         |

## Files to Modify

| File                                      | Change                              |
| ----------------------------------------- | ----------------------------------- |
| `src/sentry/api/urls.py`                  | Add URL route for the new endpoint  |
| `src/sentry/issues/endpoints/__init__.py` | Export new endpoint (if applicable) |

---

## Step 1: Create the Endpoint

**File**: `src/sentry/issues/endpoints/organization_group_search_view_star.py`

```python
from django.db import IntegrityError, router, transaction
from django.db.models import F
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
        "POST": ["member:read", "member:write"],
        "DELETE": ["member:read", "member:write"],
    }


class StarViewSerializer(serializers.Serializer):
    position = serializers.IntegerField(required=False, min_value=0, allow_null=True)


@region_silo_endpoint
class OrganizationGroupSearchViewStarEndpoint(OrganizationEndpoint):
    publish_status = {
        "POST": ApiPublishStatus.EXPERIMENTAL,
        "DELETE": ApiPublishStatus.EXPERIMENTAL,
    }
    owner = ApiOwner.ISSUES
    permission_classes = (MemberPermission,)

    def _get_view(self, organization: Organization, view_id: str, user_id: int) -> GroupSearchView:
        """Fetch a view the user has access to (own or org-shared). Raises DoesNotExist if absent."""
        return GroupSearchView.objects.get(
            id=view_id,
            organization=organization,
        )

    def _user_can_access_view(self, view: GroupSearchView, user_id: int) -> bool:
        return (
            view.user_id == user_id
            or view.visibility == GroupSearchViewVisibility.ORGANIZATION
        )

    def post(self, request: Request, organization: Organization, view_id: str) -> Response:
        """Star a view for the current user. Idempotent."""
        if not features.has("organizations:issue-view-sharing", organization, actor=request.user):
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            view = self._get_view(organization, view_id, request.user.id)
        except GroupSearchView.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not self._user_can_access_view(view, request.user.id):
            return Response(
                status=status.HTTP_403_FORBIDDEN,
                data={"detail": "You do not have access to this view"},
            )

        serializer = StarViewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        position = serializer.validated_data.get("position")
        has_global_views = features.has("organizations:global-views", organization)

        try:
            with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
                # Idempotency check: already starred?
                existing = GroupSearchViewStarred.objects.filter(
                    organization=organization,
                    user_id=request.user.id,
                    group_search_view=view,
                ).first()
                if existing is not None:
                    return Response(
                        serialize(
                            existing,
                            request.user,
                            serializer=GroupSearchViewStarredSerializer(
                                has_global_views=has_global_views,
                                organization=organization,
                            ),
                        ),
                        status=status.HTTP_200_OK,
                    )

                # Determine insert position
                count = GroupSearchViewStarred.objects.filter(
                    organization=organization,
                    user_id=request.user.id,
                ).count()
                insert_position = min(position, count) if position is not None else count

                # Shift existing views at >= insert_position upward
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
        except IntegrityError as e:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"detail": str(e.args[0])},
            )

        return Response(
            serialize(
                starred,
                request.user,
                serializer=GroupSearchViewStarredSerializer(
                    has_global_views=has_global_views,
                    organization=organization,
                ),
            ),
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request: Request, organization: Organization, view_id: str) -> Response:
        """Unstar a view for the current user. Idempotent."""
        if not features.has("organizations:issue-view-sharing", organization, actor=request.user):
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            view = self._get_view(organization, view_id, request.user.id)
        except GroupSearchView.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            starred = GroupSearchViewStarred.objects.get(
                organization=organization,
                user_id=request.user.id,
                group_search_view=view,
            )
        except GroupSearchViewStarred.DoesNotExist:
            # Idempotent — not starred is same as unstarred
            return Response(status=status.HTTP_204_NO_CONTENT)

        deleted_position = starred.position
        with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
            starred.delete()
            # Shift views with higher positions down
            GroupSearchViewStarred.objects.filter(
                organization=organization,
                user_id=request.user.id,
                position__gt=deleted_position,
            ).update(position=F("position") - 1)

        return Response(status=status.HTTP_204_NO_CONTENT)
```

---

## Step 2: Register the URL

**File**: `src/sentry/api/urls.py`

Add after the existing `/visit/` route (around line 1793):

```python
re_path(
    r"^(?P<organization_id_or_slug>[^\/]+)/group-search-views/(?P<view_id>[^\/]+)/star/$",
    OrganizationGroupSearchViewStarEndpoint.as_view(),
    name="sentry-api-0-organization-group-search-view-star",
),
```

Also add the import at the top of `urls.py` near the other group-search-view imports:

```python
from sentry.issues.endpoints.organization_group_search_view_star import (
    OrganizationGroupSearchViewStarEndpoint,
)
```

---

## Step 3: Write Tests

**File**: `tests/sentry/issues/endpoints/test_organization_group_search_view_star.py`

Test class structure (mirrors `test_organization_group_search_view_visit.py`):

```python
from sentry.testutils.cases import APITestCase

class OrganizationGroupSearchViewStarEndpointTest(APITestCase):
    endpoint = "sentry-api-0-organization-group-search-view-star"

    def setUp(self):
        super().setUp()
        self.login_as(self.user)
        # create a view
        self.view = self.create_group_search_view(
            name="Test View",
            organization=self.organization,
            user_id=self.user.id,
        )

    # --- POST (star) ---

    def test_star_view_no_position(self):
        """Stars a view, appends to end (position=0 since no existing starred views)."""
        response = self.get_success_response(
            self.organization.slug, self.view.id,
            method="post",
            status_code=201,
        )
        assert response.data["id"] == str(self.view.id)
        assert response.data["position"] == 0

    def test_star_view_at_position(self):
        """Stars a view at position 0 when user has existing starred views; others shift."""
        # star another view first
        other_view = self.create_group_search_view(...)
        self.get_success_response(self.organization.slug, other_view.id, method="post", status_code=201)

        response = self.get_success_response(
            self.organization.slug, self.view.id,
            method="post",
            position=0,
            status_code=201,
        )
        assert response.data["position"] == 0
        # verify other_view is now at position 1

    def test_star_idempotent(self):
        """Starring an already-starred view returns 200 with no changes."""
        self.get_success_response(self.organization.slug, self.view.id, method="post", status_code=201)
        response = self.get_success_response(self.organization.slug, self.view.id, method="post", status_code=200)
        assert response.data["position"] == 0

    def test_star_out_of_bounds_position_clamps(self):
        """Position larger than list size is clamped to end."""
        response = self.get_success_response(
            self.organization.slug, self.view.id,
            method="post",
            position=9999,
            status_code=201,
        )
        assert response.data["position"] == 0  # only view, so end = 0

    def test_star_view_not_found(self):
        """Returns 404 for unknown view_id."""
        self.get_error_response(self.organization.slug, 999999, method="post", status_code=404)

    def test_star_cross_org_view_rejected(self):
        """Cannot star a view belonging to a different organization."""
        other_org = self.create_organization()
        other_view = self.create_group_search_view(organization=other_org, ...)
        self.get_error_response(self.organization.slug, other_view.id, method="post", status_code=404)

    def test_star_org_shared_view(self):
        """User can star a view with visibility=organization even if they don't own it."""
        shared_view = self.create_group_search_view(
            organization=self.organization,
            user_id=self.create_user().id,
            visibility="organization",
        )
        response = self.get_success_response(
            self.organization.slug, shared_view.id, method="post", status_code=201
        )
        assert response.data["id"] == str(shared_view.id)

    def test_star_private_view_owned_by_other_user_rejected(self):
        """Cannot star a private view owned by another user."""
        other_user = self.create_user()
        private_view = self.create_group_search_view(
            organization=self.organization,
            user_id=other_user.id,
            visibility="owner",
        )
        self.get_error_response(self.organization.slug, private_view.id, method="post", status_code=403)

    def test_star_requires_feature_flag(self):
        """Returns 404 if issue-view-sharing flag is disabled."""
        with self.feature({"organizations:issue-view-sharing": False}):
            self.get_error_response(self.organization.slug, self.view.id, method="post", status_code=404)

    def test_star_negative_position_rejected(self):
        """Returns 400 for position < 0."""
        self.get_error_response(
            self.organization.slug, self.view.id,
            method="post",
            position=-1,
            status_code=400,
        )

    # --- DELETE (unstar) ---

    def test_unstar_view(self):
        """Unstars a previously starred view."""
        self.get_success_response(self.organization.slug, self.view.id, method="post", status_code=201)
        self.get_success_response(self.organization.slug, self.view.id, method="delete", status_code=204)
        assert not GroupSearchViewStarred.objects.filter(
            user_id=self.user.id, group_search_view=self.view
        ).exists()

    def test_unstar_shifts_positions(self):
        """Unstaring a view at position 0 shifts all higher views down."""
        view_b = self.create_group_search_view(...)
        self.get_success_response(self.organization.slug, self.view.id, method="post", status_code=201)
        self.get_success_response(self.organization.slug, view_b.id, method="post", status_code=201)
        # view at position 0, view_b at position 1
        self.get_success_response(self.organization.slug, self.view.id, method="delete", status_code=204)
        starred_b = GroupSearchViewStarred.objects.get(group_search_view=view_b, user_id=self.user.id)
        assert starred_b.position == 0

    def test_unstar_idempotent(self):
        """Unstaring a view not in the starred list returns 204."""
        self.get_success_response(self.organization.slug, self.view.id, method="delete", status_code=204)

    def test_unstar_view_not_found(self):
        """Returns 404 for unknown view_id."""
        self.get_error_response(self.organization.slug, 999999, method="delete", status_code=404)

    def test_unstar_requires_feature_flag(self):
        """Returns 404 if issue-view-sharing flag is disabled."""
        with self.feature({"organizations:issue-view-sharing": False}):
            self.get_error_response(self.organization.slug, self.view.id, method="delete", status_code=404)
```

---

## Key Implementation Notes

### Serializer reuse

`GroupSearchViewStarredSerializer` (in `src/sentry/api/serializers/models/groupsearchview.py`) already produces the correct response shape. Pass it `has_global_views=` and `organization=` kwargs.

### Feature flag

Always check `organizations:issue-view-sharing` (NOT `issue-stream-custom-views`) — this is the flag used by the reorder endpoint and is the correct gate for the sharing feature set.

### Transaction wrapping

Wrap the shift + create in `transaction.atomic(using=router.db_for_write(GroupSearchViewStarred))`. The deferred unique constraint allows the shift UPDATE and the INSERT to coexist in the same transaction without constraint violations.

### No new migrations

The `sentry_groupsearchviewstarred` table already exists. No schema changes needed.

### Test factory

Check whether `self.create_group_search_view()` exists in `sentry.testutils.factories`. If not, use `GroupSearchView.objects.create()` only within test setup (acceptable in fixture-style setUp but not within test body per convention). Verify the exact factory method name before implementing.

---

## Verification Checklist

- [ ] `POST /star/` creates a `GroupSearchViewStarred` row and returns `201` with correct position
- [ ] `POST /star/` on already-starred view returns `200` without creating a duplicate
- [ ] `POST /star/` with `position=N` shifts existing rows correctly
- [ ] `POST /star/` with `position > count` clamps to append
- [ ] `POST /star/` with `position < 0` returns `400`
- [ ] `DELETE /star/` removes the row and returns `204`
- [ ] `DELETE /star/` shifts all higher-positioned rows down
- [ ] `DELETE /star/` on not-starred view returns `204` (idempotent)
- [ ] Both operations return `404` for unknown `view_id`
- [ ] Both operations return `404` when feature flag is off
- [ ] `POST /star/` returns `403` for private view owned by another user
- [ ] `POST /star/` succeeds for org-shared view owned by another user
- [ ] All tests use `APITestCase` factory methods — no direct `Model.objects.create()` in test bodies
