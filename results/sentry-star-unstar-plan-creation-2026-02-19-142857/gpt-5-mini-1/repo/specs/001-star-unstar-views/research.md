Decision: Use integer `position` with shifting and transactional updates

Rationale: Per-user starred lists are expected to be small (typical <100 entries). Integer positions are simple to reason about, easy to implement with indexes, and compatible with existing relational patterns used across the codebase. They allow O(k) updates where k is number of shifted rows; with small lists this is acceptable and simpler than introducing fractional/rope numbering schemes. Using integer positions also maps cleanly to tests and migrations and is easy for clients to reason about.

Alternatives considered:

- Fractional/float positioning (e.g., assign 1.0, 2.0, insert using midpoint): reduces shifts but introduces precision/edge-case complexity over long lifetimes and is harder to reason about in migrations and DB-level constraints.
- Store ordered array on a user preference row: avoids per-row inserts but makes concurrent updates and partial reads harder and violates "batch-aware" access patterns. Also complicates partial updates and indexing when looking up by view.

Decision: Use row-level locking (SELECT ... FOR UPDATE) scoped to the user's starred set for concurrency

Rationale: When inserting at a specific position or removing an entry, we need to atomically shift the subsequent positions. The simplest DB-safe approach is to wrap the read+shift+insert/delete in a single transaction and acquire a FOR UPDATE lock on the rows for that user. This keeps the locking scope narrow (per-user) and avoids application-level distributed locks.

Alternatives considered:

- Advisory locks: viable, but adds another coordination primitive and risk of deadlocks if misused. Not necessary given per-user locking is sufficient.
- Optimistic retries (compare-and-swap): possible, but requires repeated read-modify-write cycles and more complex test coverage. FOR UPDATE is simpler and matches existing Sentry patterns for small metadata lists.

Decision: API responses are minimal; return the created/updated StarredSearchView object (id, viewId, position) and let clients fetch full starred list separately

Rationale: Returning minimal object reduces payload size and avoids duplication when clients already cache or fetch the full list. It keeps the API predictable and easy to evolve. Clients that need the full list can issue a list endpoint (not in scope for this initial change) or subscribe to push/update flows.

Alternatives considered:

- Return entire updated starred list: convenient for clients but increases payload and server work; can be added later if metrics show it is beneficial.

Implementation notes / safety:

- Gate endpoints behind a feature flag to allow incremental rollout and safe merges.
- Validate view access by checking GroupSearchView visibility and organization membership; reject if the user lacks access.
- Add DB index on (user_id, position) and on (user_id, group_search_view_id) to support common queries and uniqueness checks.
