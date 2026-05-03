import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Paper, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Button, Chip, IconButton, Drawer, Grid, CircularProgress,
  Alert, Tooltip, Stack, Divider, TextField, MenuItem, Switch, FormControlLabel,
  Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions,
  InputAdornment, TablePagination, Tabs, Tab, List, ListItem,
  ListItemText, ListItemSecondaryAction, Snackbar
} from '@mui/material';
import {
  Block as BlockIcon, CheckCircle as CheckCircleIcon,
  Logout as LogoutIcon, Storage as StorageIcon,
  Security as SecurityIcon, Bolt as BoltIcon,
  Memory as MemoryIcon, People as PeopleIcon,
  AddCircle as AddCircleIcon, Login as LoginIcon,
  Search as SearchIcon, Delete as DeleteIcon,
  Warning as WarningIcon, Visibility as VisibilityIcon,
  VpnKey as VpnKeyIcon, ContentCopy as ContentCopyIcon,
  CheckCircleOutline as CopiedIcon
} from '@mui/icons-material';
import { superadminAPI } from '../api';
import { sisAPI, SisApiKey, SisApiKeyCreated } from '../api';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

type TenantRegistrationForm = {
  name: string;
  short_name: string;
  domain: string;
  timezone: string;
  plan_tier: 'free' | 'pro' | 'enterprise';
  max_users: number;
  primary_color: string;
  secondary_color: string;
  tagline: string;
  coordinator_username: string;
  coordinator_email: string;
  coordinator_password: string;
  coordinator_full_name: string;
};

const defaultRegistrationForm: TenantRegistrationForm = {
  name: '',
  short_name: '',
  domain: '',
  timezone: 'Africa/Harare',
  plan_tier: 'free',
  max_users: 0,
  primary_color: '#1976d2',
  secondary_color: '#9c27b0',
  tagline: '',
  coordinator_username: '',
  coordinator_email: '',
  coordinator_password: '',
  coordinator_full_name: ''
};

