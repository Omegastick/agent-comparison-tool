# Developer Quickstart: Star and Unstar Shared Issue Views

**Feature**: 001-star-unstar-views  
**Date**: 2026-02-19  
**For**: Developers implementing this feature

## Overview

This guide provides a step-by-step implementation roadmap for the star/unstar feature. Follow this guide sequentially to implement, test, and deploy the feature.

**Estimated Implementation Time**: 4-6 hours

**Prerequisites**:

- Sentry development environment set up
- Familiarity with Django and Django REST Framework
- Understanding of Sentry's silo architecture
- Access to `organizations:issue-view-sharing` feature flag

---

## Quick Reference

**What You're Building**: Two new API endpoints for starring and unstarring GroupSearchView objects.

**Models**: Reusing existing `GroupSearchViewStarred` model (no changes needed)

**Files to Create**:

- `src/sentry/issues/endpoints/organization_group_search_view_star.py` - New endpoint
- `tests/sentry/issues/endpoints/test_organization_group_search_view_star.py` - New tests

**Files to Modify**:

- `src/sentry/api/urls.py` - Add new route

**No Changes Required**:

- Models (reusing existing)
- Serializers (using standard patterns)
- Migrations (models already exist)

---

## Step 1: Understand the Data Model (10 minutes)

**Read**: `data-model.md` in this directory

**Key Concepts**:

1. `GroupSearchViewStarred` is a join table with position management
2. Positions are 0-indexed and contiguous
3. Position shifting happens automatically on star/unstar
4. CASCADE deletes handle cleanup

**Verify Models Exist**:

```bash
# Check that models exist
ls -l src/sentry/models/groupsearchview*.py

# Expected output:
# src/sentry/models/groupsearchview.py
# src/sentry/models/groupsearchviewstarred.py
```

**Read Model Code**:

```bash
# Review the starred model and its manager
cat src/sentry/models/groupsearchviewstarred.py
```

**Key Takeaway**: You're NOT creating new models, just adding endpoints to interact with existing ones.

---

## Step 2: Review API Contracts (10 minutes)

**Read**: `contracts/README.md` in this directory

**Key Endpoints**:

1. `POST /organizations/{org}/group-search-views/{view_id}/star/`
   - Optional `position` in request body
   - Returns `204 No Content`
   - Idempotent

2. `DELETE /organizations/{org}/group-search-views/{view_id}/star/`
   - No request body
   - Returns `204 No Content`
   - Idempotent

**Request/Response Examples**:

```bash
# Star at end of list
curl -X POST \
  -H "Authorization: Bearer {token}" \
  https://sentry.io/api/0/organizations/sentry/group-search-views/42/star/

# Star at position 1
curl -X POST \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"position": 1}' \
  https://sentry.io/api/0/organizations/sentry/group-search-views/42/star/

# Unstar
curl -X DELETE \
  -H "Authorization: Bearer {token}" \
  https://sentry.io/api/0/organizations/sentry/group-search-views/42/star/
```

---

## Step 3: Study Existing Patterns (20 minutes)

**Objective**: Understand how similar endpoints are structured in Sentry.

### 3.1 Study Existing GroupSearchView Endpoints

```bash
# View existing endpoint structure
cat src/sentry/issues/endpoints/organization_group_search_views.py
cat src/sentry/issues/endpoints/organization_group_search_view_details.py
```

**What to Look For**:

- How `OrganizationEndpoint` is used
- How feature flags are checked
- How views are fetched with organization scoping
- How visibility is validated

### 3.2 Study Bookmark Patterns

```bash
# Study similar bookmark implementation
cat src/sentry/models/groupbookmark.py
cat src/sentry/models/projectbookmark.py
```

**What to Look For**:

- Simple create/delete patterns
- Idempotency handling (IntegrityError)
- CASCADE delete setup

### 3.3 Study Existing Tests

```bash
# Study test patterns
cat tests/sentry/issues/endpoints/test_organization_group_search_views.py
cat tests/sentry/issues/endpoints/test_organization_group_search_view_details.py
```

**What to Look For**:

- `APITestCase` setup
- `endpoint` and `method` attributes
- `get_success_response()` and `get_error_response()` helpers
- `@with_feature` decorator usage

