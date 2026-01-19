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
} from '@mui/material';
import { Add as AddIcon, Edit as EditIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { lecturersAPI, departmentsAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';

interface Lecturer {
  id: number;
  staff_number: string;
  full_name: string;
  email: string;
  department_id: number;
  max_hours_per_week: number;
  teaching_preferences?: {
    avoid_early_morning: boolean;
    avoid_late_afternoon: boolean;
  };
}

const LecturersPage: React.FC = () => {
  const [lecturers, setLecturers] = useState<Lecturer[]>([]);
  const [departments, setDepartments] = useState<unknown[]>([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingLecturer, setEditingLecturer] = useState<Lecturer | null>(null);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    staff_number: '',
    full_name: '',
    email: '',
    department_id: 1,

    max_hours_per_week: 20,
    avoid_early_morning: false,
    avoid_late_afternoon: false,
  });

  const { isCoordinator } = useAuth();

  useEffect(() => {
    void fetchLecturers();
    void fetchDepartments();
  }, []);

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
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingLecturer(null);
    setError('');
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

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" fontWeight="bold">
          Lecturers
        </Typography>
        {isCoordinator && (
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => { handleOpenDialog(); }}
          >
            Add Lecturer
          </Button>
        )}
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => { setError(''); }}>
          {error}
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell><strong>Staff Number</strong></TableCell>
              <TableCell><strong>Full Name</strong></TableCell>
              <TableCell><strong>Email</strong></TableCell>
              <TableCell><strong>Department</strong></TableCell>
              <TableCell><strong>Max Hours/Week</strong></TableCell>
              {isCoordinator && <TableCell align="center"><strong>Actions</strong></TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {lecturers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                  <Typography variant="body1" color="text.secondary">
                    No lecturers found. Click "Add Lecturer" to create one.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              lecturers.map((lecturer) => (
                <TableRow key={lecturer.id} hover>
                  <TableCell>{lecturer.staff_number}</TableCell>
                  <TableCell>{lecturer.full_name}</TableCell>
                  <TableCell>{lecturer.email}</TableCell>
                  <TableCell>
                    <Chip
                      label={departments.find((d: any) => d.id === lecturer.department_id)?.code || 'N/A'}
                      size="small"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <Chip label={`${lecturer.max_hours_per_week}h`} color="primary" size="small" />
                  </TableCell>
                  {isCoordinator && (
                    <TableCell align="center">
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
            label="Email"
            type="email"
            value={formData.email}
            onChange={(e) => { setFormData({ ...formData, email: e.target.value }); }}
            margin="normal"
            required
          />
          <FormControl fullWidth margin="normal" required>
            <InputLabel>Department</InputLabel>
            <Select
              value={formData.department_id}
              label="Department"
              onChange={(e) => { setFormData({ ...formData, department_id: e.target.value as number }); }}
            >
              {departments.map((dept) => (
                <MenuItem key={dept.id} value={dept.id}>
                  {dept.name} ({dept.code})
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
                  control = {
                  < Checkbox checked={formData.avoid_early_morning} onChange={(e) => { setFormData({ ...formData, avoid_early_morning: e.target.checked }); }} />
                }
                }
              label="Avoid Early Morning (07:00)"
              />
              <FormControlLabel
                control={
                  control = {
                  < Checkbox checked={formData.avoid_late_afternoon} onChange={(e) => { setFormData({ ...formData, avoid_late_afternoon: e.target.checked }); }} />
                }
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
    </Box>
  );
};

export default LecturersPage;
