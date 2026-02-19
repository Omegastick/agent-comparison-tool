# API Contracts

This directory contains OpenAPI 3.0 specifications for the star/unstar endpoints.

## Files

- **star-endpoint.yaml**: POST endpoint for starring a GroupSearchView
- **unstar-endpoint.yaml**: DELETE endpoint for unstarring a GroupSearchView

## Usage

These contracts define:

- Request/response schemas
- HTTP methods and status codes
- Authentication requirements
- Example requests and responses

## Implementation Notes

Both endpoints follow Sentry's API conventions:

- Use `camelCase` for JSON keys
- Return numeric IDs as strings in responses
- Use `"detail"` key for all error messages (DRF standard)
- Support both token and session authentication

## Validation

These specs can be used to:

1. Generate API documentation
2. Validate requests/responses in tests
3. Generate client SDKs
4. Configure API gateways

## Related Endpoints

These endpoints complement existing GroupSearchView operations:

- `GET /organizations/{org}/group-search-views/` - List starred views
- `PUT /organizations/{org}/group-search-views/` - Bulk create/update views
- `DELETE /organizations/{org}/group-search-views/{id}/` - Delete view
- `PUT /organizations/{org}/group-search-views-starred-order/` - Reorder starred views