---

## Step 4: Implement the Star Endpoint (60 minutes)

### 4.1 Create Endpoint File

**File**: `src/sentry/issues/endpoints/organization_group_search_view_star.py`

**Template**:

```python
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response

from django.db import IntegrityError, transaction
from django.db.models import F, Max

from sentry import features
from sentry.api.api_owners import ApiOwner
from sentry.api.api_publish_status import ApiPublishStatus
from sentry.api.base import region_silo_endpoint
from sentry.api.bases.organization import OrganizationEndpoint
from sentry.api.permissions import MemberPermission
from sentry.api.serializers.rest_framework import CamelSnakeSerializer
from sentry.db import router
from sentry.models.groupsearchview import GroupSearchView, GroupSearchViewVisibility
from sentry.models.groupsearchviewstarred import GroupSearchViewStarred


class StarViewSerializer(CamelSnakeSerializer):
    position = serializers.IntegerField(required=False, min_value=0)


@region_silo_endpoint
class OrganizationGroupSearchViewStarEndpoint(OrganizationEndpoint):
    publish_status = {
        "POST": ApiPublishStatus.EXPERIMENTAL,
        "DELETE": ApiPublishStatus.EXPERIMENTAL,
    }
    owner = ApiOwner.ISSUES
    permission_classes = (MemberPermission,)

    def post(self, request: Request, organization, view_id: str) -> Response:
        """Star a GroupSearchView"""
        # TODO: Implement star logic
        pass

    def delete(self, request: Request, organization, view_id: str) -> Response:
        """Unstar a GroupSearchView"""
        # TODO: Implement unstar logic
        pass
```

### 4.2 Implement POST (Star) Method

**Steps**:

1. Check feature flag
2. Validate and fetch the view with org scoping
3. Check visibility/access permissions
4. Validate position (if provided)
5. Calculate position (if not provided)
6. Atomic transaction: shift positions + create starred entry
7. Handle idempotency (get_or_create or IntegrityError)
8. Return 204 No Content

**Pseudocode**:

```python
def post(self, request: Request, organization, view_id: str) -> Response:
    # 1. Feature flag check
    if not features.has("organizations:issue-view-sharing", organization, actor=request.user):
        return Response({"detail": "Feature not enabled"}, status=400)

    # 2. Validate input
    serializer = StarViewSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    target_position = serializer.validated_data.get("position")

    # 3. Fetch view with org scoping
    try:
        view = GroupSearchView.objects.get(id=view_id, organization=organization)
    except GroupSearchView.DoesNotExist:
        return Response({"detail": "View not found"}, status=404)

    # 4. Check access based on visibility
    if view.visibility == GroupSearchViewVisibility.OWNER:
        if view.user_id != request.user.id:
            return Response({"detail": "Permission denied"}, status=403)

    # 5. Calculate position if not provided
    if target_position is None:
        max_pos = GroupSearchViewStarred.objects.filter(
            organization=organization,
            user_id=request.user.id,
        ).aggregate(Max("position"))["position__max"]
        target_position = (max_pos or -1) + 1
    else:
        # Clamp position to end if too large
        max_pos = GroupSearchViewStarred.objects.filter(
            organization=organization,
            user_id=request.user.id,
        ).aggregate(Max("position"))["position__max"]
        max_allowed = (max_pos or -1) + 1
        if target_position > max_allowed:
            target_position = max_allowed

    # 6. Atomic transaction
    try:
        with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
            # Check if already starred (idempotency)
            existing = GroupSearchViewStarred.objects.filter(
                organization=organization,
                user_id=request.user.id,
                group_search_view=view,
            ).first()

            if existing:
                # Already starred - idempotent, return success
                return Response(status=204)

            # Shift positions >= target
            GroupSearchViewStarred.objects.filter(
                organization=organization,
                user_id=request.user.id,
                position__gte=target_position,
            ).update(position=F("position") + 1)

            # Create starred entry
            GroupSearchViewStarred.objects.create(
                organization=organization,
                user_id=request.user.id,
                group_search_view=view,
                position=target_position,
            )
    except IntegrityError as e:
        return Response({"detail": "Position conflict. Please retry."}, status=400)

    return Response(status=204)
```

