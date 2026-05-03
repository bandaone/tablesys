import fs from 'fs';

let content = fs.readFileSync('/home/on3/DENNIS/TABLESYS/frontend/src/pages/CoursesPage.tsx', 'utf8');

// Add pageLoading state
content = content.replace(
  "const [loading, setLoading] = useState(false);",
  "const [loading, setLoading] = useState(false);\n  const [pageLoading, setPageLoading] = useState(true);"
);

// Add import for TableSkeleton
content = content.replace(
  "import { useSearchParams }",
  "import TableSkeleton from '../components/skeletons/TableSkeleton';\nimport { useSearchParams }"
);

// Update fetchCourses
content = content.replace(
  "const fetchCourses = async () => {\n      try {\n        const data = await coursesAPI.getAll() as Course[];\n        setCourses(data);\n      } catch (err) {\n        console.error('Error fetching courses:', err);\n      }\n    };",
  "const fetchCourses = async () => {\n      try {\n        const data = await coursesAPI.getAll() as Course[];\n        setCourses(data);\n      } catch (err) {\n        console.error('Error fetching courses:', err);\n      } finally {\n        setPageLoading(false);\n      }\n    };"
);

// Wrap table container in loading check
const targetString = "{/* Course Tables by Level */}";
const replaceString = "{/* Course Tables by Level */}\n          {pageLoading ? (<TableSkeleton rows={8} columns={5} />) : (\n            <Box>";

content = content.replace(targetString, replaceString);

// Close the Box check
content = content.replace(
  "            </Box>\n          )}",
  "            </Box>\n          )}\n          </Box>\n          )} // Close pageLoading Box wrapper"
);

fs.writeFileSync('/home/on3/DENNIS/TABLESYS/frontend/src/pages/CoursesPage.tsx', content);