export default function SuperAdminPage() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  // ── existing state ───────────────────────────────────────────────────────
  const [telemetry, setTelemetry] = useState<any>(null);
  const [analytics, setAnalytics] = useState<any>(null);
  const [universities, setUniversities] = useState<any[]>([]);
  const [totalUniversities, setTotalUniversities] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const [registerOpen, setRegisterOpen] = useState(false);
  const [registerLoading, setRegisterLoading] = useState(false);
  const [registerMessage, setRegisterMessage] = useState('');
  const [form, setForm] = useState<TenantRegistrationForm>(defaultRegistrationForm);
  const [unlimitedUsers, setUnlimitedUsers] = useState(true);

  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [tenantToDelete, setTenantToDelete] = useState<any>(null);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');

  const [detailsOpen, setDetailsOpen] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState<any>(null);

  // ── tab state ────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState(0);

  // ── Agent Gamma: SIS API key state ───────────────────────────────────────
  const [sisKeys, setSisKeys] = useState<SisApiKey[]>([]);
  const [sisKeysLoading, setSisKeysLoading] = useState(false);
  const [sisKeyError, setSisKeyError] = useState('');
  const [newKeyLabel, setNewKeyLabel] = useState('');
  const [newKeyNotes, setNewKeyNotes] = useState('');
  const [generatingKey, setGeneratingKey] = useState(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<SisApiKeyCreated | null>(null);
  const [revokingKeyId, setRevokingKeyId] = useState<number | null>(null);
  const [copySnack, setCopySnack] = useState(false);

  const loadSisKeys = async () => {
    try {
      setSisKeysLoading(true);
      const keys = await sisAPI.listKeys();
      setSisKeys(keys);
    } catch (err: any) {
      setSisKeyError(err?.response?.data?.detail || 'Failed to load API keys.');
    } finally {
      setSisKeysLoading(false);
    }
  };

  const handleGenerateKey = async () => {
    if (!newKeyLabel.trim()) return;
    try {
      setGeneratingKey(true);
      setSisKeyError('');
      const created = await sisAPI.generateKey({ label: newKeyLabel.trim(), notes: newKeyNotes.trim() || undefined });
      setNewlyCreatedKey(created);
      setNewKeyLabel('');
      setNewKeyNotes('');
      await loadSisKeys();
    } catch (err: any) {
      setSisKeyError(err?.response?.data?.detail || 'Failed to generate API key.');
    } finally {
      setGeneratingKey(false);
    }
  };

  const handleRevokeKey = async (keyId: number) => {
    try {
      setRevokingKeyId(keyId);
      await sisAPI.revokeKey(keyId);
      await loadSisKeys();
    } catch (err: any) {
      setSisKeyError(err?.response?.data?.detail || 'Failed to revoke key.');
    } finally {
      setRevokingKeyId(null);
    }
  };

  const handleCopyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    setCopySnack(true);
  };

  const viewTenantDetails = (tenant: any) => {
    setSelectedTenant(tenant);
    setDetailsOpen(true);
  };

  useEffect(() => {
    loadTelemetryOnly();
    const interval = setInterval(loadTelemetryOnly, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (activeTab === 1) loadSisKeys();
  }, [activeTab]);

  useEffect(() => {
    const timer = setTimeout(loadData, 350);
    return () => clearTimeout(timer);
  }, [page, rowsPerPage, searchQuery]);

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await superadminAPI.getUniversities(page * rowsPerPage, rowsPerPage, searchQuery);
      setUniversities(res.items);
      setTotalUniversities(res.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load organizations.');
    } finally {
      setLoading(false);
    }
  };

  const loadTelemetryOnly = async () => {
    try {
      const res = await superadminAPI.getTelemetry();
      setTelemetry(res);
      const analyticsRes = await superadminAPI.getAnalytics();
      setAnalytics(analyticsRes);
    } catch {
      // silent
    }
  };

  const toggleStatus = async (id: number, current: boolean) => {
    try {
      setActionLoading(id);
      await superadminAPI.updateUniversity(id, { is_active: !current });
      await loadData();
    } catch {
      setError('Failed to update status.');
    } finally {
      setActionLoading(null);
    }
  };

  const confirmDeleteTenant = (u: any) => {
    setTenantToDelete(u);
    setDeleteConfirmation('');
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!tenantToDelete) return;
    try {
      setDeleteDialogOpen(false);
      setActionLoading(tenantToDelete.id);
      await superadminAPI.wipeUniversity(tenantToDelete.id);
      await loadData();
    } catch {
      setError('Failed to delete organization.');
    } finally {
      setActionLoading(null);
      setTenantToDelete(null);
    }
  };

  const enterTenant = async (id: number) => {
    try {
      setActionLoading(id);
      const resp = await superadminAPI.impersonateUniversity(id);
      sessionStorage.setItem('superadmin_impersonator', 'true');
      sessionStorage.setItem('token', resp.access_token);
      sessionStorage.setItem('user', JSON.stringify(resp.user));
      localStorage.setItem('university_id', id.toString());
      navigate('/dashboard', { replace: true });
      window.location.reload();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Impersonation failed.');
    } finally {
      setActionLoading(null);
    }
  };

  const updateForm = (key: keyof TenantRegistrationForm, value: string | number) => {
    setForm(prev => ({ ...prev, [key]: value }));
  };

  const registerTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setRegisterLoading(true);
      setRegisterMessage('');
      const payload = { ...form };
      if (unlimitedUsers) payload.max_users = 0;
      await superadminAPI.registerUniversity({
        ...payload,
        short_name: payload.short_name || null,
        tagline: payload.tagline || null
      });
      setRegisterMessage('Organization created successfully.');
      setForm(defaultRegistrationForm);
      setUnlimitedUsers(true);
      await loadData();
    } catch (err: any) {
      setRegisterMessage(err?.response?.data?.detail || 'Registration failed.');
    } finally {
      setRegisterLoading(false);
    }
  };

  const getTierColor = (tier: string) => {
    switch (tier.toLowerCase()) {
      case 'pro': return 'primary';
      case 'enterprise': return 'secondary';
      default: return 'default';
    }
  };

  if (loading && !telemetry) {
    return (
      <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress size={40} />
      </Box>
    );
  }

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#f9fafb', p: { xs: 2, md: 4 } }}>

      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h5" fontWeight={700} color="text.primary">
            Platform Administration
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Manage organizations, monitor services, and control access.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Chip
            icon={<SecurityIcon sx={{ fontSize: 16 }} />}
            label="Super Admin"
            size="small"
            variant="outlined"
            sx={{ fontWeight: 600 }}
          />
          <Button
            size="small"
            startIcon={<LogoutIcon />}
            variant="outlined"
            color="inherit"
            onClick={() => { logout(); navigate('/login'); }}
          >
            Log out
          </Button>
        </Stack>
      </Box>

      {/* Tab navigation */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)} aria-label="superadmin tabs">
          <Tab label="Organizations" id="sa-tab-0" aria-controls="sa-panel-0" />
          <Tab
            label="SIS API Keys"
            id="sa-tab-1"
            aria-controls="sa-panel-1"
            icon={<VpnKeyIcon sx={{ fontSize: 16 }} />}
            iconPosition="start"
          />
        </Tabs>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* ── ORGANIZATIONS TAB ──────────────────────────────────────────── */}
      <Box role="tabpanel" id="sa-panel-0" hidden={activeTab !== 0}>
      <Grid container spacing={2} sx={{ mb: 4 }}>
        {[
          { label: 'Total Users', value: telemetry?.active_users ?? '–', icon: <PeopleIcon />, color: '#1976d2' },
          { label: 'Organizations', value: telemetry?.total_universities ?? '–', icon: <StorageIcon />, color: '#2e7d32' },
          { label: 'Active Jobs', value: telemetry?.active_solver_jobs ?? '–', icon: <BoltIcon />, color: '#ed6c02' },
          {
            label: 'Redis',
            value: telemetry?.redis_status === 'online' ? 'Online' : telemetry ? 'Offline' : '–',
            icon: <MemoryIcon />,
            color: telemetry?.redis_status === 'online' ? '#2e7d32' : '#d32f2f'
          },
        ].map((stat, i) => (
          <Grid item xs={6} md={3} key={i}>
            <Paper variant="outlined" sx={{ p: 2.5, display: 'flex', alignItems: 'center', gap: 2 }}>
              <Box sx={{ color: stat.color, display: 'flex' }}>
                {stat.icon}
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  {stat.label}
                </Typography>
                <Typography variant="h6" fontWeight={700} color="text.primary">
                  {typeof stat.value === 'number' ? stat.value.toLocaleString() : stat.value}
                </Typography>
              </Box>
            </Paper>
          </Grid>
        ))}
      </Grid>

      {/* Analytics Visualizations */}
      {analytics && (
        <Grid container spacing={3} sx={{ mb: 4 }}>
          {/* Top Organizations by Load */}
          <Grid item xs={12} md={4}>
            <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2, color: 'text.secondary', textTransform: 'uppercase' }}>
                Top Tenants by Users
              </Typography>
              <Stack spacing={1.5}>
                {analytics.users_per_org.map((org: any, i: number) => {
                  const percent = Math.min((org.user_count / (org.max_users || Math.max(org.user_count, 1))) * 100, 100);
                  return (
                    <Box key={i}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                        <Typography variant="body2" fontWeight={600} noWrap sx={{ maxWidth: '65%' }}>{org.name}</Typography>
                        <Typography variant="caption" color="text.secondary">{org.user_count} / {org.max_users || '∞'}</Typography>
                      </Box>
                      <Box sx={{ width: '100%', bgcolor: 'grey.100', borderRadius: 1, height: 6, overflow: 'hidden' }}>
                        <Box sx={{ width: `${percent}%`, bgcolor: percent > 90 ? 'error.main' : 'primary.main', height: '100%', transition: 'width 1s ease' }} />
                      </Box>
                    </Box>
                  );
                })}
              </Stack>
            </Paper>
          </Grid>

          {/* Plan Distribution */}
          <Grid item xs={12} md={4}>
            <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2, color: 'text.secondary', textTransform: 'uppercase' }}>
                Plan Distribution
              </Typography>
              <Stack spacing={2}>
                {analytics.plan_distribution.map((plan: any, i: number) => {
                  const total = analytics.plan_distribution.reduce((acc: number, val: any) => acc + val.count, 0);
                  const percent = total > 0 ? (plan.count / total) * 100 : 0;
                  return (
                    <Box key={i} sx={{ display: 'flex', alignItems: 'center' }}>
                      <Box sx={{ width: 85 }}>
                        <Chip label={plan.tier} size="small" variant="outlined" color={plan.tier === 'enterprise' ? 'secondary' : plan.tier === 'pro' ? 'primary' : 'default'} sx={{ textTransform: 'capitalize' }} />
                      </Box>
                      <Box sx={{ flexGrow: 1, ml: 2, mr: 2, position: 'relative' }}>
                         <Box sx={{ width: '100%', bgcolor: 'grey.100', borderRadius: 1, height: 8 }} />
                         <Box sx={{ width: `${percent}%`, bgcolor: plan.tier === 'enterprise' ? 'secondary.main' : plan.tier === 'pro' ? 'primary.main' : 'grey.400', height: 8, borderRadius: 1, position: 'absolute', top: 0, left: 0, transition: 'width 1s ease' }} />
                      </Box>
                      <Typography variant="body2" fontWeight={600}>{plan.count}</Typography>
                    </Box>
                  );
                })}
              </Stack>
            </Paper>
          </Grid>

          {/* Recent Audit Events */}
          <Grid item xs={12} md={4}>
            <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
               <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2, color: 'text.secondary', textTransform: 'uppercase' }}>
                Platform Audit Feed
              </Typography>
              <Stack spacing={1.5}>
                 {analytics.recent_events.map((evt: any, i: number) => (
                   <Box key={i} sx={{ display: 'flex', flexDirection: 'column', pb: 1.5, borderBottom: i < analytics.recent_events.length - 1 ? '1px dashed' : 'none', borderColor: 'divider' }}>
                      <Typography variant="caption" color="primary.main" fontWeight={600}>
                         {evt.action.toUpperCase()} {evt.entity_type}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                         {evt.user_email || 'System'} • {new Date(evt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </Typography>
                   </Box>
                 ))}
                 {analytics.recent_events.length === 0 && (
                   <Typography variant="caption" color="text.secondary">No recent events logged.</Typography>
                 )}
              </Stack>
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Organizations Table */}
      <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
        <Box sx={{ p: 2.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Typography variant="subtitle1" fontWeight={700}>Organizations</Typography>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <TextField
              size="small"
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setPage(0); }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ fontSize: 20, color: 'text.disabled' }} />
                  </InputAdornment>
                ),
              }}
              sx={{ width: 220 }}
            />
            <Button
              variant="contained"
              size="small"
              startIcon={<AddCircleIcon />}
              onClick={() => setRegisterOpen(true)}
              disableElevation
            >
              Add Organization
            </Button>
          </Stack>
        </Box>

        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: '#f9fafb' }}>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>Name</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>Domain</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>Plan</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>Users</TableCell>
                <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>Status</TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary' }}>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {universities.map(u => (
                <TableRow key={u.id} hover>
                  <TableCell>
                    <Typography variant="body2" fontWeight={600}>{u.name}</Typography>
                    <Typography variant="caption" color="text.secondary">ID: {u.id}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', color: 'text.secondary' }}>{u.domain}</Typography>
                  </TableCell>
                  <TableCell>
                    <Chip label={u.plan_tier} size="small" color={getTierColor(u.plan_tier) as any} variant="outlined" sx={{ fontWeight: 600, textTransform: 'capitalize' }} />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {u.user_count}{u.max_users > 0 ? ` / ${u.max_users}` : ''}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={u.is_active ? 'Active' : 'Suspended'}
                      size="small"
                      color={u.is_active ? 'success' : 'error'}
                      variant="outlined"
                      sx={{ fontWeight: 500 }}
                    />
                  </TableCell>
                  <TableCell align="right">
                    {actionLoading === u.id ? (
                      <CircularProgress size={20} />
                    ) : (
                      <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                        <Tooltip title="View Details">
                          <IconButton size="small" onClick={() => viewTenantDetails(u)}>
                            <VisibilityIcon fontSize="small" color="info" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title={u.is_active ? 'Suspend' : 'Activate'}>
                          <IconButton size="small" onClick={() => toggleStatus(u.id, u.is_active)}>
                            {u.is_active ? <BlockIcon fontSize="small" color="warning" /> : <CheckCircleIcon fontSize="small" color="success" />}
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Impersonate">
                          <span>
                            <IconButton size="small" onClick={() => enterTenant(u.id)} disabled={!u.is_active}>
                              <LoginIcon fontSize="small" color={u.is_active ? 'primary' : 'disabled'} />
                            </IconButton>
                          </span>
                        </Tooltip>
                        <Tooltip title="Delete">
                          <IconButton size="small" onClick={() => confirmDeleteTenant(u)}>
                            <DeleteIcon fontSize="small" color="error" />
                          </IconButton>
                        </Tooltip>
                      </Stack>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {universities.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} sx={{ textAlign: 'center', py: 6 }}>
                    <Typography color="text.secondary">No organizations found.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>

        <TablePagination
          component="div"
          count={totalUniversities}
          page={page}
          onPageChange={(_, p) => setPage(p)}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={(e) => { setRowsPerPage(parseInt(e.target.value, 10)); setPage(0); }}
          rowsPerPageOptions={[5, 10, 25, 50]}
        />
      </Paper>

      </Box> {/* end tabpanel 0 */}

      {/* ── SIS API KEYS TAB ─────────────────────────────────────────────── */}
      <Box role="tabpanel" id="sa-panel-1" hidden={activeTab !== 1}>

        {sisKeyError && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setSisKeyError('')}>
            {sisKeyError}
          </Alert>
        )}

        {/* Newly created key — show raw key ONE time */}
        {newlyCreatedKey && (
          <Alert
            severity="success"
            sx={{ mb: 3, fontFamily: 'monospace', wordBreak: 'break-all' }}
            action={
              <Stack direction="row" spacing={1}>
                <Tooltip title="Copy key">
                  <IconButton size="small" onClick={() => handleCopyKey(newlyCreatedKey.raw_key)}>
                    <ContentCopyIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Button size="small" color="inherit" onClick={() => setNewlyCreatedKey(null)}>Dismiss</Button>
              </Stack>
            }
          >
            <Typography variant="body2" fontWeight={700} gutterBottom>
              New key generated — copy it now. It will NOT be shown again.
            </Typography>
            <Typography variant="caption" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
              {newlyCreatedKey.raw_key}
            </Typography>
          </Alert>
        )}

        <Grid container spacing={3}>
          {/* Generate new key */}
          <Grid item xs={12} md={4}>
            <Paper variant="outlined" sx={{ p: 2.5 }}>
              <Typography variant="subtitle1" fontWeight={700} gutterBottom>
                Generate New API Key
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5 }}>
                Each key is scoped to your university and authenticates SIS webhook
                calls via the <code>X-SIS-API-Key</code> header.
              </Typography>
              <Stack spacing={2}>
                <TextField
                  id="sis-key-label"
                  size="small"
                  label="Label"
                  placeholder="e.g. Banner Production"
                  value={newKeyLabel}
                  onChange={(e) => setNewKeyLabel(e.target.value)}
                  fullWidth
                  required
                />
                <TextField
                  id="sis-key-notes"
                  size="small"
                  label="Notes (optional)"
                  placeholder="Used by Banner integration team"
                  value={newKeyNotes}
                  onChange={(e) => setNewKeyNotes(e.target.value)}
                  fullWidth
                  multiline
                  rows={2}
                />
                <Button
                  id="sis-generate-key-btn"
                  variant="contained"
                  disableElevation
                  startIcon={generatingKey ? <CircularProgress size={16} color="inherit" /> : <VpnKeyIcon />}
                  onClick={handleGenerateKey}
                  disabled={generatingKey || !newKeyLabel.trim()}
                >
                  {generatingKey ? 'Generating…' : 'Generate Key'}
                </Button>
              </Stack>
            </Paper>

            {/* Webhook endpoints reference */}
            <Paper variant="outlined" sx={{ p: 2.5, mt: 2 }}>
              <Typography variant="subtitle2" fontWeight={700} gutterBottom>Webhook Endpoints</Typography>
              <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 1 }}>
                All endpoints accept <code>X-SIS-API-Key</code> header.
              </Typography>
              {[
                ['POST', '/api/v1/sis/webhooks/students'],
                ['POST', '/api/v1/sis/webhooks/lecturers'],
                ['POST', '/api/v1/sis/webhooks/courses'],
                ['POST', '/api/v1/sis/webhooks/groups'],
                ['POST', '/api/v1/sis/webhooks/enrolments'],
              ].map(([method, path]) => (
                <Box key={path} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.8 }}>
                  <Chip label={method} size="small" color="primary" variant="outlined" sx={{ minWidth: 52, fontSize: 11 }} />
                  <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary', fontSize: '0.72rem' }}>
                    {path}
                  </Typography>
                </Box>
              ))}
            </Paper>
          </Grid>

          {/* Key list */}
          <Grid item xs={12} md={8}>
            <Paper variant="outlined" sx={{ p: 0, overflow: 'hidden' }}>
              <Box sx={{ px: 2.5, py: 2, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle1" fontWeight={700}>API Keys</Typography>
                {sisKeysLoading && <CircularProgress size={18} />}
              </Box>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor: '#f9fafb' }}>
                      <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>Label</TableCell>
                      <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>Prefix</TableCell>
                      <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>Status</TableCell>
                      <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>Last Used</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary' }}>Action</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {sisKeys.map((k) => (
                      <TableRow key={k.id} hover>
                        <TableCell>
                          <Typography variant="body2" fontWeight={600}>{k.label}</Typography>
                          {k.notes && <Typography variant="caption" color="text.secondary">{k.notes}</Typography>}
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption" sx={{ fontFamily: 'monospace', bgcolor: 'grey.100', px: 0.8, py: 0.3, borderRadius: 1 }}>
                            {k.key_prefix}…
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={k.is_active ? 'Active' : 'Revoked'}
                            size="small"
                            color={k.is_active ? 'success' : 'default'}
                            variant="outlined"
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption" color="text.secondary">
                            {k.last_used_at ? new Date(k.last_used_at).toLocaleString() : 'Never'}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          {revokingKeyId === k.id ? (
                            <CircularProgress size={18} />
                          ) : (
                            <Tooltip title={k.is_active ? 'Revoke key' : 'Already revoked'}>
                              <span>
                                <IconButton
                                  size="small"
                                  disabled={!k.is_active}
                                  onClick={() => handleRevokeKey(k.id)}
                                >
                                  <DeleteIcon fontSize="small" color={k.is_active ? 'error' : 'disabled'} />
                                </IconButton>
                              </span>
                            </Tooltip>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                    {sisKeys.length === 0 && !sisKeysLoading && (
                      <TableRow>
                        <TableCell colSpan={5} sx={{ textAlign: 'center', py: 6 }}>
                          <VpnKeyIcon sx={{ fontSize: 36, color: 'text.disabled', mb: 1 }} />
                          <Typography color="text.secondary" variant="body2">
                            No API keys yet. Generate one to start receiving SIS data.
                          </Typography>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        </Grid>
      </Box> {/* end tabpanel 1 */}

      {/* Copy snackbar */}
      <Snackbar
        open={copySnack}
        autoHideDuration={2500}
        onClose={() => setCopySnack(false)}
        message="API key copied to clipboard"
      />

      {/* Delete Confirmation */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <WarningIcon color="error" /> Confirm Deletion
        </DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            This will permanently delete <strong>{tenantToDelete?.name}</strong> and all associated data. This action cannot be undone.
          </DialogContentText>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Type <strong>{tenantToDelete?.domain}</strong> to confirm.
          </Typography>
          <TextField
            fullWidth
            size="small"
            placeholder={tenantToDelete?.domain}
            value={deleteConfirmation}
            onChange={(e) => setDeleteConfirmation(e.target.value)}
            autoFocus
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5 }}>
          <Button onClick={() => setDeleteDialogOpen(false)} color="inherit">Cancel</Button>
          <Button
            onClick={handleDeleteConfirm}
            color="error"
            variant="contained"
            disableElevation
            disabled={deleteConfirmation !== tenantToDelete?.domain}
          >
            Delete Organization
          </Button>
        </DialogActions>
      </Dialog>

      {/* Details Drawer */}
      <Drawer
        anchor="right"
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        PaperProps={{ sx: { width: { xs: '100%', md: 480 } } }}
      >
        {selectedTenant && (
          <Box sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Typography variant="h6" fontWeight={700} gutterBottom>
              Tenant Information
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Detailed metrics and configuration for this organization.
            </Typography>

            <Box sx={{ flexGrow: 1, overflowY: 'auto', pr: 1 }}>
              <Stack spacing={3}>
                {/* General Info */}
                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>General configuration</Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">Name</Typography>
                      <Typography variant="body2" fontWeight={600}>{selectedTenant.name}</Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">Short Name</Typography>
                      <Typography variant="body2" fontWeight={600}>{selectedTenant.short_name || 'N/A'}</Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">Domain / Subdomain</Typography>
                      <Typography variant="body2" fontWeight={600}>{selectedTenant.domain}</Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">Timezone</Typography>
                      <Typography variant="body2" fontWeight={600}>{selectedTenant.timezone}</Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">Registered At</Typography>
                      <Typography variant="body2" fontWeight={600}>{selectedTenant.registered_at ? new Date(selectedTenant.registered_at).toLocaleDateString() : 'N/A'}</Typography>
                    </Grid>
                  </Grid>
                </Box>

                <Divider />

                {/* Plan Metrics */}
                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>Subscription & Usage</Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">Plan Tier</Typography>
                      <Box sx={{ mt: 0.5 }}>
                        <Chip label={selectedTenant.plan_tier} size="small" color={getTierColor(selectedTenant.plan_tier) as any} variant="outlined" sx={{ fontWeight: 600, textTransform: 'capitalize' }} />
                      </Box>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">Active Status</Typography>
                      <Box sx={{ mt: 0.5 }}>
                        <Chip label={selectedTenant.is_active ? 'Active' : 'Suspended'} size="small" color={selectedTenant.is_active ? 'success' : 'error'} variant="outlined" sx={{ fontWeight: 500 }} />
                      </Box>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">Current Users</Typography>
                      <Typography variant="body2" fontWeight={600}>{selectedTenant.user_count}</Typography>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">Max Allowed Users</Typography>
                      <Typography variant="body2" fontWeight={600}>{selectedTenant.max_users === 0 ? 'Unlimited' : selectedTenant.max_users}</Typography>
                    </Grid>
                  </Grid>
                </Box>

                <Divider />

                {/* Branding Details */}
                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>Visual Branding</Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">Primary Color</Typography>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                        <Box sx={{ width: 24, height: 24, borderRadius: 1, bgcolor: selectedTenant.primary_color || '#1976d2', border: '1px solid #ccc' }} />
                        <Typography variant="body2">{selectedTenant.primary_color || '#1976d2'}</Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption" color="text.secondary">Secondary Color</Typography>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                        <Box sx={{ width: 24, height: 24, borderRadius: 1, bgcolor: selectedTenant.secondary_color || '#9c27b0', border: '1px solid #ccc' }} />
                        <Typography variant="body2">{selectedTenant.secondary_color || '#9c27b0'}</Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={12}>
                      <Typography variant="caption" color="text.secondary">Tagline</Typography>
                      <Typography variant="body2" fontWeight={600} fontStyle={selectedTenant.tagline ? 'normal' : 'italic'}>
                        {selectedTenant.tagline || 'No tagline set'}
                      </Typography>
                    </Grid>
                    <Grid item xs={12}>
                       <Typography variant="caption" color="text.secondary">Logo Asset</Typography>
                       <Typography variant="body2" fontWeight={600} color="text.secondary">
                         {selectedTenant.logo_url || 'Default System Logo'}
                       </Typography>
                    </Grid>
                  </Grid>
                </Box>
              </Stack>
            </Box>

            <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider', display: 'flex', justifyContent: 'flex-end' }}>
              <Button onClick={() => setDetailsOpen(false)} color="inherit" variant="outlined">Close</Button>
            </Box>
          </Box>
        )}
      </Drawer>

      {/* Registration Drawer */}
      <Drawer
        anchor="right"
        open={registerOpen}
        onClose={() => setRegisterOpen(false)}
        PaperProps={{ sx: { width: { xs: '100%', md: 520 } } }}
      >
        <Box component="form" onSubmit={registerTenant} sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
          <Typography variant="h6" fontWeight={700} gutterBottom>
            New Organization
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Create a new tenant with an initial administrator account.
          </Typography>

          <Box sx={{ flexGrow: 1, overflowY: 'auto', pr: 1 }}>
            <Stack spacing={3}>
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>Organization</Typography>
                <Grid container spacing={2}>
                  <Grid item xs={12}>
                    <TextField size="small" label="Name" value={form.name} onChange={(e) => updateForm('name', e.target.value)} required fullWidth />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField size="small" label="Short Name" value={form.short_name} onChange={(e) => updateForm('short_name', e.target.value)} fullWidth />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField size="small" label="Domain" placeholder="acme.tablesys.com" value={form.domain} onChange={(e) => updateForm('domain', e.target.value)} required fullWidth />
                  </Grid>
                </Grid>
              </Box>

              <Divider />

              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>Plan</Typography>
                <Grid container spacing={2} alignItems="center">
                  <Grid item xs={6}>
                    <TextField
                      select size="small" label="Tier" value={form.plan_tier}
                      onChange={(e) => updateForm('plan_tier', e.target.value)} fullWidth
                    >
                      <MenuItem value="free">Free</MenuItem>
                      <MenuItem value="pro">Pro</MenuItem>
                      <MenuItem value="enterprise">Enterprise</MenuItem>
                    </TextField>
                  </Grid>
                  <Grid item xs={6}>
                    <FormControlLabel
                      control={<Switch checked={unlimitedUsers} onChange={(e) => setUnlimitedUsers(e.target.checked)} />}
                      label="Unlimited users"
                    />
                  </Grid>
                  {!unlimitedUsers && (
                    <Grid item xs={12}>
                      <TextField size="small" type="number" label="Max Users" value={form.max_users}
                        onChange={(e) => updateForm('max_users', Number(e.target.value || 0))} fullWidth required />
                    </Grid>
                  )}
                </Grid>
              </Box>

              <Divider />

              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>Branding</Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <TextField size="small" type="color" label="Primary Color" value={form.primary_color} onChange={(e) => updateForm('primary_color', e.target.value)} fullWidth />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField size="small" type="color" label="Secondary Color" value={form.secondary_color} onChange={(e) => updateForm('secondary_color', e.target.value)} fullWidth />
                  </Grid>
                  <Grid item xs={12}>
                    <TextField size="small" label="Tagline" value={form.tagline} onChange={(e) => updateForm('tagline', e.target.value)} fullWidth />
                  </Grid>
                </Grid>
              </Box>

              <Divider />

              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>Administrator</Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <TextField size="small" label="Full Name" value={form.coordinator_full_name} onChange={(e) => updateForm('coordinator_full_name', e.target.value)} required fullWidth />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField size="small" type="email" label="Email" value={form.coordinator_email} onChange={(e) => updateForm('coordinator_email', e.target.value)} required fullWidth />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField size="small" label="Username" value={form.coordinator_username} onChange={(e) => updateForm('coordinator_username', e.target.value)} required fullWidth />
                  </Grid>
                  <Grid item xs={6}>
                    <TextField size="small" type="password" label="Password" value={form.coordinator_password} onChange={(e) => updateForm('coordinator_password', e.target.value)} required fullWidth />
                  </Grid>
                </Grid>
              </Box>
            </Stack>
          </Box>

          <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
            {registerMessage && (
              <Alert severity={registerMessage.includes('successfully') ? 'success' : 'error'} sx={{ mb: 2 }}>
                {registerMessage}
              </Alert>
            )}
            <Stack direction="row" spacing={1.5} justifyContent="flex-end">
              <Button onClick={() => setRegisterOpen(false)} color="inherit">Cancel</Button>
              <Button
                type="submit"
                variant="contained"
                disableElevation
                disabled={registerLoading || !form.name || !form.domain || !form.coordinator_username || !form.coordinator_password}
              >
                {registerLoading ? <CircularProgress size={20} /> : 'Create'}
              </Button>
            </Stack>
          </Box>
        </Box>
      </Drawer>
    </Box>
  );
}
