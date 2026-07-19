import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box, Typography, Container, Grid, Chip, Snackbar, Alert, Card, CardContent,
  LinearProgress, Paper, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, TextField, MenuItem, IconButton, Collapse, Tooltip, Stack, InputAdornment,
  TablePagination, Badge,
} from '@mui/material';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  Security as SecurityIcon, CloudUpload as UploadIcon, Memory as GenerateIcon,
  Dashboard as DashboardIcon, FiberManualRecord as LiveIcon, Warning as WarningIcon,
  Storage as StorageIcon, Dns as ServerIcon, Search as SearchIcon,
  KeyboardArrowDown as ExpandIcon, KeyboardArrowUp as CollapseIconBtn,
  CheckCircle as OkIcon, Cancel as FailIcon, FilterList as FilterIcon,
  Person as PersonIcon, Computer as UAIcon, Download as ExportIcon,
} from '@mui/icons-material';
import axios from 'axios';

interface AuditEvent {
  id?: number;
  timestamp: string;
  event_type: string;
  user_id: number | null;
  username: string | null;
  resource: string;
  action: string;
  success: boolean;
  details: any;
  ip_address?: string;
  user_agent?: string;
  tenant_name?: string;
  entity_name?: string;
  error_message?: string;
  changes?: any;
  status?: string;
}

function formatUptime(hours: number): string {
  const totalMinutes = Math.round(hours * 60);
  const days = Math.floor(totalMinutes / 1440);
  const hrs = Math.floor((totalMinutes % 1440) / 60);
  const mins = totalMinutes % 60;
  const parts = [];
  if (days > 0) parts.push(`${days}d`);
  if (hrs > 0) parts.push(`${hrs}h`);
  if (mins > 0 || parts.length === 0) parts.push(`${mins}m`);
  return parts.join(' ');
}

interface SuperAdminTelemetry {
  redis_status: string; active_solver_jobs: number; total_universities: number;
  active_users: number; system_uptime_hours: number; cpu_usage_percent: number;
  memory_usage_percent: number; disk_usage_percent: number; db_connection_status: string;
}

function transformAuditLog(log: any): AuditEvent {
  return {
    id: log.id,
    timestamp: log.timestamp,
    event_type: log.event_type || (log.action && log.entity_type ? `${log.action}_${log.entity_type}`.toUpperCase() : log.action || 'UNKNOWN'),
    user_id: log.user_id ?? null,
    username: log.user_email || log.username || null,
    resource: log.entity_type || log.resource || '',
    action: log.action ?? '',
    success: log.status === 'success' || log.success === true,
    details: log.changes || log.details || {},
    ip_address: log.ip_address ?? null,
    user_agent: log.user_agent ?? null,
    tenant_name: log.tenant_name ?? null,
    entity_name: log.entity_name ?? null,
    error_message: log.error_message ?? null,
    changes: log.changes ?? null,
    status: log.status ?? (log.success ? 'success' : 'failure'),
  };
}

const ACTION_COLORS: Record<string, string> = {
  LOGIN: '#3b82f6', LOGOUT: '#64748b', CREATE: '#10b981', UPDATE: '#f59e0b',
  DELETE: '#ef4444', GENERATE: '#8b5cf6', BULK_UPLOAD: '#ec4899', IMPORT: '#ec4899',
  CLEANUP: '#6b7280', SYSTEM_ERROR: '#dc2626',
};

const getActionColor = (action: string) => ACTION_COLORS[action?.toUpperCase()] ?? '#1976d2';

function ActionChip({ action }: { action: string }) {
  return (
    <Chip
      label={action || 'UNKNOWN'}
      size="small"
      sx={{
        bgcolor: getActionColor(action) + '22',
        color: getActionColor(action),
        border: `1px solid ${getActionColor(action)}55`,
        fontWeight: 700, fontSize: 11, letterSpacing: 0.3,
      }}
    />
  );
}

