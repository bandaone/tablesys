import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import {
  Add as AddIcon,
  LockReset as LockResetIcon,
  ManageAccounts as ManageAccountsIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Search as SearchIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
} from '@mui/icons-material';
import { departmentsAPI, schoolsAPI, School as SchoolRecord, usersAPI } from '../api';
import {
  BrandedEmptyState,
  DataTableShell,
  GlassFilterBar,
  HeroButton,
  lightGlassFieldSx,
  lightGlassSelectMenuProps,
  StatusBadge,
  TenantPageHero,
} from '../components/tenant/TenantAdminUI';
import { useAuth } from '../contexts/AuthContext';
import { useBranding } from '../contexts/BrandingContext';
import { formatPersonName } from '../utils/displayFormatters';

interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: 'tenant_admin' | 'school_coordinator' | 'coordinator' | 'hod' | 'lab_coordinator';
  school_id?: number | null;
  department_id?: number;
  is_active: boolean;
}

interface Department {
  id: number;
  name: string;
  code: string;
}

const roleOptions: Array<{ value: User['role']; label: string }> = [
  { value: 'hod', label: 'HOD' },
  { value: 'lab_coordinator', label: 'Lab Coordinator' },
  { value: 'coordinator', label: 'Coordinator' },
  { value: 'school_coordinator', label: 'School Coordinator' },
  { value: 'tenant_admin', label: 'Tenant Admin' },
];

