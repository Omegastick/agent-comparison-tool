Quickstart: Star / Unstar Shared Views (backend)

1. Data model: add `StarredSearchView` model in `src/sentry/models/starred_search_view.py` with fields `(user_id, group_search_view_id, position, date_created)` and indexes on `(user_id, position)` and `(user_id, group_search_view_id)`.

2. API: add organization-scoped endpoints:

- POST `/api/0/organizations/{org_slug}/starred-views/` -> body `{viewId, position?}`
- DELETE `/api/0/organizations/{org_slug}/starred-views/{viewId}/`

3. Permissions: use `OrganizationEndpoint` and `SentryPermission` scope mapping (org:read for GET, org:write for POST/DELETE) and validate the user has access to the GroupSearchView before changing state.

4. Concurrency: wrap insert/remove in a transaction and `SELECT ... FOR UPDATE` the user's starred rows to shift positions safely.

5. Tests: add pytest tests in `tests/sentry/api/endpoints/test_organization_starred_views.py` using `self.create_user()`, `self.create_organization()`, `self.create_project()`, and factories for `GroupSearchView` where applicable. Follow existing test helpers for request helpers `self.get_success_response`.
