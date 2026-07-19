import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Grid,
  IconButton,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import {
  Assessment as AssessmentIcon,
  Delete as DeleteIcon,
  Download as DownloadIcon,
  ExpandLess as ExpandLessIcon,
  ExpandMore as ExpandMoreIcon,
  History as HistoryIcon,
} from '@mui/icons-material';
import axios from 'axios';
import dayjs from 'dayjs';
import {
  DataTableShell,
  GlassFilterBar,
  HeroButton,
  HeroGhostButton,
  InsightCard,
  lightGlassFieldSx,
  lightGlassSelectMenuProps,
  StatusBadge,
  TenantPageHero,
} from '../components/tenant/TenantAdminUI';
import { useBranding } from '../contexts/BrandingContext';

interface AuditLog {
  id: number;
  user_id?: number;
  user_email: string;
  action: string;
  entity_type: string;
  entity_id?: number;
  entity_name?: string;
  changes?: any;
  ip_address?: string;
  user_agent?: string;
  timestamp: string;
  status: string;
  error_message?: string;
}

interface Statistics {
  total_logs: number;
  by_action: Record<string, number>;
  by_entity: Record<string, number>;
  by_status: Record<string, number>;
  unique_users: number;
}

const AuditLogsPage: React.FC = () => {
  const { branding } = useBranding();
  const primaryColor = branding.primary_color || '#1976d2';
  const secondaryColor = branding.secondary_color || '#9c27b0';

  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [statistics, setStatistics] = useState<Statistics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalLogs, setTotalLogs] = useState(0);
  const [actionFilter, setActionFilter] = useState('');
  const [entityFilter, setEntityFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [cleanupDialogOpen, setCleanupDialogOpen] = useState(false);
  const [cleanupDays, setCleanupDays] = useState(90);

  useEffect(() => {
    void fetchLogs();
    void fetchStatistics();
  }, [page, rowsPerPage, actionFilter, entityFilter, statusFilter, startDate, endDate]);

  const fetchLogs = async () => {
    setLoading(true);
    setError('');
    try {
      const params: any = {
        limit: rowsPerPage,
        offset: page * rowsPerPage,
      };
      if (actionFilter) params.action = actionFilter;
      if (entityFilter) params.entity_type = entityFilter;
      if (statusFilter) params.status = statusFilter;
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      const response = await axios.get('/api/v1/audit/', { params });
      setLogs(response.data.logs);
      setTotalLogs(response.data.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch audit logs');
    } finally {
      setLoading(false);
    }
  };

  const fetchStatistics = async () => {
    try {
      const params: any = {};
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      const response = await axios.get('/api/v1/audit/statistics', { params });
      setStatistics(response.data);
    } catch (err) {
      console.error('Failed to fetch statistics:', err);
    }
  };

  const handleExport = async () => {
    try {
      const params: any = {};
      if (actionFilter) params.action = actionFilter;
      if (entityFilter) params.entity_type = entityFilter;
      if (statusFilter) params.status = statusFilter;
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      const response = await axios.get('/api/v1/audit/export/json', {
        params,
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `audit_logs_${dayjs().format('YYYY-MM-DD')}.json`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      setError('Failed to export logs');
    }
  };

  const handleCleanup = async () => {
    if (cleanupDays < 30) {
      setError('Minimum retention period is 30 days');
      return;
    }
    try {
      await axios.delete(`/api/v1/audit/cleanup?days=${cleanupDays}`);
      setCleanupDialogOpen(false);
      void fetchLogs();
      void fetchStatistics();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to cleanup logs');
    }
  };

  const getStatusTone = (status: string) => {
    switch (status.toLowerCase()) {
      case 'success':
        return 'success' as const;
      case 'failure':
      case 'error':
        return 'danger' as const;
      default:
        return 'default' as const;
    }
  };

  const getActionTone = (action: string) => {
    switch (action.toUpperCase()) {
      case 'CREATE':
        return 'success' as const;
      case 'UPDATE':
        return 'info' as const;
      case 'DELETE':
        return 'danger' as const;
      case 'GENERATE':
        return 'warning' as const;
      default:
        return 'default' as const;
    }
  };

  return (
    <Box>
      <TenantPageHero
        title="Audit Logs"
        description="Trace changes, login activity, and operational events in a denser surface that still speaks the same blue-purple glass language as the rest of the tenant-admin suite."
        eyebrow="Operations Trace"
        icon={<HistoryIcon />}
        primaryColor={primaryColor}
        secondaryColor={secondaryColor}
        meta={statistics ? <Typography variant="body2" sx={{ color: '#fff' }}>{statistics.total_logs} events tracked</Typography> : undefined}
        actions={(
          <>
            <HeroButton startIcon={<DownloadIcon />} onClick={handleExport}>Export</HeroButton>
            <HeroGhostButton startIcon={<DeleteIcon />} onClick={() => setCleanupDialogOpen(true)}>Cleanup</HeroGhostButton>
          </>
        )}
      />

      {error && <Alert severity="error" sx={{ mb: 2.5 }} onClose={() => setError('')}>{error}</Alert>}

      {statistics && (
        <Grid container spacing={2.5} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6} md={3}>
            <InsightCard title="Total Logs" icon={<AssessmentIcon />} primaryColor={primaryColor} secondaryColor={secondaryColor}>
              <Typography variant="h4" fontWeight={900}>{statistics.total_logs}</Typography>
            </InsightCard>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <InsightCard title="Unique Users" icon={<HistoryIcon />} primaryColor={primaryColor} secondaryColor={secondaryColor}>
              <Typography variant="h4" fontWeight={900}>{statistics.unique_users}</Typography>
            </InsightCard>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <InsightCard title="Action Mix" primaryColor={primaryColor} secondaryColor={secondaryColor}>
              <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
                {Object.entries(statistics.by_action).slice(0, 3).map(([action, count]) => (
                  <StatusBadge key={action} label={`${action}: ${count}`} tone={getActionTone(action)} subtle />
                ))}
              </Box>
            </InsightCard>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <InsightCard title="Status Mix" primaryColor={primaryColor} secondaryColor={secondaryColor}>
              <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
                {Object.entries(statistics.by_status).map(([status, count]) => (
                  <StatusBadge key={status} label={`${status}: ${count}`} tone={getStatusTone(status)} subtle />
                ))}
              </Box>
            </InsightCard>
          </Grid>
        </Grid>
      )}

      <GlassFilterBar primaryColor={primaryColor} secondaryColor={secondaryColor}>
        <TextField
          select
          fullWidth
          label="Action"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          size="small"
          sx={lightGlassFieldSx}
          SelectProps={{ MenuProps: lightGlassSelectMenuProps }}
        >
          <MenuItem value="">All</MenuItem>
          <MenuItem value="CREATE">CREATE</MenuItem>
          <MenuItem value="UPDATE">UPDATE</MenuItem>
          <MenuItem value="DELETE">DELETE</MenuItem>
          <MenuItem value="LOGIN">LOGIN</MenuItem>
          <MenuItem value="LOGOUT">LOGOUT</MenuItem>
          <MenuItem value="GENERATE">GENERATE</MenuItem>
        </TextField>
        <TextField
          select
          fullWidth
          label="Entity Type"
          value={entityFilter}
          onChange={(e) => setEntityFilter(e.target.value)}
          size="small"
          sx={lightGlassFieldSx}
          SelectProps={{ MenuProps: lightGlassSelectMenuProps }}
        >
          <MenuItem value="">All</MenuItem>
          <MenuItem value="course">Course</MenuItem>
          <MenuItem value="timetable">Timetable</MenuItem>
          <MenuItem value="user">User</MenuItem>
          <MenuItem value="lecturer">Lecturer</MenuItem>
          <MenuItem value="room">Room</MenuItem>
          <MenuItem value="department">Department</MenuItem>
          <MenuItem value="group">Group</MenuItem>
        </TextField>
        <TextField
          select
          fullWidth
          label="Status"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          size="small"
          sx={lightGlassFieldSx}
          SelectProps={{ MenuProps: lightGlassSelectMenuProps }}
        >
          <MenuItem value="">All</MenuItem>
          <MenuItem value="success">Success</MenuItem>
          <MenuItem value="failure">Failure</MenuItem>
          <MenuItem value="error">Error</MenuItem>
        </TextField>
        <TextField
          fullWidth
          type="date"
          label="Start Date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          InputLabelProps={{ shrink: true }}
          size="small"
          sx={lightGlassFieldSx}
        />
        <TextField
          fullWidth
          type="date"
          label="End Date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          InputLabelProps={{ shrink: true }}
          size="small"
          sx={lightGlassFieldSx}
        />
      </GlassFilterBar>

      <DataTableShell
        title="Audit Event Stream"
        description="Expand a row for request context, user agent, and change payload."
        primaryColor={primaryColor}
        secondaryColor={secondaryColor}
      >
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: 'rgba(15,23,42,0.03)' }}>
              <TableCell width={56} />
              <TableCell sx={{ fontWeight: 800 }}>Timestamp</TableCell>
              <TableCell sx={{ fontWeight: 800 }}>User</TableCell>
              <TableCell sx={{ fontWeight: 800 }}>Action</TableCell>
              <TableCell sx={{ fontWeight: 800 }}>Entity</TableCell>
              <TableCell sx={{ fontWeight: 800 }}>Status</TableCell>
              <TableCell sx={{ fontWeight: 800 }}>IP Address</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 5 }}>
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : logs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 5 }}>
                  <Typography color="text.secondary">No audit logs found.</Typography>
                </TableCell>
              </TableRow>
            ) : (
              logs.map((log) => (
                <React.Fragment key={log.id}>
                  <TableRow hover>
                    <TableCell>
                      <IconButton size="small" onClick={() => setExpandedRow(expandedRow === log.id ? null : log.id)}>
                        {expandedRow === log.id ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                      </IconButton>
                    </TableCell>
                    <TableCell>{dayjs(log.timestamp).format('YYYY-MM-DD HH:mm:ss')}</TableCell>
                    <TableCell>{log.user_email}</TableCell>
                    <TableCell><StatusBadge label={log.action} tone={getActionTone(log.action)} subtle /></TableCell>
                    <TableCell>{log.entity_name || `${log.entity_type} #${log.entity_id || 'N/A'}`}</TableCell>
                    <TableCell><StatusBadge label={log.status} tone={getStatusTone(log.status)} subtle /></TableCell>
                    <TableCell>{log.ip_address || 'N/A'}</TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell colSpan={7} sx={{ p: 0, borderBottom: expandedRow === log.id ? undefined : 'none' }}>
                      <Collapse in={expandedRow === log.id} timeout="auto" unmountOnExit>
                        <Box sx={{ p: 2.5, bgcolor: 'rgba(15,23,42,0.02)' }}>
                          <Typography variant="subtitle2" sx={{ fontWeight: 800, mb: 1.5 }}>Details</Typography>
                          {log.user_agent && (
                            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                              User Agent: {log.user_agent}
                            </Typography>
                          )}
                          {log.error_message && <Alert severity="error" sx={{ mb: 1.5 }}>{log.error_message}</Alert>}
                          {log.changes && (
                            <Box sx={{ p: 2, borderRadius: 3, bgcolor: '#0f172a', color: '#e2e8f0', overflowX: 'auto' }}>
                              <pre style={{ margin: 0, fontSize: '0.82rem' }}>
                                {JSON.stringify(log.changes, null, 2)}
                              </pre>
                            </Box>
                          )}
                        </Box>
                      </Collapse>
                    </TableCell>
                  </TableRow>
                </React.Fragment>
              ))
            )}
          </TableBody>
        </Table>
        <TablePagination
          rowsPerPageOptions={[10, 25, 50, 100]}
          component="div"
          count={totalLogs}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={(_, nextPage) => setPage(nextPage)}
          onRowsPerPageChange={(event) => {
            setRowsPerPage(parseInt(event.target.value, 10));
            setPage(0);
          }}
        />
      </DataTableShell>

      <Dialog open={cleanupDialogOpen} onClose={() => setCleanupDialogOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Cleanup Audit Logs</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            Delete audit logs older than the selected retention period.
          </DialogContentText>
          <TextField
            fullWidth
            type="number"
            label="Retention Period (days)"
            value={cleanupDays}
            onChange={(e) => setCleanupDays(Number(e.target.value))}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCleanupDialogOpen(false)}>Cancel</Button>
          <Button color="error" variant="contained" onClick={() => { void handleCleanup(); }}>
            Delete Old Logs
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AuditLogsPage;
