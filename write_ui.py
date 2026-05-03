import os

react_code = """import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Paper, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Button, Chip, IconButton, Drawer, Grid, CircularProgress, 
  Alert, Tooltip, Stack, LinearProgress, Divider
} from '@mui/material';
import {
  Block as BlockIcon, CheckCircle as CheckCircleIcon,
  Logout as LogoutIcon, RocketLaunch as RocketLaunchIcon, Storage as StorageIcon,
  Security as SecurityIcon, Terminal as TerminalIcon, Bolt as BoltIcon,
  Memory as MemoryIcon, AccessTime as AccessTimeIcon
} from '@mui/icons-material';
import { superadminAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';

// Terminal God-Mode Theme Variables
const SA_BG = '#030303'; // Pitch black
const CARD_BG = '#0a0a0a';
const BORDER = '1px solid #1f1f1f';
const PRIMARY = '#00ffcc'; // Cybernetic cyan/green for primary actions
const DANGER = '#ff3333';  // High intensity danger red
const TEXT_MAIN = '#e0e0e0';
const TEXT_MUTED = '#666666';
const HIGHLIGHT = 'rgba(0, 255, 204, 0.05)';

const MotionPaper = motion(Paper);

export default function SuperAdminPage() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const [telemetry, setTelemetry] = useState<any>(null);
  const [universities, setUniversities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  useEffect(() => {
    loadData();
    // Poll telemetry every 10 seconds for real-time god-mode feel
    const interval = setInterval(() => {
      loadTelemetryOnly();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [telemetryRes, univRes] = await Promise.all([
        superadminAPI.getTelemetry(),
        superadminAPI.getUniversities()
      ]);
      setTelemetry(telemetryRes);
      setUniversities(univRes);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'System Core Offline. Telemetry connection refused.');
    } finally {
      setLoading(false);
    }
  };

  const loadTelemetryOnly = async () => {
    try {
      const res = await superadminAPI.getTelemetry();
      setTelemetry(res);
    } catch (e) {
      // Silent fail on background polling
    }
  };

  const toggleStatus = async (id: number, current: boolean) => {
    try {
      setActionLoading(id);
      await superadminAPI.updateUniversity(id, { is_active: !current });
      await loadData();
    } catch {
      setError('Overload failure on tenant status mutation.');
    } finally {
      setActionLoading(null);
    }
  };

  const deleteTenant = async (id: number) => {
    if (!window.confirm('CRITICAL WARN: Purge tenant from platform registry? This is destructive.')) return;
    try {
      setActionLoading(id);
      await superadminAPI.suspendUniversity(id);
      await loadData();
    } catch {
      setError('Purge failed. Constraint block active.');
    } finally {
      setActionLoading(null);
    }
  };

  const formatUptime = (seconds: number) => {
    if (!seconds) return 'OFFLINE';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${hrs}h ${mins}m`;
  };

  if (loading && !telemetry) {
    return (
      <Box sx={{ minHeight: '100vh', background: SA_BG, color: PRIMARY, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <TerminalIcon sx={{ fontSize: 60, mb: 2, animation: 'pulse 1.5s infinite' }} />
        <Typography fontFamily="monospace" variant="h6">ESTABLISHING GOD-MODE UPLINK...</Typography>
        <LinearProgress sx={{ w: 300, mt: 2, '& .MuiLinearProgress-bar': { bgcolor: PRIMARY }, bgcolor: '#111' }} />
      </Box>
    );
  }

  return (
    <Box sx={{ minHeight: '100vh', background: SA_BG, p: { xs: 2, md: 4 }, color: TEXT_MAIN, fontFamily: 'monospace' }}>
      
      {/* HEADER CONTROLS */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4, borderBottom: BORDER, pb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <RocketLaunchIcon sx={{ color: PRIMARY, fontSize: 32 }} />
          <Box>
            <Typography variant="h5" fontWeight="bold" fontFamily="monospace" sx={{ letterSpacing: 2, textTransform: 'uppercase' }}>
              TableSys Core Command
            </Typography>
            <Typography variant="caption" sx={{ color: TEXT_MUTED, fontFamily: 'monospace' }}>
              System Uptime: {formatUptime(telemetry?.uptime_seconds)} • Root Access Granted
            </Typography>
          </Box>
        </Box>
        
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <Chip icon={<SecurityIcon fontSize="small" />} label="GOD-MODE ACTIVE" size="small" 
                sx={{ bgcolor: PRIMARY, color: '#000', fontWeight: 'bold', fontFamily: 'monospace', borderRadius: 0 }} />
          <Button startIcon={<LogoutIcon />} variant="outlined" size="small"
                  onClick={() => { logout(); navigate('/login'); }}
                  sx={{ color: DANGER, borderColor: DANGER, fontFamily: 'monospace', borderRadius: 0, '&:hover': { bgcolor: 'rgba(255,51,51,0.1)' } }}>
            TERMINATE SESSION
          </Button>
        </Box>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 3, bgcolor: '#330000', color: DANGER, border: `1px solid ${DANGER}`, borderRadius: 0 }} onClose={() => setError('')}>{error}</Alert>}

      {/* TELEMETRY MATRIX */}
      <Grid container spacing={2} mb={4}>
        <Grid item xs={12} md={3}>
          <MotionPaper initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
                       sx={{ p: 2, bgcolor: CARD_BG, border: BORDER, borderRadius: 0, '&:hover': { borderColor: PRIMARY } }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="caption" sx={{ color: TEXT_MUTED, fontFamily: 'monospace' }}>PLATFORM USERS</Typography>
              <PeopleIcon sx={{ color: PRIMARY, fontSize: 18 }} />
            </Box>
            <Typography variant="h3" fontFamily="monospace" fontWeight="bold">
              {telemetry?.total_users?.toString().padStart(4, '0')}
            </Typography>
          </MotionPaper>
        </Grid>
        
        <Grid item xs={12} md={3}>
          <MotionPaper initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
                       sx={{ p: 2, bgcolor: CARD_BG, border: BORDER, borderRadius: 0, '&:hover': { borderColor: PRIMARY } }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="caption" sx={{ color: TEXT_MUTED, fontFamily: 'monospace' }}>TENANT SHARDS</Typography>
              <StorageIcon sx={{ color: PRIMARY, fontSize: 18 }} />
            </Box>
            <Typography variant="h3" fontFamily="monospace" fontWeight="bold">
              {telemetry?.total_tenants?.toString().padStart(4, '0')}
            </Typography>
          </MotionPaper>
        </Grid>

        <Grid item xs={12} md={3}>
          <MotionPaper initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
                       sx={{ p: 2, bgcolor: CARD_BG, border: BORDER, borderRadius: 0, '&:hover': { borderColor: PRIMARY } }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="caption" sx={{ color: TEXT_MUTED, fontFamily: 'monospace' }}>SOLVER ENGINES</Typography>
              <BoltIcon sx={{ color: PRIMARY, fontSize: 18 }} />
            </Box>
            <Typography variant="h3" fontFamily="monospace" fontWeight="bold">
              {telemetry?.active_celery_jobs?.toString().padStart(4, '0')}
            </Typography>
            <Typography variant="caption" sx={{ color: TEXT_MUTED, fontFamily: 'monospace' }}>
              Q: {telemetry?.queued_celery_jobs || 0} PENDING
            </Typography>
          </MotionPaper>
        </Grid>
        
        <Grid item xs={12} md={3}>
          <MotionPaper initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}
                       sx={{ p: 2, bgcolor: CARD_BG, border: BORDER, borderRadius: 0, '&:hover': { borderColor: PRIMARY } }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="caption" sx={{ color: TEXT_MUTED, fontFamily: 'monospace' }}>REDIS HEARTBEAT</Typography>
              <MemoryIcon sx={{ color: telemetry?.redis_alive ? PRIMARY : DANGER, fontSize: 18 }} />
            </Box>
            <Typography variant="h4" fontFamily="monospace" sx={{ mt: 1, color: telemetry?.redis_alive ? PRIMARY : DANGER }}>
              {telemetry?.redis_alive ? 'ONLINE' : 'CRITICAL'}
            </Typography>
          </MotionPaper>
        </Grid>
      </Grid>

      {/* TENANT DATA GRID - HIGH DENSITY */}
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="body1" fontFamily="monospace" sx={{ color: PRIMARY, textTransform: 'uppercase' }}>
          > Global Tenant Registry
        </Typography>
      </Box>

      <TableContainer component={Paper} sx={{ bgcolor: CARD_BG, border: BORDER, borderRadius: 0 }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ bgcolor: '#111' }}>
              <TableCell sx={{ color: TEXT_MUTED, fontFamily: 'monospace', borderBottom: BORDER, py: 1.5 }}>UUID/ID</TableCell>
              <TableCell sx={{ color: TEXT_MUTED, fontFamily: 'monospace', borderBottom: BORDER, py: 1.5 }}>TENANT_NAME</TableCell>
              <TableCell sx={{ color: TEXT_MUTED, fontFamily: 'monospace', borderBottom: BORDER, py: 1.5 }}>ROUTING_DOMAIN</TableCell>
              <TableCell sx={{ color: TEXT_MUTED, fontFamily: 'monospace', borderBottom: BORDER, py: 1.5 }}>SYS_STATUS</TableCell>
              <TableCell align="right" sx={{ color: TEXT_MUTED, fontFamily: 'monospace', borderBottom: BORDER, py: 1.5 }}>OVERRIDE</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {universities.map(u => (
              <TableRow key={u.id} sx={{ '&:hover': { bgcolor: HIGHLIGHT }, transition: 'background 0.2s', borderBottom: BORDER }}>
                <TableCell sx={{ color: TEXT_MAIN, fontFamily: 'monospace', borderBottom: 'none', py: 1 }}>{u.id.toString().padStart(4, '0')}</TableCell>
                <TableCell sx={{ color: 'white', fontFamily: 'monospace', fontWeight: 'bold', borderBottom: 'none', py: 1 }}>{u.name}</TableCell>
                <TableCell sx={{ color: PRIMARY, fontFamily: 'monospace', borderBottom: 'none', py: 1 }}>{u.domain}</TableCell>
                <TableCell sx={{ borderBottom: 'none', py: 1 }}>
                  <Chip label={u.is_active ? 'OP_NORMAL' : 'HALTED'} 
                        size="small" 
                        sx={{ 
                          bgcolor: u.is_active ? 'rgba(0,255,204,0.1)' : 'rgba(255,51,51,0.1)', 
                          color: u.is_active ? PRIMARY : DANGER, 
                          fontFamily: 'monospace', 
                          borderRadius: 0,
                          height: 20,
                          fontSize: '0.7rem',
                          border: `1px solid ${u.is_active ? PRIMARY : DANGER}`
                        }} />
                </TableCell>
                <TableCell align="right" sx={{ borderBottom: 'none', py: 1 }}>
                  <Stack direction="row" spacing={1} justifyContent="flex-end">
                    {actionLoading === u.id ? <CircularProgress size={20} sx={{color: PRIMARY}} /> : (
                      <>
                        <Tooltip title={u.is_active ? "HALT CLUSTER" : "RESUME CLUSTER"}>
                          <IconButton size="small" onClick={() => toggleStatus(u.id, u.is_active)}
                                      sx={{ color: u.is_active ? '#aa0000' : PRIMARY, border: u.is_active ? '1px solid #440000' : `1px solid ${PRIMARY}`, borderRadius: 0 }}>
                            <BlockIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="PURGE TENANT (DANGER)">
                          <IconButton size="small" onClick={() => deleteTenant(u.id)}
                                      sx={{ color: DANGER, border: `1px solid ${DANGER}`, borderRadius: 0, '&:hover': {bgcolor: 'rgba(255,0,0,0.1)'} }}>
                            <TerminalIcon fontSize="small" sx={{transform: 'rotate(90deg)'}} />
                          </IconButton>
                        </Tooltip>
                      </>
                    )}
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
            {universities.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} sx={{ textAlign: 'center', py: 4, color: TEXT_MUTED, fontFamily: 'monospace', borderBottom: 'none' }}>
                  NO TENANTS ALLOCATED IN CLUSTER
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Box sx={{ mt: 4, display: 'flex', justifyContent: 'center', opacity: 0.5 }}>
        <Typography variant="caption" sx={{ fontFamily: 'monospace', color: TEXT_MUTED }}>
          v2.0 • TERMINAL MODE • STRICT ISOLATION PROTOCOLS ENFORCED
        </Typography>
      </Box>

    </Box>
  );
}
"""

with open("frontend/src/pages/SuperAdminPage.tsx", "w", encoding="utf-8") as f:
    f.write(react_code)
print("File written successfully.")

