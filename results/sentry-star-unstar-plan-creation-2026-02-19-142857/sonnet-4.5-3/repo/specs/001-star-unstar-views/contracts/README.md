# API Contracts: Star and Unstar Shared Issue Views

**Feature**: 001-star-unstar-views  
**Date**: 2026-02-19  
**Status**: Design Complete

## Overview

This document provides a human-readable summary of the API contracts for the star/unstar feature. For the complete machine-readable specification, see `openapi.yaml` in this directory.

## Endpoints Summary

### 1. Star a View

**Endpoint**: `POST /organizations/{organization_id_or_slug}/group-search-views/{view_id}/star/`

**Purpose**: Add a GroupSearchView to the user's personal starred list, optionally at a specific position.

**Authentication**: Required (bearer token or session)

**Feature Flag**: `organizations:issue-view-sharing`

**URL Parameters**:

- `organization_id_or_slug` (string, required): Organization ID or slug
- `view_id` (integer, required): GroupSearchView ID

**Request Body** (optional):

```json
{
  "position": 2
}
```

**Fields**:

- `position` (integer, optional): 0-based position where view should be inserted. Omit to append to end.

**Success Response**: `204 No Content`

**Error Responses**:

- `400 Bad Request`: Feature flag disabled, invalid position, or position conflict
- `403 Forbidden`: User doesn't have access to the view
- `404 Not Found`: View doesn't exist or is in a different organization

**Idempotency**: YES - starring an already-starred view returns 204 without changes

**Example Usage**:

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
```

---

### 2. Unstar a View

**Endpoint**: `DELETE /organizations/{organization_id_or_slug}/group-search-views/{view_id}/star/`

**Purpose**: Remove a GroupSearchView from the user's personal starred list.

**Authentication**: Required (bearer token or session)

**Feature Flag**: `organizations:issue-view-sharing`

**URL Parameters**:

- `organization_id_or_slug` (string, required): Organization ID or slug
- `view_id` (integer, required): GroupSearchView ID

**Request Body**: None

**Success Response**: `204 No Content`

**Error Responses**:

- `400 Bad Request`: Feature flag disabled
- `404 Not Found`: View doesn't exist or is in a different organization

**Idempotency**: YES - unstarring a non-starred view returns 204 without error

**Side Effects**: Automatically adjusts positions of remaining starred views to maintain contiguous ordering

**Example Usage**:

```bash
# Unstar a view
curl -X DELETE \
  -H "Authorization: Bearer {token}" \
  https://sentry.io/api/0/organizations/sentry/group-search-views/42/star/
