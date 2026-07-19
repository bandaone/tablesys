# Timetable Generation Guide

Generating a conflict-free timetable involves kicking off asynchronous background solvers. Due to the high computational intensity of constraint satisfaction, generation occurs in the background and notifies you when completed.

## 1. Prerequisites for Generation

Before triggering a generation task, ensure the following:
* You have sufficient **Timetable Generation Quota** left in your plan for the month. (You can check this in the *Billing & Usage* dashboard).
* Your core data (Venues, Courses, Lecturers, and Groups) has been successfully uploaded for the department or entire university.
* You have defined an **Academic Calendar Period** (e.g. "Fall 2026").

## 2. Setting Up Constraints

TABLESYS operates on two types of rules:
* **Hard Constraints (Mandatory):** Things that absolutely cannot be violated.
    * No teacher can be in two places at once.
    * Room capacity must be `>` course enrollment.
* **Soft Constraints (Preferences):** Things the algorithm will try to optimize for, up to a mathematical limit.
    * Minimize gaps between classes for students.
    * Keep departments in their preferred venues.

*Note: You can tweak grid configurations, such as teaching hours (e.g., 08:00 to 18:00) before clicking generate.*

## 3. Running the Generator

### Via the App
1. Navigate to the **Timetable Workspace**.
2. Select the **Term/Semester** targeting the generation.
3. Select scope (**Entire University** or **Specific Department**).
4. Click **Generate Timetable**.

### What Happens Next?
1. **Validation & Quota Check:** The system validates your data and deducts `1` generation from your quota. (If your plan limit is reached, it will block generation).
2. **Enqueued:** A background Celery worker picks up the heavy mathematical sorting.
3. **Solving:** During this time, the workspace will read *In Progress*.
4. **Completion:** When the constraint solver finishes, you receive an in-app notification. You can then review, manually tweak via the drag-and-drop board, and finally **Publish** to users.