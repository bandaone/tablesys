# Troubleshooting and Common Errors

If you encounter issues during your TABLESYS setup or usage, refer to these common errors and fixes.

## 1. Import / CSV Upload Errors

**Error:** `Department [Name] does not exist.`
* **Cause:** You uploaded courses or lecturers mapping to a department name that has not been created yet in the database.
* **Fix:** Ensure you upload your Departments template first, or spell the department name exactly as it appears in the system.

**Error:** `Invalid email format for xyz`
* **Cause:** The CSV row for a lecturer or student contains a broken email string.
* **Fix:** Correct the email string formats and re-upload. Clean out trailing spaces.

## 2. Timetable Generation Errors

**Error:** `402 Payment Required: Quota Exceeded for metric timetable_generations`
* **Cause:** You have run out of allocated AI timetable generations for you current billing cycle. (Starter plans allow limited monthly generations).
* **Fix:** You can either wait until the 1st of the next month for the quota to reset, or contact your platform administrator to upgrade your SaaS tier.

**Error:** `Unsatisfiable Constraint: Capacity limits impossible`
* **Cause:** The solver could not find a mathematical answer. For example, if you have a Course with 800 enrolled students, but your largest Venue only holds 500.
* **Fix:** Check your Course enrollments against your Venue capacities. You either need to split the large course into two separate cohorts or add larger venues.

## 3. Account / Login Issues

**Error:** `429 Too Many Requests`
* **Cause:** The public API rate limit kicked in. We strictly limit login attempts and public registration submissions per hour to prevent abuse.
* **Fix:** Wait an hour for the rate limit to expire. 

## General Support
If you've encountered an issue not listed here, please export your tenant audit logs and reach out to our team:
* **Starter and Professional users:** Email us at `support@tablesys.com`.
* **Enterprise users:** Contact your dedicated support channel included in your enterprise agreement.