```

---

## Related Endpoints (Existing)

These endpoints already exist and work with starred views:

### 3. List Starred Views

**Endpoint**: `GET /organizations/{organization_id_or_slug}/group-search-views/`

**Purpose**: Retrieve the user's starred views, ordered by position.

**Returns**: Paginated list of GroupSearchView objects with positions.

**Note**: This endpoint already exists and doesn't need modification.

---

### 4. Reorder Starred Views

**Endpoint**: `PUT /organizations/{organization_id_or_slug}/group-search-views-starred-order/`

**Purpose**: Bulk reorder all starred views in one operation.

**Request Body**:

```json
{
  "viewIds": [43, 42, 45]
}
```

**Note**: This endpoint already exists and doesn't need modification.

---

## Request/Response Format Conventions

Following Sentry API standards:

### Request Bodies

- Format: JSON
- Field naming: `camelCase`
- Content-Type: `application/json`

### Response Bodies

- Format: JSON
- Field naming: `camelCase`
- IDs: Returned as strings (e.g., `"id": "42"`)
- Error format: `{"detail": "Error message"}`

### HTTP Methods

- `POST`: Create resource (star)
- `DELETE`: Remove resource (unstar)
- `PUT`: Update resource (reorder - existing endpoint)
- `GET`: Retrieve resource (list - existing endpoint)

### Status Codes

- `200 OK`: Successful GET with body
- `204 No Content`: Successful POST/DELETE/PUT without body
- `400 Bad Request`: Client error (validation, feature flag)
- `403 Forbidden`: Permission denied
- `404 Not Found`: Resource not found

---

## Position Management Rules

### Position Semantics

- **0-indexed**: First starred view has position 0, second has position 1, etc.
- **Contiguous**: No gaps in positions (always 0, 1, 2, 3, ...)
- **Per-user**: Each user has their own position ordering
- **Unique**: No two starred views can have the same position for a user

### Position Operations

**Star without position** (append):

```
Before: [view_A:0, view_B:1, view_C:2]
Action: Star view_D
After:  [view_A:0, view_B:1, view_C:2, view_D:3]
```

**Star with position** (insert):

```
Before: [view_A:0, view_B:1, view_C:2]
Action: Star view_D at position 1
After:  [view_A:0, view_D:1, view_B:2, view_C:3]
```

**Unstar** (remove and compact):

```
Before: [view_A:0, view_B:1, view_C:2, view_D:3]
Action: Unstar view_B
After:  [view_A:0, view_C:1, view_D:2]
```

**Position out of bounds**:

```
Before: [view_A:0, view_B:1]
Action: Star view_C at position 100
After:  [view_A:0, view_B:1, view_C:2]  (clamped to end)
```

---

## Access Control Rules

### Organization Scoping

1. User must be authenticated
2. User must be a member of the organization in the URL path
3. View must belong to that organization
4. Cross-organization starring is not allowed

### View Visibility

1. **OWNER visibility**:
   - Only the view owner can see and star it
   - Attempting to star as non-owner returns `403 Forbidden`

2. **ORGANIZATION visibility**:
   - Any organization member can see and star it
   - Shared views are accessible to all org members

### Permission Matrix

| View Visibility | User is Owner | User is Org Member | Can Star?   |
| --------------- | ------------- | ------------------ | ----------- |
| OWNER           | Yes           | Yes                | ✅ Yes      |
| OWNER           | No            | Yes                | ❌ No (403) |
| ORGANIZATION    | Yes           | Yes                | ✅ Yes      |
| ORGANIZATION    | No            | Yes                | ✅ Yes      |
| Any             | Any           | No                 | ❌ No (404) |

---

## Idempotency Guarantees

### Star Operation

- **First call**: View is starred at position P, returns 204
- **Second call**: View is already starred, no change, returns 204
- **Nth call**: View remains starred at original position, returns 204

**Behavior**: Position is NOT updated on duplicate star. Use reorder endpoint to change position.

### Unstar Operation

- **First call**: View is unstarred, positions compacted, returns 204
- **Second call**: View is not starred, no change, returns 204
- **Nth call**: View remains not starred, returns 204

**Behavior**: Safe to call even if view is not starred.

---

## Error Handling

### Error Response Format

All errors follow the standard Sentry format:

```json
{
  "detail": "Human-readable error message"
}
```

### Common Errors

**400 Bad Request - Feature Disabled**:

```json
{
  "detail": "Feature not enabled for this organization"
}
```

**400 Bad Request - Invalid Position**:

```json
{
  "detail": "Position must be >= 0"
}
```

**400 Bad Request - Position Conflict**:

```json
{
  "detail": "Position conflict. Please retry."
}
```

_Note_: Rare error from concurrent operations. Client should retry.

**403 Forbidden - Permission Denied**:

```json
{
  "detail": "Permission denied"
}
```

**404 Not Found - View Not Found**:

```json
{
  "detail": "View not found"
}
```

---

## Feature Flag

**Flag Name**: `organizations:issue-view-sharing`

**Scope**: Organization-level

**Behavior**:

- **Enabled**: Star/unstar operations work normally
- **Disabled**: All operations return `400 Bad Request` with "Feature not enabled" error

**Checking**:

```python
if not features.has("organizations:issue-view-sharing", organization, actor=request.user):
    return Response({"detail": "Feature not enabled for this organization"}, status=400)
