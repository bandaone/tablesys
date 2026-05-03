import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import TableSkeleton from '../components/skeletons/TableSkeleton';
import {
  Box,
  Button,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  Chip,
  Tooltip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
  Card,
  CardContent,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  LinearProgress,
  Divider,
} from '@mui/material';
import {
  Add as AddIcon,
  Assessment as AssessmentIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Upload as UploadIcon,
  Download as DownloadIcon,
  ExpandMore as ExpandMoreIcon,
  School as SchoolIcon,
} from '@mui/icons-material';
import { coursesAPI, departmentsAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';
import { CourseGroupAssigner } from '../components/CourseGroupAssigner';

interface CourseRow {
  id: number;
  code: string;
  name: string;
  department_id: number;
  level: number;
  credits: number;
  lecture_hours: number;
  tutorial_hours: number;
  practical_hours: number;
  shared_with_department_ids?: number[];
}

interface DepartmentRow {
  id: number;
  code?: string;
  name: string;
}

const CoursesPage: React.FC = () => {
  const [courses, setCourses] = useState<CourseRow[]>([]);
  const [departments, setDepartments] = useState<DepartmentRow[]>([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [openUploadDialog, setOpenUploadDialog] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingCourse, setEditingCourse] = useState<any>(null);
  const [groupAssignCourse, setGroupAssignCourse] = useState<any>(null);
  const [groupAssignDialogOpen, setGroupAssignDialogOpen] = useState(false);
  const [clearAllDialogOpen, setClearAllDialogOpen] = useState(false);
  const [dialogError, setDialogError] = useState('');
  const [formData, setFormData] = useState({
    code: '',
    name: '',
    department_id: '',
    level: 100,
    credits: 3,
    lecture_hours: 2,
    tutorial_hours: 0,
    practical_hours: 0,
    shared_with_department_ids: [] as number[],
  });

  const [searchParams, setSearchParams] = useSearchParams();
  const deptFilter = searchParams.get('dept');

  const { user, isCoordinator, isHOD } = useAuth();

  useEffect(() => {
    fetchCourses();
    fetchDepartments();
  }, []);

  const fetchCourses = async () => {
    try {
      const data = await coursesAPI.getAll();
      setCourses(data);
    } catch (err) {
      console.error('Error fetching courses:', err);    } finally {
      setPageLoading(false);    }
  };

  const fetchDepartments = async () => {
    try {
      const data = await departmentsAPI.getAll();
      setDepartments(data);
    } catch (err) {
      console.error('Error fetching departments:', err);
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this course?')) {
      try {
        await coursesAPI.delete(id);
        fetchCourses();
      } catch (err) {
        setError('Error deleting course');
      }
    }
  };

  const handleClearAll = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await coursesAPI.deleteAll();
      setClearAllDialogOpen(false);
      alert(`Successfully deleted ${result.deleted} courses`);
      fetchCourses();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error clearing courses');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      setSelectedFile(event.target.files[0]);
    }
  };

  const handleBulkUpload = async () => {
    if (!selectedFile) {
      setError('Please select a file');
      return;
    }

    setLoading(true);
    setError('');
    setUploadResult(null);

    try {
      const result = await coursesAPI.bulkUpload(selectedFile);
      setUploadResult(result);
      fetchCourses();
      if (result.skipped === 0) {
        setTimeout(() => {
          setOpenUploadDialog(false);
          setSelectedFile(null);
          setUploadResult(null);
          const input = document.getElementById('file-upload') as HTMLInputElement;
          if (input) input.value = '';
        }, 3000);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error uploading file');
    } finally {
      setLoading(false);
    }
  };

  const downloadMasterCSV = () => {
    const link = document.createElement('a');
    link.href = '/assets/course_import_template.csv';
    link.download = 'course_import_template.csv';
    link.click();
  };

  const getDepartmentName = (deptId: number) => {
    const dept = departments.find(d => d.id === deptId);
    return dept ? dept.name : 'Unknown';
  };

  const getDepartmentCode = (deptId: number) => {
    const dept = departments.find(d => d.id === deptId);
    return dept ? (dept.code || dept.name.substring(0, 3).toUpperCase()) : 'UNK';
  };

  const canManageCourseMapping = (course: CourseRow) => {
    if (isCoordinator) return true;
    return isHOD && user?.department_id === course.department_id;
  };

  // Filter and Group courses by level
  const filteredCourses = deptFilter
    ? courses.filter(c => c.department_id === parseInt(deptFilter))
    : courses;

  const coursesByLevel = filteredCourses.reduce((acc, course) => {
    if (!acc[course.level]) acc[course.level] = [];
    acc[course.level].push(course);
    return acc;
  }, {} as Record<number, typeof courses>);

  // Sort courses within each level
  Object.values(coursesByLevel).forEach((levelCourses: CourseRow[]) => {
    levelCourses.sort((a, b) => a.code.localeCompare(b.code));
  });

  // Calculate statistics
  const stats = {
    total: courses.length,
    byLevel: Object.keys(coursesByLevel).reduce((acc, level) => {
      acc[level] = coursesByLevel[parseInt(level)].length;
      return acc;
    }, {} as Record<string, number>),
    byDepartment: courses.reduce((acc, course) => {
      const code = getDepartmentCode(course.department_id);
      acc[code] = (acc[code] || 0) + 1;
      return acc;
    }, {} as Record<string, number>),
  };

  const handleSaveCourse = async () => {
    setDialogError('');
    try {
      if (editingCourse) {
        await coursesAPI.update(editingCourse.id, formData);
      } else {
        await coursesAPI.create(formData);
      }
      setOpenDialog(false);
      setEditingCourse(null);
      setDialogError('');
      setFormData({
        code: '',
        name: '',
        department_id: '',
        level: 1,
        credits: 3,
        lecture_hours: 2,
        tutorial_hours: 0,
        practical_hours: 0,
        shared_with_department_ids: [],
      });
      fetchCourses();
    } catch (e: unknown) {
      const err = (e as any);
      const detail = err?.response?.data?.detail;
      // detail can be a string or a FastAPI validation array
      if (Array.isArray(detail)) {
        setDialogError(detail.map((d: any) => d.msg || d).join(', '));
      } else {
        setDialogError(detail || err?.message || 'Failed to save course');
      }
    }
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Typography variant="h4" fontWeight="600" color="primary.main">
          Course Management
        </Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          {deptFilter && (
            <Button
              variant="outlined"
              onClick={() => { setSearchParams({}); }}
              sx={{ textTransform: 'none' }}
            >
              Show All Departments
            </Button>
          )}
          {isCoordinator && (
            <Button
              variant="outlined"
              color="error"
              onClick={() => { setClearAllDialogOpen(true); }}
              sx={{ textTransform: 'none' }}
            >
              Clear All Courses
            </Button>
          )}
          <Button
            variant="outlined"
            startIcon={<UploadIcon />}
            onClick={() => setOpenUploadDialog(true)}
            sx={{ textTransform: 'none' }}
          >
            Bulk Upload
          </Button>
          {isHOD && (
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => {
                setEditingCourse(null);
                setOpenDialog(true);
              }}
              sx={{ textTransform: 'none' }}
            >
              Add Course
            </Button>
          )}
        </Box>
      </Box>

      {/* Statistics Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={3}>
          <Card elevation={2}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Total Courses
                  </Typography>
                  <Typography variant="h4" fontWeight="600">
                    {stats.total}
                  </Typography>
                </Box>
                <SchoolIcon sx={{ fontSize: 40, color: 'primary.main', opacity: 0.6 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {Object.entries(stats.byLevel).map(([level, count]) => (
          <Grid item xs={6} md={2.25} key={level}>
            <Card elevation={2}>
              <CardContent>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Year {level}
                </Typography>
                <Typography variant="h5" fontWeight="600">
                  {count} courses
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => { setError(''); }}>
          {error}
        </Alert>
      )}

      {/* Course Tables by Level */}
      {pageLoading ? (<TableSkeleton rows={8} columns={5} />) : (
      <Box>
        {Object.keys(coursesByLevel)
          .map(Number)
          .sort((a, b) => b - a)
          .map(level => {
          const levelCourses = coursesByLevel[level] || [];
          if (levelCourses.length === 0) return null;

          return (
            <Accordion key={level} defaultExpanded={level >= 3} sx={{ mb: 2 }}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ bgcolor: 'grey.50' }}>
                <Typography variant="h6" fontWeight="600">
                  Year {level} Courses
                  <Chip
                    label={`${levelCourses.length} courses`}
                    size="small"
                    sx={{ ml: 2 }}
                    color="primary"
                  />
                </Typography>
              </AccordionSummary>
              <AccordionDetails sx={{ p: 0 }}>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow sx={{ bgcolor: 'primary.main' }}>
                        <TableCell sx={{ color: 'white', fontWeight: 'bold', width: '12%' }}>Code</TableCell>
                        <TableCell sx={{ color: 'white', fontWeight: 'bold', width: '35%' }}>Name</TableCell>
                        <TableCell sx={{ color: 'white', fontWeight: 'bold', width: '15%' }}>Department</TableCell>
                        <TableCell sx={{ color: 'white', fontWeight: 'bold', width: '10%' }}>Credits</TableCell>
                        <TableCell sx={{ color: 'white', fontWeight: 'bold', width: '18%' }}>Contact Hours</TableCell>
                        {(isCoordinator || isHOD) && (
                          <TableCell sx={{ color: 'white', fontWeight: 'bold', width: '10%' }}>Actions</TableCell>
                        )}
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {levelCourses.map((course) => (
                        <TableRow key={course.id} hover>
                          <TableCell>
                            <Typography variant="body2" fontWeight="600" fontFamily="monospace">
                              {course.code}
                            </Typography>
                          </TableCell>
                          <TableCell>{course.name}</TableCell>
                          <TableCell>
                            <Chip
                              label={getDepartmentCode(course.department_id)}
                              size="small"
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell>{course.credits}</TableCell>
                          <TableCell>
                            <Typography variant="body2" color="text.secondary">
                              L: {course.lecture_hours} | T: {course.tutorial_hours} | P: {course.practical_hours}
                            </Typography>
                          </TableCell>
                          {(isCoordinator || isHOD) && (
                            <TableCell>
                              {canManageCourseMapping(course) && (
                                <Tooltip title="Edit">
                                  <IconButton
                                    size="small"
                                    color="primary"
                                    onClick={() => {
                                      setEditingCourse(course);
                                      setFormData({
                                        code: course.code,
                                        name: course.name,
                                        department_id: String(course.department_id),
                                        level: course.level,
                                        credits: course.credits,
                                        lecture_hours: course.lecture_hours,
                                        tutorial_hours: course.tutorial_hours,
                                        practical_hours: course.practical_hours,
                                        shared_with_department_ids: course.shared_with_department_ids || [],
                                      });
                                      setDialogError('');
                                      setOpenDialog(true);
                                    }}
                                  >
                                    <EditIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              )}

                              {canManageCourseMapping(course) && (
                                <Tooltip title="Manage Groups For This Course">
                                  <IconButton
                                    size="small"
                                    color="info"
                                    onClick={() => {
                                      setGroupAssignCourse(course);
                                      setGroupAssignDialogOpen(true);
                                    }}
                                  >
                                    <AssessmentIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              )}
                              
                              {canManageCourseMapping(course) && (
                                <Tooltip title="Delete">
                                  <IconButton
                                    size="small"
                                    color="error"
                                    onClick={() => { void handleDelete(course.id); }}
                                  >
                                    <DeleteIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              )}
                            </TableCell>
                          )}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </AccordionDetails>
            </Accordion>
          );
        })}
      </Box>
      )}

      {/* Add/Edit Course Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>{editingCourse ? 'Edit Course' : 'Add New Course'}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mt: 1 }}>
            <TextField
              label="Course Code"
              value={formData.code}
              onChange={(e) => { setFormData({ ...formData, code: e.target.value.toUpperCase() }); }}
              fullWidth
              required
            />
            <FormControl fullWidth required>
              <InputLabel>Department</InputLabel>
              <Select
                value={formData.department_id}
                label="Department"
                onChange={(e) => { setFormData({ ...formData, department_id: e.target.value as unknown as string }); }}
              >
                {departments.map((dept: any) => (
                  <MenuItem key={dept.id} value={dept.id}>
                    {dept.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Course Name"
              value={formData.name}
              onChange={(e) => { setFormData({ ...formData, name: e.target.value }); }}
              fullWidth
              required
              sx={{ gridColumn: 'span 2' }}
            />
            <FormControl fullWidth required>
              <InputLabel>Level</InputLabel>
              <Select
                value={formData.level}
                label="Level"
                onChange={(e) => { setFormData({ ...formData, level: parseInt(e.target.value as string) || 1 }); }}
              >
                {[1, 2, 3, 4, 5, 6, 7].map(val => (
                  <MenuItem key={val} value={val}>Year {val}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>Shared Details (Depts)</InputLabel>
              <Select
                multiple
                value={formData.shared_with_department_ids}
                label="Shared Details (Depts)"
                onChange={(e) => { 
                  const val = e.target.value;
                  setFormData({ ...formData, shared_with_department_ids: typeof val === 'string' ? val.split(',').map(Number) : val as number[] }); 
                }}
                renderValue={(selected) => (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {(selected as number[]).map((val) => {
                      const dept = departments.find(d => d.id === val);
                      return <Chip key={val} label={dept?.code || val} size="small" />;
                    })}
                  </Box>
                )}
              >
                {departments.map((dept: any) => (
                  <MenuItem key={dept.id} value={dept.id}>
                    {dept.code}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Credits"
              type="number"
              value={formData.credits}
              onChange={(e) => { setFormData({ ...formData, credits: parseInt(e.target.value) || 0 }); }}
              fullWidth
            />
            <TextField
              label="Lecture Hours"
              type="number"
              value={formData.lecture_hours}
              onChange={(e) => { setFormData({ ...formData, lecture_hours: parseInt(e.target.value) || 0 }); }}
              fullWidth
            />
            <TextField
              label="Tutorial Hours"
              type="number"
              value={formData.tutorial_hours}
              onChange={(e) => { setFormData({ ...formData, tutorial_hours: parseInt(e.target.value) || 0 }); }}
              fullWidth
            />
            <TextField
              label="Practical Hours"
              type="number"
              value={formData.practical_hours}
              onChange={(e) => { setFormData({ ...formData, practical_hours: parseInt(e.target.value) || 0 }); }}
              fullWidth
              sx={{ gridColumn: 'span 2' }}
            />
          </Box>
          {dialogError && (
            <Alert severity="error" sx={{ mx: 3, mb: 1 }}>{dialogError}</Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setOpenDialog(false); }}>Cancel</Button>
          <Button onClick={() => { void handleSaveCourse(); }} variant="contained">
            {editingCourse ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Bulk Upload Dialog */}
      <Dialog
        open={openUploadDialog}
        onClose={() => {
          setOpenUploadDialog(false);
          setSelectedFile(null);
          setUploadResult(null);
          // Reset the file input element so the same file can be re-selected
          const input = document.getElementById('file-upload') as HTMLInputElement;
          if (input) input.value = '';
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Bulk Upload Courses</DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 2 }}>
            {!uploadResult && (
              <>
                <Alert severity="info" sx={{ mb: 2 }}>
                  Upload a <strong>CSV or Excel</strong> file with your course data.
                  <Box component="ul" sx={{ mt: 1, mb: 0, pl: 2 }}>
                    <li>Accepted formats: .csv, .xlsx, .xls</li>
                    <li>Maximum file size: 5 MB</li>
                    <li>Duplicate entries will be automatically skipped</li>
                  </Box>
                </Alert>

                {isCoordinator && (
                  <Button
                    variant="outlined"
                    startIcon={<DownloadIcon />}
                    onClick={downloadMasterCSV}
                    fullWidth
                    sx={{ mb: 2, textTransform: 'none' }}
                  >
                    Download Import Template
                  </Button>
                )}

                <Divider sx={{ my: 2 }} />

                <input
                  accept=".csv,.xlsx,.xls"
                  style={{ display: 'none' }}
                  id="file-upload"
                  type="file"
                  onChange={handleFileSelect}
                />
                <label htmlFor="file-upload">
                  <Button
                    variant={selectedFile ? 'contained' : 'outlined'}
                    component="span"
                    fullWidth
                    sx={{ py: 1.5, textTransform: 'none' }}
                  >
                    {selectedFile ? `✓ ${selectedFile.name}` : 'Select File'}
                  </Button>
                </label>
              </>
            )}

            {loading && <LinearProgress sx={{ mt: 2 }} />}

            {uploadResult && (
              <Box>
                <Alert
                  severity={uploadResult.errors && uploadResult.errors.length > 0 ? 'warning' : 'success'}
                  sx={{ mb: 2 }}
                >
                  <strong>{uploadResult.created} course{uploadResult.created !== 1 ? 's' : ''} successfully imported.</strong>
                  {uploadResult.skipped > 0 && (
                    <Box sx={{ mt: 0.5 }}>
                      {uploadResult.skipped} row{uploadResult.skipped !== 1 ? 's' : ''} skipped (duplicates or errors).
                    </Box>
                  )}
                </Alert>

                {uploadResult.errors && uploadResult.errors.length > 0 && (
                  <Box sx={{ maxHeight: 220, overflowY: 'auto', border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1.5 }}>
                    <Typography variant="caption" fontWeight="bold" color="error" display="block" sx={{ mb: 1 }}>
                      Rows that could not be imported:
                    </Typography>
                    {uploadResult.errors.map((err: string, i: number) => (
                      <Typography key={i} variant="caption" display="block" color="text.secondary" sx={{ mb: 0.5 }}>
                        • {err}
                      </Typography>
                    ))}
                  </Box>
                )}

                <Button
                  variant="outlined"
                  fullWidth
                  sx={{ mt: 2, textTransform: 'none' }}
                  onClick={() => {
                    setSelectedFile(null);
                    setUploadResult(null);
                    const input = document.getElementById('file-upload') as HTMLInputElement;
                    if (input) input.value = '';
                  }}
                >
                  Upload Another File
                </Button>
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          {uploadResult ? (
            <Button
              variant="contained"
              onClick={() => {
                setOpenUploadDialog(false);
                setSelectedFile(null);
                setUploadResult(null);
                const input = document.getElementById('file-upload') as HTMLInputElement;
                if (input) input.value = '';
              }}
            >
              Done
            </Button>
          ) : (
            <>
              <Button onClick={() => { 
                setOpenUploadDialog(false); 
                setSelectedFile(null); 
                setUploadResult(null); 
                const input = document.getElementById('file-upload') as HTMLInputElement;
                if (input) input.value = '';
              }}>Cancel</Button>
              <Button
                onClick={() => { void handleBulkUpload(); }}
                variant="contained"
                disabled={!selectedFile || loading}
              >
                {loading ? 'Uploading...' : 'Upload'}
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>

      {/* Clear All Confirmation Dialog */}
      <Dialog open={clearAllDialogOpen} onClose={() => setClearAllDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Clear All Courses?</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mt: 1 }}>
            This will permanently delete all {stats.total} courses from the system. This action cannot be undone.
          </Alert>
          <Typography sx={{ mt: 2 }}>
            Are you sure you want to proceed?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setClearAllDialogOpen(false); }}>Cancel</Button>
          <Button onClick={() => { void handleClearAll(); }} variant="contained" color="error" disabled={loading}>
            {loading ? 'Deleting...' : 'Delete All Courses'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={groupAssignDialogOpen}
        onClose={() => {
          setGroupAssignDialogOpen(false);
          setGroupAssignCourse(null);
        }}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Manage Groups For This Course</DialogTitle>
        <DialogContent>
          {groupAssignCourse && (
            <CourseGroupAssigner
              courseId={groupAssignCourse.id}
              courseLevel={groupAssignCourse.level}
              onSaved={() => { void fetchCourses(); }}
            />
          )}
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setGroupAssignDialogOpen(false);
              setGroupAssignCourse(null);
            }}
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default CoursesPage;
