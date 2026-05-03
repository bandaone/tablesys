import re

with open('/home/on3/DENNIS/TABLESYS/frontend/src/pages/CoursesPage.tsx', 'r') as f:
    content = f.read()

content = content.replace(
    "import { useSearchParams }",
    "import TableSkeleton from '../components/skeletons/TableSkeleton';\nimport { useSearchParams }"
)

content = content.replace(
    "const [loading, setLoading] = useState(false);",
    "const [loading, setLoading] = useState(false);\n  const [pageLoading, setPageLoading] = useState(true);"
)

old_fetch = """    const fetchCourses = async () => {
      try {
        const data = await coursesAPI.getAll() as Course[];
        setCourses(data);
      } catch (err) {
        console.error('Error fetching courses:', err);
      }
    };"""

new_fetch = """    const fetchCourses = async () => {
      try {
        const data = await coursesAPI.getAll() as Course[];
        setCourses(data);
      } catch (err) {
        console.error('Error fetching courses:', err);
      } finally {
        setPageLoading(false);
      }
    };"""

content = content.replace(old_fetch, new_fetch)

# Now wrap the courses table mapping
old_tables = """          {/* Course Tables by Level */}
          <Box>"""

new_tables = """          {/* Course Tables by Level */}
          {pageLoading ? (<TableSkeleton rows={8} columns={5} />) : (
          <Box>"""

content = content.replace(old_tables, new_tables)

old_end = """              );
            })}
          </Box>"""

new_end = """              );
            })}
          </Box>
          )}"""
content = content.replace(old_end, new_end)


with open('/home/on3/DENNIS/TABLESYS/frontend/src/pages/CoursesPage.tsx', 'w') as f:
    f.write(content)