### 4.3 Implement DELETE (Unstar) Method

**Steps**:

1. Check feature flag
2. Fetch view with org scoping
3. Atomic transaction: delete starred entry + decrement positions
4. Handle idempotency (delete returns 0 rows is OK)
5. Return 204 No Content

**Pseudocode**:

```python
def delete(self, request: Request, organization, view_id: str) -> Response:
    # 1. Feature flag check
    if not features.has("organizations:issue-view-sharing", organization, actor=request.user):
        return Response({"detail": "Feature not enabled"}, status=400)

    # 2. Fetch view (ensure it exists in this org)
    try:
        view = GroupSearchView.objects.get(id=view_id, organization=organization)
    except GroupSearchView.DoesNotExist:
        return Response({"detail": "View not found"}, status=404)

    # 3. Atomic transaction
    with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
        # Get starred entry
        starred = GroupSearchViewStarred.objects.filter(
            organization=organization,
            user_id=request.user.id,
            group_search_view=view,
        ).first()

        if not starred:
            # Not starred - idempotent, return success
            return Response(status=204)

        deleted_position = starred.position
        starred.delete()

        # Decrement positions > deleted
        GroupSearchViewStarred.objects.filter(
            organization=organization,
            user_id=request.user.id,
            position__gt=deleted_position,
        ).update(position=F("position") - 1)

    return Response(status=204)
```

---

## Step 5: Add URL Route (5 minutes)

**File**: `src/sentry/api/urls.py`

**Find the GroupSearchView routes section**:

```bash
# Search for existing group-search-views routes
grep -n "group-search-views" src/sentry/api/urls.py
```

**Add new route after existing GroupSearchView routes**:

```python
re_path(
    r"^(?P<organization_id_or_slug>[^\/]+)/group-search-views/(?P<view_id>[^\/]+)/star/$",
    OrganizationGroupSearchViewStarEndpoint.as_view(),
    name="sentry-api-0-organization-group-search-view-star",
),
```

**Add import at top of file**:

```python
from sentry.issues.endpoints.organization_group_search_view_star import (
    OrganizationGroupSearchViewStarEndpoint,
)
```

---

## Step 6: Write Tests (90 minutes)

**File**: `tests/sentry/issues/endpoints/test_organization_group_search_view_star.py`

### 6.1 Test Template

```python
from sentry.models.groupsearchview import GroupSearchView, GroupSearchViewVisibility
from sentry.models.groupsearchviewstarred import GroupSearchViewStarred
from sentry.testutils.cases import APITestCase
from sentry.testutils.helpers.features import with_feature


class OrganizationGroupSearchViewStarEndpointTest(APITestCase):
    endpoint = "sentry-api-0-organization-group-search-view-star"

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
            user_id=self.user.id,
            query="is:unresolved assigned:me",
            visibility=GroupSearchViewVisibility.ORGANIZATION,
            position=1,
        )

    # Star tests
    @with_feature("organizations:issue-view-sharing")
    def test_star_view_append(self):
        """Test starring a view without position (append to end)"""
        pass

    @with_feature("organizations:issue-view-sharing")
    def test_star_view_with_position(self):
        """Test starring a view at specific position (insert and shift)"""
        pass

    @with_feature("organizations:issue-view-sharing")
    def test_star_already_starred_idempotent(self):
        """Test starring an already-starred view (idempotent)"""
        pass

    # Unstar tests
    @with_feature("organizations:issue-view-sharing")
    def test_unstar_view(self):
        """Test unstarring a starred view (remove and compact)"""
        pass

    @with_feature("organizations:issue-view-sharing")
    def test_unstar_not_starred_idempotent(self):
        """Test unstarring a non-starred view (idempotent)"""
        pass

    # Permission tests
    @with_feature("organizations:issue-view-sharing")
    def test_star_owner_view_as_non_owner(self):
        """Test starring an OWNER view as non-owner (403)"""
        pass

    # Feature flag tests
    def test_star_feature_disabled(self):
        """Test starring with feature flag disabled (400)"""
        pass

    # Edge case tests
    @with_feature("organizations:issue-view-sharing")
    def test_star_position_out_of_bounds(self):
        """Test starring with position > max (clamp to end)"""
        pass
```

