# Todo API Constitution

## Core Principles

### I. Simplicity First
Every feature must justify its complexity. Prefer straightforward solutions over clever ones. Code should be readable by a developer unfamiliar with the project. No premature abstractions.

### II. Type Safety
All code must be fully typed using Python type hints. No `Any` types except when interfacing with untyped external libraries. Pydantic models for all data structures.

### III. Test-Driven Development (NON-NEGOTIABLE)
TDD is mandatory: Tests written first, tests must fail, then implement. Red-Green-Refactor cycle strictly enforced. No feature is complete without tests.

### IV. RESTful Design
API endpoints follow REST conventions. Resources are nouns, actions are HTTP verbs. Consistent response formats across all endpoints. Proper HTTP status codes.

### V. Explicit Error Handling
No silent failures. All errors must be logged and returned with meaningful messages. Use appropriate HTTP status codes. Validate all inputs at boundaries.

## Technology Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Database**: SQLite (file-based, no external dependencies)
- **Validation**: Pydantic v2
- **Testing**: pytest with httpx for API tests
- **Package Manager**: uv

## Code Standards

- Follow PEP 8 style guidelines, enforced by ruff
- Maximum function length: 30 lines
- Maximum file length: 300 lines
- All public functions must have docstrings
- No global mutable state
- No `*` imports

## Security Requirements

- Input validation on all endpoints
- No SQL injection vulnerabilities (use parameterized queries)
- No sensitive data in logs
- Proper error messages (no stack traces in production responses)

## Governance

This constitution supersedes all other practices. All implementation decisions must align with these principles. Deviations require explicit justification and documentation.

**Version**: 1.0.0 | **Ratified**: 2025-02-11
