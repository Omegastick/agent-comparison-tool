Decision: Scale/Scope

Decision: Treat per-user starred lists as small (tens of entries) and optimize for simple, strongly consistent operations rather than extreme bulk scaling. Assume global scale (many users/orgs) but per-user operations are O(n) where n is the user's starred list length.
Rationale: Starred lists are personal and typically short; keeping the model and operations simple (integer positions with transactional shifts) minimizes complexity and risk. This keeps migrations and queries straightforward and aligns with Sentry's existing patterns.
Alternatives considered: Use fractional positions (lexicographic ordering/floating-point), linked-list references, or CRDTs for fully concurrent ordering. Rejected because they add complexity, make migrations and queries harder, and are unnecessary given expected small list sizes.

---

Decision: Position management and concurrency

Decision: Use an integer `position` field and perform position shifts inside a single database transaction. To avoid race conditions across processes, acquire a PostgreSQL advisory lock scoped to the user (pg_advisory_lock(hashtext('starred_views', user_id)) or pg_advisory_lock(user_id) if safe) for star/unstar operations. Also use SELECT ... FOR UPDATE on the user's StarredView rows when shifting positions.
Rationale: Transactions + row-level locks ensure correctness; advisory locks provide a cross-process, cross-connection serialization primitive that is easy to reason about and low-overhead for the expected contention profile (rare per-user concurrent mutations). This keeps operations deterministic and avoids complex distributed algorithms.
Alternatives considered: Rely solely on SELECT ... FOR UPDATE (works but can still race when inserting new rows if the set is empty); use optimistic retries with version numbers; use fractional positions to avoid shifting. Rejected because advisory lock + transaction provides the simplest strong-correct semantics.

Edge behaviors decided:

- If requested `position` <= 1, insert at position 1.
- If requested `position` > current_size + 1, append to end.
- Starring an already-starred view is a no-op and returns 200 with the current starred entry.
- Unstarring a non-starred view is a no-op and returns 204 (or 200) — choose 204 No Content to reflect successful removal with no body.
- If the target GroupSearchView does not exist or the user lacks access, return 404 (not found) or 403; prefer 404 to avoid leaking existence across orgs.

---

Decision: Data model shape

Decision: Add a region-silo Django model `StarredSearchView` (or `StarredView`) with fields:

- id: bigint PK
- user_id: HybridCloudForeignKey(settings.AUTH_USER_MODEL)
- group_search_view_id: FlexibleForeignKey('sentry.GroupSearchView')
- position: PositiveIntegerField
- date_added: DateTimeField(auto_now_add=True)

Constraints and indexes:

- UniqueConstraint(user_id, group_search_view_id) to enforce idempotency
- Index on (user_id, position) for ordered listing

Rationale: Matches repository patterns (HybridCloudForeignKey for users, FlexibleForeignKey for internal models) and satisfies requirements for persistence, ordering, and idempotency.

Alternatives considered: Embed starred metadata on GroupSearchView or on a per-user JSON blob. Rejected for complexity in queries and updates, and to preserve simple relational integrity and indexing.

---

Decision: API semantics

Decision: Expose two REST endpoints in the region silo under organization scope:

- POST /api/0/organizations/{organization_id_or_slug}/views/{view_id}/star/ (body: { position?: integer }) — idempotent; returns 200 with starred entry
- DELETE /api/0/organizations/{organization_id_or_slug}/views/{view_id}/star/ — idempotent; returns 204 No Content

Rationale: Mirrors common bookmark/star APIs; keeps route names intuitive and scoped to organization; leverages OrganizationEndpoint for permissions.

Alternatives considered: Use a single PATCH endpoint on a /starred/ collection. Rejected for clarity and mapping directly to the user's action on a target view.

---

Decision: Tests and validation

Decision: Implement APITestCase tests following Sentry patterns: create organization, create users, create GroupSearchView entries via factories, assert behavior for star/unstar, position insertion and shifting, idempotency, and access checks. Use transactional tests and simulate concurrency for a critical test (two concurrent star requests at same position) using thread-based concurrent workers or database-level advisory lock assertions.

Rationale: Conforms to constitution (tests with factories, no direct Model.objects.create in tests) and ensures coverage of requirements.

---

All previous NEEDS CLARIFICATION items are resolved by the decisions above. If new unknowns arise in Phase 1 design (migrations edge cases, exact advisory lock key function), they will be recorded and addressed.
