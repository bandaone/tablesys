# Getting Started with TABLESYS

Welcome to TABLESYS, the automated SaaS timetable generation platform for universities. This guide will walk you through the essential first steps needed to prepare your tenant environment for timetable generation.

## 1. Onboarding and Initial Setup

When your university's account is verified and provisioned, a default environment is spun up instantly. The onboarding sequence will prompt you to set your defaults, but here are the core models you must understand:

- **University Branding:** Logos and colors used by both the student mobile app and lecturer interfaces.
- **Academic Calendar:** Represents Semesters/Terms spanning given dates.
- **Quotas:** Based on your plan (Starter / Professional / Enterprise), your tenant is provisioned with a set amount of active seats, allowed monthly timetable generations, and overall department capacity.

## 2. Core Data Flow

Timetables cannot be generated from thin air. The TABLESYS constraint solver requires data in a specific hierarchy:

1. **Departments:** Establish who manages the curriculum.
2. **Venues:** Establish where teaching happens and capacity limits.
3. **Courses:** Set up the curriculum.
4. **Lecturers:** The teaching resources linked to the courses.
5. **Student Groups:** Cohorts of students that take groups of courses together.

## 3. Preparation Pathway

Rather than entering data one by one, TABLESYS supports bulk uploads via CSV to make this process painless:

* **Step 1:** Read through the [Data Templates and Validations Rules](./02-data-templates-and-rules.md) to understand mapping.
* **Step 2:** Download the sample CSVs from the admin dashboard and populate them.
* **Step 3:** Use the automated data importer. The system strictly validates the data (e.g., checking that lecturers have valid email formats or venues have capacities > 0) before saving.
* **Step 4:** Follow the [Timetable Generation Guide](./03-timetable-generation-guide.md) to kick off the background solver.

If you encounter errors during uploading or solving, refer to our [Troubleshooting Guide](./04-troubleshooting.md).