function ExpandableRow({ event }: { event: AuditEvent }) {
  const [open, setOpen] = useState(false);
  const ts = new Date(event.timestamp);
  const timeStr = isNaN(ts.getTime()) ? event.timestamp : ts.toLocaleString();

  return (
    <>
      <TableRow
        hover
        sx={{
          borderLeft: `3px solid ${event.success ? '#10b981' : '#ef4444'}`,
          '&:hover': { bgcolor: '#f8fafc' },
        }}
      >
        <TableCell sx={{ py: 1, width: 36 }}>
          <IconButton size="small" onClick={() => setOpen(!open)}>
            {open ? <CollapseIconBtn fontSize="small" /> : <ExpandIcon fontSize="small" />}
          </IconButton>
        </TableCell>
        <TableCell sx={{ py: 1, minWidth: 150 }}>
          <Typography variant="caption" fontWeight={600} sx={{ fontFamily: 'monospace' }}>
            {timeStr}
          </Typography>
        </TableCell>
        <TableCell sx={{ py: 1 }}>
          <Chip
            label={event.tenant_name || 'Platform'}
            size="small"
            variant="outlined"
            sx={{ fontSize: 11, fontWeight: 600,
              color: event.tenant_name ? '#7c3aed' : '#64748b',
              borderColor: event.tenant_name ? '#7c3aed55' : '#cbd5e1',
            }}
          />
        </TableCell>
        <TableCell sx={{ py: 1 }}>
          <Typography variant="body2" fontWeight={600} noWrap sx={{ maxWidth: 160 }}>
            {event.username || <span style={{ color: '#94a3b8' }}>System</span>}
          </Typography>
          {event.ip_address && (
            <Typography variant="caption" sx={{ color: '#64748b', fontFamily: 'monospace' }}>
              {event.ip_address}
            </Typography>
          )}
        </TableCell>
        <TableCell sx={{ py: 1 }}><ActionChip action={event.action} /></TableCell>
        <TableCell sx={{ py: 1 }}>
          <Typography variant="body2" noWrap sx={{ maxWidth: 160, textTransform: 'capitalize' }}>
            {event.resource}
          </Typography>
          {event.entity_name && (
            <Typography variant="caption" color="text.secondary" noWrap>{event.entity_name}</Typography>
          )}
        </TableCell>
        <TableCell sx={{ py: 1 }}>
          {event.success ? (
            <Chip icon={<OkIcon />} label="Success" size="small" color="success" variant="outlined" sx={{ fontWeight: 700 }} />
          ) : (
            <Chip icon={<FailIcon />} label="Failed" size="small" color="error" variant="outlined" sx={{ fontWeight: 700 }} />
          )}
        </TableCell>
      </TableRow>
      <TableRow>
        <TableCell colSpan={7} sx={{ py: 0, bgcolor: '#f8fafc' }}>
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Box sx={{ p: 2, display: 'flex', gap: 3, flexWrap: 'wrap' }}>
              {event.user_agent && (
                <Box>
                  <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                    <UAIcon sx={{ fontSize: 12 }} /> User Agent
                  </Typography>
                  <Typography variant="caption" sx={{ fontFamily: 'monospace', color: '#475569', maxWidth: 400, display: 'block', wordBreak: 'break-all' }}>
                    {event.user_agent}
                  </Typography>
                </Box>
              )}
              {event.error_message && (
                <Box>
                  <Typography variant="caption" fontWeight={700} color="error" sx={{ textTransform: 'uppercase', mb: 0.5, display: 'block' }}>
                    Error Message
                  </Typography>
                  <Typography variant="caption" sx={{ fontFamily: 'monospace', color: '#dc2626', maxWidth: 400, display: 'block' }}>
                    {event.error_message}
                  </Typography>
                </Box>
              )}
              {event.changes && Object.keys(event.changes).length > 0 && (
                <Box sx={{ flexGrow: 1 }}>
                  <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ textTransform: 'uppercase', mb: 0.5, display: 'block' }}>
                    Change Details
                  </Typography>
                  <Box component="pre" sx={{
                    bgcolor: '#1e293b', color: '#e2e8f0', p: 1.5, borderRadius: 1,
                    fontSize: 11, overflowX: 'auto', maxHeight: 160, m: 0,
                    fontFamily: 'monospace', lineHeight: 1.6,
                  }}>
                    {JSON.stringify(event.changes, null, 2)}
                  </Box>
                </Box>
              )}
              {!event.user_agent && !event.error_message && (!event.changes || Object.keys(event.changes).length === 0) && (
                <Typography variant="caption" color="text.disabled">No additional details available.</Typography>
              )}
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
}

