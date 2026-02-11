# Constitution

This document defines the principles and constraints that guide all development in this project.

## Core Principles

1. **Simplicity First**: Prefer simple solutions over complex ones. Every line of code should earn its place.

2. **Type Safety**: Use strong typing throughout. All public APIs must have complete type annotations.

3. **Test Coverage**: All features must have corresponding tests. Aim for >80% coverage on new code.

4. **Documentation**: Public APIs must be documented. Complex logic should have explanatory comments.

5. **Error Handling**: Fail explicitly rather than silently. All errors should be actionable.

## Technical Constraints

- **Language**: Python 3.11+
- **Package Manager**: Use `uv` for dependency management
- **Code Style**: Follow PEP 8, enforced by `ruff`
- **Type Checking**: Use `pyright` in strict mode

## Architecture Guidelines

- Keep modules small and focused
- Use dependency injection for external services
- Avoid global state
- Prefer composition over inheritance

## Prohibited Patterns

- No `*` imports
- No mutable default arguments
- No bare `except:` clauses
- No hardcoded credentials or secrets
