Entity: StarredView (StarredSearchView)

Fields:

- id: bigint primary key
- user_id: HybridCloudForeignKey(settings.AUTH_USER_MODEL) — references User; tenant-scoped
- group_search_view_id: FlexibleForeignKey("sentry.GroupSearchView") — the saved view being starred
- position: BoundedPositiveIntegerField — 1-based ordinal in user's starred list
- date_added: DateTimeField(auto_now_add=True)

Indexes & Constraints:

- UniqueConstraint(fields=(user_id, group_search_view_id)) — ensures idempotency
- Index: (user_id, position) — supports ordered listing and efficient position updates

Relationships:

- Many-to-one: user -> StarredView (a user has many starred views)
- Many-to-one: GroupSearchView -> StarredView (a saved view can be starred by many users)

Validation rules:

- position must be >= 1
- group_search_view_id must exist and the user must have access to it (enforced in endpoint/service layer)

State transitions:

- create (star): inserts a StarredView, shifts positions >= requested position up by 1
- delete (unstar): removes StarredView, shifts positions > removed position down by 1
- idempotent create/delete: duplicate create returns existing row; delete of non-existent row is no-op

Notes on migrations:

- Add model in a backwards-compatible manner: initial migration creates table; use data-less migrations for reordering logic. Avoid removing columns or changing constraints without compatibility shims.
