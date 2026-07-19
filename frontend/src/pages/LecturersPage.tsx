import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Alert,
  Chip,
  FormControlLabel,
  Checkbox,
  FormGroup,
  FormLabel,
  FormControl,
  MenuItem,
  InputLabel,
  Select,
  LinearProgress,
  Divider,
  Fade,
  Grow,
  Slide,
  CircularProgress,
  Snackbar,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  InputAdornment,
} from '@mui/material';
import { Add as AddIcon, Edit as EditIcon, Delete as DeleteIcon, Upload as UploadIcon, Assignment as AssignIcon, Print as PrintIcon, Search as SearchIcon } from '@mui/icons-material';
import { lecturersAPI, departmentsAPI, coursesAPI } from '../api';
import { useAuth } from '../contexts/AuthContext'; import { useNavigate } from 'react-router-dom';
import TableSkeleton from '../components/skeletons/TableSkeleton';
import { formatDepartmentName, formatPersonName } from '../utils/displayFormatters';

interface Lecturer {
  id: number;
  staff_number: string;
  full_name: string;
  email: string;
  department_id: number;
  max_hours_per_week: number;
  welcome_email_sent?: boolean;
  teaching_preferences?: {
    avoid_early_morning: boolean;
    avoid_late_afternoon: boolean;
  };
  assignments?: {
    course_id?: number;
    course: {
      code: string;
      name: string;
    }
  }[];
}

interface Department {
  id: number;
  code: string;
  name: string;
}

interface CourseOption {
  id: number;
  code: string;
  name: string;
  department_id: number;
}

const issueLabels: Record<string, string> = {
  missing_staff_number: 'Rows missing staff number',
  missing_full_name: 'Rows missing lecturer name',
  invalid_department: 'Rows with missing or invalid department',
  missing_course_match: 'Course codes not found in the system',
  missing_lecturer_match: 'Lecturers not found for assignment',
  missing_course_value: 'Rows missing course values',
  row_validation_error: 'Other row validation issues',
  missing_email: 'Lecturers loaded without email — portal access link NOT sent',
};

