Entity: StarredSearchView

- Description: Relationship between a user and a GroupSearchView indicating the user starred that view and the desired position within the user's ordered starred list.
- Path: src/sentry/models/starred.py (region_silo_model)

Fields:

- id: auto PK
- user_id: HybridCloudForeignKey(settings.AUTH_USER_MODEL) (indexed)
- group_search_view_id: FlexibleForeignKey("sentry.GroupSearchView") (indexed)
- position: IntegerField (1-based index)
- date_added: DateTimeField (auto_now_add)

Constraints & Indexes:

- unique_together: (user_id, group_search_view_id)
- unique_together or partial unique: (user_id, position)
- index on (user_id, position) for ordered retrieval

Validation Rules:

- position must be >= 1
- user must have access to the referenced GroupSearchView (enforced at API/service layer)

State Transitions:

- Create (star): insert row at specified position or append at end, shifting positions >= pos by +1
- Delete (unstar): remove row and shift positions > pos by -1
- Idempotency: creating when already exists is no-op; deleting when missing is no-op

Notes:

- To avoid costly UPDATEs on very large lists, we expect per-user lists to be modest. For extreme scale, consider dense ordering with periodic rebalancing.
