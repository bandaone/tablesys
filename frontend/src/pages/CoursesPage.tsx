import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
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
  Edit as EditIcon,
  Delete as DeleteIcon,
  Upload as UploadIcon,
  Download as DownloadIcon,
  ExpandMore as ExpandMoreIcon,
  School as SchoolIcon,
  Assessment as AssessmentIcon,
} from '@mui/icons-material';
import { coursesAPI, departmentsAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';

const CoursesPage: React.FC = () => {
  const [courses, setCourses] = useState<unknown[]>([]);
  const [departments, setDepartments] = useState<unknown[]>([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [openUploadDialog, setOpenUploadDialog] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [editingCourse, setEditingCourse] = useState<unknown>(null);
  const [clearAllDialogOpen, setClearAllDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    code: '',
    name: '',
    department_id: '',
    level: 2,
    credits: 3,
    lecture_hours: 2,
    tutorial_hours: 0,
    practical_hours: 0,
  });

  const [searchParams, setSearchParams] = useSearchParams();
  const deptFilter = searchParams.get('dept');

  const { user, isCoordinator } = useAuth();

  useEffect(() => {
    fetchCourses();
    fetchDepartments();
  }, []);

  const fetchCourses = async () => {
    try {
      const data = await coursesAPI.getAll();
      setCourses(data);
    } catch (err) {
      console.error('Error fetching courses:', err);
    }
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
      setTimeout(() => {
        setOpenUploadDialog(false);
        setSelectedFile(null);
        setUploadResult(null);
      }, 4000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error uploading file');
    } finally {
      setLoading(false);
    }
  };

  const downloadMasterCSV = () => {
    const link = document.createElement('a');
    link.href = '/backend/engineering_courses_ master_corrected.csv';
    link.download = 'engineering_courses_master_corrected.csv';
    link.click();
  };

  const getDepartmentName = (deptId: number) => {
    const dept = departments.find(d => d.id === deptId);
    return dept ? dept.name : 'Unknown';
  };

  const getDepartmentCode = (deptId: number) => {
    const codes: Record<number, string> = { 0: 'GEN', 1: 'AEN', 2: 'CEE', 3: 'EEE', 4: 'GEE', 5: 'MEC' };
    return codes[deptId] || 'UNK';
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
  Object.values(coursesByLevel).forEach(levelCourses => {
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
    try {
      if (editingCourse) {
        await coursesAPI.update(editingCourse.id, formData);
      } else {
        await coursesAPI.create(formData);
      }
      setOpenDialog(false);
      setEditingCourse(null);
      setFormData({
        code: '',
        name: '',
        department_id: '',
        level: 2,
        credits: 3,
        lecture_hours: 2,
        tutorial_hours: 0,
        practical_hours: 0,
      });
      fetchCourses();
    } catch (e: unknown) {
      setError((e as any).response?.data?.detail || 'Failed to save course');
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
          {isCoordinator && (
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
      <Box>
        {[2, 3, 4, 5].map(level => {
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
                        {isCoordinator && (
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
                          {isCoordinator && (
                            <TableCell>
                              <Tooltip title="Edit">
                                <IconButton
                                  size="small"
                                  color="primary"
                                  onClick={() => {
                                    setEditingCourse(course);
                                    setFormData(course);
                                    setOpenDialog(true);
                                  }}
                                >
                                  <EditIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                              <Tooltip title="Delete">
                                <IconButton
                                  size="small"
                                  color="error"
                                  onClick={() => { void handleDelete(course.id); }}
                                >
                                  <DeleteIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
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
                onChange={(e) => { setFormData({ ...formData, level: e.target.value as unknown as number }); }}
              >
                {[2, 3, 4, 5].map((l) => (
                  <MenuItem key={l} value={l}>Year {l}</MenuItem>
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
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setOpenDialog(false); }}>Cancel</Button>
          <Button onClick={() => { void handleSaveCourse(); }} variant="contained">
            {editingCourse ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Bulk Upload Dialog */}
      <Dialog open={openUploadDialog} onClose={() => setOpenUploadDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Bulk Upload Courses</DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 2 }}>
            <Alert severity="info" sx={{ mb: 3 }}>
              Upload a CSV or Excel file with course data. Download the master template below for the correct format.
            </Alert>

            {isCoordinator && (
              <Button
                variant="outlined"
                startIcon={<DownloadIcon />}
                onClick={downloadMasterCSV}
                fullWidth
                sx={{ mb: 2, textTransform: 'none' }}
              >
                Download Master Course CSV (91 Courses)
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
                variant="outlined"
                component="span"
                fullWidth
                sx={{ py: 1.5, textTransform: 'none' }}
              >
                {selectedFile ? selectedFile.name : 'Select File'}
              </Button>
            </label>

            {loading && <LinearProgress sx={{ mt: 2 }} />}

            {uploadResult && (
              <Alert severity="success" sx={{ mt: 2 }}>
                Successfully created {uploadResult.created} courses.
                {uploadResult.skipped > 0 && ` Skipped ${uploadResult.skipped} duplicates.`}
                {uploadResult.errors && uploadResult.errors.length > 0 && (
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="caption" color="error">
                      Errors: {uploadResult.errors.join(', ')}
                    </Typography>
                  </Box>
                )}
              </Alert>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setOpenUploadDialog(false); }}>Cancel</Button>
          <Button
            onClick={() => { void handleBulkUpload(); }}
            variant="contained"
            disabled={!selectedFile || loading}
          >
            {loading ? 'Uploading...' : 'Upload'}
          </Button>
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
    </Box>
  );
};

export default CoursesPage;
