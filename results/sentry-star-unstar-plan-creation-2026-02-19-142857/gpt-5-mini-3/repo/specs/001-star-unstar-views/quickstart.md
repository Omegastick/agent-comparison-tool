Quickstart: Star / Unstar Shared Issue Views

Files produced by this plan:

- `/workspace/repo/specs/001-star-unstar-views/contracts/openapi.yaml` (API contract)
- `/workspace/repo/specs/001-star-unstar-views/data-model.md` (data model)
- `/workspace/repo/specs/001-star-unstar-views/research.md` (research & decisions)

Developer steps to implement and test locally

1. Create model and migration
   - Add `StarredSearchView` model at `src/sentry/models/starred.py` as a region-silo model.
   - Migration must be additive (new table only). Use Django migrations and keep compatibility.

2. Implement endpoints and serializers
   - Endpoint paths (mirror OpenAPI):
     - POST `/api/0/organizations/{org_slug}/starred-views/` { viewId, position? }
     - DELETE `/api/0/organizations/{org_slug}/starred-views/` { viewId }
     - GET `/api/0/organizations/{org_slug}/starred-views/list/`
   - Use `OrganizationEndpoint` / `@region_silo_endpoint` and Sentry permission classes.
   - Enforce access validation: user must have access to GroupSearchView before mutation.

3. Concurrency & transactions
   - Use advisory lock (recommended) per user id or SELECT ... FOR UPDATE within a transaction when shifting positions.

4. Tests
   - Add `tests/sentry/api/endpoints/test_starred_views.py` using factory helpers (do not use direct model creation).
   - Cover acceptance scenarios and edge cases: idempotency, position insertion, concurrent mutations (integration test if possible).

5. Feature gating
   - Wrap endpoints/logic behind feature flag `organizations:starred-views` and add flag checks before making them available.

6. Run checks
   - From repo root: `pytest tests/sentry/api/endpoints/test_starred_views.py` (or run full test suite as needed).

7. Agent context
   - Agent context updated for `opencode` by running `.specify/scripts/bash/update-agent-context.sh opencode`.

Notes

- See `contracts/openapi.yaml` for request/response shapes and `data-model.md` for the DB schema and constraints.
- Keep all DB operations scoped by user/org to satisfy security constitution.
