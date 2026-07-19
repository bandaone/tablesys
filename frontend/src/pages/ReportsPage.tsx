import React, { useEffect, useState } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  MenuItem,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Tooltip,
  Divider,
  Paper,
  Select,
  FormControl,
  InputLabel,
  SelectChangeEvent
} from '@mui/material';
import {
  Assessment as AssessmentIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
  Person as PersonIcon,
  Room as RoomIcon,
  Business as BusinessIcon,
  CalendarMonth as CalendarIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon
} from '@mui/icons-material';
import api from '../api';

interface ReportType {
  type: string;
  name: string;
  description: string;
}

interface LecturerWorkloadData {
  lecturer_id: number;
  staff_number: string;
  name: string;
  department: string;
  actual_hours: number;
  max_hours: number;
  workload_percentage: number;
  workload_status: string;
  total_slots: number;
  courses: Array<{
    code: string;
    name: string;
    credit_hours: number;
    slot_count: number;
  }>;
}

interface RoomUtilizationData {
  room_id: number;
  room_number: string;
  building: string;
  capacity: number;
  slots_used: number;
  utilization_percent: number;
  utilization_status: string;
  avg_capacity_usage: number;
}

interface DepartmentComparisonData {
  department_id: number;
  name: string;
  code: string;
  courses: number;
  lecturers: number;
  student_groups: number;
  total_students: number;
  timetables: number;
  generated_timetables: number;
  avg_hours_per_lecturer: number;
  student_lecturer_ratio: number;
  timetable_completion: number;
}