interface SystemMonitorPageProps {
  isEmbedded?: boolean;
}

const SystemMonitorPage: React.FC<SystemMonitorPageProps> = ({ isEmbedded }) => {
  const { isSuperadmin } = useAuth();

  if (!isEmbedded && !isSuperadmin) {
    return <Navigate to="/dashboard" replace />;
  }

  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [wsStatus, setWsStatus] = useState<'connecting' | 'live' | 'error'>('connecting');
  const [liveNotification, setLiveNotification] = useState<AuditEvent | null>(null);
  const [telemetry, setTelemetry] = useState<SuperAdminTelemetry | null>(null);
  const [search, setSearch] = useState('');
  const [filterAction, setFilterAction] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterTenant, setFilterTenant] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  const ws = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMounted = useRef(true);
  const fetchRef = useRef<() => Promise<void>>();

  const fetchHistoricalEvents = useCallback(async () => {
    try {
      const token = sessionStorage.getItem('token');
      if (!token) return;
      const res = await axios.get('/api/v1/audit/?limit=500', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!isMounted.current) return;
      const historical: AuditEvent[] = res.data.map(transformAuditLog);
      setEvents((prev) => {
        const existingIds = new Set(prev.map((e) => e.id).filter(Boolean));
        const newOnes = historical.filter((e) => !e.id || !existingIds.has(e.id));
        return [...newOnes, ...prev].slice(0, 2000);
      });
    } catch { /* silent */ }
  }, []);

  useEffect(() => { fetchRef.current = fetchHistoricalEvents; }, [fetchHistoricalEvents]);

  const connectWs = useCallback(() => {
    if (!isMounted.current) return;
    if (ws.current) { ws.current.onclose = null; ws.current.close(); }
    if (pingInterval.current) clearInterval(pingInterval.current);

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const port = window.location.port ? `:${window.location.port}` : '';
    const socket = new WebSocket(`${protocol}//${host}${port}/api/v1/audit/stream`);
    ws.current = socket;
    setWsStatus('connecting');

    socket.onopen = () => {
      if (!isMounted.current) return;
      setWsStatus('live');
      pingInterval.current = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send('ping');
      }, 20000);
    };
    socket.onmessage = (e) => {
      if (!isMounted.current) return;
      try {
        const data = transformAuditLog(JSON.parse(e.data));
        setEvents((prev) => [data, ...prev].slice(0, 2000));
        setLiveNotification(data);
      } catch { /* ignore pongs */ }
    };
    socket.onerror = () => setWsStatus('error');
    socket.onclose = () => {
      if (pingInterval.current) clearInterval(pingInterval.current);
      if (!isMounted.current) return;
      setWsStatus('error');
      reconnectTimer.current = setTimeout(() => {
        if (isMounted.current) { fetchRef.current?.(); connectWs(); }
      }, 4000);
    };
  }, []);

  const fetchTelemetry = useCallback(async () => {
    try {
      const token = sessionStorage.getItem('token');
      if (!token) return;
      const res = await axios.get('/api/v1/superadmin/telemetry', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (isMounted.current) setTelemetry(res.data);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    isMounted.current = true;
    fetchHistoricalEvents();
    connectWs();
    fetchTelemetry();
    const eventPoll = setInterval(fetchHistoricalEvents, 30000);
    const telemetryPoll = setInterval(fetchTelemetry, 5000);
    return () => {
      isMounted.current = false;
      if (ws.current) { ws.current.onclose = null; ws.current.close(); }
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (pingInterval.current) clearInterval(pingInterval.current);
      clearInterval(eventPoll);
      clearInterval(telemetryPoll);
    };
  }, [fetchHistoricalEvents, connectWs, fetchTelemetry]);

  const allTenants = Array.from(new Set(events.map((e) => e.tenant_name).filter(Boolean)));
  const allActions = Array.from(new Set(events.map((e) => e.action).filter(Boolean)));

  const filtered = events.filter((e) => {
    const q = search.toLowerCase();
    const matchSearch = !q || (e.username?.toLowerCase().includes(q)) || (e.ip_address?.includes(q)) || (e.entity_name?.toLowerCase().includes(q)) || (e.action?.toLowerCase().includes(q));
    const matchAction = !filterAction || e.action === filterAction;
    const matchStatus = !filterStatus || (filterStatus === 'success' ? e.success : !e.success);
    const matchTenant = !filterTenant || e.tenant_name === filterTenant;
    return matchSearch && matchAction && matchStatus && matchTenant;
  });

  const paginated = filtered.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  const handleExport = () => {
    const rows = filtered.map((e) => ({
      id: e.id, timestamp: e.timestamp, tenant: e.tenant_name, user: e.username,
      ip: e.ip_address, action: e.action, resource: e.resource, entity: e.entity_name,
      status: e.status, error: e.error_message,
    }));
    const blob = new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = `audit_trail_${Date.now()}.json`; a.click();
  };

  const statusColor = wsStatus === 'live' ? 'success' : wsStatus === 'connecting' ? 'warning' : 'error';
  const statusLabel = wsStatus === 'live' ? 'Live' : wsStatus === 'connecting' ? 'Connecting...' : 'Reconnecting...';

  const failures = filtered.filter((e) => !e.success).length;

  return (
    <Container maxWidth={false} sx={{ mt: isEmbedded ? 0 : 3, mb: 4 }}>
      {/* ── Hero Card ─────────────────────────────────────────────────────── */}
      <Card variant="outlined" sx={{ mb: 3, borderRadius: 2 }}>
        <CardContent sx={{ py: 2.5, px: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <SecurityIcon sx={{ fontSize: 40, color: '#60a5fa' }} />
              <Box>
                <Typography variant="h5" fontWeight="bold">System Monitor & Audit Trail</Typography>
                <Typography variant="body2" color="text.secondary">
                  Real-time audit log with per-tenant isolation, IP tracking, and full event details
                </Typography>
              </Box>
            </Box>
            <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap">
              <Chip icon={<LiveIcon sx={{ fontSize: 10, animation: wsStatus === 'live' ? 'pulse 1.5s infinite' : 'none' }} />}
                label={statusLabel} color={statusColor} size="small" variant="filled" sx={{ fontWeight: 'bold' }} />
              <Chip label={`${filtered.length} events`} size="small" variant="outlined" color="primary" />
              {failures > 0 && (
                <Chip label={`${failures} failures`} size="small"
                  sx={{ bgcolor: '#ef444422', color: '#fca5a5', border: '1px solid #ef444455', fontWeight: 700 }} />
              )}
            </Stack>
          </Box>
          {wsStatus === 'connecting' && (
            <LinearProgress sx={{ mt: 1.5, borderRadius: 1, bgcolor: 'rgba(255,255,255,0.1)' }} />
          )}
        </CardContent>
      </Card>

      {/* ── Infrastructure Health ─────────────────────────────────────────── */}
      {telemetry && (
        <Card sx={{ mb: 3, bgcolor: '#f8fafc', border: '1px solid #e2e8f0', boxShadow: 'none' }}>
          <CardContent>
            <Typography variant="h6" fontWeight="bold" sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1 }}>
              <ServerIcon /> Infrastructure Health
            </Typography>
            <Grid container spacing={2}>
              {[
                { label: 'CPU', value: `${telemetry.cpu_usage_percent}%`, bad: telemetry.cpu_usage_percent > 80, warn: telemetry.cpu_usage_percent > 65 },
                { label: 'Memory', value: `${telemetry.memory_usage_percent}%`, bad: telemetry.memory_usage_percent > 80, warn: telemetry.memory_usage_percent > 65 },
                { label: 'Disk', value: `${telemetry.disk_usage_percent}%`, bad: telemetry.disk_usage_percent > 90, warn: telemetry.disk_usage_percent > 75 },
                { label: 'PostgreSQL', value: telemetry.db_connection_status.toUpperCase(), bad: telemetry.db_connection_status !== 'online', warn: false },
                { label: 'Redis / Celery', value: `${telemetry.redis_status} · ${telemetry.active_solver_jobs} jobs`, bad: telemetry.redis_status !== 'online', warn: false },
                { label: 'Uptime', value: formatUptime(telemetry.system_uptime_hours), bad: false, warn: telemetry.system_uptime_hours < 1 },
              ].map((s) => (
                <Grid item xs={6} sm={4} md={2} key={s.label}>
                  <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center', borderColor: s.bad ? '#ef4444' : s.warn ? '#f59e0b' : '#e2e8f0' }}>
                    <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ textTransform: 'uppercase', display: 'block' }}>{s.label}</Typography>
                    <Typography variant="body1" fontWeight={800} sx={{ color: s.bad ? '#ef4444' : s.warn ? '#f59e0b' : '#10b981' }}>{s.value}</Typography>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* ── Audit Trail Table ─────────────────────────────────────────────── */}
      <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
        {/* Filter Bar */}
        <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', gap: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexGrow: 1 }}>
            <SecurityIcon sx={{ color: '#3b82f6', fontSize: 20 }} />
            <Typography variant="subtitle1" fontWeight={700}>Audit Trail</Typography>
            <Badge badgeContent={filtered.length} color="primary" max={9999} sx={{ ml: 1 }} />
          </Box>
          <TextField
            size="small" placeholder="Search user, IP, entity..." value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> }}
            sx={{ minWidth: 220 }}
          />
          <TextField select size="small" label="Action" value={filterAction}
            onChange={(e) => { setFilterAction(e.target.value); setPage(0); }} sx={{ minWidth: 140 }}>
            <MenuItem value="">All Actions</MenuItem>
            {allActions.map((a) => <MenuItem key={a} value={a}>{a}</MenuItem>)}
          </TextField>
          <TextField select size="small" label="Status" value={filterStatus}
            onChange={(e) => { setFilterStatus(e.target.value); setPage(0); }} sx={{ minWidth: 120 }}>
            <MenuItem value="">All</MenuItem>
            <MenuItem value="success">Success</MenuItem>
            <MenuItem value="failure">Failure</MenuItem>
          </TextField>
          <TextField select size="small" label="Tenant" value={filterTenant}
            onChange={(e) => { setFilterTenant(e.target.value); setPage(0); }} sx={{ minWidth: 160 }}>
            <MenuItem value="">All Tenants</MenuItem>
            {allTenants.map((t) => <MenuItem key={t} value={t!}>{t}</MenuItem>)}
          </TextField>
          <Tooltip title="Export filtered logs as JSON">
            <IconButton size="small" onClick={handleExport}><ExportIcon fontSize="small" /></IconButton>
          </Tooltip>
        </Box>

        {/* Table */}
        <TableContainer sx={{ maxHeight: 620 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow sx={{ '& th': { bgcolor: '#0f172a', color: '#cbd5e1', fontWeight: 700, fontSize: 12, letterSpacing: 0.5 } }}>
                <TableCell sx={{ width: 36 }} />
                <TableCell>Timestamp</TableCell>
                <TableCell>Tenant</TableCell>
                <TableCell>User / IP</TableCell>
                <TableCell>Action</TableCell>
                <TableCell>Resource</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginated.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 6, color: 'text.secondary' }}>
                    <SecurityIcon sx={{ fontSize: 40, color: '#cbd5e1', mb: 1, display: 'block', mx: 'auto' }} />
                    No audit events match your filters.
                  </TableCell>
                </TableRow>
              ) : (
                paginated.map((event, idx) => (
                  <ExpandableRow key={event.id ? `id-${event.id}` : `idx-${idx}`} event={event} />
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>

        <TablePagination
          component="div" count={filtered.length} page={page} rowsPerPage={rowsPerPage}
          onPageChange={(_, p) => setPage(p)}
          onRowsPerPageChange={(e) => { setRowsPerPage(Number(e.target.value)); setPage(0); }}
          rowsPerPageOptions={[10, 25, 50, 100]}
        />
      </Paper>

      {/* ── Live Notification ─────────────────────────────────────────────── */}
      <Snackbar open={Boolean(liveNotification)} autoHideDuration={4000}
        onClose={() => setLiveNotification(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}>
        {liveNotification ? (
          <Alert onClose={() => setLiveNotification(null)}
            severity={liveNotification.success ? 'success' : 'error'}
            variant="filled" sx={{ width: '100%', boxShadow: 6 }}>
            <strong>{liveNotification.action}</strong>
            {' — '}
            {liveNotification.username || 'System'}
            {liveNotification.tenant_name && ` · ${liveNotification.tenant_name}`}
            {' '}
            {liveNotification.success ? 'succeeded' : 'failed'}
          </Alert>
        ) : <Box />}
      </Snackbar>
    </Container>
  );
};

export default SystemMonitorPage;
