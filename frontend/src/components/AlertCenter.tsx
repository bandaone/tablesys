import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Badge, IconButton, Drawer, Box, Typography, Chip, Stack, Divider,
  Button, Tooltip, CircularProgress, Paper,
} from '@mui/material';
import {
  NotificationsActive as BellIcon,
  CheckCircle as AckIcon,
  Close as CloseIcon,
  Error as CritIcon,
  Warning as WarnIcon,
  Info as InfoIcon,
  CheckCircleOutline as ResolvedIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import axios from 'axios';

interface PlatformAlert {
  id: number;
  severity: 'critical' | 'warning' | 'info';
  category: string;
  title: string;
  detail?: string;
  tenant_name?: string;
  triggered_at: string;
  acknowledged_by?: string;
  alert_key: string;
}

const SEVERITY_CONFIG = {
  critical: { color: '#ef4444', bg: '#fef2f2', border: '#fecaca', icon: <CritIcon sx={{ color: '#ef4444', fontSize: 18 }} />, label: 'Critical' },
  warning:  { color: '#f59e0b', bg: '#fffbeb', border: '#fde68a', icon: <WarnIcon sx={{ color: '#f59e0b', fontSize: 18 }} />, label: 'Warning' },
  info:     { color: '#3b82f6', bg: '#eff6ff', border: '#bfdbfe', icon: <InfoIcon sx={{ color: '#3b82f6', fontSize: 18 }} />, label: 'Info' },
};

const authHeader = () => ({ Authorization: `Bearer ${sessionStorage.getItem('token')}` });

export const AlertCenter: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState<PlatformAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [ackingId, setAckingId] = useState<number | null>(null);
  const [resolvingId, setResolvingId] = useState<number | null>(null);
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchAlerts = useCallback(async () => {
    try {
      const res = await axios.get('/api/v1/superadmin/alerts/', { headers: authHeader() });
      setAlerts(res.data);
    } catch { /* silent — user may not be superadmin on all pages */ }
  }, []);

  useEffect(() => {
    fetchAlerts();
    pollTimer.current = setInterval(fetchAlerts, 60_000);
    return () => { if (pollTimer.current) clearInterval(pollTimer.current); };
  }, [fetchAlerts]);

  const handleAck = async (id: number) => {
    setAckingId(id);
    try {
      await axios.post(`/api/v1/superadmin/alerts/${id}/acknowledge`, {}, { headers: authHeader() });
      await fetchAlerts();
    } finally { setAckingId(null); }
  };

  const handleResolve = async (id: number) => {
    setResolvingId(id);
    try {
      await axios.post(`/api/v1/superadmin/alerts/${id}/resolve`, {}, { headers: authHeader() });
      await fetchAlerts();
    } finally { setResolvingId(null); }
  };

  const handleRunCheck = async () => {
    setLoading(true);
    try {
      await axios.post('/api/v1/superadmin/alerts/run-check', {}, { headers: authHeader() });
      await fetchAlerts();
    } finally { setLoading(false); }
  };

  const critCount = alerts.filter(a => a.severity === 'critical').length;
  const warnCount = alerts.filter(a => a.severity === 'warning').length;
  const totalActive = alerts.length;

  const grouped = {
    critical: alerts.filter(a => a.severity === 'critical'),
    warning:  alerts.filter(a => a.severity === 'warning'),
    info:     alerts.filter(a => a.severity === 'info'),
  };

  return (
    <>
      <Tooltip title={totalActive > 0 ? `${totalActive} active alert${totalActive > 1 ? 's' : ''}` : 'No active alerts'}>
        <IconButton
          onClick={() => setOpen(true)}
          sx={{
            position: 'relative',
            color: critCount > 0 ? '#ef4444' : warnCount > 0 ? '#f59e0b' : 'inherit',
          }}
        >
          <Badge
            badgeContent={totalActive || null}
            color={critCount > 0 ? 'error' : warnCount > 0 ? 'warning' : 'default'}
            max={99}
          >
            <BellIcon sx={{ animation: critCount > 0 ? 'pulse 1.5s infinite' : 'none' }} />
          </Badge>
        </IconButton>
      </Tooltip>

      <Drawer
        anchor="right"
        open={open}
        onClose={() => setOpen(false)}
        PaperProps={{ sx: { width: { xs: '100vw', sm: 440 }, display: 'flex', flexDirection: 'column' } }}
      >
        {/* Header */}
        <Box sx={{ p: 2.5, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 1 }}>
          <BellIcon color={critCount > 0 ? 'error' : 'inherit'} />
          <Typography variant="h6" fontWeight={700} sx={{ flexGrow: 1 }}>
            Alert Center
          </Typography>
          <Tooltip title="Run alert check now">
            <IconButton size="small" onClick={handleRunCheck} disabled={loading}>
              {loading ? <CircularProgress size={16} /> : <RefreshIcon fontSize="small" />}
            </IconButton>
          </Tooltip>
          <IconButton size="small" onClick={() => setOpen(false)}><CloseIcon fontSize="small" /></IconButton>
        </Box>

        {/* Summary bar */}
        <Box sx={{ px: 2.5, py: 1.5, bgcolor: '#f8fafc', borderBottom: '1px solid', borderColor: 'divider' }}>
          <Stack direction="row" spacing={1}>
            <Chip label={`${critCount} Critical`} size="small" color="error" variant={critCount > 0 ? 'filled' : 'outlined'} sx={{ fontWeight: 700 }} />
            <Chip label={`${warnCount} Warning`} size="small" color="warning" variant={warnCount > 0 ? 'filled' : 'outlined'} sx={{ fontWeight: 700 }} />
            <Chip label={`${grouped.info.length} Info`} size="small" color="info" variant={grouped.info.length > 0 ? 'filled' : 'outlined'} sx={{ fontWeight: 700 }} />
          </Stack>
        </Box>

        {/* Alert list */}
        <Box sx={{ flexGrow: 1, overflowY: 'auto', p: 2 }}>
          {totalActive === 0 ? (
            <Box sx={{ py: 8, textAlign: 'center' }}>
              <ResolvedIcon sx={{ fontSize: 48, color: '#10b981', mb: 1 }} />
              <Typography variant="body1" fontWeight={600} color="text.secondary">All Clear</Typography>
              <Typography variant="caption" color="text.disabled">No active platform alerts.</Typography>
            </Box>
          ) : (
            (['critical', 'warning', 'info'] as const).map(severity => {
              const group = grouped[severity];
              if (!group.length) return null;
              const cfg = SEVERITY_CONFIG[severity];
              return (
                <Box key={severity} sx={{ mb: 2 }}>
                  <Typography variant="caption" fontWeight={700} sx={{ color: cfg.color, textTransform: 'uppercase', letterSpacing: 0.8, display: 'block', mb: 1 }}>
                    {cfg.label} ({group.length})
                  </Typography>
                  <Stack spacing={1.5}>
                    {group.map(alert => (
                      <Paper
                        key={alert.id}
                        variant="outlined"
                        sx={{
                          p: 1.5,
                          bgcolor: cfg.bg,
                          borderColor: cfg.border,
                          borderLeft: `4px solid ${cfg.color}`,
                        }}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 0.5 }}>
                          {cfg.icon}
                          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                            <Typography variant="body2" fontWeight={700} sx={{ lineHeight: 1.3 }}>
                              {alert.title}
                            </Typography>
                            {alert.tenant_name && (
                              <Chip label={alert.tenant_name} size="small"
                                sx={{ fontSize: 10, height: 18, mt: 0.5, color: '#7c3aed', borderColor: '#7c3aed55', bgcolor: 'transparent', border: '1px solid' }} />
                            )}
                          </Box>
                        </Box>
                        {alert.detail && (
                          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1, pl: 3.25 }}>
                            {alert.detail}
                          </Typography>
                        )}
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pl: 3.25 }}>
                          <Typography variant="caption" color="text.disabled" sx={{ fontFamily: 'monospace' }}>
                            {new Date(alert.triggered_at).toLocaleString()}
                          </Typography>
                          <Stack direction="row" spacing={0.5}>
                            {!alert.acknowledged_by && (
                              <Button size="small" startIcon={<AckIcon sx={{ fontSize: 12 }} />}
                                disabled={ackingId === alert.id}
                                onClick={() => handleAck(alert.id)}
                                sx={{ fontSize: 11, py: 0.25, px: 0.75, minWidth: 0 }}>
                                Ack
                              </Button>
                            )}
                            <Button size="small" color="error" startIcon={<ResolvedIcon sx={{ fontSize: 12 }} />}
                              disabled={resolvingId === alert.id}
                              onClick={() => handleResolve(alert.id)}
                              sx={{ fontSize: 11, py: 0.25, px: 0.75, minWidth: 0 }}>
                              Resolve
                            </Button>
                          </Stack>
                        </Box>
                      </Paper>
                    ))}
                  </Stack>
                </Box>
              );
            })
          )}
        </Box>
      </Drawer>
    </>
  );
};

export default AlertCenter;
