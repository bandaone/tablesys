import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Paper, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Button, Chip, IconButton, Drawer, Grid, CircularProgress, LinearProgress,
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
  CheckCircleOutline as CopiedIcon,
  MonitorHeart as MonitorHeartIcon,
  Insights as InsightsIcon,
  Dashboard as DashboardIcon
} from '@mui/icons-material';
import { superadminAPI } from '../api';
import { sisAPI, SisApiKey, SisApiKeyCreated } from '../api';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import SystemMonitorPage from './SystemMonitorPage';
import AlertCenter from '../components/AlertCenter';

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
  const [tenantObservability, setTenantObservability] = useState<any>(null);
  const [tenantObservabilityLoading, setTenantObservabilityLoading] = useState(false);
  const [performanceOverview, setPerformanceOverview] = useState<any>(null);
  const [performanceLoading, setPerformanceLoading] = useState(false);
  const [performanceWindowDays, setPerformanceWindowDays] = useState(30);
  const [businessMetrics, setBusinessMetrics] = useState<any>(null);
  const [businessMetricsLoading, setBusinessMetricsLoading] = useState(false);
  const [businessMetricsWindowDays, setBusinessMetricsWindowDays] = useState(30);
  const [operationalMetrics, setOperationalMetrics] = useState<any>(null);
  const [operationalMetricsLoading, setOperationalMetricsLoading] = useState(false);
  const [operationalMetricsWindowDays, setOperationalMetricsWindowDays] = useState(30);

  // ── tab state ────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState(0);

  // ── Dashboard Metrics Tab State ──────────────────────────────────────────
  const [dashboardMetrics, setDashboardMetrics] = useState<any>(null);
  const [dashboardMetricsLoading, setDashboardMetricsLoading] = useState(false);
  const [dashboardMetricsTenantId, setDashboardMetricsTenantId] = useState<number | ''>('');

  const loadDashboardMetrics = async (tenantId: number) => {
    if (!tenantId) return;
    try {
      setDashboardMetricsLoading(true);
      const data = await superadminAPI.getTenantDashboardMetrics(tenantId);
      setDashboardMetrics(data);
    } catch (err) {
      console.error('Failed to load dashboard metrics', err);
    } finally {
      setDashboardMetricsLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 6 && dashboardMetricsTenantId) {
      loadDashboardMetrics(dashboardMetricsTenantId as number);
    }
  }, [activeTab, dashboardMetricsTenantId]);

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

  const viewTenantDetails = async (tenant: any) => {
    const resolvedTenant = universities.find((u) => u.id === (tenant.id ?? tenant.tenant_id)) || tenant;
    setSelectedTenant(resolvedTenant);
    setDetailsOpen(true);
    setTenantObservability(null);
    try {
      setTenantObservabilityLoading(true);
      const tenantId = resolvedTenant.id ?? resolvedTenant.tenant_id;
      const observability = await superadminAPI.getTenantObservability(tenantId);
      setTenantObservability(observability);
    } catch {
      setTenantObservability(null);
    } finally {
      setTenantObservabilityLoading(false);
    }
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
    if (activeTab !== 2) return;
    loadPerformanceOverview(performanceWindowDays);
    const interval = setInterval(() => loadPerformanceOverview(performanceWindowDays), 30000);
    return () => clearInterval(interval);
  }, [activeTab, performanceWindowDays]);

  useEffect(() => {
    if (activeTab !== 3) return;
    loadBusinessMetricsOverview(businessMetricsWindowDays);
    const interval = setInterval(() => loadBusinessMetricsOverview(businessMetricsWindowDays), 45000);
    return () => clearInterval(interval);
  }, [activeTab, businessMetricsWindowDays]);

  useEffect(() => {
    if (activeTab !== 4) return;
    loadOperationalMetricsOverview(operationalMetricsWindowDays);
    const interval = setInterval(() => loadOperationalMetricsOverview(operationalMetricsWindowDays), 45000);
    return () => clearInterval(interval);
  }, [activeTab, operationalMetricsWindowDays]);

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

  const loadPerformanceOverview = async (windowDays: number) => {
    try {
      setPerformanceLoading(true);
      const res = await superadminAPI.getPerformanceOverview(windowDays);
      setPerformanceOverview(res);
    } catch {
      setError('Failed to load tenant performance analytics.');
    } finally {
      setPerformanceLoading(false);
    }
  };

  const loadBusinessMetricsOverview = async (windowDays: number) => {
    try {
      setBusinessMetricsLoading(true);
      const res = await superadminAPI.getBusinessMetricsOverview(windowDays);
      setBusinessMetrics(res);
    } catch {
      setError('Failed to load business metrics analytics.');
    } finally {
      setBusinessMetricsLoading(false);
    }
  };

  const loadOperationalMetricsOverview = async (windowDays: number) => {
    try {
      setOperationalMetricsLoading(true);
      const res = await superadminAPI.getOperationalMetricsOverview(windowDays);
      setOperationalMetrics(res);
    } catch {
      setError('Failed to load operational metrics analytics.');
    } finally {
      setOperationalMetricsLoading(false);
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

  const formatDurationMinutes = (value?: number | null) => {
    if (value === null || value === undefined) return 'N/A';
    if (value < 60) return `${value.toFixed(0)} min`;
    return `${(value / 60).toFixed(1)} hrs`;
  };

  const formatPercent = (value?: number | null) => {
    if (value === null || value === undefined) return 'N/A';
    return `${value.toFixed(1)}%`;
  };

  const formatBytes = (value?: number | null) => {
    if (value === null || value === undefined) return 'N/A';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = value;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex += 1;
    }
    return `${size.toFixed(size >= 100 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
  };

  const currentTenantPerformance = selectedTenant
    ? performanceOverview?.tenants?.find((tenant: any) => tenant.tenant_id === selectedTenant.id)
    : null;

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
          <AlertCenter />
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
          <Tab
            label="Tenant Performance"
            id="sa-tab-2"
            aria-controls="sa-panel-2"
            icon={<BoltIcon sx={{ fontSize: 16 }} />}
            iconPosition="start"
          />
          <Tab
            label="Business Metrics"
            id="sa-tab-3"
            aria-controls="sa-panel-3"
            icon={<InsightsIcon sx={{ fontSize: 16 }} />}
            iconPosition="start"
          />
          <Tab
            label="Operational Metrics"
            id="sa-tab-4"
            aria-controls="sa-panel-4"
            icon={<StorageIcon sx={{ fontSize: 16 }} />}
            iconPosition="start"
          />
          <Tab
            label="System Monitor"
            id="sa-tab-5"
            aria-controls="sa-panel-5"
            icon={<MonitorHeartIcon sx={{ fontSize: 16 }} />}
            iconPosition="start"
          />
          <Tab
            label="Dashboard Metrics"
            id="sa-tab-6"
            aria-controls="sa-panel-6"
            icon={<DashboardIcon sx={{ fontSize: 16 }} />}
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

      <Box role="tabpanel" id="sa-panel-2" hidden={activeTab !== 2}>
        <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="h6" fontWeight={700}>Tenant Performance & SLA</Typography>
              <Typography variant="body2" color="text.secondary">
                Platform-owner view of per-tenant response times, error rates, and timetable generation health.
              </Typography>
            </Box>
            <Stack direction="row" spacing={1.5} alignItems="center">
              <TextField
                select
                size="small"
                label="Window"
                value={performanceWindowDays}
                onChange={(e) => setPerformanceWindowDays(Number(e.target.value))}
                sx={{ minWidth: 140 }}
              >
                {[7, 14, 30, 60, 90].map((days) => (
                  <MenuItem key={days} value={days}>Last {days} days</MenuItem>
                ))}
              </TextField>
              <Button variant="outlined" size="small" onClick={() => loadPerformanceOverview(performanceWindowDays)}>
                Refresh
              </Button>
            </Stack>
          </Box>
        </Paper>

        {performanceLoading && !performanceOverview ? (
          <Box sx={{ py: 8, display: 'flex', justifyContent: 'center' }}>
            <CircularProgress />
          </Box>
        ) : performanceOverview && (
          <>
            <Grid container spacing={2} sx={{ mb: 3 }}>
              {[
                { label: 'Active Tenants', value: performanceOverview.summary.active_tenants, helper: `of ${performanceOverview.summary.tenant_count} total`, color: '#1976d2' },
                { label: 'Meeting SLA', value: performanceOverview.summary.tenants_meeting_sla, helper: `${performanceOverview.summary.at_risk_tenants} at risk`, color: '#2e7d32' },
                { label: 'Platform Avg API Time', value: `${performanceOverview.summary.platform_avg_response_ms.toFixed(0)} ms`, helper: `${performanceWindowDays}-day window`, color: '#ed6c02' },
                { label: 'Platform Error Rate', value: `${performanceOverview.summary.platform_error_rate_percent.toFixed(2)}%`, helper: 'client + server', color: '#d32f2f' },
                { label: 'Generation Success', value: `${performanceOverview.summary.platform_generation_success_rate_percent.toFixed(1)}%`, helper: 'all tenant runs', color: '#6a1b9a' },
              ].map((item) => (
                <Grid item xs={12} sm={6} md={4} lg={3} key={item.label}>
                  <Paper variant="outlined" sx={{ p: 2.25, height: '100%' }}>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
                      {item.label}
                    </Typography>
                    <Typography variant="h5" fontWeight={800} sx={{ mt: 0.75, color: item.color }}>
                      {item.value}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {item.helper}
                    </Typography>
                  </Paper>
                </Grid>
              ))}
            </Grid>

            <Grid container spacing={3} sx={{ mb: 3 }}>
              <Grid item xs={12} md={7}>
                <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
                  <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
                    Tenants Requiring Attention
                  </Typography>
                  <Stack spacing={1.5}>
                    {performanceOverview.tenants.filter((tenant: any) => tenant.health_status !== 'healthy' && tenant.health_status !== 'quiet').slice(0, 5).map((tenant: any) => (
                      <Paper key={tenant.tenant_id} variant="outlined" sx={{ p: 1.75, borderColor: tenant.health_status === 'critical' ? 'error.light' : 'warning.light' }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
                          <Box>
                            <Typography variant="body2" fontWeight={700}>{tenant.tenant_name}</Typography>
                            <Typography variant="caption" color="text.secondary">
                              {tenant.plan_tier} plan • {tenant.avg_response_ms.toFixed(0)} ms avg • {tenant.error_rate_percent.toFixed(2)}% errors
                            </Typography>
                          </Box>
                          <Stack direction="row" spacing={1} alignItems="center">
                            <Chip
                              label={tenant.health_status}
                              size="small"
                              color={tenant.health_status === 'critical' ? 'error' : 'warning'}
                              variant="outlined"
                              sx={{ textTransform: 'capitalize' }}
                            />
                            <Button size="small" onClick={() => viewTenantDetails({
                              id: tenant.tenant_id,
                              name: tenant.tenant_name,
                              domain: tenant.domain,
                              plan_tier: tenant.plan_tier,
                              user_count: 0,
                              max_users: 0,
                              timezone: '',
                              is_active: true,
                            })}>
                              Open
                            </Button>
                          </Stack>
                        </Box>
                      </Paper>
                    ))}
                    {performanceOverview.tenants.filter((tenant: any) => tenant.health_status !== 'healthy' && tenant.health_status !== 'quiet').length === 0 && (
                      <Typography variant="body2" color="text.secondary">
                        No tenants are currently breaching your warning thresholds.
                      </Typography>
                    )}
                  </Stack>
                </Paper>
              </Grid>

              <Grid item xs={12} md={5}>
                <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
                  <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
                    Top Failure Endpoints
                  </Typography>
                  <Stack spacing={1.25}>
                    {performanceOverview.top_failure_endpoints.map((item: any) => (
                      <Box key={item.endpoint}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5, gap: 2 }}>
                          <Typography variant="body2" fontWeight={600} sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>
                            {item.endpoint}
                          </Typography>
                          <Chip label={`${item.count}`} size="small" color="error" variant="outlined" />
                        </Box>
                        <LinearProgress variant="determinate" value={Math.min(100, item.count * 5)} color="error" sx={{ height: 7, borderRadius: 999 }} />
                      </Box>
                    ))}
                    {performanceOverview.top_failure_endpoints.length === 0 && (
                      <Typography variant="body2" color="text.secondary">
                        No API failure hotspots captured in this window.
                      </Typography>
                    )}
                  </Stack>
                </Paper>
              </Grid>
            </Grid>

            <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
              <Box sx={{ px: 2.5, py: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                <Typography variant="subtitle1" fontWeight={700}>Per-Tenant Performance Matrix</Typography>
              </Box>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor: '#f9fafb' }}>
                      <TableCell sx={{ fontWeight: 600 }}>Tenant</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Health</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>API Avg</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Error Rate</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>SLA Compliance</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Generation Success</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Generation Avg</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Fallbacks</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 600 }}>Action</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {performanceOverview.tenants.map((tenant: any) => (
                      <TableRow key={tenant.tenant_id} hover>
                        <TableCell>
                          <Typography variant="body2" fontWeight={700}>{tenant.tenant_name}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {tenant.domain} • {tenant.plan_tier}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={tenant.health_status}
                            size="small"
                            color={tenant.health_status === 'critical' ? 'error' : tenant.health_status === 'warning' ? 'warning' : tenant.health_status === 'healthy' ? 'success' : 'default'}
                            variant="outlined"
                            sx={{ textTransform: 'capitalize' }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{tenant.avg_response_ms.toFixed(0)} ms</Typography>
                          <Typography variant="caption" color="text.secondary">target {tenant.sla_target_ms} ms</Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{tenant.error_rate_percent.toFixed(2)}%</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {tenant.server_errors} server / {tenant.client_errors} client
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{tenant.sla_compliance_percent.toFixed(1)}%</Typography>
                          <Typography variant="caption" color="text.secondary">{tenant.sla_breaches} breaches</Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            {tenant.generation_success_rate_percent === null ? 'N/A' : `${tenant.generation_success_rate_percent.toFixed(1)}%`}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">{tenant.generation_attempts} runs</Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            {tenant.generation_avg_duration_ms === null ? 'N/A' : `${(tenant.generation_avg_duration_ms / 1000).toFixed(1)} sec`}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{tenant.generation_fallback_runs}</Typography>
                          <Typography variant="caption" color="text.secondary">{tenant.generation_timeout_runs} timeout-like</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Button size="small" onClick={() => viewTenantDetails({
                            id: tenant.tenant_id,
                            name: tenant.tenant_name,
                            domain: tenant.domain,
                            plan_tier: tenant.plan_tier,
                            user_count: 0,
                            max_users: 0,
                            timezone: '',
                            is_active: true,
                          })}>
                            Inspect
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </>
        )}
      </Box>

      <Box role="tabpanel" id="sa-panel-3" hidden={activeTab !== 3}>
        <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="h6" fontWeight={700}>Business Metrics</Typography>
              <Typography variant="body2" color="text.secondary">
                Tenant adoption, engagement patterns, and plan-tier usage correlation for platform owners.
              </Typography>
            </Box>
            <Stack direction="row" spacing={1.5} alignItems="center">
              <TextField
                select
                size="small"
                label="Window"
                value={businessMetricsWindowDays}
                onChange={(e) => setBusinessMetricsWindowDays(Number(e.target.value))}
                sx={{ minWidth: 140 }}
              >
                {[7, 14, 30, 60, 90].map((days) => (
                  <MenuItem key={days} value={days}>Last {days} days</MenuItem>
                ))}
              </TextField>
              <Button variant="outlined" size="small" onClick={() => loadBusinessMetricsOverview(businessMetricsWindowDays)}>
                Refresh
              </Button>
            </Stack>
          </Box>
        </Paper>

        {businessMetricsLoading && !businessMetrics ? (
          <Box sx={{ py: 8, display: 'flex', justifyContent: 'center' }}>
            <CircularProgress />
          </Box>
        ) : businessMetrics && (
          <>
            <Grid container spacing={2} sx={{ mb: 3 }}>
              {[
                { label: 'Active Tenants', value: businessMetrics.summary.active_tenants, helper: `of ${businessMetrics.summary.tenant_count} total`, color: '#1976d2' },
                { label: 'Adopted Features', value: businessMetrics.summary.adopted_feature_count, helper: 'tracked modules in use', color: '#2e7d32' },
                { label: 'Avg Features / Tenant', value: businessMetrics.summary.avg_features_per_tenant.toFixed(1), helper: `${businessMetricsWindowDays}-day window`, color: '#ed6c02' },
                { label: 'Avg Logins / Tenant', value: businessMetrics.summary.avg_logins_per_tenant.toFixed(1), helper: businessMetrics.summary.login_data_available ? 'audit-backed' : 'login telemetry unavailable', color: '#6a1b9a' },
                { label: 'Avg Session Duration', value: formatDurationMinutes(businessMetrics.summary.avg_session_duration_minutes), helper: businessMetrics.summary.login_data_available ? 'matched login/logout sessions' : 'not enough login events', color: '#00838f' },
              ].map((item) => (
                <Grid item xs={12} sm={6} md={4} lg={3} key={item.label}>
                  <Paper variant="outlined" sx={{ p: 2.25, height: '100%' }}>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
                      {item.label}
                    </Typography>
                    <Typography variant="h5" fontWeight={800} sx={{ mt: 0.75, color: item.color }}>
                      {item.value}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {item.helper}
                    </Typography>
                  </Paper>
                </Grid>
              ))}
            </Grid>

            <Grid container spacing={3} sx={{ mb: 3 }}>
              <Grid item xs={12} md={7}>
                <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
                  <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
                    Feature Adoption
                  </Typography>
                  <Stack spacing={1.75}>
                    {businessMetrics.feature_adoption.map((feature: any) => (
                      <Box key={feature.feature_key}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2, mb: 0.75 }}>
                          <Box>
                            <Typography variant="body2" fontWeight={700}>{feature.feature_name}</Typography>
                            <Typography variant="caption" color="text.secondary">
                              {feature.tenant_count} tenants • {feature.usage_events.toLocaleString()} tracked events
                              {feature.top_tenants.length > 0 ? ` • Top: ${feature.top_tenants.map((tenant: any) => tenant.tenant_name).join(', ')}` : ''}
                            </Typography>
                          </Box>
                          <Chip label={`${feature.adoption_percent.toFixed(0)}%`} size="small" color="primary" variant="outlined" />
                        </Box>
                        <LinearProgress variant="determinate" value={Math.min(100, feature.adoption_percent)} sx={{ height: 8, borderRadius: 999 }} />
                      </Box>
                    ))}
                    {businessMetrics.feature_adoption.length === 0 && (
                      <Typography variant="body2" color="text.secondary">
                        No feature adoption telemetry has been captured in this reporting window yet.
                      </Typography>
                    )}
                  </Stack>
                </Paper>
              </Grid>

              <Grid item xs={12} md={5}>
                <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
                  <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
                    Plan Tier Correlation
                  </Typography>
                  <Stack spacing={1.5}>
                    {businessMetrics.plan_correlation.map((plan: any) => (
                      <Paper key={plan.plan_tier} variant="outlined" sx={{ p: 1.75 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                          <Chip
                            label={plan.plan_tier}
                            size="small"
                            color={getTierColor(plan.plan_tier) as any}
                            variant="outlined"
                            sx={{ fontWeight: 600, textTransform: 'capitalize' }}
                          />
                          <Typography variant="caption" color="text.secondary">
                            {plan.tenant_count} tenants
                          </Typography>
                        </Box>
                        <Typography variant="body2" color="text.secondary">
                          Avg features: <strong>{plan.avg_features_adopted.toFixed(1)}</strong> • Avg requests: <strong>{plan.avg_api_requests.toFixed(0)}</strong>
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Avg logins: <strong>{plan.avg_login_count.toFixed(1)}</strong> • Avg session: <strong>{formatDurationMinutes(plan.avg_session_duration_minutes)}</strong>
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Most adopted feature: {plan.most_adopted_feature || 'N/A'} • Avg generation runs: {plan.avg_generation_runs.toFixed(1)}
                        </Typography>
                      </Paper>
                    ))}
                    {businessMetrics.plan_correlation.length === 0 && (
                      <Typography variant="body2" color="text.secondary">
                        No plan-tier usage correlation is available yet.
                      </Typography>
                    )}
                  </Stack>
                </Paper>
              </Grid>
            </Grid>

            <Paper variant="outlined" sx={{ overflow: 'hidden', mb: 3 }}>
              <Box sx={{ px: 2.5, py: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                <Typography variant="subtitle1" fontWeight={700}>Tenant Feature Matrix</Typography>
              </Box>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor: '#f9fafb' }}>
                      <TableCell sx={{ fontWeight: 600 }}>Tenant</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Plan</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Features Used</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Top Feature</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Feature Events</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {businessMetrics.tenant_feature_matrix.map((tenant: any) => (
                      <TableRow key={tenant.tenant_id} hover>
                        <TableCell>
                          <Typography variant="body2" fontWeight={700}>{tenant.tenant_name}</Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={tenant.plan_tier}
                            size="small"
                            color={getTierColor(tenant.plan_tier) as any}
                            variant="outlined"
                            sx={{ textTransform: 'capitalize' }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{tenant.feature_count}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {tenant.features_used.length > 0 ? tenant.features_used.join(', ') : 'No tracked features yet'}
                          </Typography>
                        </TableCell>
                        <TableCell>{tenant.top_feature || 'N/A'}</TableCell>
                        <TableCell>{tenant.total_feature_events.toLocaleString()}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>

            <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
              <Box sx={{ px: 2.5, py: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                <Typography variant="subtitle1" fontWeight={700}>Engagement Patterns</Typography>
                <Typography variant="caption" color="text.secondary">
                  Session duration is derived from matched login/logout audit events when available.
                </Typography>
              </Box>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor: '#f9fafb' }}>
                      <TableCell sx={{ fontWeight: 600 }}>Tenant</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Logins</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Active Days</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Avg Logins / Week</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Avg Session</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>API Requests</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Requests / Active Day</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Peak Hour (UTC)</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {businessMetrics.engagement.map((tenant: any) => (
                      <TableRow key={tenant.tenant_id} hover>
                        <TableCell>
                          <Typography variant="body2" fontWeight={700}>{tenant.tenant_name}</Typography>
                          <Typography variant="caption" color="text.secondary">{tenant.plan_tier}</Typography>
                        </TableCell>
                        <TableCell>{tenant.login_count}</TableCell>
                        <TableCell>{tenant.active_days}</TableCell>
                        <TableCell>{tenant.avg_logins_per_week.toFixed(1)}</TableCell>
                        <TableCell>{formatDurationMinutes(tenant.avg_session_duration_minutes)}</TableCell>
                        <TableCell>{tenant.api_requests.toLocaleString()}</TableCell>
                        <TableCell>{tenant.avg_api_requests_per_active_day.toFixed(1)}</TableCell>
                        <TableCell>{tenant.peak_hour_utc === null || tenant.peak_hour_utc === undefined ? 'N/A' : `${tenant.peak_hour_utc.toString().padStart(2, '0')}:00`}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </>
        )}
      </Box>

      <Box role="tabpanel" id="sa-panel-4" hidden={activeTab !== 4}>
        <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="h6" fontWeight={700}>Operational Metrics</Typography>
              <Typography variant="body2" color="text.secondary">
                Solver reliability, conflict-free outcomes, storage growth, and tenant rate-limit pressure.
              </Typography>
            </Box>
            <Stack direction="row" spacing={1.5} alignItems="center">
              <TextField
                select
                size="small"
                label="Window"
                value={operationalMetricsWindowDays}
                onChange={(e) => setOperationalMetricsWindowDays(Number(e.target.value))}
                sx={{ minWidth: 140 }}
              >
                {[7, 14, 30, 60, 90].map((days) => (
                  <MenuItem key={days} value={days}>Last {days} days</MenuItem>
                ))}
              </TextField>
              <Button variant="outlined" size="small" onClick={() => loadOperationalMetricsOverview(operationalMetricsWindowDays)}>
                Refresh
              </Button>
            </Stack>
          </Box>
        </Paper>

        {operationalMetricsLoading && !operationalMetrics ? (
          <Box sx={{ py: 8, display: 'flex', justifyContent: 'center' }}>
            <CircularProgress />
          </Box>
        ) : operationalMetrics && (
          <>
            <Grid container spacing={2} sx={{ mb: 3 }}>
              {[
                { label: 'Solver Runs', value: operationalMetrics.summary.total_solver_runs.toLocaleString(), helper: `${operationalMetrics.summary.active_tenants} active tenants`, color: '#1976d2' },
                { label: 'Fallback Frequency', value: formatPercent(operationalMetrics.summary.avg_fallback_rate_percent), helper: 'share of solver runs using fallback', color: '#ed6c02' },
                { label: 'Timeout Frequency', value: formatPercent(operationalMetrics.summary.avg_timeout_rate_percent), helper: 'timeout-like solver outcomes', color: '#d32f2f' },
                { label: 'Conflict-Free Success', value: formatPercent(operationalMetrics.summary.conflict_free_rate_percent), helper: 'successful runs with zero detected conflicts', color: '#2e7d32' },
                { label: 'Storage Added', value: formatBytes(operationalMetrics.summary.storage_growth_bytes_window), helper: `${operationalMetricsWindowDays}-day tracked artifact growth`, color: '#6a1b9a' },
                { label: 'Rate Limit Hits', value: operationalMetrics.summary.rate_limit_hits.toLocaleString(), helper: 'audit-observed tenant lockouts', color: '#00838f' },
              ].map((item) => (
                <Grid item xs={12} sm={6} md={4} lg={2} key={item.label}>
                  <Paper variant="outlined" sx={{ p: 2.25, height: '100%' }}>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
                      {item.label}
                    </Typography>
                    <Typography variant="h5" fontWeight={800} sx={{ mt: 0.75, color: item.color }}>
                      {item.value}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {item.helper}
                    </Typography>
                  </Paper>
                </Grid>
              ))}
            </Grid>

            <Grid container spacing={3} sx={{ mb: 3 }}>
              <Grid item xs={12} lg={8}>
                <Paper variant="outlined" sx={{ overflow: 'hidden', height: '100%' }}>
                  <Box sx={{ px: 2.5, py: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                    <Typography variant="subtitle1" fontWeight={700}>Solver Timeout / Fallback Frequency</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Frequency view only, to avoid repeating the raw generation counts already shown in Tenant Performance.
                    </Typography>
                  </Box>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow sx={{ bgcolor: '#f9fafb' }}>
                          <TableCell sx={{ fontWeight: 600 }}>Tenant</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Runs</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Fallbacks</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Fallback Rate</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Timeouts</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Timeout Rate</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {operationalMetrics.solver_reliability.map((tenant: any) => (
                          <TableRow key={tenant.tenant_id} hover>
                            <TableCell>
                              <Typography variant="body2" fontWeight={700}>{tenant.tenant_name}</Typography>
                              <Typography variant="caption" color="text.secondary">
                                {tenant.domain} • {tenant.plan_tier}
                              </Typography>
                            </TableCell>
                            <TableCell>{tenant.attempts}</TableCell>
                            <TableCell>{tenant.fallback_runs}</TableCell>
                            <TableCell>{formatPercent(tenant.fallback_rate_percent)}</TableCell>
                            <TableCell>{tenant.timeout_runs}</TableCell>
                            <TableCell>{formatPercent(tenant.timeout_rate_percent)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Paper>
              </Grid>

              <Grid item xs={12} lg={4}>
                <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
                  <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
                    API Rate Limit Hits
                  </Typography>
                  <Stack spacing={1.5}>
                    {operationalMetrics.rate_limits.filter((tenant: any) => tenant.hit_count > 0).slice(0, 8).map((tenant: any) => (
                      <Paper key={tenant.tenant_id} variant="outlined" sx={{ p: 1.75 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                          <Typography variant="body2" fontWeight={700}>{tenant.tenant_name}</Typography>
                          <Chip label={`${tenant.hit_count} hits`} size="small" color="warning" variant="outlined" />
                        </Box>
                        <Typography variant="caption" color="text.secondary" component="div">
                          {tenant.distinct_user_count} users affected
                          {tenant.last_hit_at ? ` • Last hit ${new Date(tenant.last_hit_at).toLocaleString()}` : ''}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" component="div">
                          {tenant.top_endpoints.length > 0
                            ? `Top endpoints: ${tenant.top_endpoints.map((endpoint: any) => `${endpoint.endpoint} (${endpoint.count})`).join(', ')}`
                            : 'No endpoint detail available'}
                        </Typography>
                      </Paper>
                    ))}
                    {operationalMetrics.rate_limits.every((tenant: any) => tenant.hit_count === 0) && (
                      <Typography variant="body2" color="text.secondary">
                        No tenant-attributed rate-limit blocks were found in the selected window.
                      </Typography>
                    )}
                  </Stack>
                </Paper>
              </Grid>
            </Grid>

            <Grid container spacing={3} sx={{ mb: 3 }}>
              <Grid item xs={12} md={5}>
                <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
                  <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
                    Storage Growth Trend
                  </Typography>
                  <Stack spacing={1.5}>
                    {operationalMetrics.storage_growth.map((bucket: any) => {
                      const maxGrowth = Math.max(...operationalMetrics.storage_growth.map((item: any) => item.total_bytes_added), 1);
                      const ratio = maxGrowth > 0 ? (bucket.total_bytes_added / maxGrowth) * 100 : 0;
                      return (
                        <Box key={bucket.label}>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5, gap: 2 }}>
                            <Typography variant="body2" fontWeight={600}>{bucket.label}</Typography>
                            <Typography variant="caption" color="text.secondary">
                              {formatBytes(bucket.total_bytes_added)}
                            </Typography>
                          </Box>
                          <LinearProgress variant="determinate" value={Math.max(ratio, bucket.total_bytes_added > 0 ? 4 : 0)} sx={{ height: 8, borderRadius: 999 }} />
                          <Typography variant="caption" color="text.secondary">
                            {bucket.top_tenant_name ? `Largest contributor: ${bucket.top_tenant_name} (${formatBytes(bucket.top_tenant_bytes)})` : 'No tracked growth in this bucket'}
                          </Typography>
                        </Box>
                      );
                    })}
                  </Stack>
                </Paper>
              </Grid>

              <Grid item xs={12} md={7}>
                <Paper variant="outlined" sx={{ overflow: 'hidden', height: '100%' }}>
                  <Box sx={{ px: 2.5, py: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                    <Typography variant="subtitle1" fontWeight={700}>Tenant Storage Growth</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Estimated from operational artifacts like usage telemetry, versions, and generation metadata.
                    </Typography>
                  </Box>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow sx={{ bgcolor: '#f9fafb' }}>
                          <TableCell sx={{ fontWeight: 600 }}>Tenant</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Current Footprint</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Added This Window</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Previous Window</TableCell>
                          <TableCell sx={{ fontWeight: 600 }}>Growth Shift</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {operationalMetrics.tenant_storage.map((tenant: any) => (
                          <TableRow key={tenant.tenant_id} hover>
                            <TableCell>
                              <Typography variant="body2" fontWeight={700}>{tenant.tenant_name}</Typography>
                              <Typography variant="caption" color="text.secondary">{tenant.plan_tier}</Typography>
                            </TableCell>
                            <TableCell>{formatBytes(tenant.current_estimated_storage_bytes)}</TableCell>
                            <TableCell>{formatBytes(tenant.storage_added_bytes_window)}</TableCell>
                            <TableCell>{formatBytes(tenant.storage_added_bytes_previous_window)}</TableCell>
                            <TableCell>{tenant.growth_percent === null || tenant.growth_percent === undefined ? 'N/A' : `${tenant.growth_percent > 0 ? '+' : ''}${tenant.growth_percent.toFixed(1)}%`}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Paper>
              </Grid>
            </Grid>

            <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
              <Box sx={{ px: 2.5, py: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                <Typography variant="subtitle1" fontWeight={700}>Conflict Resolution Success Rates</Typography>
                <Typography variant="caption" color="text.secondary">
                  Based on successful timetable runs in the selected window and whether the resulting timetable is conflict-free.
                </Typography>
              </Box>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor: '#f9fafb' }}>
                      <TableCell sx={{ fontWeight: 600 }}>Tenant</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Evaluated Runs</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Conflict-Free</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Success Rate</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Unresolved Runs</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Total Conflicts</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Top Conflict Type</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {operationalMetrics.conflict_resolution.map((tenant: any) => (
                      <TableRow key={tenant.tenant_id} hover>
                        <TableCell>
                          <Typography variant="body2" fontWeight={700}>{tenant.tenant_name}</Typography>
                          <Typography variant="caption" color="text.secondary">{tenant.plan_tier}</Typography>
                        </TableCell>
                        <TableCell>{tenant.evaluated_runs}</TableCell>
                        <TableCell>{tenant.conflict_free_runs}</TableCell>
                        <TableCell>{formatPercent(tenant.conflict_free_rate_percent)}</TableCell>
                        <TableCell>{tenant.unresolved_runs}</TableCell>
                        <TableCell>{tenant.total_conflicts}</TableCell>
                        <TableCell>{tenant.top_conflict_type || 'N/A'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </>
        )}
      </Box>

      <Box role="tabpanel" id="sa-panel-5" hidden={activeTab !== 5}>
        <SystemMonitorPage isEmbedded />
      </Box>

      <Box role="tabpanel" id="sa-panel-6" hidden={activeTab !== 6}>
        <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="h6" fontWeight={700}>Tenant Dashboard Metrics</Typography>
              <Typography variant="body2" color="text.secondary">
                Detailed real-time overview of users, timetables, resource utilization, and recent activity for a selected organization.
              </Typography>
            </Box>
            <Stack direction="row" spacing={1.5} alignItems="center">
              <TextField
                select
                size="small"
                label="Select Tenant"
                value={dashboardMetricsTenantId}
                onChange={(e) => setDashboardMetricsTenantId(Number(e.target.value))}
                sx={{ minWidth: 200 }}
              >
                {universities.map((uni: any) => (
                  <MenuItem key={uni.id} value={uni.id}>{uni.name}</MenuItem>
                ))}
              </TextField>
              <Button 
                variant="outlined" 
                size="small" 
                disabled={!dashboardMetricsTenantId || dashboardMetricsLoading}
                onClick={() => loadDashboardMetrics(dashboardMetricsTenantId as number)}
              >
                Refresh
              </Button>
            </Stack>
          </Box>
        </Paper>

        {!dashboardMetricsTenantId ? (
          <Box sx={{ py: 8, display: 'flex', justifyContent: 'center', alignItems: 'center', flexDirection: 'column' }}>
            <DashboardIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
            <Typography variant="body1" color="text.secondary">Select an organization above to view its dashboard metrics.</Typography>
          </Box>
        ) : dashboardMetricsLoading && !dashboardMetrics ? (
          <Box sx={{ py: 8, display: 'flex', justifyContent: 'center' }}>
            <CircularProgress />
          </Box>
        ) : dashboardMetrics && (
          <Box>
            <Grid container spacing={3} sx={{ mb: 3 }}>
              {/* Resource Utilization */}
              <Grid item xs={12} md={4}>
                <Paper variant="outlined" sx={{ p: 2.5, height: '100%', background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)', border: 'none' }}>
                  <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2, textTransform: 'uppercase', color: 'text.primary' }}>
                    Resource Utilization
                  </Typography>
                  <Stack spacing={2}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', p: 1.5, bgcolor: 'rgba(255,255,255,0.7)', borderRadius: 1 }}>
                      <Typography variant="body2" fontWeight={600}>Total Rooms</Typography>
                      <Typography variant="h6" fontWeight={700} color="primary.main">{dashboardMetrics.resource_utilization.total_rooms}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', p: 1.5, bgcolor: 'rgba(255,255,255,0.7)', borderRadius: 1 }}>
                      <Typography variant="body2" fontWeight={600}>Total Lecturers</Typography>
                      <Typography variant="h6" fontWeight={700} color="secondary.main">{dashboardMetrics.resource_utilization.total_lecturers}</Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', p: 1.5, bgcolor: 'rgba(255,255,255,0.7)', borderRadius: 1 }}>
                      <Typography variant="body2" fontWeight={600}>Seating Capacity</Typography>
                      <Typography variant="h6" fontWeight={700} color="success.main">{dashboardMetrics.resource_utilization.total_capacity.toLocaleString()}</Typography>
                    </Box>
                  </Stack>
                </Paper>
              </Grid>

              {/* Timetable Statistics */}
              <Grid item xs={12} md={4}>
                <Paper variant="outlined" sx={{ p: 2.5, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                  <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 3, textTransform: 'uppercase', color: 'text.secondary' }}>
                    Timetable Pipeline
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Box sx={{ textAlign: 'center', p: 2, bgcolor: '#f1f8e9', borderRadius: 2 }}>
                        <CheckCircleIcon sx={{ color: 'success.main', mb: 1, fontSize: 32 }} />
                        <Typography variant="h4" fontWeight={800} color="success.main">{dashboardMetrics.timetable_stats.generated_count}</Typography>
                        <Typography variant="caption" fontWeight={600} color="text.secondary">GENERATED</Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={6}>
                      <Box sx={{ textAlign: 'center', p: 2, bgcolor: '#fff3e0', borderRadius: 2 }}>
                        <BoltIcon sx={{ color: 'warning.main', mb: 1, fontSize: 32 }} />
                        <Typography variant="h4" fontWeight={800} color="warning.main">{dashboardMetrics.timetable_stats.draft_count}</Typography>
                        <Typography variant="caption" fontWeight={600} color="text.secondary">DRAFT</Typography>
                      </Box>
                    </Grid>
                  </Grid>
                </Paper>
              </Grid>

              {/* Users by Role */}
              <Grid item xs={12} md={4}>
                <Paper variant="outlined" sx={{ p: 2.5, height: '100%' }}>
                  <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2, textTransform: 'uppercase', color: 'text.secondary' }}>
                    Users by Role
                  </Typography>
                  <Stack spacing={1.5}>
                    {dashboardMetrics.user_counts.length === 0 ? (
                       <Typography variant="body2" color="text.secondary">No users found.</Typography>
                    ) : (
                      dashboardMetrics.user_counts.map((roleInfo: any, idx: number) => {
                        const total = dashboardMetrics.user_counts.reduce((acc: number, val: any) => acc + val.count, 0);
                        const percent = total > 0 ? (roleInfo.count / total) * 100 : 0;
                        return (
                          <Box key={idx}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                              <Typography variant="body2" fontWeight={600} sx={{ textTransform: 'capitalize' }}>{roleInfo.role}</Typography>
                              <Typography variant="caption" color="text.secondary">{roleInfo.count} users ({percent.toFixed(0)}%)</Typography>
                            </Box>
                            <Box sx={{ width: '100%', bgcolor: 'grey.100', borderRadius: 1, height: 6, overflow: 'hidden' }}>
                              <Box sx={{ width: `${percent}%`, bgcolor: 'primary.main', height: '100%' }} />
                            </Box>
                          </Box>
                        );
                      })
                    )}
                  </Stack>
                </Paper>
              </Grid>
            </Grid>

            {/* Recent Activity */}
            <Paper variant="outlined" sx={{ p: 2.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2, gap: 1 }}>
                <MonitorHeartIcon color="primary" />
                <Typography variant="subtitle1" fontWeight={700}>Recent Activity Feed</Typography>
              </Box>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor: '#f9fafb' }}>
                      <TableCell sx={{ fontWeight: 600 }}>Action</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Entity Type</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>User</TableCell>
                      <TableCell sx={{ fontWeight: 600 }}>Time</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {dashboardMetrics.recent_activity_logs.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={4} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                          No recent activity recorded for this tenant.
                        </TableCell>
                      </TableRow>
                    ) : (
                      dashboardMetrics.recent_activity_logs.map((log: any, idx: number) => (
                        <TableRow key={idx} hover>
                          <TableCell>
                            <Chip size="small" label={log.action} color={log.action.toLowerCase().includes('error') || log.action.toLowerCase().includes('fail') || log.action.toLowerCase().includes('delete') ? 'error' : 'primary'} variant="outlined" />
                          </TableCell>
                          <TableCell sx={{ textTransform: 'capitalize', fontWeight: 500 }}>{log.entity_type}</TableCell>
                          <TableCell>{log.user_email || <Typography variant="caption" color="text.disabled">System</Typography>}</TableCell>
                          <TableCell>{new Date(log.timestamp).toLocaleString()}</TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Box>
        )}
      </Box>

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

                <Divider />

                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>Generation observability</Typography>
                  {tenantObservabilityLoading ? (
                    <Box sx={{ py: 2, display: 'flex', justifyContent: 'center' }}>
                      <CircularProgress size={22} />
                    </Box>
                  ) : tenantObservability ? (
                    <Stack spacing={2}>
                      <Grid container spacing={2}>
                        <Grid item xs={6}>
                          <Typography variant="caption" color="text.secondary">Attempts</Typography>
                          <Typography variant="body2" fontWeight={600}>{tenantObservability.generation.attempts}</Typography>
                        </Grid>
                        <Grid item xs={6}>
                          <Typography variant="caption" color="text.secondary">Success Rate</Typography>
                          <Typography variant="body2" fontWeight={600}>{tenantObservability.generation.success_rate_percent.toFixed(1)}%</Typography>
                        </Grid>
                        <Grid item xs={6}>
                          <Typography variant="caption" color="text.secondary">Average Duration</Typography>
                          <Typography variant="body2" fontWeight={600}>
                            {tenantObservability.generation.average_duration_ms ? `${(tenantObservability.generation.average_duration_ms / 1000).toFixed(1)} sec` : 'N/A'}
                          </Typography>
                        </Grid>
                        <Grid item xs={6}>
                          <Typography variant="caption" color="text.secondary">Fallback Runs</Typography>
                          <Typography variant="body2" fontWeight={600}>{tenantObservability.generation.fallback_runs}</Typography>
                        </Grid>
                      </Grid>

                      {tenantObservability.generation.last_completed_at && (
                        <Typography variant="body2" color="text.secondary">
                          Last completed generation: {new Date(tenantObservability.generation.last_completed_at).toLocaleString()}
                        </Typography>
                      )}

                      <Stack spacing={1.5}>
                        {tenantObservability.generation.recent_runs.length > 0 ? tenantObservability.generation.recent_runs.map((run: any) => (
                          <Paper key={`${run.timetable_id}-${run.completed_at || run.started_at || run.status}`} variant="outlined" sx={{ p: 1.5 }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 1 }}>
                              <Box>
                                <Typography variant="body2" fontWeight={700}>{run.timetable_name}</Typography>
                                <Typography variant="caption" color="text.secondary">
                                  {run.completed_at ? new Date(run.completed_at).toLocaleString() : 'Run in progress'}
                                </Typography>
                              </Box>
                              <Chip
                                label={run.status}
                                size="small"
                                color={run.status === 'success' ? 'success' : run.status === 'running' ? 'warning' : 'error'}
                                variant="outlined"
                                sx={{ textTransform: 'capitalize' }}
                              />
                            </Box>
                            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                              Duration: {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)} sec` : 'N/A'} • Slots: {run.saved_slot_count} • Fallback: {run.fallback_used ? 'Yes' : 'No'}
                            </Typography>
                            {run.error_message && (
                              <Typography variant="caption" color="error.main" sx={{ display: 'block', mt: 0.5 }}>
                                {run.error_message}
                              </Typography>
                            )}
                          </Paper>
                        )) : (
                          <Typography variant="body2" color="text.secondary">
                            No generation telemetry recorded for this tenant yet.
                          </Typography>
                        )}
                      </Stack>
                    </Stack>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      Observability data is not available for this tenant yet.
                    </Typography>
                  )}
                </Box>

                <Divider />

                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>API performance & SLA</Typography>
                  {currentTenantPerformance ? (
                    <Grid container spacing={2}>
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.secondary">Average Response</Typography>
                        <Typography variant="body2" fontWeight={600}>{currentTenantPerformance.avg_response_ms.toFixed(0)} ms</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.secondary">SLA Target</Typography>
                        <Typography variant="body2" fontWeight={600}>{currentTenantPerformance.sla_target_ms} ms</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.secondary">Error Rate</Typography>
                        <Typography variant="body2" fontWeight={600}>{currentTenantPerformance.error_rate_percent.toFixed(2)}%</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.secondary">SLA Compliance</Typography>
                        <Typography variant="body2" fontWeight={600}>{currentTenantPerformance.sla_compliance_percent.toFixed(1)}%</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.secondary">Server Errors</Typography>
                        <Typography variant="body2" fontWeight={600}>{currentTenantPerformance.server_errors}</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.secondary">Client Errors</Typography>
                        <Typography variant="body2" fontWeight={600}>{currentTenantPerformance.client_errors}</Typography>
                      </Grid>
                      <Grid item xs={12}>
                        <Typography variant="caption" color="text.secondary">Failure hotspots</Typography>
                        <Stack spacing={1} sx={{ mt: 1 }}>
                          {currentTenantPerformance.top_failure_endpoints.length > 0 ? currentTenantPerformance.top_failure_endpoints.map((endpoint: any) => (
                            <Paper key={endpoint.endpoint} variant="outlined" sx={{ p: 1.25 }}>
                              <Typography variant="caption" sx={{ fontFamily: 'monospace', display: 'block' }}>
                                {endpoint.endpoint}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {endpoint.count} failures{endpoint.status_codes?.length ? ` • ${endpoint.status_codes.join(', ')}` : ''}
                              </Typography>
                            </Paper>
                          )) : (
                            <Typography variant="body2" color="text.secondary">
                              No repeated failure endpoints in the selected reporting window.
                            </Typography>
                          )}
                        </Stack>
                      </Grid>
                    </Grid>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      Open the Tenant Performance tab to load SLA analytics for this tenant.
                    </Typography>
                  )}
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