```

---

## Performance Characteristics

### Star Operation

- **Without position**: O(1) - append to end
- **With position**: O(N) where N = number of views at position >= target
- **Database queries**: 3 queries + position shifts

### Unstar Operation

- **Complexity**: O(N) where N = number of views at position > deleted
- **Database queries**: 3 queries + position shifts

### Expected Latency

- **Typical case** (10-20 starred views): 5-10ms
- **99th percentile**: <20ms
- **p95 requirement**: <200ms ✅

### Concurrency

- All operations wrapped in atomic transactions
- DEFERRED constraint allows temporary position duplicates within transaction
- Constraint enforced at commit time
- Rare conflicts return 400 with retry instruction

---

## Data Model Summary

### GroupSearchViewStarred Table

**Purpose**: Join table tracking starred views with position ordering

**Key Fields**:

- `id`: Primary key
- `group_search_view_id`: FK to GroupSearchView (CASCADE delete)
- `user_id`: FK to User (CASCADE delete)
- `organization_id`: FK to Organization (CASCADE delete)
- `position`: Integer, NOT NULL, 0-indexed
- `date_added`: Timestamp
- `date_updated`: Timestamp

**Constraints**:

- `UNIQUE(user_id, organization_id, position)` - DEFERRED

**Cascade Behavior**:

- Delete view → all stars auto-deleted
- Delete user → all their stars auto-deleted
- Delete organization → all stars auto-deleted

---

## Testing Checklist

### Functional Tests

- [ ] Star view without position (append)
- [ ] Star view with position (insert and shift)
- [ ] Star already-starred view (idempotent)
- [ ] Star with position > max (clamp to end)
- [ ] Star with position < 0 (validation error)
- [ ] Unstar starred view (remove and compact)
- [ ] Unstar non-starred view (idempotent)
- [ ] Star OWNER view as owner (success)
- [ ] Star OWNER view as non-owner (403)
- [ ] Star ORGANIZATION view as member (success)
- [ ] Star deleted view (404)
- [ ] Star view from different org (404)

### Feature Flag Tests

- [ ] Star with feature enabled (success)
- [ ] Star with feature disabled (400)
- [ ] Unstar with feature enabled (success)
- [ ] Unstar with feature disabled (400)

### Position Management Tests

- [ ] Verify positions after star at beginning
- [ ] Verify positions after star at middle
- [ ] Verify positions after star at end
- [ ] Verify positions after unstar at beginning
- [ ] Verify positions after unstar at middle
- [ ] Verify positions after unstar at end
- [ ] Verify no gaps in positions

### Edge Case Tests

- [ ] Empty starred list (star first view)
- [ ] Single starred view (unstar only view)
- [ ] Maximum position value (32767)
- [ ] Concurrent star requests (conflict handling)

---

## Implementation Notes

### URL Pattern

```python
# In src/sentry/api/urls.py
re_path(
    r"^(?P<organization_id_or_slug>[^\/]+)/group-search-views/(?P<view_id>[^\/]+)/star/$",
    OrganizationGroupSearchViewStarEndpoint.as_view(),
    name="sentry-api-0-organization-group-search-view-star",
)
```

### Endpoint Base Class

```python
from sentry.api.bases.organization import OrganizationEndpoint
from sentry.api.base import region_silo_endpoint

@region_silo_endpoint
class OrganizationGroupSearchViewStarEndpoint(OrganizationEndpoint):
    publish_status = {
        "POST": ApiPublishStatus.EXPERIMENTAL,
        "DELETE": ApiPublishStatus.EXPERIMENTAL,
    }
    owner = ApiOwner.ISSUES
    permission_classes = (MemberPermission,)
```

### Input Serializer

```python
from sentry.api.serializers.rest_framework import CamelSnakeSerializer

class StarViewSerializer(CamelSnakeSerializer):
    position = serializers.IntegerField(required=False, min_value=0)
```

### Transaction Pattern

```python
from sentry.db import router
from django.db import transaction

with transaction.atomic(using=router.db_for_write(GroupSearchViewStarred)):
    # Position shifting + insert/delete
    pass
```

---

## Migration Path

**Database Migrations**: None required (models exist)

**Deployment Steps**:

1. Merge endpoint code (behind feature flag)
2. Deploy to staging
3. Test with feature flag enabled
4. Gradually enable for production organizations
5. Monitor error rates and latency
6. Full rollout if metrics are good

**Rollback Plan**:

- Disable feature flag immediately
- No data migration needed
- Safe to revert code

---

## Summary

**Endpoints Added**: 2 (POST star, DELETE unstar)

**Database Changes**: None (reusing existing models)

**Feature Flag**: Reusing `organizations:issue-view-sharing`

**Breaking Changes**: None

**API Stability**: Experimental (can evolve based on feedback)

**Ready for Implementation**: ✅ Yes

For complete technical specification, see `openapi.yaml` in this directory.
