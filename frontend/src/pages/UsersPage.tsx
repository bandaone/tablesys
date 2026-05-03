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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  InputAdornment,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  LockReset as LockResetIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
} from '@mui/icons-material';
import { usersAPI, departmentsAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';
import { formatPersonName } from '../utils/displayFormatters';

interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: 'coordinator' | 'hod';
  department_id?: number;
  is_active: boolean;
}

interface Department {
  id: number;
  name: string;
  code: string;
}

const UsersPage: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [openPasswordDialog, setOpenPasswordDialog] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [resetUserId, setResetUserId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    full_name: '',
    password: '',
    role: 'hod' as 'coordinator' | 'hod',
    department_id: undefined as number | undefined,
    is_active: true,
  });
  const [newPassword, setNewPassword] = useState('');

  const { user: currentUser, isCoordinator } = useAuth();

  useEffect(() => {
    if (isCoordinator) {
      void fetchUsers();
      void fetchDepartments();
    }
  }, [isCoordinator]);

  const fetchDepartments = async () => {
    try {
      const data = await departmentsAPI.getAll();
      setDepartments(data);
    } catch (err) {
      console.error('Failed to load departments');
    }
  };

  const fetchUsers = async () => {
    try {
      const data = await usersAPI.getAll();
      setUsers(data);
    } catch (err) {
      setError('Failed to load users');
    }
  };

  const handleOpenDialog = (user?: User) => {
    if (user) {
      setEditingUser(user);
      setFormData({
        username: user.username,
        email: user.email,
        full_name: user.full_name,
        password: '', // Don't show existing password
        role: user.role,
        department_id: user.department_id,
        is_active: user.is_active,
      });
    } else {
      setEditingUser(null);
      setFormData({
        username: '',
        email: '',
        full_name: '',
        password: '',
        role: 'hod',
        department_id: undefined,
        is_active: true,
      });
    }
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setOpenDialog(false);
    setEditingUser(null);
    setError('');
    setShowPassword(false);
  };

  const handleSubmit = async () => {
    try {
      setError('');
      
      if (editingUser) {
        // Update existing user (password not included in update)
        const updateData = {
          email: formData.email,
          full_name: formData.full_name,
          role: formData.role,
          department_id: formData.department_id || null,
          is_active: formData.is_active,
        };
        await usersAPI.update(editingUser.id, updateData);
        setSuccess('User updated successfully');
      } else {
        // Create new user (requires password)
        if (!formData.password) {
          setError('Password is required for new users');
          return;
        }
        await usersAPI.create(formData);
        setSuccess('User created successfully');
      }
      
      await fetchUsers();
      handleCloseDialog();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(Array.isArray(detail) ? detail[0]?.msg : (detail || 'Failed to save user'));
    }
  };

  const handleDelete = async (id: number, username: string) => {
    if (currentUser?.id === id) {
      setError('Cannot delete your own account');
      return;
    }

    if (window.confirm(`Are you sure you want to delete user "${username}"?`)) {
      try {
        await usersAPI.delete(id);
        setSuccess('User deleted successfully');
        await fetchUsers();
        setTimeout(() => setSuccess(''), 3000);
      } catch (err: any) {
        const detail = err.response?.data?.detail;
        setError(Array.isArray(detail) ? detail[0]?.msg : (detail || 'Failed to delete user'));
      }
    }
  };

  const handleOpenPasswordDialog = (userId: number) => {
    setResetUserId(userId);
    setNewPassword('');
    setShowNewPassword(false);
    setOpenPasswordDialog(true);
  };

  const handleResetPassword = async () => {
    if (!newPassword) {
      setError('Please enter a new password');
      return;
    }

    if (newPassword.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    try {
      await usersAPI.resetPassword(resetUserId!, newPassword);
      setSuccess('Password reset successfully');
      setOpenPasswordDialog(false);
      setResetUserId(null);
      setNewPassword('');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(Array.isArray(detail) ? detail[0]?.msg : (detail || 'Failed to reset password'));
    }
  };

  if (!isCoordinator) {
    return (
      <Box>
        <Alert severity="error">
          Access Denied. Only Coordinators can manage users.
        </Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" fontWeight="bold">
          User Management
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => { handleOpenDialog(); }}
        >
          Add User
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => { setError(''); }}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => { setSuccess(''); }}>
          {success}
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell><strong>Username</strong></TableCell>
              <TableCell><strong>Full Name</strong></TableCell>
              <TableCell><strong>Email</strong></TableCell>
              <TableCell><strong>Role</strong></TableCell>
              <TableCell><strong>Department</strong></TableCell>
              <TableCell><strong>Status</strong></TableCell>
              <TableCell align="center"><strong>Actions</strong></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 4 }}>
                  <Typography variant="body1" color="text.secondary">
                    No users found.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              users.map((user) => (
                <TableRow 
                  key={user.id} 
                  hover
                  sx={{ opacity: user.is_active ? 1 : 0.5 }}
                >
                  <TableCell>
                    <Typography fontWeight="medium">{user.username}</Typography>
                  </TableCell>
                  <TableCell>{formatPersonName(user.full_name)}</TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>
                    <Chip
                      label={user.role.toUpperCase()}
                      color={user.role === 'coordinator' ? 'primary' : 'secondary'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {user.department_id ? (
                      <Chip
                        label={departments.find((d) => d.id === user.department_id)?.code || 'N/A'}
                        size="small"
                        variant="outlined"
                      />
                    ) : (
                      <Typography variant="caption" color="text.secondary">—</Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={user.is_active ? 'Active' : 'Inactive'}
                      color={user.is_active ? 'success' : 'error'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell align="center">
                    <IconButton
                      size="small"
                      color="primary"
                      onClick={() => { handleOpenDialog(user); }}
                      title="Edit user"
                    >
                      <EditIcon />
                    </IconButton>
                    <IconButton
                      size="small"
                      color="warning"
                      onClick={() => { handleOpenPasswordDialog(user.id); }}
                      title="Reset password"
                    >
                      <LockResetIcon />
                    </IconButton>
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => { void handleDelete(user.id, user.username); }}
                      disabled={currentUser?.id === user.id}
                      title={currentUser?.id === user.id ? "Can't delete yourself" : "Delete user"}
                    >
                      <DeleteIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Create/Edit User Dialog */}
      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingUser ? 'Edit User' : 'Add New User'}
        </DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Username"
            value={formData.username}
            onChange={(e) => { setFormData({ ...formData, username: e.target.value }); }}
            margin="normal"
            required
            disabled={!!editingUser} // Can't change username
            helperText={editingUser ? "Username cannot be changed" : ""}
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
          <TextField
            fullWidth
            label="Full Name"
            value={formData.full_name}
            onChange={(e) => { setFormData({ ...formData, full_name: e.target.value }); }}
            margin="normal"
            required
          />
          
          {!editingUser && (
            <TextField
              fullWidth
              label="Password"
              type={showPassword ? 'text' : 'password'}
              value={formData.password}
              onChange={(e) => { setFormData({ ...formData, password: e.target.value }); }}
              margin="normal"
              required
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowPassword(!showPassword)}
                      edge="end"
                    >
                      {showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
              helperText="Minimum 6 characters"
            />
          )}

          <FormControl fullWidth margin="normal" required>
            <InputLabel>Role</InputLabel>
            <Select
              value={formData.role}
              label="Role"
              onChange={(e) => { setFormData({ ...formData, role: e.target.value as 'coordinator' | 'hod' }); }}
            >
              <MenuItem value="hod">HOD (Head of Department)</MenuItem>
              <MenuItem value="coordinator">Coordinator (Full Access)</MenuItem>
            </Select>
          </FormControl>

          <FormControl fullWidth margin="normal">
            <InputLabel>Department</InputLabel>
            <Select
              value={formData.department_id || ''}
              label="Department"
              onChange={(e) => { setFormData({ ...formData, department_id: e.target.value ? Number(e.target.value) : undefined }); }}
            >
              <MenuItem value="">
                <em>None</em>
              </MenuItem>
              {departments.map((dept) => (
                <MenuItem key={dept.id} value={dept.id}>
                  {dept.name} ({dept.code})
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControlLabel
            control={
              <Switch
                checked={formData.is_active}
                onChange={(e) => { setFormData({ ...formData, is_active: e.target.checked }); }}
              />
            }
            label="Active Account"
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={() => { void handleSubmit(); }} variant="contained">
            {editingUser ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Password Reset Dialog */}
      <Dialog open={openPasswordDialog} onClose={() => setOpenPasswordDialog(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Reset User Password</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mt: 2, mb: 2 }}>
            This will reset the user's password. They will need to use this new password to log in.
          </Alert>
          <TextField
            fullWidth
            label="New Password"
            type={showNewPassword ? 'text' : 'password'}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            margin="normal"
            required
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowNewPassword(!showNewPassword)}
                    edge="end"
                  >
                    {showNewPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
            helperText="Minimum 6 characters"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenPasswordDialog(false)}>Cancel</Button>
          <Button onClick={() => { void handleResetPassword(); }} variant="contained" color="warning">
            Reset Password
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default UsersPage;
