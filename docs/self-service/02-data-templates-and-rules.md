# Data Templates and Validation Rules

To quickly populate your TABLESYS environment, use our bulk CSV import endpoints. This document outlines the expected format for each standard upload. 

## 1. Venues Template

Defines physical locations where classes or exams can take place.

| Column | Required | Data Type | Notes |
| :--- | :--- | :--- | :--- |
| `name` | **Yes** | String | Must be unique within the tenant. Example: "Main Hall A" |
| `capacity` | **Yes** | Integer | Must be > 0. Used by the constraint solver to guarantee no over-enrollment. |
| `type` | No | Enum | e.g. "Lecture Room", "Laboratory". Defaults to "Lecture Room". |
| `department_name`| No | String | If provided, assigns primary ownership of this venue to a department. |

## 2. Courses Template

Defines the curriculum to be scheduled.

| Column | Required | Data Type | Notes |
| :--- | :--- | :--- | :--- |
| `code` | **Yes** | String | Must be unique. Example: "CS301" |
| `name` | **Yes** | String | Example: "Data Structures & Algorithms" |
| `department_name`| **Yes** | String | Must match an existing Department. |
| `credits` | No | Integer | Must be > 0. Used to calculate default required contact hours. |
| `lecture_hours` | No | Integer | Number of hours for theoretical lectures per week. |
| `tutorial_hours` | No | Integer | Number of hours for tutorials per week. |
| `practical_hours`| No | Integer | Number of hours for laboratory/practical sessions per week. |

## 3. Lecturers Template

Defines teaching staff.

| Column | Required | Data Type | Notes |
| :--- | :--- | :--- | :--- |
| `email` | **Yes** | String | Unique valid email. Used for account creation and invites. |
| `first_name` | **Yes** | String | |
| `last_name` | **Yes** | String | |
| `department_name`| **Yes** | String | Must match an existing Department. |
| `max_hours_week` | No | Integer | Defaults to 40. Used as a hard solver constraint. |

## 4. Student Groups Template

Defines the student cohorts that will be attending the courses.

| Column | Required | Data Type | Notes |
| :--- | :--- | :--- | :--- |
| `name` | **Yes** | String | Unique group name. Example: "BCS Year 1" |
| `level` | **Yes** | Integer | The academic year level (e.g., 1). |
| `size` | **Yes** | Integer | The number of students in the group. Critical for venue capacity checks. |
| `group_type` | No | Enum | e.g. "Main", "Tutorial", "Practical". Defaults to "Main". |
| `parent_group_id`| No | Integer | References another group's ID if this is a sub-split (like a practical group). |

## Data Validation Constraints
When uploading, TABLESYS performs the following checks:
1. **Uniqueness:** Re-uploading a course with the same `code` will update it, meaning templates are idempotent.
2. **Missing Dependencies:** A course mapped to a `department_name` that does not exist will fail the row.
3. **Format Integrity:** Emails must be strictly valid. 

You can download the raw empty templates directly from the Application Dashboard or via the API.