const ReportsPage: React.FC = () => {
  const [tabValue, setTabValue] = useState<number>(0);
  const [reportTypes, setReportTypes] = useState<ReportType[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Lecturer Workload Report states
  const [lecturerReport, setLecturerReport] = useState<any>(null);
  const [lecturerDeptFilter, setLecturerDeptFilter] = useState<string>('');

  // Room Utilization Report states
  const [roomReport, setRoomReport] = useState<any>(null);
  const [roomBuildingFilter, setRoomBuildingFilter] = useState<string>('');

  // Department Comparison Report states
  const [deptReport, setDeptReport] = useState<any>(null);

  // Departments list for filters
  const [departments, setDepartments] = useState<any[]>([]);

  useEffect(() => {
    fetchReportTypes();
    fetchDepartments();
  }, []);

  const fetchReportTypes = async () => {
    try {
      const response = await api.get('/reports/types');
      setReportTypes(response.data);
    } catch (err) {
      console.error('Failed to fetch report types:', err);
    }
  };

  const fetchDepartments = async () => {
    try {
      const response = await api.get('/departments/');
      setDepartments(response.data);
    } catch (err) {
      console.error('Failed to fetch departments:', err);
    }
  };

  const generateLecturerWorkloadReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {};
      if (lecturerDeptFilter) {
        params.department_id = lecturerDeptFilter;
      }
      const response = await api.get('/reports/lecturer-workload', { params });
      setLecturerReport(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate lecturer workload report');
    } finally {
      setLoading(false);
    }
  };

  const generateRoomUtilizationReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = {};
      if (roomBuildingFilter) {
        params.building = roomBuildingFilter;
      }
      const response = await api.get('/reports/room-utilization', { params });
      setRoomReport(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate room utilization report');
    } finally {
      setLoading(false);
    }
  };

  const generateDepartmentComparisonReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get('/reports/department-comparison');
      setDeptReport(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate department comparison report');
    } finally {
      setLoading(false);
    }
  };

  const downloadReport = async (reportType: string) => {
    try {
      let params: any = { format: 'json' };
      
      if (reportType === 'lecturer-workload' && lecturerDeptFilter) {
        params.department_id = lecturerDeptFilter;
      } else if (reportType === 'room-utilization' && roomBuildingFilter) {
        params.building = roomBuildingFilter;
      }

      const response = await api.get(`/api/v1/reports/export/${reportType}`, {
        params,
        responseType: 'blob'
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${reportType}_report.json`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error('Failed to download report:', err);
      setError('Failed to download report');
    }
  };

  const getWorkloadColor = (status: string): 'success' | 'warning' | 'error' => {
    switch (status) {
      case 'optimal':
        return 'success';
      case 'overloaded':
        return 'error';
      case 'underutilized':
        return 'warning';
      default:
        return 'warning';
    }
  };

  const getUtilizationColor = (status: string): 'success' | 'warning' | 'error' => {
    switch (status) {
      case 'well_utilized':
        return 'success';
      case 'moderately_utilized':
        return 'warning';
      case 'underutilized':
        return 'error';
      default:
        return 'warning';
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" fontWeight="bold">
          Reports & Analytics
        </Typography>
        <AssessmentIcon sx={{ fontSize: 40, color: '#1976d2' }} />
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Tabs value={tabValue} onChange={(e, newValue) => setTabValue(newValue)} sx={{ mb: 3 }}>
        <Tab label="Lecturer Workload" icon={<PersonIcon />} iconPosition="start" />
        <Tab label="Room Utilization" icon={<RoomIcon />} iconPosition="start" />
        <Tab label="Department Comparison" icon={<BusinessIcon />} iconPosition="start" />
      </Tabs>

      {/* Lecturer Workload Report Tab */}
      {tabValue === 0 && (
        <Box>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Generate Lecturer Workload Report
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Analyze lecturer teaching hours, course assignments, and workload distribution
              </Typography>
              <Grid container spacing={2} alignItems="center">
                <Grid item xs={12} md={4}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Filter by Department</InputLabel>
                    <Select
                      value={lecturerDeptFilter}
                      onChange={(e: SelectChangeEvent) => setLecturerDeptFilter(e.target.value)}
                      label="Filter by Department"
                    >
                      <MenuItem value="">All Departments</MenuItem>
                      {departments.map((dept: any) => (
                        <MenuItem key={dept.id} value={dept.id}>
                          {dept.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Button
                    variant="contained"
                    startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <AssessmentIcon />}
                    onClick={generateLecturerWorkloadReport}
                    disabled={loading}
                    fullWidth
                  >
                    Generate Report
                  </Button>
                </Grid>
                {lecturerReport && (
                  <Grid item xs={12} md={4}>
                    <Button
                      variant="outlined"
                      startIcon={<DownloadIcon />}
                      onClick={() => downloadReport('lecturer-workload')}
                      fullWidth
                    >
                      Download JSON
                    </Button>
                  </Grid>
                )}
              </Grid>
            </CardContent>
          </Card>

          {lecturerReport && (
            <>
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Summary
                  </Typography>
                  <Divider sx={{ mb: 2 }} />
                  <Grid container spacing={2}>
                    <Grid item xs={6} md={3}>
                      <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#f5f5f5' }}>
                        <Typography variant="h5" color="primary" fontWeight="bold">
                          {lecturerReport.summary.total_lecturers}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Total Lecturers
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={6} md={3}>
                      <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#f5f5f5' }}>
                        <Typography variant="h5" color="primary" fontWeight="bold">
                          {lecturerReport.summary.average_hours}h
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Average Hours
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={6} md={3}>
                      <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#f5f5f5' }}>
                        <Typography variant="h5" color="error" fontWeight="bold">
                          {lecturerReport.summary.overloaded_lecturers}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Overloaded
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={6} md={3}>
                      <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#f5f5f5' }}>
                        <Typography variant="h5" color="warning.main" fontWeight="bold">
                          {lecturerReport.summary.underutilized_lecturers}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Underutilized
                        </Typography>
                      </Paper>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>

              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Lecturer Details
                  </Typography>
                  <Divider sx={{ mb: 2 }} />
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow sx={{ bgcolor: '#f5f5f5' }}>
                          <TableCell><strong>Lecturer</strong></TableCell>
                          <TableCell><strong>Department</strong></TableCell>
                          <TableCell align="center"><strong>Hours</strong></TableCell>
                          <TableCell align="center"><strong>Slots</strong></TableCell>
                          <TableCell align="center"><strong>Workload %</strong></TableCell>
                          <TableCell align="center"><strong>Status</strong></TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {lecturerReport.data.map((lecturer: LecturerWorkloadData) => (
                          <TableRow key={lecturer.lecturer_id} hover>
                            <TableCell>
                              <Typography variant="body2" fontWeight="medium">
                                {lecturer.name}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {lecturer.staff_number}
                              </Typography>
                            </TableCell>
                            <TableCell>{lecturer.department}</TableCell>
                            <TableCell align="center">
                              {lecturer.actual_hours} / {lecturer.max_hours}
                            </TableCell>
                            <TableCell align="center">{lecturer.total_slots}</TableCell>
                            <TableCell align="center">
                              <Typography
                                variant="body2"
                                fontWeight="bold"
                                color={
                                  lecturer.workload_percentage > 100
                                    ? 'error.main'
                                    : lecturer.workload_percentage < 50
                                    ? 'warning.main'
                                    : 'success.main'
                                }
                              >
                                {lecturer.workload_percentage}%
                              </Typography>
                            </TableCell>
                            <TableCell align="center">
                              <Chip
                                label={lecturer.workload_status}
                                color={getWorkloadColor(lecturer.workload_status)}
                                size="small"
                                sx={{ textTransform: 'capitalize' }}
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </>
          )}
        </Box>
      )}

      {/* Room Utilization Report Tab */}
      {tabValue === 1 && (
        <Box>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Generate Room Utilization Report
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Analyze room usage statistics, utilization rates, and capacity usage
              </Typography>
              <Grid container spacing={2} alignItems="center">
                <Grid item xs={12} md={4}>
                  <TextField
                    label="Filter by Building"
                    value={roomBuildingFilter}
                    onChange={(e) => setRoomBuildingFilter(e.target.value)}
                    size="small"
                    fullWidth
                    placeholder="e.g., Main Block"
                  />
                </Grid>
                <Grid item xs={12} md={4}>
                  <Button
                    variant="contained"
                    startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <AssessmentIcon />}
                    onClick={generateRoomUtilizationReport}
                    disabled={loading}
                    fullWidth
                  >
                    Generate Report
                  </Button>
                </Grid>
                {roomReport && (
                  <Grid item xs={12} md={4}>
                    <Button
                      variant="outlined"
                      startIcon={<DownloadIcon />}
                      onClick={() => downloadReport('room-utilization')}
                      fullWidth
                    >
                      Download JSON
                    </Button>
                  </Grid>
                )}
              </Grid>
            </CardContent>
          </Card>

          {roomReport && (
            <>
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Summary
                  </Typography>
                  <Divider sx={{ mb: 2 }} />
                  <Grid container spacing={2}>
                    <Grid item xs={6} md={3}>
                      <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#f5f5f5' }}>
                        <Typography variant="h5" color="primary" fontWeight="bold">
                          {roomReport.summary.total_rooms}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Total Rooms
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={6} md={3}>
                      <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#f5f5f5' }}>
                        <Typography variant="h5" color="primary" fontWeight="bold">
                          {roomReport.summary.average_utilization}%
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Average Utilization
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={6} md={3}>
                      <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#f5f5f5' }}>
                        <Typography variant="h5" color="success.main" fontWeight="bold">
                          {roomReport.summary.well_utilized_rooms}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Well Utilized
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={6} md={3}>
                      <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#f5f5f5' }}>
                        <Typography variant="h5" color="error" fontWeight="bold">
                          {roomReport.summary.underutilized_rooms}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Underutilized
                        </Typography>
                      </Paper>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>

              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Room Details
                  </Typography>
                  <Divider sx={{ mb: 2 }} />
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow sx={{ bgcolor: '#f5f5f5' }}>
                          <TableCell><strong>Room</strong></TableCell>
                          <TableCell><strong>Building</strong></TableCell>
                          <TableCell align="center"><strong>Capacity</strong></TableCell>
                          <TableCell align="center"><strong>Slots Used</strong></TableCell>
                          <TableCell align="center"><strong>Utilization</strong></TableCell>
                          <TableCell align="center"><strong>Avg Capacity</strong></TableCell>
                          <TableCell align="center"><strong>Status</strong></TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {roomReport.data.map((room: RoomUtilizationData) => (
                          <TableRow key={room.room_id} hover>
                            <TableCell>
                              <Typography variant="body2" fontWeight="medium">
                                {room.room_number}
                              </Typography>
                            </TableCell>
                            <TableCell>{room.building}</TableCell>
                            <TableCell align="center">{room.capacity}</TableCell>
                            <TableCell align="center">{room.slots_used} / 40</TableCell>
                            <TableCell align="center">
                              <Typography
                                variant="body2"
                                fontWeight="bold"
                                color={
                                  room.utilization_percent >= 70
                                    ? 'success.main'
                                    : room.utilization_percent >= 50
                                    ? 'warning.main'
                                    : 'error.main'
                                }
                              >
                                {room.utilization_percent}%
                              </Typography>
                            </TableCell>
                            <TableCell align="center">{room.avg_capacity_usage}%</TableCell>
                            <TableCell align="center">
                              <Chip
                                label={room.utilization_status.replace('_', ' ')}
                                color={getUtilizationColor(room.utilization_status)}
                                size="small"
                                sx={{ textTransform: 'capitalize' }}
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </>
          )}
        </Box>
      )}

      {/* Department Comparison Report Tab */}
      {tabValue === 2 && (
        <Box>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Generate Department Comparison Report
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Compare resource distribution and metrics across all departments
              </Typography>
              <Grid container spacing={2} alignItems="center">
                <Grid item xs={12} md={6}>
                  <Button
                    variant="contained"
                    startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <AssessmentIcon />}
                    onClick={generateDepartmentComparisonReport}
                    disabled={loading}
                    fullWidth
                  >
                    Generate Report
                  </Button>
                </Grid>
                {deptReport && (
                  <Grid item xs={12} md={6}>
                    <Button
                      variant="outlined"
                      startIcon={<DownloadIcon />}
                      onClick={() => downloadReport('department-comparison')}
                      fullWidth
                    >
                      Download JSON
                    </Button>
                  </Grid>
                )}
              </Grid>
            </CardContent>
          </Card>

          {deptReport && (
            <>
              <Card sx={{ mb: 3 }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    University-Wide Summary
                  </Typography>
                  <Divider sx={{ mb: 2 }} />
                  <Grid container spacing={2}>
                    <Grid item xs={6} md={2.4}>
                      <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#f5f5f5' }}>
                        <Typography variant="h5" color="primary" fontWeight="bold">
                          {deptReport.summary.total_departments}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Departments
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={6} md={2.4}>
                      <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#f5f5f5' }}>
                        <Typography variant="h5" color="primary" fontWeight="bold">
                          {deptReport.summary.total_courses}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Courses
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={6} md={2.4}>
                      <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#f5f5f5' }}>
                        <Typography variant="h5" color="primary" fontWeight="bold">
                          {deptReport.summary.total_lecturers}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Lecturers
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={6} md={2.4}>
                      <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#f5f5f5' }}>
                        <Typography variant="h5" color="primary" fontWeight="bold">
                          {deptReport.summary.total_students}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Students
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={6} md={2.4}>
                      <Paper sx={{ p: 2, textAlign: 'center', bgcolor: '#f5f5f5' }}>
                        <Typography variant="h5" color="success.main" fontWeight="bold">
                          {deptReport.summary.average_timetable_completion}%
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Avg Completion
                        </Typography>
                      </Paper>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>

              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Department Comparison
                  </Typography>
                  <Divider sx={{ mb: 2 }} />
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow sx={{ bgcolor: '#f5f5f5' }}>
                          <TableCell><strong>Department</strong></TableCell>
                          <TableCell align="center"><strong>Courses</strong></TableCell>
                          <TableCell align="center"><strong>Lecturers</strong></TableCell>
                          <TableCell align="center"><strong>Students</strong></TableCell>
                          <TableCell align="center"><strong>Avg Hours/Lecturer</strong></TableCell>
                          <TableCell align="center"><strong>Student/Lecturer</strong></TableCell>
                          <TableCell align="center"><strong>Completion</strong></TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {deptReport.data.map((dept: DepartmentComparisonData) => (
                          <TableRow key={dept.department_id} hover>
                            <TableCell>
                              <Typography variant="body2" fontWeight="medium">
                                {dept.name}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {dept.code}
                              </Typography>
                            </TableCell>
                            <TableCell align="center">{dept.courses}</TableCell>
                            <TableCell align="center">{dept.lecturers}</TableCell>
                            <TableCell align="center">{dept.total_students}</TableCell>
                            <TableCell align="center">{dept.avg_hours_per_lecturer}h</TableCell>
                            <TableCell align="center">{dept.student_lecturer_ratio}</TableCell>
                            <TableCell align="center">
                              <Chip
                                label={`${dept.timetable_completion}%`}
                                color={
                                  dept.timetable_completion >= 80
                                    ? 'success'
                                    : dept.timetable_completion >= 50
                                    ? 'warning'
                                    : 'error'
                                }
                                size="small"
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            </>
          )}
        </Box>
      )}
    </Box>
  );
};

export default ReportsPage;
