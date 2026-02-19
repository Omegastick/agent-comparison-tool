Quickstart: Adding star/unstar to saved views

1. Data model
   - Add `StarredView` model (see `data-model.md`) and run migrations.

2. API
   - Implement two endpoints in `src/sentry/api/endpoints/`:
     - `views_star.py` with POST and DELETE handlers on `/organizations/{org}/views/{view_id}/star/`
     - Inherit from `OrganizationEndpoint` and use `@region_silo_endpoint`.

3. Business logic
   - POST: validate access to GroupSearchView, acquire advisory lock for user, begin transaction, shift positions >= requested position, insert or return existing row.
   - DELETE: validate access, acquire advisory lock, remove row if exists, shift positions > removed position down by 1.

4. Tests
   - Add APITestCase tests under `tests/sentry/api/endpoints/` mirroring patterns in repository. Use factories to create orgs, users, and GroupSearchView objects.

5. Feature flag
   - Gate endpoints with feature flag `organizations:starred-views`.

6. Agent context
   - Run `.specify/scripts/bash/update-agent-context.sh opencode` to update agent files with new technology references (Python, Django, PostgreSQL).
