import fs from 'fs';

let content = fs.readFileSync('/home/on3/DENNIS/TABLESYS/frontend/src/pages/DashboardPage.tsx', 'utf8');

content = content.replace(
  "import TimetableAnalytics from '../components/TimetableAnalytics';",
  "import TimetableAnalytics from '../components/TimetableAnalytics';\nimport DashboardSkeleton from '../components/skeletons/DashboardSkeleton';"
);

content = content.replace(
  "const [readinessLoading, setReadinessLoading] = useState(true);",
  "const [readinessLoading, setReadinessLoading] = useState(true);\n  const [pageLoading, setPageLoading] = useState(true);"
);

content = content.replace(
  "const fetchStats = async () => {",
  "const fetchStats = async () => {\n    try {\n      const [courses, lecturers, rooms, groups] = await Promise.all([\n        coursesAPI.getAll(),\n        lecturersAPI.getAll(),\n        roomsAPI.getAll(),\n        groupsAPI.getAll(),\n      ]);\n      setStats({ courses: courses.length, lecturers: lecturers.length, rooms: rooms.length, groups: groups.length });\n    } catch (err) {\n      console.error('Error fetching stats:', err);\n    } finally {\n      setPageLoading(false);\n    }\n  };\n\n  // Original fetchStats:"
);

const renderCheck = "const DashboardPage: React.FC = () => {";
content = content.replace(
  "  return (\n    <Box",
  "  if (pageLoading) return <DashboardSkeleton />;\n\n  return (\n    <Box"
);

fs.writeFileSync('/home/on3/DENNIS/TABLESYS/frontend/src/pages/DashboardPage.tsx', content);

