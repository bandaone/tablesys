# API Documentation Overview

TABLESYS provides an extensive REST API for university integrators looking to plug the timetable schedule directly into their internal portals or Custom Mobile Apps.

## Authentication
All protected routes require an OAuth2 Bearer token in the Authorization header:
`Authorization: Bearer <your_jwt_token>`

Tokens are obtained by standard login exchange through:
`POST /api/v1/auth/login`

## Key Integration Endpoints

### 1. Usage and Metering
* **`GET /api/v1/usage/summary`**
  * **Description:** Retrieve your tenant's current monthly quota usage.
  * **Output:** JSON array detailing limits, current metrics, and percent used for `seats_active`, `timetable_generations`, and `department_count`.

### 2. Timetable Generation
* **`POST /api/v1/scheduler/generate/{timetable_id}`**
  * **Description:** Triggers the asynchronous background generation of class timetables for a specific timetable context.
  * **Protection:** Consumes quota. Warns or blocks at metric limits.

### 3. Public Data Export
* **`GET /api/v1/export/tenant-data`**
  * **Description:** Extracts your entire university's data as a clean JSON backup.
  * **Access:** Restricted to `COORDINATOR` and `SUPERADMIN` level users.

## Rate Limiting
To ensure platform stability, TABLESYS strictly enforces rate limiting on public-facing APIs. The system will return `429 Too Many Requests` if abused, and provides tracking headers per transaction:
* `X-RateLimit-Limit`: The total number of requests permitted in the sliding time window.
* `X-RateLimit-Remaining`: The number of requests remaining in the current window.

## Interactive Docs
For full schema details, test payloads, and Swagger UI, append `/docs` to the root URL of your active deployed TABLESYS instance (e.g. `https://api.tablesys.app/docs`). All endpoints adhere perfectly to OpenAPI v3 specifications.