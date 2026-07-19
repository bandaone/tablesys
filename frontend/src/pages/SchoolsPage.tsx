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
  IconButton,
  LinearProgress,
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
  Apartment as ApartmentIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Upload as UploadIcon,
} from '@mui/icons-material';
import {
  School,
  SchoolProfileUploadApplyResponse,
  SchoolProfileUploadPreviewResponse,
  schoolsAPI,
} from '../api';
import { useAuth } from '../contexts/AuthContext';
import { useBranding } from '../contexts/BrandingContext';
import {
  BrandedEmptyState,
  DataTableShell,
  GlassFilterBar,
  HeroButton,
  TenantPageHero,
} from '../components/tenant/TenantAdminUI';

const emptyForm = {
  name: '',
  code: '',
  description: '',
};

const SchoolsPage: React.FC = () => {
  const { isTenantAdmin } = useAuth();
  const { branding } = useBranding();
  const primaryColor = branding.primary_color || '#1976d2';
  const secondaryColor = branding.secondary_color || '#9c27b0';

  const [schools, setSchools] = useState<School[]>([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<School | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [uploadSchool, setUploadSchool] = useState<School | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<SchoolProfileUploadPreviewResponse | null>(null);
  const [applyResult, setApplyResult] = useState<SchoolProfileUploadApplyResponse | null>(null);
  const [uploadLoading, setUploadLoading] = useState(false);

  const loadSchools = async () => {
    try {
      setSchools(await schoolsAPI.getAll());
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load schools');
    }
  };

  useEffect(() => {
    if (isTenantAdmin) {
      void loadSchools();
    }
  }, [isTenantAdmin]);

  const handleOpen = (school?: School) => {
    if (school) {
      setEditing(school);
      setForm({
        name: school.name,
        code: school.code,
        description: school.description || '',
      });
    } else {
      setEditing(null);
      setForm(emptyForm);
    }
    setOpen(true);
  };

  const handleSave = async () => {
    try {
      setError('');
      if (editing) {
        await schoolsAPI.update(editing.id, form);
        setSuccess('School updated successfully');
      } else {
        await schoolsAPI.create(form);
        setSuccess('School created successfully');
      }
      setOpen(false);
      setForm(emptyForm);
      setEditing(null);
      await loadSchools();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save school');
    }
  };

  const handleDelete = async (school: School) => {
    if (!window.confirm(`Delete school "${school.name}"?`)) return;
    try {
      await schoolsAPI.delete(school.id);
      setSuccess('School deleted successfully');
      await loadSchools();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete school');
    }
  };

  const closeUploadDialog = () => {
    setUploadSchool(null);
    setUploadFile(null);
    setPreview(null);
    setApplyResult(null);
    setUploadLoading(false);
  };

  const handlePreviewUpload = async () => {
    if (!uploadSchool || !uploadFile) {
      setError('Select a school file before previewing.');
      return;
    }
    try {
      setError('');
      setUploadLoading(true);
      setApplyResult(null);
      const result = await schoolsAPI.previewProfileUpload(uploadSchool.id, uploadFile);
      setPreview(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to preview school profile upload.');
    } finally {
      setUploadLoading(false);
    }
  };

  const handleApplyUpload = async () => {
    if (!uploadSchool || !preview) return;
    try {
      setError('');
      setUploadLoading(true);
      const result = await schoolsAPI.applyProfileUpload(uploadSchool.id, {
        fingerprint: preview.fingerprint,
        expires_at: preview.expires_at,
        rows: preview.rows,
      });
      setApplyResult(result);
      setSuccess(`School profile applied for ${uploadSchool.name}. Coordinators and HODs can now complete the missing details.`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to apply school profile upload.');
    } finally {
      setUploadLoading(false);
    }
  };

  if (!isTenantAdmin) {
    return <Alert severity="info">School management is available to tenant admins only.</Alert>;
  }

  return (
    <Box>
      <TenantPageHero
        title="Schools"
        description="Define the academic structure of the institution with clean school records, stable codes, and clear ownership for downstream scheduling."
        eyebrow="Tenant Admin"
        icon={<ApartmentIcon />}
        primaryColor={primaryColor}
        secondaryColor={secondaryColor}
        meta={<Typography variant="body2" sx={{ color: '#fff' }}>{schools.length} school records configured</Typography>}
        actions={(
          <HeroButton startIcon={<AddIcon />} onClick={() => handleOpen()}>
            Add School
          </HeroButton>
        )}
      />

      {error && <Alert severity="error" sx={{ mb: 2.5 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2.5 }}>{success}</Alert>}

      <GlassFilterBar primaryColor={primaryColor} secondaryColor={secondaryColor}>
        <Typography variant="body2" sx={{ color: '#0f172a', fontWeight: 700 }}>
          Institution structure
        </Typography>
        <Typography variant="body2" sx={{ color: '#475569' }}>
          Keep names, codes, and descriptions consistent so school-scoped users and timetables stay easy to manage.
        </Typography>
      </GlassFilterBar>

      <DataTableShell
        title="School Directory"
        description="All schools available to tenant administration."
        primaryColor={primaryColor}
        secondaryColor={secondaryColor}
      >
        {schools.length === 0 ? (
          <Box sx={{ p: 3 }}>
            <BrandedEmptyState
              title="No schools created yet"
              description="Create your first school to start assigning school coordinators and scoping timetable operations cleanly."
              icon={<ApartmentIcon />}
              primaryColor={primaryColor}
              secondaryColor={secondaryColor}
              action={(
                <Button variant="contained" startIcon={<AddIcon />} onClick={() => handleOpen()} sx={{ borderRadius: 999, textTransform: 'none', fontWeight: 800 }}>
                  Create First School
                </Button>
              )}
            />
          </Box>
        ) : (
          <Table>
            <TableHead>
              <TableRow sx={{ bgcolor: 'rgba(15,23,42,0.03)' }}>
                <TableCell sx={{ fontWeight: 800 }}>Name</TableCell>
                <TableCell sx={{ fontWeight: 800 }}>Code</TableCell>
                <TableCell sx={{ fontWeight: 800 }}>Description</TableCell>
                <TableCell align="right" sx={{ fontWeight: 800 }}>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {schools.map((school) => (
                <TableRow key={school.id} hover>
                  <TableCell>
                    <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>{school.name}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 700, color: 'primary.main' }}>{school.code}</Typography>
                  </TableCell>
                  <TableCell sx={{ color: 'text.secondary' }}>{school.description || 'No description provided.'}</TableCell>
                  <TableCell align="right">
                    <IconButton onClick={() => setUploadSchool(school)} title="Upload school profile">
                      <UploadIcon />
                    </IconButton>
                    <IconButton onClick={() => handleOpen(school)}><EditIcon /></IconButton>
                    <IconButton color="error" onClick={() => handleDelete(school)}><DeleteIcon /></IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DataTableShell>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editing ? 'Edit School' : 'Create School'}</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <TextField
            margin="normal"
            fullWidth
            label="School Name"
            value={form.name}
            onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
          />
          <TextField
            margin="normal"
            fullWidth
            label="Code"
            value={form.code}
            onChange={(e) => setForm((prev) => ({ ...prev, code: e.target.value }))}
          />
          <TextField
            margin="normal"
            fullWidth
            multiline
            minRows={3}
            label="Description"
            value={form.description}
            onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSave}>{editing ? 'Update' : 'Create'}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(uploadSchool)} onClose={closeUploadDialog} fullWidth maxWidth="md">
        <DialogTitle>
          {uploadSchool ? `Upload School Profile: ${uploadSchool.name}` : 'Upload School Profile'}
        </DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <Alert severity="info" sx={{ mb: 2 }}>
            Upload one CSV or Excel file for this school with these columns:
            <Box component="div" sx={{ mt: 1, fontFamily: 'monospace' }}>
              school | programme | year_level | course_code | course_name | lecturer_name
            </Box>
            <Box sx={{ mt: 1 }}>
              Missing course details such as credits and hours will stay pending so the school coordinator or HOD can complete them later in the existing workflows.
            </Box>
          </Alert>

          {uploadLoading && <LinearProgress sx={{ mb: 2 }} />}

          {!preview && !applyResult && (
            <Box>
              <input
                accept=".csv,.xlsx,.xls"
                style={{ display: 'none' }}
                id="school-profile-upload"
                type="file"
                onChange={(event) => {
                  const nextFile = event.target.files?.[0] || null;
                  setUploadFile(nextFile);
                  setPreview(null);
                  setApplyResult(null);
                }}
              />
              <label htmlFor="school-profile-upload">
                <Button component="span" variant={uploadFile ? 'contained' : 'outlined'} fullWidth sx={{ textTransform: 'none', py: 1.5 }}>
                  {uploadFile ? `Selected: ${uploadFile.name}` : 'Select CSV or Excel File'}
                </Button>
              </label>
            </Box>
          )}

          {preview && !applyResult && (
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 1.5 }}>
                Preview Summary
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                <Chip label={`${preview.summary.total_rows} rows`} color="default" />
                <Chip label={`${preview.summary.ready_rows} ready`} color="success" variant="outlined" />
                <Chip label={`${preview.summary.conflicted_rows} conflicts`} color="warning" variant="outlined" />
                <Chip label={`${preview.summary.departments_to_create} departments`} color="primary" variant="outlined" />
                <Chip label={`${preview.summary.courses_to_create} new courses`} color="primary" variant="outlined" />
                <Chip label={`${preview.summary.courses_to_update} course updates`} color="info" variant="outlined" />
                <Chip label={`${preview.summary.lecturers_to_create} new lecturers`} color="secondary" variant="outlined" />
              </Box>

              <Alert severity="info" sx={{ mb: 2 }}>
                Preview expires at {new Date(preview.expires_at).toLocaleString()}.
              </Alert>

              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Row</TableCell>
                    <TableCell>Programme</TableCell>
                    <TableCell>Course</TableCell>
                    <TableCell>Lecturer</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {preview.rows.slice(0, 12).map((row) => (
                    <TableRow key={`${row.row_number}-${row.course_code}`}>
                      <TableCell>{row.row_number}</TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 700 }}>{row.programme}</Typography>
                        <Typography variant="caption" color="text.secondary">{row.department_action} department {row.department_code ? `(${row.department_code})` : ''}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 700 }}>{row.course_code}</Typography>
                        <Typography variant="caption" color="text.secondary">{row.course_action} • Year {row.year_level / 100}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">{row.lecturer_name || 'Pending later'}</Typography>
                        <Typography variant="caption" color="text.secondary">{row.assignment_action} assignment</Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={row.can_apply ? 'Ready' : 'Conflict'}
                          color={row.can_apply ? 'success' : 'warning'}
                          variant="outlined"
                        />
                        {row.issues.length > 0 && (
                          <Box sx={{ mt: 0.75 }}>
                            {row.issues.map((issue) => (
                              <Typography key={issue} variant="caption" color="error" display="block">
                                {issue}
                              </Typography>
                            ))}
                          </Box>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {preview.rows.length > 12 && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  Showing the first 12 preview rows.
                </Typography>
              )}
            </Box>
          )}

          {applyResult && (
            <Box>
              <Alert severity="success" sx={{ mb: 2 }}>
                Applied successfully. The school now has its seeded profile, and the school coordinator or HOD can continue filling in missing course and lecturer details.
              </Alert>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                <Chip label={`${applyResult.created_departments} departments created`} color="primary" variant="outlined" />
                <Chip label={`${applyResult.created_courses} courses created`} color="primary" variant="outlined" />
                <Chip label={`${applyResult.updated_courses} courses updated`} color="info" variant="outlined" />
                <Chip label={`${applyResult.created_lecturers} lecturers created`} color="secondary" variant="outlined" />
                <Chip label={`${applyResult.created_assignments} assignments created`} color="success" variant="outlined" />
                <Chip label={`${applyResult.skipped_rows} rows skipped`} color="warning" variant="outlined" />
              </Box>
              {applyResult.issues.length > 0 && (
                <Box sx={{ maxHeight: 220, overflowY: 'auto' }}>
                  {applyResult.issues.map((issue) => (
                    <Typography key={issue} variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
                      {issue}
                    </Typography>
                  ))}
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeUploadDialog}>
            {applyResult ? 'Close' : 'Cancel'}
          </Button>
          {!preview && !applyResult && (
            <Button variant="contained" disabled={!uploadFile || uploadLoading} onClick={() => { void handlePreviewUpload(); }}>
              Preview
            </Button>
          )}
          {preview && !applyResult && (
            <Button variant="contained" disabled={uploadLoading} onClick={() => { void handleApplyUpload(); }}>
              Apply Profile
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SchoolsPage;
