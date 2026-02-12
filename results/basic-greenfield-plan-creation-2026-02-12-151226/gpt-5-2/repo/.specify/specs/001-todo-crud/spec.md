# Feature Specification: Todo CRUD API

**Feature Branch**: `001-todo-crud`
**Created**: 2025-02-11
**Status**: Final

## User Scenarios & Testing

### User Story 1 - Create a Todo (Priority: P1)

As a user, I want to create a new todo item so I can track tasks I need to complete.

**Why this priority**: Core functionality - cannot have a todo app without creating todos.

**Independent Test**: Can be fully tested by POST /todos with a title and verifying the response contains the created todo with an ID.

**Acceptance Scenarios**:

1. **Given** an empty database, **When** I POST /todos with `{"title": "Buy groceries"}`, **Then** I receive 201 Created with the todo containing an id, title, created_at, and completed=false
2. **Given** an empty database, **When** I POST /todos with `{"title": "Call mom", "description": "About birthday"}`, **Then** I receive 201 Created with both title and description populated
3. **Given** any state, **When** I POST /todos with `{"title": ""}`, **Then** I receive 400 Bad Request with a validation error

---

### User Story 2 - List All Todos (Priority: P1)

As a user, I want to see all my todos so I can review what needs to be done.

**Why this priority**: Essential companion to create - users need to see what they've added.

**Independent Test**: Can be tested by creating 2-3 todos and verifying GET /todos returns all of them.

**Acceptance Scenarios**:

1. **Given** an empty database, **When** I GET /todos, **Then** I receive 200 OK with an empty list
2. **Given** 3 todos exist, **When** I GET /todos, **Then** I receive 200 OK with all 3 todos
3. **Given** todos exist, **When** I GET /todos, **Then** todos are ordered by created_at descending (newest first)

---

### User Story 3 - Get a Single Todo (Priority: P1)

As a user, I want to view details of a specific todo so I can see its full information.

**Why this priority**: Required for viewing individual todo details and for edit/delete workflows.

**Independent Test**: Can be tested by creating a todo and fetching it by ID.

**Acceptance Scenarios**:

1. **Given** a todo exists with id "abc-123", **When** I GET /todos/abc-123, **Then** I receive 200 OK with that todo's full details
2. **Given** no todo with id "nonexistent", **When** I GET /todos/nonexistent, **Then** I receive 404 Not Found

---

### User Story 4 - Update a Todo (Priority: P2)

As a user, I want to edit a todo's title or description so I can correct or clarify my tasks.

**Why this priority**: Important for maintaining accurate task list, but not critical for MVP.

**Independent Test**: Can be tested by creating a todo, updating its title, and verifying the change persists.

**Acceptance Scenarios**:

1. **Given** a todo exists, **When** I PATCH /todos/{id} with `{"title": "New title"}`, **Then** I receive 200 OK with the updated todo
2. **Given** a todo exists, **When** I PATCH /todos/{id} with `{"description": "New desc"}`, **Then** only the description changes, title remains
3. **Given** no todo with that id, **When** I PATCH /todos/{id}, **Then** I receive 404 Not Found

---

### User Story 5 - Delete a Todo (Priority: P2)

As a user, I want to remove a todo so I can clean up tasks I no longer need.

**Why this priority**: Necessary for list maintenance but not critical for initial use.

**Independent Test**: Can be tested by creating a todo, deleting it, and verifying it no longer appears in the list.

**Acceptance Scenarios**:

1. **Given** a todo exists with id "abc-123", **When** I DELETE /todos/abc-123, **Then** I receive 204 No Content
2. **Given** a todo was deleted, **When** I GET /todos, **Then** the deleted todo is not in the list
3. **Given** no todo with that id, **When** I DELETE /todos/{id}, **Then** I receive 404 Not Found

---

### User Story 6 - Mark Todo Complete/Incomplete (Priority: P2)

As a user, I want to mark todos as complete or incomplete so I can track my progress.

**Why this priority**: Core todo functionality but can be achieved via update in MVP.

**Independent Test**: Can be tested by creating a todo, marking it complete, and verifying the status change.

**Acceptance Scenarios**:

1. **Given** an incomplete todo, **When** I PATCH /todos/{id}/complete, **Then** I receive 200 OK with completed=true and completed_at set
2. **Given** a completed todo, **When** I PATCH /todos/{id}/incomplete, **Then** I receive 200 OK with completed=false and completed_at=null
3. **Given** no todo with that id, **When** I PATCH /todos/{id}/complete, **Then** I receive 404 Not Found

---

### Edge Cases

- Empty title: Return 400 Bad Request with clear validation error
- Title too long (>500 chars): Return 400 Bad Request
- Description too long (>2000 chars): Return 400 Bad Request
- Invalid UUID format for id: Return 400 Bad Request (not 404)
- Database file missing on startup: Create it automatically
- Concurrent updates: SQLite handles locking, last write wins

## Requirements

### Functional Requirements

- **FR-001**: System MUST allow creating todos with title (required, 1-500 chars) and description (optional, max 2000 chars)
- **FR-002**: System MUST assign a UUID v4 to each new todo
- **FR-003**: System MUST record created_at timestamp (UTC) when todo is created
- **FR-004**: System MUST track completed status (boolean, default false)
- **FR-005**: System MUST track completed_at timestamp when marked complete (null when incomplete)
- **FR-006**: System MUST support listing all todos ordered by created_at descending
- **FR-007**: System MUST support retrieving a single todo by ID
- **FR-008**: System MUST support partial updates (PATCH) to title and description
- **FR-009**: System MUST support deleting a todo by ID
- **FR-010**: System MUST support marking a todo complete/incomplete via dedicated endpoints
- **FR-011**: System MUST persist all data to SQLite database
- **FR-012**: System MUST return appropriate HTTP status codes (200, 201, 204, 400, 404, 500)

### Key Entities

- **Todo**: A task to be completed
  - `id`: UUID v4 (primary key, auto-generated)
  - `title`: string (1-500 characters, required)
  - `description`: string (0-2000 characters, optional)
  - `completed`: boolean (default: false)
  - `created_at`: datetime UTC (auto-set on creation)
  - `completed_at`: datetime UTC (nullable, set when completed)

## API Endpoints

| Method | Endpoint | Request Body | Response | Status Codes |
|--------|----------|--------------|----------|--------------|
| POST | /todos | `{title, description?}` | Todo | 201, 400 |
| GET | /todos | - | Todo[] | 200 |
| GET | /todos/{id} | - | Todo | 200, 404 |
| PATCH | /todos/{id} | `{title?, description?}` | Todo | 200, 400, 404 |
| DELETE | /todos/{id} | - | - | 204, 404 |
| PATCH | /todos/{id}/complete | - | Todo | 200, 404 |
| PATCH | /todos/{id}/incomplete | - | Todo | 200, 404 |

## Success Criteria

### Measurable Outcomes

- **SC-001**: All 7 API endpoints implemented and functional
- **SC-002**: 100% of acceptance scenarios pass in automated tests
- **SC-003**: All CRUD operations complete in under 50ms for database with <1000 todos
- **SC-004**: Zero validation bypass - all invalid inputs return 400
- **SC-005**: Consistent JSON response format across all endpoints
