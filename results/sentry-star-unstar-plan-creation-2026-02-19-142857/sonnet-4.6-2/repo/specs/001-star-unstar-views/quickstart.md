# Quickstart: Implementing Star / Unstar Issue Views

**Feature**: `001-star-unstar-views`
**Branch**: `001-star-unstar-views`

This guide describes the exact files to create or modify and the key steps to implement the
star/unstar endpoint. It is written for a developer picking up this task fresh.

---

## Prerequisites

- Python 3.13+, Django 5.2+ dev environment configured
- `organizations:issue-view-sharing` feature flag enabled in your local instance
- Familiarity with `src/sentry/issues/endpoints/organization_group_search_view_visit.py`
  (the closest analogue — a simple per-view POST endpoint)

---

## What already exists (do NOT recreate)

| What                            | Where                                                                                       |
| ------------------------------- | ------------------------------------------------------------------------------------------- |
| `GroupSearchViewStarred` model  | `src/sentry/models/groupsearchviewstarred.py`                                               |
| DB migration for starred table  | `0836_create_groupsearchviewstarred_table.py`                                               |
| Starred serializer              | `src/sentry/api/serializers/models/groupsearchview.py` → `GroupSearchViewStarredSerializer` |
| Reorder endpoint (PUT)          | `src/sentry/issues/endpoints/organization_group_search_view_starred_order.py`               |
| `__all__` stub for new endpoint | `src/sentry/issues/endpoints/__init__.py` line 57                                           |

---

## Step 1 — Create the endpoint file

**New file**: `src/sentry/issues/endpoints/organization_group_search_view_star.py`

Mirror the structure of `organization_group_search_view_visit.py`. Key differences:

```python
# Permissions: both POST and DELETE require member:read + member:write
class MemberPermission(OrganizationPermission):
    scope_map = {
        "POST": ["member:read", "member:write"],
        "DELETE": ["member:read", "member:write"],
    }

@region_silo_endpoint
class OrganizationGroupSearchViewStarredEndpoint(OrganizationEndpoint):
    publish_status = {
        "POST": ApiPublishStatus.EXPERIMENTAL,
        "DELETE": ApiPublishStatus.EXPERIMENTAL,
    }
    owner = ApiOwner.ISSUES
    permission_classes = (MemberPermission,)
```

### POST handler (star)

```python
def post(self, request: Request, organization: Organization, view_id: str) -> Response:
    # 1. Feature flag check — return 400 if not enabled
    # 2. Fetch view: must exist in org AND be accessible (owner OR org-visibility)
    #    → 404 if not found or inaccessible
    # 3. Check idempotency: if already starred, return 204 immediately
    # 4. Parse optional position from request.data (non-negative int or absent)
    #    → 400 if present but not a non-negative int
    # 5. Within transaction.atomic:
    #    a. count = current starred count for (user, org)
    #    b. insert_pos = min(position ?? count, count)  ← clamping
    #    c. UPDATE position = position + 1
    #       WHERE user_id=user AND org=org AND position >= insert_pos
    #    d. INSERT GroupSearchViewStarred(user, org, view, position=insert_pos)
    # 6. Return Response(status=204)
```

### DELETE handler (unstar)

```python
def delete(self, request: Request, organization: Organization, view_id: str) -> Response:
    # 1. Feature flag check — return 400 if not enabled
    # 2. Fetch view: scoped to org and accessible
    #    → 404 if not found or inaccessible
    # 3. Within transaction.atomic:
    #    a. Try to get GroupSearchViewStarred for (user, org, view)
    #    b. If DoesNotExist → return 204 (idempotent)
    #    c. deleted_position = starred.position
    #    d. starred.delete()
    #    e. UPDATE position = position - 1
    #       WHERE user_id=user AND org=org AND position > deleted_position
    # 4. Return Response(status=204)
```

**Imports needed**:

```python
from django.db import router, transaction
from django.db.models import F
from rest_framework import status
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
```

---

## Step 2 — Register the endpoint in `__init__.py`

**File**: `src/sentry/issues/endpoints/__init__.py`

Add the import (the `__all__` entry already exists at line 57):

```python
from .organization_group_search_view_star import OrganizationGroupSearchViewStarredEndpoint
```

---

## Step 3 — Add the URL pattern

**File**: `src/sentry/api/urls.py`

Add after the existing `/visit/` pattern (around line 1792):

```python
re_path(
    r"^(?P<organization_id_or_slug>[^\/]+)/group-search-views/(?P<view_id>[^\/]+)/star/$",
    OrganizationGroupSearchViewStarredEndpoint.as_view(),
    name="sentry-api-0-organization-group-search-view-star",
),
```

Also add the import near the other group-search-view imports:

```python
from sentry.issues.endpoints import OrganizationGroupSearchViewStarredEndpoint
```

---

## Step 4 — Write tests

**New file**: `tests/sentry/issues/endpoints/test_organization_group_search_view_star.py`

Use `APITestCase`. Test class skeleton:

```python
class OrganizationGroupSearchViewStarPostTest(APITestCase):
    endpoint = "sentry-api-0-organization-group-search-view-star"
    method = "post"
    # Tests:
    # - star a shared view → 204, row created at end
    # - star an owned view → 204, row created
    # - star at specific position → 204, existing views shifted
    # - star at position > count → clamped to end
    # - star already-starred view → 204, no change (idempotent)
    # - star a view not in org → 404
    # - star an org-owned view with different user → 404
    # - feature flag off → 400
    # - position = negative int → 400

class OrganizationGroupSearchViewStarDeleteTest(APITestCase):
    endpoint = "sentry-api-0-organization-group-search-view-star"
    method = "delete"
    # Tests:
    # - unstar a starred view → 204, row deleted, others shifted
    # - unstar a non-starred view → 204 (idempotent)
    # - unstar a view not in org → 404
    # - feature flag off → 400

class OrganizationGroupSearchViewStarTransactionTest(TransactionTestCase):
    # - concurrent star at same position (DB-level uniqueness)
    # - position invariant: after any star/unstar sequence, positions are contiguous
```

---

## Step 5 — Run the tests

```bash
pytest tests/sentry/issues/endpoints/test_organization_group_search_view_star.py -x -v
```

To run the full related test suite:

```bash
pytest tests/sentry/issues/endpoints/ -x -v -k "group_search_view"
```

---

## Key invariants to preserve

1. After any POST or DELETE, the `(user_id, organization_id)` position sequence is always
   a contiguous zero-based range `[0, 1, ..., n-1]`.
2. All position mutations happen inside `transaction.atomic(using=router.db_for_write(GroupSearchViewStarred))`.
3. Access control: never allow starring a view owned by another user in a different org,
   or a view with `visibility="owner"` belonging to another user.
4. Return `404` (not `403`) when a view is inaccessible — avoids leaking existence.
5. Feature flag: return `400` (consistent with starred-order endpoint) when
   `organizations:issue-view-sharing` is not enabled.
