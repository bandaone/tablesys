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
  MenuItem,
  FormControl,
  InputLabel,
  Select,
} from '@mui/material';
import { Add as AddIcon, Edit as EditIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { groupsAPI, departmentsAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';

interface Group {
  id: number;
  group_name: string;
  level: number;
  size: number;
  department_id: number;
  group_type?: 'general' | 'department' | 'lab_group' | 'tutorial_group';
  display_code?: string;
}

const GroupsPage: React.FC = () => {
  const [groups, setGroups] = useState<Group[]>([]);
  const [departments, setDepartments] = useState<unknown[]>([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [editingGroup, setEditingGroup] = useState<Group | null>(null);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    group_name: '',
    level: 2,
    size: 30,
    department_id: 1,
    group_type: 'department',
    display_code: '',
  });

  const { isCoordinator } = useAuth();

  const levels = [2, 3, 4, 5]; // Year levels for students

  useEffect(() => {
    void fetchGroups();
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

  const fetchGroups = async () => {
    try {
      const data = await groupsAPI.getAll();
      setGroups(data);
    } catch (err) {
      setError('Failed to load groups');
    }
  };

  const handleOpenDialog = (group?: Group) => {
    if (group) {
      setEditingGroup(group);
      setFormData({
        group_name: group.group_name,
        level: group.level,
        size: group.size,
        department_id: group.department_id,
        group_type: group.group_type || 'department',
        display_code: group.display_code || '',
      });
    } else {
      setEditingGroup(null);
      setFormData({
        group_name: '',
        level: 2,
        size: 30,
        department_id: 1,
        group_type: 'department',
        display_code: '',
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingGroup(null);
    setError('');
  };

  const handleSubmit = async () => {
    try {
      if (editingGroup) {
        await groupsAPI.update(editingGroup.id, formData);
      } else {
        await groupsAPI.create(formData);
      }
      await fetchGroups();
      handleCloseDialog();
    } catch (err) {
      setError('Failed to save group');
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this group?')) {
      try {
        await groupsAPI.delete(id);
        await fetchGroups();
      } catch (err) {
        setError('Failed to delete group');
      }
    }
  };

  const getLevelColor = (level: number) => {
    const colors: Record<number, 'success' | 'info' | 'warning' | 'error'> = {
      2: 'success',
      3: 'info',
      4: 'warning',
      5: 'error',
    };
    return colors[level] || 'default';
  };

  const getDepartmentCode = (deptId: number) => {
    const codes: Record<number, string> = { 0: 'GEN', 1: 'AEN', 2: 'CEE', 3: 'EEE', 4: 'GEE', 5: 'MEC' };
    return codes[deptId] || 'UNK';
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" fontWeight="bold">
          Student Groups
        </Typography>
        {isCoordinator && (
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => { handleOpenDialog(); }}
          >
            Add Group
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
              <TableCell><strong>Group Name</strong></TableCell>
              <TableCell><strong>Department</strong></TableCell>
              <TableCell><strong>Level</strong></TableCell>
              <TableCell><strong>Size</strong></TableCell>
              {isCoordinator && <TableCell align="center"><strong>Actions</strong></TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {groups.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} align="center" sx={{ py: 4 }}>
                  <Typography variant="body1" color="text.secondary">
                    No student groups found. Click "Add Group" to create one.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              groups.map((group) => (
                <TableRow key={group.id} hover>
                  <TableCell>
                    <Typography variant="body1" fontWeight="medium">
                      {group.group_name}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={getDepartmentCode(group.department_id)}
                      size="small"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={`Level ${group.level}`}
                      color={getLevelColor(group.level)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={`${group.size} students`}
                      variant="outlined"
                      size="small"
                    />
                  </TableCell>
                  {isCoordinator && (
                    <TableCell align="center">
                      <IconButton
                        size="small"
                        color="primary"
                        onClick={() => { handleOpenDialog(group); }}
                      >
                        <EditIcon />
                      </IconButton>
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => { void handleDelete(group.id); }}
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
          {editingGroup ? 'Edit Student Group' : 'Add New Student Group'}
        </DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Group Name"
            value={formData.group_name}
            onChange={(e) => { setFormData({ ...formData, group_name: e.target.value }); }}
            margin="normal"
            required
            placeholder="e.g., AEN-5A, MEC-3B"
            helperText="Use format: DEPT-LEVEL+Section (e.g., AEN-5A)"
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
            label="Display Code"
            value={formData.display_code}
            onChange={(e) => { setFormData({ ...formData, display_code: e.target.value }); }}
            margin="normal"
            placeholder="e.g., AEN"
            helperText="Short code for timetable grid (e.g., AEN)"
          />
          <FormControl fullWidth margin="normal">
            <InputLabel>Group Type</InputLabel>
            <Select
              value={formData.group_type}
              label="Group Type"
              label="Group Type"
              onChange={(e) => { setFormData({ ...formData, group_type: e.target.value as any }); }}
            >
            >
              <MenuItem value="general">General</MenuItem>
              <MenuItem value="department">Department</MenuItem>
              <MenuItem value="lab_group">Lab Group</MenuItem>
              <MenuItem value="tutorial_group">Tutorial Group</MenuItem>
            </Select>
          </FormControl>
          <TextField
            fullWidth
            select
            label="Level"
            value={formData.level}
            onChange={(e) => { setFormData({ ...formData, level: parseInt(e.target.value) }); }}
            margin="normal"
            required
          >
            {levels.map((level) => (
              <MenuItem key={level} value={level}>
                Level {level}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            fullWidth
            label="Group Size"
            type="number"
            value={formData.size}
            onChange={(e) => { setFormData({ ...formData, size: parseInt(e.target.value) }); }}
            margin="normal"
            required
            inputProps={{ min: 1, max: 200 }}
            helperText="Number of students in this group"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={() => { void handleSubmit(); }} variant="contained">
            {editingGroup ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default GroupsPage;
