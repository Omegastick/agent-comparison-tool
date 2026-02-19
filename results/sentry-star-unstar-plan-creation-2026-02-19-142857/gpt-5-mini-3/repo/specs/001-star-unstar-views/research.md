Decision: Use integer position with transactional shifts and per-user advisory locking

Rationale:

- Keep model simple and compatible with existing Sentry patterns (Django + Postgres).
- Integer positions are easy to reason about, enforce with DB constraints, and align with acceptance criteria requiring shifting of subsequent items.
- Use a DB transaction plus either SELECT ... FOR UPDATE on the user's starred rows or a Postgres advisory lock to serialize concurrent reordering for a single user. This prevents lost updates from concurrent star/unstar requests.

Alternatives considered:

- Dense ordering (floats): Easier insert without shifting but leads to precision and eventual rebalancing complexity. Rejected for complexity and subtle bugs at scale.
- Linked-list via next_id pointers: Complex for queries (ordering, pagination) and harder to batch-fetch related GroupSearchView objects. Rejected for implementation and maintenance cost.

Storage and locking choices:

- Primary: PostgreSQL table `sentry_starredsearchview` (region-silo model). Add foreign keys to user and GroupSearchView, unique(user, group_search_view), unique(user, position) to maintain invariants.
- Concurrency: Use transactional updates with one of:
  1. SELECT ... FOR UPDATE on all starred rows for the user (bounded by user's starred list size), then perform positional shifts and insert/remove within the same transaction.
  2. (Preferred) Acquire a Postgres advisory lock keyed by user id before mutation, then perform positional shifts in a transaction. Advisory locks avoid locking many rows and are a proven pattern for per-tenant serialization.

Idempotency and validation:

- Starring an already-starred view: return 200 (no-op). If position differs, allow a separate reorder API or treat same call as a move (decide below).
- Unstarring a non-starred view: return 200 (no-op).
- Validation enforces user access to the GroupSearchView (scoped by organization) before performing any mutation.

Feature flag & backward compatibility:

- Gate the endpoints and any migrations behind a feature flag (e.g., `organizations:starred-views`) so code can be merged safely.
- Migrations are additive: new table with default null/empty state; does not change existing tables.

Integration notes:

- Listing endpoint must use serializer get_attrs to batch fetch GroupSearchView payloads and avoid N+1.
- When a GroupSearchView is deleted, DB FK should cascade delete starred rows, or a periodic cleanup job ensures no dangling starred entries exist.

Conclusion: Implement integer-position model + advisory lock approach for robustness and simplicity.
