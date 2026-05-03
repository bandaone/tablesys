import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  Alert,
  Chip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Snackbar,
  CircularProgress,
  Fade,
  Grow,
  Slide,
} from '@mui/material';
import {
  Domain as DomainIcon,
  School as SchoolIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Close as CloseIcon,
  Edit as EditIcon,
} from '@mui/icons-material';
import { departmentsAPI } from '../api';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import TableSkeleton from '../components/skeletons/TableSkeleton';

interface Department {
  id: number;
  code: string;
  name: string;
}

const DepartmentsPage: React.FC = () => {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedDept, setSelectedDept] = useState<Department | null>(null);
  const [newDept, setNewDept] = useState({ name: '', code: '' });
  const [editDept, setEditDept] = useState({ id: 0, name: '', code: '' });
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' });
  const [pageLoading, setPageLoading] = useState(true);
  const navigate = useNavigate();
  const { user } = useAuth();

  const isCoordinatorOrAdmin = user?.role === 'coordinator' || user?.role === 'admin';

  useEffect(() => {
    fetchDepartments().finally(() => setPageLoading(false));
  }, []);

  const fetchDepartments = async () => {
    setLoading(true);
    try {
      const data = await departmentsAPI.getAll();
      setDepartments(data);
    } catch (err) {
      setError('Failed to load departments');
    } finally {
      setLoading(false);
    }
  };

  const getDepartmentColor = (id: number) => {
    const colors = [
      '#4caf50', '#2196f3', '#ff9800', '#9c27b0', '#f44336', '#607d8b',
      '#009688', '#e91e63', '#673ab7', '#3f51b5', '#00bcd4', '#795548'
    ];
    return colors[id % colors.length];
  };

  const handleCreateDepartment = async () => {
    if (!newDept.name.trim() || !newDept.code.trim()) {
      setSnackbar({ open: true, message: 'Please fill in all fields', severity: 'error' });
      return;
    }

    try {
      await departmentsAPI.create(newDept);
      setSnackbar({ open: true, message: 'Department created successfully!', severity: 'success' });
      setCreateDialogOpen(false);
      setNewDept({ name: '', code: '' });
      await fetchDepartments();
    } catch (err: any) {
      setSnackbar({ 
        open: true, 
        message: err.response?.data?.detail || 'Failed to create department', 
        severity: 'error' 
      });
    }
  };

  const handleEditDepartment = async () => {
    if (!editDept.name.trim() || !editDept.code.trim()) {
      setSnackbar({ open: true, message: 'Please fill in all fields', severity: 'error' });
      return;
    }

    try {
      await departmentsAPI.update(editDept.id, { name: editDept.name, code: editDept.code });
      setSnackbar({ open: true, message: 'Department updated successfully!', severity: 'success' });
      setEditDialogOpen(false);
      setEditDept({ id: 0, name: '', code: '' });
      await fetchDepartments();
    } catch (err: any) {
      setSnackbar({ 
        open: true, 
        message: err.response?.data?.detail || 'Failed to update department', 
        severity: 'error' 
      });
    }
  };

  const openEditDialog = (dept: Department) => {
    setEditDept({ id: dept.id, name: dept.name, code: dept.code });
    setEditDialogOpen(true);
  };

  const handleDeleteDepartment = async () => {
    if (!selectedDept) return;

    try {
      await departmentsAPI.delete(selectedDept.id);
      setSnackbar({ open: true, message: 'Department deleted successfully!', severity: 'success' });
      setDeleteDialogOpen(false);
      setSelectedDept(null);
      await fetchDepartments();
    } catch (err: any) {
      setSnackbar({ 
        open: true, 
        message: err.response?.data?.detail || 'Failed to delete department', 
        severity: 'error' 
      });
    }
  };

  const openDeleteDialog = (dept: Department, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedDept(dept);
    setDeleteDialogOpen(true);
  };

  return (
    <Fade in timeout={600}>
      <Box>
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <Typography variant="h4" fontWeight="bold" gutterBottom>
              Departments
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Manage departments within the institution
            </Typography>
          </Box>
          {isCoordinatorOrAdmin && (
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setCreateDialogOpen(true)}
              sx={{
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                transition: 'all 0.3s ease',
                '&:hover': {
                  transform: 'translateY(-2px)',
                  boxShadow: '0 8px 16px rgba(102, 126, 234, 0.3)',
                },
              }}
            >
              Add Department
            </Button>
          )}
        </Box>

        {error && (
          <Slide in direction="down">
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => { setError(''); }}>
              {error}
            </Alert>
          </Slide>
        )}

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Grid container spacing={3}>
            {departments.map((dept, index) => (
              <Grow
                in
                timeout={400 + index * 100}
                key={dept.id}
              >
                <Grid item xs={12} sm={6} md={4}>
                  <Card
                    elevation={3}
                    onClick={() => { navigate(`/courses?dept=${dept.id}`); }}
                    sx={{
                      height: '100%',
                      borderTop: `4px solid ${getDepartmentColor(dept.id)}`,
                      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                      cursor: 'pointer',
                      position: 'relative',
                      '&:hover': {
                        transform: 'translateY(-8px) scale(1.02)',
                        boxShadow: '0 12px 24px rgba(0,0,0,0.15)',
                      },
                    }}
                  >
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2, justifyContent: 'space-between' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          <DomainIcon
                            sx={{
                              fontSize: 40,
                              color: getDepartmentColor(dept.id),
                              mr: 2,
                              transition: 'transform 0.3s ease',
                              '.MuiCard-root:hover &': {
                                transform: 'rotate(10deg) scale(1.1)',
                              },
                            }}
                          />
                          <Chip
                            label={dept.code}
                            sx={{
                              backgroundColor: getDepartmentColor(dept.id),
                              color: 'white',
                              fontWeight: 'bold',
                              transition: 'all 0.3s ease',
                            }}
                          />
                        </Box>
                        <Box>
                          {isCoordinatorOrAdmin && (
                            <IconButton
                              size="small"
                              onClick={(e) => { e.stopPropagation(); openEditDialog(dept); }}
                              sx={{
                                opacity: 0,
                                mr: 0.5,
                                transition: 'all 0.3s ease',
                                '.MuiCard-root:hover &': {
                                  opacity: 1,
                                },
                                '&:hover': {
                                  color: 'primary.main',
                                  transform: 'scale(1.2)',
                                },
                              }}
                            >
                              <EditIcon />
                            </IconButton>
                          )}
                          {isCoordinatorOrAdmin && (
                            <IconButton
                              size="small"
                              onClick={(e) => openDeleteDialog(dept, e)}
                              sx={{
                                opacity: 0,
                                transition: 'all 0.3s ease',
                                '.MuiCard-root:hover &': {
                                  opacity: 1,
                                },
                                '&:hover': {
                                  color: 'error.main',
                                  transform: 'scale(1.2)',
                                },
                              }}
                            >
                              <DeleteIcon />
                            </IconButton>
                          )}
                        </Box>
                      </Box>
                      <Typography variant="h6" fontWeight="bold" gutterBottom>
                        {dept.name}
                      </Typography>
                      <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                        <SchoolIcon fontSize="small" color="action" />
                        <Typography variant="body2" color="text.secondary">
                          Academic Department
                        </Typography>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              </Grow>
            ))}
          </Grid>
        )}

        {departments.length === 0 && !error && !loading && (
          <Fade in>
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <Typography variant="body1" color="text.secondary">
                No departments found. {isCoordinatorOrAdmin && 'Click "Add Department" to create one.'}
              </Typography>
            </Paper>
          </Fade>
        )}

        <Box sx={{ mt: 4 }}>
          <Paper 
            sx={{ 
              p: 3,
              transition: 'all 0.3s ease',
              '&:hover': {
                boxShadow: 4,
              }
            }}
          >
            <Typography variant="h6" fontWeight="bold" gutterBottom>
              About the Departments
            </Typography>
            <Typography variant="body2" paragraph>
              A department is a fundamental organizational unit within your institution. It groups related degree programs, courses, lecturers, and students.
            </Typography>
            <ul>
              <li>
                <Typography variant="body2">
                  Assign <strong>HODs</strong> (Heads of Department) to manage specific departmental operations.
                </Typography>
              </li>
              <li>
                <Typography variant="body2">
                  Each course belongs to one department, which helps organize scheduling.
                </Typography>
              </li>
              <li>
                <Typography variant="body2">
                  Student groups and timetables are organized based on departmental boundaries.
                </Typography>
              </li>
            </ul>
          </Paper>
        </Box>

        {/* Edit Department Dialog */}
        <Dialog 
          open={editDialogOpen} 
          onClose={() => setEditDialogOpen(false)}
          maxWidth="sm"
          fullWidth
          TransitionComponent={Slide}
          TransitionProps={{ direction: 'up' } as any}
        >
          <DialogTitle sx={{ 
            background: 'linear-gradient(135deg, #1976d2 0%, #1565c0 100%)',
            color: 'white',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <span>Edit Department</span>
            <IconButton 
              size="small" 
              onClick={() => setEditDialogOpen(false)}
              sx={{ color: 'white' }}
            >
              <CloseIcon />
            </IconButton>
          </DialogTitle>
          <DialogContent sx={{ mt: 2 }}>
            <TextField
              fullWidth
              label="Department Name"
              value={editDept.name}
              onChange={(e) => setEditDept({ ...editDept, name: e.target.value })}
              margin="normal"
              placeholder="e.g., Computer Science"
              autoFocus
            />
            <TextField
              fullWidth
              label="Department Code"
              value={editDept.code}
              onChange={(e) => setEditDept({ ...editDept, code: e.target.value.toUpperCase() })}
              margin="normal"
              placeholder="e.g., CSC"
              helperText="2-4 uppercase characters"
              inputProps={{ maxLength: 10, style: { textTransform: 'uppercase' } }}
            />
          </DialogContent>
          <DialogActions sx={{ p: 3 }}>
            <Button 
              onClick={() => setEditDialogOpen(false)}
              sx={{ 
                transition: 'all 0.3s ease',
                '&:hover': { transform: 'scale(1.05)' }
              }}
            >
              Cancel
            </Button>
            <Button 
              onClick={handleEditDepartment} 
              variant="contained"
              sx={{ 
                background: 'linear-gradient(135deg, #1976d2 0%, #1565c0 100%)',
                transition: 'all 0.3s ease',
                '&:hover': { 
                  transform: 'scale(1.05)',
                  boxShadow: '0 4px 12px rgba(25, 118, 210, 0.4)'
                }
              }}
            >
              Save Changes
            </Button>
          </DialogActions>
        </Dialog>

        {/* Create Department Dialog */}
        <Dialog 
          open={createDialogOpen} 
          onClose={() => setCreateDialogOpen(false)}
          maxWidth="sm"
          fullWidth
          TransitionComponent={Slide}
          TransitionProps={{ direction: 'up' } as any}
        >
          <DialogTitle sx={{ 
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            color: 'white',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <span>Create New Department</span>
            <IconButton 
              size="small" 
              onClick={() => setCreateDialogOpen(false)}
              sx={{ color: 'white' }}
            >
              <CloseIcon />
            </IconButton>
          </DialogTitle>
          <DialogContent sx={{ mt: 2 }}>
            <TextField
              fullWidth
              label="Department Name"
              value={newDept.name}
              onChange={(e) => setNewDept({ ...newDept, name: e.target.value })}
              margin="normal"
              placeholder="e.g., Computer Science"
              autoFocus
            />
            <TextField
              fullWidth
              label="Department Code"
              value={newDept.code}
              onChange={(e) => setNewDept({ ...newDept, code: e.target.value.toUpperCase() })}
              margin="normal"
              placeholder="e.g., CSC"
              inputProps={{ maxLength: 10 }}
            />
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button 
              onClick={() => setCreateDialogOpen(false)}
              sx={{ 
                transition: 'all 0.3s ease',
                '&:hover': { transform: 'scale(1.05)' }
              }}
            >
              Cancel
            </Button>
            <Button 
              onClick={handleCreateDepartment} 
              variant="contained"
              sx={{ 
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                transition: 'all 0.3s ease',
                '&:hover': { 
                  transform: 'scale(1.05)',
                  boxShadow: '0 4px 12px rgba(102, 126, 234, 0.4)'
                }
              }}
            >
              Create
            </Button>
          </DialogActions>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <Dialog 
          open={deleteDialogOpen} 
          onClose={() => setDeleteDialogOpen(false)}
          TransitionComponent={Grow}
        >
          <DialogTitle sx={{ color: 'error.main' }}>
            Delete Department?
          </DialogTitle>
          <DialogContent>
            <Typography>
              Are you sure you want to delete <strong>{selectedDept?.name}</strong>? 
              This action cannot be undone.
            </Typography>
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button 
              onClick={() => setDeleteDialogOpen(false)}
              sx={{ 
                transition: 'all 0.3s ease',
                '&:hover': { transform: 'scale(1.05)' }
              }}
            >
              Cancel
            </Button>
            <Button 
              onClick={handleDeleteDepartment} 
              color="error" 
              variant="contained"
              sx={{ 
                transition: 'all 0.3s ease',
                '&:hover': { 
                  transform: 'scale(1.05)',
                }
              }}
            >
              Delete
            </Button>
          </DialogActions>
        </Dialog>

        {/* Snackbar for notifications */}
        <Snackbar
          open={snackbar.open}
          autoHideDuration={4000}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
          <Alert 
            onClose={() => setSnackbar({ ...snackbar, open: false })} 
            severity={snackbar.severity}
            sx={{ 
              width: '100%',
              animation: 'slideIn 0.3s ease',
              '@keyframes slideIn': {
                from: { transform: 'translateX(100%)' },
                to: { transform: 'translateX(0)' }
              }
            }}
          >
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Box>
    </Fade>
  );
};

export default DepartmentsPage;
