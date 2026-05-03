import re

with open('/home/on3/DENNIS/TABLESYS/frontend/src/pages/DashboardPage.tsx', 'r') as f:
    content = f.read()

# Only replace once
if "DashboardSkeleton" not in content:
    content = content.replace(
        "import TimetableAnalytics from '../components/TimetableAnalytics';",
        "import TimetableAnalytics from '../components/TimetableAnalytics';\nimport DashboardSkeleton from '../components/skeletons/DashboardSkeleton';"
    )

if "pageLoading" not in content:
    content = content.replace(
        "const [readinessLoading, setReadinessLoading] = useState(true);",
        "const [readinessLoading, setReadinessLoading] = useState(true);\n  const [pageLoading, setPageLoading] = useState(true);"
    )

old_fetch = """  const fetchStats = async () => {
    try {
      const [courses, lecturers, rooms, groups] = await Promise.all([
        coursesAPI.getAll(),
        lecturersAPI.getAll(),
        roomsAPI.getAll(),
        groupsAPI.getAll(),
      ]);
      setStats({ courses: courses.length, lecturers: lecturers.length, rooms: rooms.length, groups: groups.length });
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };"""

new_fetch = """  const fetchStats = async () => {
    try {
      const [courses, lecturers, rooms, groups] = await Promise.all([
        coursesAPI.getAll(),
        lecturersAPI.getAll(),
        roomsAPI.getAll(),
        groupsAPI.getAll(),
      ]);
      setStats({ courses: courses.length, lecturers: lecturers.length, rooms: rooms.length, groups: groups.length });
    } catch (err) {
      console.error('Error fetching stats:', err);
    } finally {
      setPageLoading(false);
    }
  };"""

content = content.replace(old_fetch, new_fetch)

content = content.replace(
    "  return (\n    <Box",
    "  if (pageLoading) return <DashboardSkeleton />;\n\n  return (\n    <Box"
)

with open('/home/on3/DENNIS/TABLESYS/frontend/src/pages/DashboardPage.tsx', 'w') as f:
    f.write(content)