### 6.2 Implement Key Tests

**Test 1: Star view append**:

```python
@with_feature("organizations:issue-view-sharing")
def test_star_view_append(self):
    response = self.get_success_response(
        self.organization.slug,
        self.view_shared.id,
        method="post",
        status_code=204,
    )

    # Verify starred
    starred = GroupSearchViewStarred.objects.get(
        organization=self.organization,
        user_id=self.user.id,
        group_search_view=self.view_shared,
    )
    assert starred.position == 0
```

**Test 2: Star with position (insert)**:

```python
@with_feature("organizations:issue-view-sharing")
def test_star_view_with_position(self):
    # Pre-star two views
    GroupSearchViewStarred.objects.create(
        organization=self.organization,
        user_id=self.user.id,
        group_search_view=self.view_owner,
        position=0,
    )
    GroupSearchViewStarred.objects.create(
        organization=self.organization,
        user_id=self.user.id,
        group_search_view=self.view_shared,
        position=1,
    )

    # Create third view
    view3 = GroupSearchView.objects.create(
        name="Third View",
        organization=self.organization,
        user_id=self.user.id,
        query="is:unresolved",
        visibility=GroupSearchViewVisibility.ORGANIZATION,
        position=2,
    )

    # Star at position 1
    response = self.get_success_response(
        self.organization.slug,
        view3.id,
        method="post",
        status_code=204,
        position=1,
    )

    # Verify positions
    starred_views = list(
        GroupSearchViewStarred.objects.filter(
            organization=self.organization,
            user_id=self.user.id,
        ).order_by("position")
    )

    assert len(starred_views) == 3
    assert starred_views[0].group_search_view_id == self.view_owner.id
    assert starred_views[0].position == 0
    assert starred_views[1].group_search_view_id == view3.id
    assert starred_views[1].position == 1
    assert starred_views[2].group_search_view_id == self.view_shared.id
    assert starred_views[2].position == 2
```

**Test 3: Idempotency**:

```python
@with_feature("organizations:issue-view-sharing")
def test_star_already_starred_idempotent(self):
    # Star once
    self.get_success_response(
        self.organization.slug,
        self.view_shared.id,
        method="post",
        status_code=204,
    )

    # Star again (idempotent)
    self.get_success_response(
        self.organization.slug,
        self.view_shared.id,
        method="post",
        status_code=204,
    )

    # Should only have one starred entry
    count = GroupSearchViewStarred.objects.filter(
        organization=self.organization,
        user_id=self.user.id,
        group_search_view=self.view_shared,
    ).count()
    assert count == 1
```

**Test 4: Unstar**:

```python
@with_feature("organizations:issue-view-sharing")
def test_unstar_view(self):
    # Pre-star three views
    for i, view in enumerate([self.view_owner, self.view_shared]):
        GroupSearchViewStarred.objects.create(
            organization=self.organization,
            user_id=self.user.id,
            group_search_view=view,
            position=i,
        )

    # Unstar the first view
    self.get_success_response(
        self.organization.slug,
        self.view_owner.id,
        method="delete",
        status_code=204,
    )

    # Verify only one starred view remains
    starred_views = list(
        GroupSearchViewStarred.objects.filter(
            organization=self.organization,
            user_id=self.user.id,
        ).order_by("position")
    )

    assert len(starred_views) == 1
    assert starred_views[0].group_search_view_id == self.view_shared.id
    assert starred_views[0].position == 0  # Position adjusted
```

**Test 5: Permission denied**:

```python
@with_feature("organizations:issue-view-sharing")
def test_star_owner_view_as_non_owner(self):
    other_user = self.create_user()
    self.create_member(organization=self.organization, user=other_user)
    self.login_as(user=other_user)

    # Try to star OWNER view as non-owner
    self.get_error_response(
        self.organization.slug,
        self.view_owner.id,
        method="post",
        status_code=403,
    )
```

### 6.3 Run Tests

```bash
# Run tests
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_star.py -v

# Run with coverage
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_star.py --cov=src/sentry/issues/endpoints/organization_group_search_view_star --cov-report=term-missing
```

