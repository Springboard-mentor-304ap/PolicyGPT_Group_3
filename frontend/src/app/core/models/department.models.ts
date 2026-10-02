/**
 * Department models — mapped to `backend/app/departments/schemas.py`.
 *
 *   GET /api/departments -> DepartmentOptionsResponse
 *
 * `department` is a free-form string column, so the option list is derived
 * from the values already stored on policies and schemes rather than from a
 * hardcoded catalogue.
 */

export interface DepartmentOptionsResponse {
  departments: string[];
}
