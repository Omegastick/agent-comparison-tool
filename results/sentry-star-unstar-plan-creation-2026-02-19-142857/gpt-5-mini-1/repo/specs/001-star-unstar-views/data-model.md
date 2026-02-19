Entities

- StarredSearchView
  - id: UUID / auto PK
  - user_id: FK -> sentry.User (HybridCloudForeignKey pattern)
  - group_search_view_id: FK -> sentry.GroupSearchView (FlexibleForeignKey)
  - position: Integer (1-based index)
  - date_created: datetime
  - date_updated: datetime

Relationships

- One User has many StarredSearchView
- One GroupSearchView can be starred by many Users

Validation rules

- position MUST be >= 1
- (user_id, group_search_view_id) MUST be unique (idempotency)
- position gaps are allowed (but insertion logic should shift subsequent positions to maintain contiguous ordering starting at 1)

State transitions

- NotStarred -> Starred (create record with position; if position unspecified append to max+1)
- Starred -> NotStarred (delete record and shift subsequent positions down by 1)

Indexes

- (user_id, position) -- for ordered queries
- (user_id, group_search_view_id) -- uniqueness and lookup