const LecturersPage: React.FC = () => {
  const [lecturers, setLecturers] = useState<Lecturer[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [courses, setCourses] = useState<CourseOption[]>([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [openUploadDialog, setOpenUploadDialog] = useState(false);
  const [openAssignDialog, setOpenAssignDialog] = useState(false);
  const [openCourseMapDialog, setOpenCourseMapDialog] = useState(false);
  const [editingLecturer, setEditingLecturer] = useState<Lecturer | null>(null);
  const [mappingLecturer, setMappingLecturer] = useState<Lecturer | null>(null);
  const [mappingSearch, setMappingSearch] = useState('');
  const [mappingCourseIds, setMappingCourseIds] = useState<number[]>([]);
  const [error, setError] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [assignFile, setAssignFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [assignResult, setAssignResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [assigning, setAssigning] = useState(false);
  const [mappingSaving, setMappingSaving] = useState(false);
  const [formData, setFormData] = useState({
    staff_number: '',
    full_name: '',
    email: '',
    department_id: 1,

    max_hours_per_week: 20,
    avoid_early_morning: false,
    avoid_late_afternoon: false,
    course_ids: [] as number[],
  });

  const { isCoordinator } = useAuth();
  const navigate = useNavigate();

  const assignedCourseIdsForLecturer = (lecturer: Lecturer | null): number[] => {
    if (!lecturer?.assignments) {
      return [];
    }
    return lecturer.assignments
      .map((assignment) => assignment.course_id || courses.find((course) => course.code === assignment.course?.code)?.id)
      .filter((courseId): courseId is number => Boolean(courseId));
  };

  const eligibleCoursesForDepartment = (departmentId: number | null | undefined, selectedCourseIds: number[] = []) => {
    const selectedLookup = new Set(selectedCourseIds);
    return courses
      .filter((course) => course.department_id === departmentId || selectedLookup.has(course.id))
      .sort((left, right) => left.code.localeCompare(right.code));
  };

  const editDialogCourses = eligibleCoursesForDepartment(formData.department_id, formData.course_ids);
  const mappingDialogCourses = eligibleCoursesForDepartment(mappingLecturer?.department_id, mappingCourseIds)
    .filter((course) => {
      const search = mappingSearch.trim().toLowerCase();
      if (!search) {
        return true;
      }
      return `${course.code} ${course.name}`.toLowerCase().includes(search);
    });

  useEffect(() => {
    Promise.all([
      fetchLecturers(),
      fetchDepartments(),
      fetchCourses()
    ]).finally(() => setPageLoading(false));
  }, []);

  const fetchCourses = async () => {
    try {
      const data = await coursesAPI.getAll();
      setCourses(data);
    } catch (err) {
      console.error('Failed to load courses');
    }
  };

  const fetchDepartments = async () => {
    try {
      const data = await departmentsAPI.getAll();
      setDepartments(data);
    } catch (err) {
      console.error('Failed to load departments');
    }
  };

  const fetchLecturers = async () => {
    try {
      const data = await lecturersAPI.getAll();
      setLecturers(data);
    } catch (err) {
      setError('Failed to load lecturers');
    }
  };

  const handleOpenDialog = (lecturer?: Lecturer) => {
    if (lecturer) {
      setEditingLecturer(lecturer);
      setFormData({
        staff_number: lecturer.staff_number,
        full_name: lecturer.full_name,
        email: lecturer.email,
        department_id: lecturer.department_id,
        max_hours_per_week: lecturer.max_hours_per_week,
        avoid_early_morning: lecturer.teaching_preferences?.avoid_early_morning || false,
        avoid_late_afternoon: lecturer.teaching_preferences?.avoid_late_afternoon || false,
        course_ids: assignedCourseIdsForLecturer(lecturer),
      });
    } else {
      setEditingLecturer(null);
      setFormData({
        staff_number: '',
        full_name: '',
        email: '',
        department_id: 1,
        max_hours_per_week: 20,
        avoid_early_morning: false,
        avoid_late_afternoon: false,
        course_ids: [],
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingLecturer(null);
    setError('');
  };

  const handleOpenCourseMapDialog = (lecturer: Lecturer) => {
    setMappingLecturer(lecturer);
    setMappingSearch('');
    setMappingCourseIds(assignedCourseIdsForLecturer(lecturer));
    setOpenCourseMapDialog(true);
    setError('');
  };

  const handleCloseCourseMapDialog = () => {
    setOpenCourseMapDialog(false);
    setMappingLecturer(null);
    setMappingSearch('');
    setMappingCourseIds([]);
    setMappingSaving(false);
  };

  const handleToggleMappedCourse = (courseId: number) => {
    setMappingCourseIds((previous) => (
      previous.includes(courseId)
        ? previous.filter((id) => id !== courseId)
        : [...previous, courseId]
    ));
  };

  const handleSaveCourseMapping = async () => {
    if (!mappingLecturer) {
      return;
    }
    setMappingSaving(true);
    setError('');
    try {
      await lecturersAPI.update(mappingLecturer.id, { course_ids: mappingCourseIds });
      await fetchLecturers();
      handleCloseCourseMapDialog();
    } catch (err) {
      setError('Failed to update lecturer course assignments');
    } finally {
      setMappingSaving(false);
    }
  };

  const handleSubmit = async () => {
    try {
      const payload = {
        ...formData,
        teaching_preferences: {
          avoid_early_morning: formData.avoid_early_morning,
          avoid_late_afternoon: formData.avoid_late_afternoon
        }
      };

      if (editingLecturer) {
        await lecturersAPI.update(editingLecturer.id, payload);
      } else {
        await lecturersAPI.create(payload);
      }
      await fetchLecturers();
      handleCloseDialog();
    } catch (err) {
      setError('Failed to save lecturer');
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this lecturer?')) {
      try {
        await lecturersAPI.delete(id);
        await fetchLecturers();
      } catch (err) {
        setError('Failed to delete lecturer');
      }
    }
  };

  const handleDeleteAll = async () => {
    if (window.confirm('Are you sure you want to clear ALL lecturers? This action cannot be undone.')) {
      try {
        await lecturersAPI.deleteAll();
        await fetchLecturers();
      } catch (err) {
        setError('Failed to clear lecturers');
      }
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      setSelectedFile(event.target.files[0]);
    }
  };

  const handleBulkUpload = async () => {
    if (!selectedFile) { setError('Please select a file'); return; }
    setLoading(true); setError(''); setUploadResult(null);
    try {
      const result = await lecturersAPI.bulkUpload(selectedFile);
      setUploadResult(result);
      void fetchLecturers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error uploading file');
    } finally { setLoading(false); }
  };

  const handleBulkAssignCourses = async () => {
    if (!assignFile) { setError('Please select a file'); return; }
    setAssigning(true); setError(''); setAssignResult(null);
    try {
      const data = await lecturersAPI.bulkAssignCourses(assignFile);
      setAssignResult(data);
      void fetchLecturers();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Error processing file');
    } finally { setAssigning(false); }
  };

  const renderIssueSummary = (result: any) => {
    if (!result?.issue_summary) return null;

    const entries = Object.entries(result.issue_summary) as Array<[string, { count: number; examples: string[] }]>;
    if (entries.length === 0) return null;

    return (
      <Alert severity="warning" sx={{ mt: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Some rows need attention before they can fully load.
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1.5 }}>
          {entries.map(([key, value]) => (
            <Chip
              key={key}
              label={`${issueLabels[key] || key}: ${value.count}`}
              size="small"
              variant="outlined"
              color="warning"
            />
          ))}
        </Box>
        {entries.map(([key, value]) => (
          <Box key={key} sx={{ mb: 1.25 }}>
            <Typography variant="body2" fontWeight={700}>
              {issueLabels[key] || key}
            </Typography>
            {value.examples.map((example, index) => (
              <Typography key={`${key}-${index}`} variant="body2" color="text.secondary">
                {example}
              </Typography>
            ))}
          </Box>
        ))}
      </Alert>
    );
  };

  return (
    <Fade in timeout={600}>
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" fontWeight="bold">
            Lecturers
          </Typography>
          {isCoordinator && (
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button
                variant="outlined"
                color="secondary"
                startIcon={<AssignIcon />}
                onClick={() => { setOpenAssignDialog(true); }}
                sx={{ transition: 'all 0.3s ease', '&:hover': { transform: 'translateY(-2px)' } }}
              >
                Assign Courses
              </Button>
              <Button
                variant="outlined"
                startIcon={<UploadIcon />}
                onClick={() => { setOpenUploadDialog(true); }}
                sx={{ transition: 'all 0.3s ease', '&:hover': { transform: 'translateY(-2px)' } }}
              >
                Bulk Upload
              </Button>
              <Button
                variant="outlined"
                color="error"
                startIcon={<DeleteIcon />}
                onClick={() => { void handleDeleteAll(); }}
                sx={{ transition: 'all 0.3s ease', '&:hover': { transform: 'translateY(-2px)' } }}
              >
                Clear All
              </Button>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={() => { handleOpenDialog(); }}
                sx={{
                  background: 'linear-gradient(135deg, #1976d2 0%, #115293 100%)',
                  transition: 'all 0.3s ease',
                  '&:hover': { transform: 'translateY(-2px)', boxShadow: '0 6px 16px rgba(0,104,55,0.3)' },
                }}
              >
                Add Lecturer
              </Button>
            </Box>
          )}
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => { setError(''); }}>
            {error}
          </Alert>
        )}

        {pageLoading ? (
          <TableSkeleton columns={isCoordinator ? 6 : 5} rows={8} />
        ) : (
          <TableContainer component={Paper} elevation={0} sx={{ borderRadius: 3, border: '1px solid rgba(0,0,0,0.06)', boxShadow: '0 4px 20px rgba(0,0,0,0.03)' }}>
            <Table sx={{ '& .MuiTableCell-root': { borderBottom: '1px solid rgba(0,0,0,0.05)' }}}>
            <TableHead sx={{ bgcolor: '#f8fafc' }}>
              <TableRow>
                <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Staff Number</TableCell>
                <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Full Name</TableCell>
                <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Email</TableCell>
                <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Department</TableCell>
                <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Max Hours/Week</TableCell>
                <TableCell sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Assigned Courses</TableCell>
                {isCoordinator && <TableCell align="center" sx={{ color: '#475569', fontWeight: '700', fontSize: '0.8rem', textTransform: 'uppercase' }}>Actions</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {lecturers.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={isCoordinator ? 7 : 6} align="center" sx={{ py: 4 }}>
                    <Typography variant="body1" color="text.secondary">
                      No lecturers found. Click "Add Lecturer" to create one.
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                lecturers.map((lecturer) => (
                  <TableRow key={lecturer.id} hover>
                    <TableCell>{lecturer.staff_number}</TableCell>
                    <TableCell>{formatPersonName(lecturer.full_name)}</TableCell>
                    <TableCell>
                      {lecturer.email ? (
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <span>{lecturer.email}</span>
                          {!lecturer.welcome_email_sent && (
                            <Chip label="Access link not sent" size="small" color="warning" variant="outlined" sx={{ fontSize: '0.68rem' }} />
                          )}
                        </Box>
                      ) : (
                        <Chip label="No email — add to notify" size="small" color="error" variant="outlined" sx={{ fontSize: '0.68rem' }} />
                      )}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={departments.find((d) => d.id === lecturer.department_id)?.code || 'N/A'}
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Chip label={`${lecturer.max_hours_per_week}h`} color="primary" size="small" />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                        {lecturer.assignments && lecturer.assignments.length > 0 ? (
                          lecturer.assignments.map((assignment, index) => (
                            <Chip 
                              key={index} 
                              label={assignment.course?.code || "Unknown"} 
                              size="small" 
                              sx={{ bgcolor: '#e2e8f0', color: '#1e293b', fontSize: '0.75rem', fontWeight: 600 }} 
                            />
                          ))
                        ) : (
                          <Typography variant="caption" color="text.secondary">None</Typography>
                        )}
                      </Box>
                    </TableCell>
                    {isCoordinator && (
                      <TableCell align="center">
                        <IconButton
                          size="small"
                          color="secondary"
                          onClick={() => { navigate(`/print?type=lecturer&id=${lecturer.id}`); }}
                          title="Print schedule"
                        >
                          <PrintIcon />
                        </IconButton>
                        <IconButton
                          size="small"
                          color="secondary"
                          onClick={() => { handleOpenCourseMapDialog(lecturer); }}
                          title="Assign department courses"
                        >
                          <AssignIcon />
                        </IconButton>
                        <IconButton
                          size="small"
                          color="primary"
                          onClick={() => { handleOpenDialog(lecturer); }}
                        >
                          <EditIcon />
                        </IconButton>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => { void handleDelete(lecturer.id); }}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </TableCell>
                    )}
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
        )}

        <Dialog open={openDialog} onClose={() => { setOpenDialog(false); }} maxWidth="sm" fullWidth>
          <DialogTitle>
            {editingLecturer ? 'Edit Lecturer' : 'Add New Lecturer'}
          </DialogTitle>
          <DialogContent>
            <TextField
              fullWidth
              label="Staff Number"
              value={formData.staff_number}
              onChange={(e) => { setFormData({ ...formData, staff_number: e.target.value }); }}
              margin="normal"
              required
            />
            <TextField
              fullWidth
              label="Full Name"
              value={formData.full_name}
              onChange={(e) => { setFormData({ ...formData, full_name: e.target.value }); }}
              margin="normal"
              required
            />
            <TextField
              fullWidth
              label="Email (optional — can be added later)"
              type="email"
              value={formData.email}
              onChange={(e) => { setFormData({ ...formData, email: e.target.value }); }}
              margin="normal"
              helperText="Leave blank if not yet known"
            />
            <FormControl fullWidth margin="normal" required>
              <InputLabel>Department</InputLabel>
              <Select
                value={formData.department_id}
                label="Department"
                onChange={(e) => { setFormData({ ...formData, department_id: e.target.value as number }); }}
              >
                {departments.map((dept: any) => (
                  <MenuItem key={dept.id} value={dept.id}>
                    {formatDepartmentName(dept.name)} ({dept.code})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth margin="normal">
              <InputLabel>Assigned Courses</InputLabel>
              <Select
                multiple
                value={formData.course_ids}
                label="Assigned Courses"
                onChange={(e) => { 
                  const val = e.target.value;
                  setFormData({ ...formData, course_ids: typeof val === 'string' ? val.split(',').map(Number) : val as number[] }); 
                }}
                renderValue={(selected) => (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {(selected as number[]).map((value) => {
                      const course = courses.find(c => c.id === value);
                      return <Chip key={value} label={course?.code || value} size="small" />;
                    })}
                  </Box>
                )}
              >
                {editDialogCourses.map((course) => (
                  <MenuItem key={course.id} value={course.id}>
                    {course.code} - {course.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              fullWidth
              label="Max Hours Per Week"
              type="number"
              value={formData.max_hours_per_week}
              onChange={(e) => { setFormData({ ...formData, max_hours_per_week: parseInt(e.target.value) }); }}
              margin="normal"
              required
              inputProps={{ min: 1, max: 40 }}
            />

            <FormControl component="fieldset" variant="standard" sx={{ mt: 2 }}>
              <FormLabel component="legend">Teaching Preferences</FormLabel>
              <FormGroup>
                <FormControlLabel
                  control={
                    <Checkbox checked={formData.avoid_early_morning} onChange={(e) => { setFormData({ ...formData, avoid_early_morning: e.target.checked }); }} />
                  }
                  label="Avoid Early Morning (07:00)"
                />
                <FormControlLabel
                  control={
                    <Checkbox checked={formData.avoid_late_afternoon} onChange={(e) => { setFormData({ ...formData, avoid_late_afternoon: e.target.checked }); }} />
                  }
                  label="Avoid Late Afternoon (17:00+)"
                />
              </FormGroup>
            </FormControl>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleCloseDialog}>Cancel</Button>
            <Button onClick={() => { void handleSubmit(); }} variant="contained">
              {editingLecturer ? 'Update' : 'Create'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Bulk Upload Dialog */}
        <Dialog
          open={openUploadDialog}
          onClose={() => { setOpenUploadDialog(false); setSelectedFile(null); setUploadResult(null); setError(''); }}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>Bulk Upload Lecturers</DialogTitle>
          <DialogContent>
            <Box sx={{ mt: 2 }}>
              <Alert severity="info" sx={{ mb: 3 }}>
                Upload a <strong>CSV or Excel</strong> file with lecturer details.
                <Box component="ul" sx={{ mt: 1, mb: 0, pl: 2 }}>
                  <li>Accepted formats: .csv, .xlsx, .xls (max 5 MB)</li>
                  <li>Include staff number, full name, and department</li>
                  <li>Email and weekly hour limits are optional</li>
                  <li>Duplicate entries will be automatically skipped</li>
                </Box>
              </Alert>

              <input
                key={openUploadDialog ? 'open' : 'closed'}
                accept=".csv,.xlsx,.xls"
                style={{ display: 'none' }}
                id="lecturer-file-upload"
                type="file"
                onChange={handleFileSelect}
              />
              <label htmlFor="lecturer-file-upload">
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
                <Box sx={{ mt: 2 }}>
                  <Alert severity={uploadResult.issue_summary ? 'info' : 'success'} sx={{ mb: uploadResult.errors?.length ? 2 : 0 }}>
                    Created {uploadResult.created} lecturers and updated {uploadResult.updated || 0}.
                    {uploadResult.assigned !== undefined && ` Auto-assigned ${uploadResult.assigned} course links.`}
                    {uploadResult.skipped > 0 && ` ${uploadResult.skipped} row(s) were skipped.`}
                  </Alert>
                  {renderIssueSummary(uploadResult)}
                  {uploadResult.errors && uploadResult.errors.length > 0 && (
                    <Alert severity="warning" sx={{ mt: 2 }}>
                      <Typography variant="subtitle2" sx={{ mb: 1 }}>Detailed row messages</Typography>
                      <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '0.85rem' }}>
                        {uploadResult.errors.map((err: string, i: number) => (
                          <li key={i}>{err}</li>
                        ))}
                      </ul>
                    </Alert>
                  )}
                </Box>
              )}
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => { setOpenUploadDialog(false); setSelectedFile(null); setUploadResult(null); setError(''); }}>
              {uploadResult ? 'Close' : 'Cancel'}
            </Button>
            <Button
              onClick={() => { void handleBulkUpload(); }}
              variant="contained"
              disabled={!selectedFile || loading}
            >
              {loading ? 'Uploading...' : uploadResult ? 'Upload Another File' : 'Upload'}
            </Button>
          </DialogActions>
        </Dialog>

        <Dialog open={openCourseMapDialog} onClose={handleCloseCourseMapDialog} maxWidth="md" fullWidth>
          <DialogTitle>
            Assign Courses
            {mappingLecturer ? ` • ${formatPersonName(mappingLecturer.full_name)}` : ''}
          </DialogTitle>
          <DialogContent>
            <Box sx={{ mt: 1 }}>
              <Alert severity="info" sx={{ mb: 2 }}>
                Available courses are filtered to the lecturer&apos;s department, and already assigned courses are pre-selected.
              </Alert>

              <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
                <Chip
                  label={`Department: ${departments.find((dept) => dept.id === mappingLecturer?.department_id)?.name || 'Unknown'}`}
                  color="primary"
                  variant="outlined"
                />
                <Chip
                  label={`${mappingCourseIds.length} course(s) selected`}
                  color="success"
                  variant="outlined"
                />
              </Box>

              <TextField
                fullWidth
                placeholder="Search department courses by code or name"
                value={mappingSearch}
                onChange={(event) => { setMappingSearch(event.target.value); }}
                margin="normal"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" />
                    </InputAdornment>
                  ),
                }}
              />

              <Paper
                variant="outlined"
                sx={{
                  mt: 2,
                  borderRadius: 2,
                  overflow: 'hidden',
                }}
              >
                <List dense disablePadding sx={{ maxHeight: 420, overflowY: 'auto' }}>
                  {mappingDialogCourses.length === 0 ? (
                    <Box sx={{ p: 3 }}>
                      <Typography variant="body2" color="text.secondary">
                        No department courses match the current search.
                      </Typography>
                    </Box>
                  ) : (
                    mappingDialogCourses.map((course) => {
                      const checked = mappingCourseIds.includes(course.id);
                      return (
                        <ListItemButton
                          key={course.id}
                          onClick={() => { handleToggleMappedCourse(course.id); }}
                          divider
                          sx={{ py: 1.25 }}
                        >
                          <ListItemIcon sx={{ minWidth: 40 }}>
                            <Checkbox edge="start" checked={checked} tabIndex={-1} disableRipple />
                          </ListItemIcon>
                          <ListItemText
                            primary={`${course.code} - ${course.name}`}
                            secondary={departments.find((dept) => dept.id === course.department_id)?.code || 'Department course'}
                            primaryTypographyProps={{ fontWeight: checked ? 700 : 500 }}
                          />
                        </ListItemButton>
                      );
                    })
                  )}
                </List>
              </Paper>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleCloseCourseMapDialog}>Cancel</Button>
            <Button onClick={() => { void handleSaveCourseMapping(); }} variant="contained" disabled={mappingSaving}>
              {mappingSaving ? 'Saving...' : 'Save Assignments'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Bulk Assign Courses Dialog */}
        <Dialog open={openAssignDialog} onClose={() => setOpenAssignDialog(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Bulk Assign Lecturers → Courses</DialogTitle>
          <DialogContent>
            <Box sx={{ mt: 2 }}>
              <Alert severity="info" sx={{ mb: 3 }}>
                Upload a <strong>CSV or Excel</strong> file to assign lecturers to their courses.
                <Box component="ul" sx={{ mt: 1, mb: 0, pl: 2 }}>
                  <li>Accepted formats: .csv, .xlsx, .xls (max 5 MB)</li>
                  <li>Include staff number and course code(s)</li>
                  <li>You can list multiple courses per lecturer in a single row</li>
                  <li>Existing assignments will be safely preserved</li>
                </Box>
              </Alert>

              <input
                key={openAssignDialog ? 'open' : 'closed'}
                accept=".csv,.xlsx,.xls"
                style={{ display: 'none' }}
                id="assign-file-upload"
                type="file"
                onChange={(e) => { if (e.target.files?.[0]) setAssignFile(e.target.files[0]); }}
              />
              <label htmlFor="assign-file-upload">
                <Button variant="outlined" component="span" fullWidth sx={{ py: 1.5, textTransform: 'none' }}>
                  {assignFile ? assignFile.name : 'Select File (.csv / .xlsx)'}
                </Button>
              </label>

              {assigning && <LinearProgress sx={{ mt: 2 }} />}

              {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}

              {assignResult && (
                <Box sx={{ mt: 2 }}>
                  <Alert severity={assignResult.issue_summary ? 'info' : 'success'} sx={{ mb: assignResult.errors?.length ? 2 : 0 }}>
                    Successfully assigned {assignResult.assigned} course links.
                    {assignResult.processed_rows !== undefined && ` Processed ${assignResult.processed_rows} row(s).`}
                    {assignResult.skipped > 0 && ` Skipped ${assignResult.skipped} existing matches.`}
                  </Alert>
                  {renderIssueSummary(assignResult)}
                  {assignResult.errors && assignResult.errors.length > 0 && (
                    <Alert severity="warning" sx={{ mt: 2 }}>
                      <Typography variant="subtitle2" sx={{ mb: 1 }}>Detailed row messages</Typography>
                      <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '0.85rem' }}>
                        {assignResult.errors.map((err: string, i: number) => (
                          <li key={i}>{err}</li>
                        ))}
                      </ul>
                    </Alert>
                  )}
                </Box>
              )}
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => { setOpenAssignDialog(false); setAssignFile(null); setAssignResult(null); setError(''); }}>Cancel</Button>
            <Button
              onClick={() => { void handleBulkAssignCourses(); }}
              variant="contained"
              disabled={!assignFile || assigning}
            >
              {assigning ? 'Processing...' : 'Upload & Assign'}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Fade>
  );
};

export default LecturersPage;