---

## Step 7: Manual Testing (30 minutes)

### 7.1 Start Development Server

```bash
# Start Sentry development server
sentry devserver --workers
```

### 7.2 Enable Feature Flag

```bash
# Enable feature flag for your test organization
sentry shell

>>> from sentry.models import Organization
>>> from sentry import features
>>> org = Organization.objects.get(slug="your-test-org")
>>> # Feature flag is already enabled globally or per-org
>>> # If needed, add to sentry.conf.py:
>>> # SENTRY_FEATURES['organizations:issue-view-sharing'] = True
```

### 7.3 Create Test Data

```bash
# Create a test view via Django shell or API
sentry shell

>>> from sentry.models import GroupSearchView, Organization
>>> from sentry.models.groupsearchview import GroupSearchViewVisibility
>>> org = Organization.objects.get(slug="your-test-org")
>>> user = org.member_set.first().user
>>> view = GroupSearchView.objects.create(
...     name="Test View",
...     organization=org,
...     user_id=user.id,
...     query="is:unresolved",
...     visibility=GroupSearchViewVisibility.ORGANIZATION,
...     position=0,
... )
>>> print(f"Created view ID: {view.id}")
```

### 7.4 Test Star Endpoint

```bash
# Get auth token (or use session cookie from browser)
# Assuming you're logged in to http://localhost:8000

# Star a view
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/0/organizations/your-test-org/group-search-views/VIEW_ID/star/

# Expected: 204 No Content

# Verify in database
sentry shell
>>> from sentry.models.groupsearchviewstarred import GroupSearchViewStarred
>>> GroupSearchViewStarred.objects.filter(user_id=YOUR_USER_ID).values()
```

### 7.5 Test Unstar Endpoint

```bash
# Unstar the view
curl -X DELETE \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/0/organizations/your-test-org/group-search-views/VIEW_ID/star/

# Expected: 204 No Content

# Verify in database
sentry shell
>>> GroupSearchViewStarred.objects.filter(user_id=YOUR_USER_ID).count()
# Expected: 0
```

---

## Step 8: Code Review Checklist (10 minutes)

Before submitting PR, verify:

### Functionality

- [ ] Star without position appends to end
- [ ] Star with position inserts and shifts correctly
- [ ] Unstar removes and compacts positions
- [ ] Star is idempotent (returns 204 on duplicate)
- [ ] Unstar is idempotent (returns 204 on non-starred)

### Security

- [ ] All queries scoped by organization
- [ ] OWNER views only accessible by owner
- [ ] ORGANIZATION views accessible by all org members
- [ ] Feature flag checked before operations
- [ ] View existence validated before operations

### Code Quality

- [ ] Uses `OrganizationEndpoint` base class
- [ ] Uses `@region_silo_endpoint` decorator
- [ ] Uses atomic transactions with `router.db_for_write`
- [ ] Uses F() expressions for position updates
- [ ] Handles IntegrityError gracefully
- [ ] Returns correct HTTP status codes
- [ ] Error responses use `"detail"` key

### Testing

- [ ] All test methods have docstrings
- [ ] Tests use `APITestCase` pattern
- [ ] Tests use `get_success_response` and `get_error_response`
- [ ] Tests use `@with_feature` decorator
- [ ] Tests verify position ordering
- [ ] Tests cover edge cases (idempotency, permissions, feature flag)
- [ ] All tests pass

### Documentation

- [ ] Code comments explain complex logic
- [ ] Endpoint has publish_status and owner
- [ ] Serializer has field descriptions

---

## Step 9: Submit PR (15 minutes)

### 9.1 Create Branch

```bash
# Ensure you're on the feature branch
git checkout -b 001-star-unstar-views

# Or if branch exists
git checkout 001-star-unstar-views
```

### 9.2 Commit Changes

```bash
# Add files
git add src/sentry/issues/endpoints/organization_group_search_view_star.py
git add src/sentry/api/urls.py
git add tests/sentry/issues/endpoints/test_organization_group_search_view_star.py

# Commit
git commit -m "feat(issues): Add star/unstar endpoints for GroupSearchView

- Add POST/DELETE endpoints for starring views
- Support optional position parameter for insertion
- Automatic position management on star/unstar
- Idempotent operations
- Feature gated behind organizations:issue-view-sharing

Closes: #ISSUE-NUMBER"
```