const UsersPage: React.FC = () => {
  const { user: currentUser, isCoordinator, isTenantAdmin } = useAuth();
  const { branding } = useBranding();
  const primaryColor = branding.primary_color || '#1976d2';
  const secondaryColor = branding.secondary_color || '#9c27b0';

  const [users, setUsers] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [schools, setSchools] = useState<SchoolRecord[]>([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [openPasswordDialog, setOpenPasswordDialog] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [resetUserId, setResetUserId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    full_name: '',
    password: '',
    role: 'hod' as User['role'],
    school_id: undefined as number | undefined,
    department_id: undefined as number | undefined,
    is_active: true,
  });
  const [newPassword, setNewPassword] = useState('');

  const canManageUsers = isCoordinator || isTenantAdmin;

  useEffect(() => {
    if (canManageUsers) {
      void fetchUsers();
      void fetchDepartments();
      void fetchSchools();
    }
  }, [canManageUsers]);

  const fetchSchools = async () => {
    try {
      setSchools(await schoolsAPI.getAll());
    } catch {
      setSchools([]);
    }
  };

  const fetchDepartments = async () => {
    try {
      setDepartments(await departmentsAPI.getAll());
    } catch {
      console.error('Failed to load departments');
    }
  };

  const fetchUsers = async () => {
    try {
      setUsers(await usersAPI.getAll());
    } catch {
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
        password: '',
        role: user.role,
        school_id: user.school_id || undefined,
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
        school_id: !isTenantAdmin && currentUser?.school_id ? currentUser.school_id : undefined,
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
        await usersAPI.update(editingUser.id, {
          email: formData.email,
          full_name: formData.full_name,
          role: formData.role,
          school_id: formData.school_id || null,
          department_id: formData.department_id || null,
          is_active: formData.is_active,
        });
        setSuccess('User updated successfully');
      } else {
        if (!formData.password) {
          setError('Password is required for new users');
          return;
        }
        await usersAPI.create({ ...formData, school_id: formData.school_id || null });
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
    if (!window.confirm(`Are you sure you want to delete user "${username}"?`)) return;

    try {
      await usersAPI.delete(id);
      setSuccess('User deleted successfully');
      await fetchUsers();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(Array.isArray(detail) ? detail[0]?.msg : (detail || 'Failed to delete user'));
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

  const filteredUsers = users.filter((entry) => {
    const matchesSearch = !searchQuery || [entry.username, entry.email, entry.full_name]
      .some((value) => value.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesRole = !roleFilter || entry.role === roleFilter;
    const matchesStatus = !statusFilter || (statusFilter === 'active' ? entry.is_active : !entry.is_active);
    return matchesSearch && matchesRole && matchesStatus;
  });

  if (!canManageUsers) {
    return <Alert severity="error">Access denied. Only tenant admins and school operators can manage users.</Alert>;
  }

  return (
    <Box>
      <TenantPageHero
        title="User Management"
        description="Manage academic operators, school coordinators, and tenant-level administrators with a clearer operational workflow and more reliable account hygiene."
        eyebrow="Access Control"
        icon={<ManageAccountsIcon />}
        primaryColor={primaryColor}
        secondaryColor={secondaryColor}
        meta={(
          <>
            <Typography variant="body2" sx={{ color: '#fff' }}>{users.length} total users</Typography>
            <Typography variant="body2" sx={{ color: '#fff' }}>{users.filter((entry) => entry.is_active).length} active accounts</Typography>
          </>
        )}
        actions={(
          <HeroButton startIcon={<AddIcon />} onClick={() => handleOpenDialog()}>
            Add User
          </HeroButton>
        )}
      />

      {error && <Alert severity="error" sx={{ mb: 2.5 }} onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2.5 }} onClose={() => setSuccess('')}>{success}</Alert>}

      <GlassFilterBar primaryColor={primaryColor} secondaryColor={secondaryColor}>
        <TextField
          size="small"
          placeholder="Search by name, username, or email"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ color: '#64748b' }} />
              </InputAdornment>
            ),
          }}
          sx={{
            ...lightGlassFieldSx,
            minWidth: { xs: '100%', md: 280 },
          }}
        />
        <FormControl size="small" sx={lightGlassFieldSx}>
          <InputLabel>Role</InputLabel>
          <Select
            value={roleFilter}
            label="Role"
            onChange={(e) => setRoleFilter(e.target.value)}
            MenuProps={lightGlassSelectMenuProps}
          >
            <MenuItem value="">All roles</MenuItem>
            {roleOptions.filter((option) => isTenantAdmin || option.value !== 'tenant_admin').map((option) => (
              <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={lightGlassFieldSx}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            label="Status"
            onChange={(e) => setStatusFilter(e.target.value)}
            MenuProps={lightGlassSelectMenuProps}
          >
            <MenuItem value="">All statuses</MenuItem>
            <MenuItem value="active">Active</MenuItem>
            <MenuItem value="inactive">Inactive</MenuItem>
          </Select>
        </FormControl>
      </GlassFilterBar>

      <DataTableShell
        title="Workspace Users"
        description="Scoped operational accounts for this tenant."
        primaryColor={primaryColor}
        secondaryColor={secondaryColor}
      >
        {filteredUsers.length === 0 ? (
          <Box sx={{ p: 3 }}>
            <BrandedEmptyState
              title="No matching users"
              description={users.length === 0
                ? 'Create your first user to start delegating school and department operations.'
                : 'Try adjusting the filters to see more accounts.'}
              icon={<ManageAccountsIcon />}
              primaryColor={primaryColor}
              secondaryColor={secondaryColor}
            />
          </Box>
        ) : (
          <Table>
            <TableHead>
              <TableRow sx={{ bgcolor: 'rgba(15,23,42,0.03)' }}>
                <TableCell sx={{ fontWeight: 800 }}>User</TableCell>
                <TableCell sx={{ fontWeight: 800 }}>Role</TableCell>
                <TableCell sx={{ fontWeight: 800 }}>School</TableCell>
                <TableCell sx={{ fontWeight: 800 }}>Department</TableCell>
                <TableCell sx={{ fontWeight: 800 }}>Status</TableCell>
                <TableCell align="center" sx={{ fontWeight: 800 }}>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredUsers.map((entry) => (
                <TableRow key={entry.id} hover sx={{ opacity: entry.is_active ? 1 : 0.66 }}>
                  <TableCell>
                    <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>{formatPersonName(entry.full_name)}</Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
                      {entry.username} • {entry.email}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <StatusBadge label={entry.role.replace(/_/g, ' ')} subtle />
                  </TableCell>
                  <TableCell>
                    {entry.school_id
                      ? schools.find((school) => school.id === entry.school_id)?.name || 'Unknown school'
                      : 'University-wide'}
                  </TableCell>
                  <TableCell>
                    {entry.department_id
                      ? departments.find((department) => department.id === entry.department_id)?.name || 'Unknown department'
                      : 'Not assigned'}
                  </TableCell>
                  <TableCell>
                    <StatusBadge label={entry.is_active ? 'Active' : 'Inactive'} tone={entry.is_active ? 'success' : 'warning'} subtle />
                  </TableCell>
                  <TableCell align="center">
                    <IconButton color="primary" onClick={() => handleOpenDialog(entry)} title="Edit user">
                      <EditIcon />
                    </IconButton>
                    <IconButton color="warning" onClick={() => handleOpenPasswordDialog(entry.id)} title="Reset password">
                      <LockResetIcon />
                    </IconButton>
                    <IconButton
                      color="error"
                      onClick={() => { void handleDelete(entry.id, entry.username); }}
                      disabled={currentUser?.id === entry.id}
                      title={currentUser?.id === entry.id ? "Can't delete yourself" : 'Delete user'}
                    >
                      <DeleteIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DataTableShell>

      <Dialog open={openDialog} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>{editingUser ? 'Edit User' : 'Add New User'}</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Username"
            value={formData.username}
            onChange={(e) => setFormData({ ...formData, username: e.target.value })}
            margin="normal"
            required
            disabled={!!editingUser}
            helperText={editingUser ? 'Username cannot be changed' : ''}
          />
          <TextField
            fullWidth
            label="Email"
            type="email"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            margin="normal"
            required
          />
          <TextField
            fullWidth
            label="Full Name"
            value={formData.full_name}
            onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
            margin="normal"
            required
          />

          {!editingUser && (
            <TextField
              fullWidth
              label="Password"
              type={showPassword ? 'text' : 'password'}
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              margin="normal"
              required
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton onClick={() => setShowPassword(!showPassword)} edge="end">
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
              onChange={(e) => setFormData({ ...formData, role: e.target.value as User['role'] })}
            >
              <MenuItem value="hod">HOD</MenuItem>
              <MenuItem value="lab_coordinator">Lab Coordinator</MenuItem>
              <MenuItem value="coordinator">Coordinator</MenuItem>
              <MenuItem value="school_coordinator">School Coordinator</MenuItem>
              {isTenantAdmin && <MenuItem value="tenant_admin">Tenant Admin</MenuItem>}
            </Select>
          </FormControl>

          <FormControl fullWidth margin="normal">
            <InputLabel>School</InputLabel>
            <Select
              value={formData.school_id || ''}
              label="School"
              onChange={(e) => setFormData({ ...formData, school_id: e.target.value ? Number(e.target.value) : undefined })}
              disabled={!isTenantAdmin}
            >
              <MenuItem value=""><em>None / University-wide</em></MenuItem>
              {schools.map((school) => (
                <MenuItem key={school.id} value={school.id}>{school.name} ({school.code})</MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth margin="normal">
            <InputLabel>Department</InputLabel>
            <Select
              value={formData.department_id || ''}
              label="Department"
              onChange={(e) => setFormData({ ...formData, department_id: e.target.value ? Number(e.target.value) : undefined })}
            >
              <MenuItem value=""><em>None</em></MenuItem>
              {departments.map((department) => (
                <MenuItem key={department.id} value={department.id}>{department.name} ({department.code})</MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControlLabel
            control={<Switch checked={formData.is_active} onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })} />}
            label="Active Account"
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={() => { void handleSubmit(); }} variant="contained">{editingUser ? 'Update' : 'Create'}</Button>
        </DialogActions>
      </Dialog>

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
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton onClick={() => setShowNewPassword(!showNewPassword)} edge="end">
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
          <Button variant="contained" color="warning" onClick={() => { void handleResetPassword(); }}>
            Reset Password
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default UsersPage;