### 9.3 Push and Create PR

```bash
# Push to remote
git push origin 001-star-unstar-views

# Create PR via GitHub CLI or web interface
gh pr create \
  --title "feat(issues): Add star/unstar endpoints for GroupSearchView" \
  --body "$(cat specs/001-star-unstar-views/plan.md)"
```

---

## Troubleshooting

### Issue: IntegrityError on position constraint

**Symptom**: `IntegrityError: duplicate key value violates unique constraint`

**Solution**: Ensure atomic transaction wraps both position shift and insert:

```python
with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
    # All operations here
    pass
```

### Issue: Test imports fail

**Symptom**: `ImportError: cannot import name 'OrganizationGroupSearchViewStarEndpoint'`

**Solution**: Ensure import is added to `urls.py` and endpoint class name matches

### Issue: Feature flag not working

**Symptom**: Tests pass with `@with_feature` but manual testing returns 400

**Solution**: Verify feature flag is enabled in your dev environment:

```python
# In sentry.conf.py or via Django shell
SENTRY_FEATURES['organizations:issue-view-sharing'] = True
```

### Issue: Positions have gaps after operations

**Symptom**: Positions are [0, 2, 3] instead of [0, 1, 2]

**Solution**: Ensure unstar decrements positions correctly:

```python
GroupSearchViewStarred.objects.filter(
    organization=organization,
    user_id=request.user.id,
    position__gt=deleted_position,  # Note: __gt not __gte
).update(position=F("position") - 1)
```

---

## Performance Optimization Tips

### Reduce Database Queries

**Before** (N+1 queries):

```python
for view_id in view_ids:
    view = GroupSearchView.objects.get(id=view_id)
    # Process view
```

**After** (1 query):

```python
views = GroupSearchView.objects.filter(id__in=view_ids)
view_map = {view.id: view for view in views}
for view_id in view_ids:
    view = view_map[view_id]
    # Process view
```

**Note**: This feature only deals with single views, so this optimization isn't needed here. But keep it in mind if you add bulk operations later.

### Use select_for_update for Concurrency

If you encounter frequent position conflicts, consider locking:

```python
with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
    starred_views = GroupSearchViewStarred.objects.select_for_update().filter(
        organization=organization,
        user_id=request.user.id,
    )
    # Perform operations
```

**Tradeoff**: Better consistency but reduced concurrency. Only add if conflicts are common.

---

## Next Steps After Implementation

1. **Monitor Metrics**:
   - Track error rates for new endpoints
   - Monitor p95 latency
   - Watch for IntegrityError frequency

2. **Gather Feedback**:
   - Test with beta organizations
   - Collect user feedback on position management
   - Identify any usability issues

3. **Iterate**:
   - Add bulk star/unstar if needed
   - Optimize position management if slow
   - Add more advanced features (e.g., starred view folders)

4. **Documentation**:
   - Update API documentation
   - Add user-facing documentation
   - Create demo videos if applicable

---

## Summary

**Implementation Checklist**:

- [ ] Step 1: Understand data model (10 min)
- [ ] Step 2: Review API contracts (10 min)
- [ ] Step 3: Study existing patterns (20 min)
- [ ] Step 4: Implement star endpoint (60 min)
- [ ] Step 5: Add URL route (5 min)
- [ ] Step 6: Write tests (90 min)
- [ ] Step 7: Manual testing (30 min)
- [ ] Step 8: Code review (10 min)
- [ ] Step 9: Submit PR (15 min)

**Total Estimated Time**: 4-6 hours

**Key Files**:

- `src/sentry/issues/endpoints/organization_group_search_view_star.py` (NEW)
- `src/sentry/api/urls.py` (MODIFIED)
- `tests/sentry/issues/endpoints/test_organization_group_search_view_star.py` (NEW)

**No Changes**:

- Models (reusing existing)
- Migrations (not needed)
- Serializers (using inline)

**Ready to Start**: Follow steps 1-9 sequentially. Good luck! 🚀
