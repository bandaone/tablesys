import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
    Box,
    Typography,
    Container,
    Grid,
    Chip,
    Snackbar,
    Alert,
    Card,
    CardContent,
    LinearProgress,
    CircularProgress,
    Paper,
    Divider
} from '@mui/material';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

import {
    Security as SecurityIcon,
    CloudUpload as UploadIcon,
    Memory as GenerateIcon,
    Visibility as ViewIcon,
    Dashboard as DashboardIcon,
    FiberManualRecord as LiveIcon,
    Warning as WarningIcon,
    Storage as StorageIcon,
    Dns as ServerIcon,
    Computer as CpuIcon,
    Memory as RamIcon,
    Storage as DbIcon
} from '@mui/icons-material';
import { MonitorWidget } from '../components/MonitorWidget';
import axios from 'axios';

interface SuperAdminTelemetry {
    redis_status: string;
    active_solver_jobs: number;
    total_universities: number;
    active_users: number;
    system_uptime_hours: number;
    cpu_usage_percent: number;
    memory_usage_percent: number;
    disk_usage_percent: number;
    db_connection_status: string;
}

interface AuditEvent {    id?: number;
    timestamp: string;
    event_type: string;
    user_id: number | null;
    username: string | null;
    resource: string;
    action: string;
    success: boolean;
    details: any;
}

// Transform a REST audit log into the shape MonitorWidget expects
function transformAuditLog(log: any): AuditEvent {
    return {
        id: log.id,
        timestamp: log.timestamp,
        // Merge fields carefully to handle both REST ActivityLog and WS AuditEvent shapes
        event_type: log.event_type || (log.action && log.entity_type ? `${log.action}_${log.entity_type}`.toUpperCase() : log.action || 'UNKNOWN'),
        user_id: log.user_id ?? null,
        username: log.user_email || log.username || null,
        resource: log.entity_type || log.resource || '',
        action: log.action ?? '',
        success: log.status === 'success' || log.success === true,
        details: log.changes || log.details || {},
    };
}

const SystemMonitorPage: React.FC = () => {
    const { isSuperadmin, isCoordinator } = useAuth();

    // Redirect standard users immediately
    if (!isSuperadmin && !isCoordinator) {
        return <Navigate to="/dashboard" replace />;
    }

    const [events, setEvents] = useState<AuditEvent[]>([]);
    const [wsStatus, setWsStatus] = useState<'connecting' | 'live' | 'error'>('connecting');
    const [liveNotification, setLiveNotification] = useState<AuditEvent | null>(null);

    // New telemetry state
    const [telemetry, setTelemetry] = useState<SuperAdminTelemetry | null>(null);
    const [telemetryLoading, setTelemetryLoading] = useState(false);

    const ws = useRef<WebSocket | null>(null);
    const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const pingInterval = useRef<ReturnType<typeof setInterval> | null>(null);
    const isMounted = useRef(true);
    // Use a ref for fetchHistoricalEvents to avoid stale closures inside WS handlers
    const fetchRef = useRef<() => Promise<void>>();

    // Fetch historical events from the REST API so the dashboard is never empty
    const fetchHistoricalEvents = useCallback(async () => {
        try {
            const token = sessionStorage.getItem('token');
            if (!token) return;
            const res = await axios.get('/api/v1/audit/?limit=200', {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!isMounted.current) return;
            const historical: AuditEvent[] = res.data.map(transformAuditLog);
            setEvents(prev => {
                // Merge historical into current, deduplicate by id
                const existingIds = new Set(prev.map(e => e.id).filter(Boolean));
                const newOnes = historical.filter(e => !e.id || !existingIds.has(e.id));
                return [...prev, ...newOnes].slice(0, 1000);
            });
        } catch {
            // Not critical — WS will provide live data
        }
    }, []);

    // Keep fetchRef in sync so WS handlers always have the latest version
    useEffect(() => { fetchRef.current = fetchHistoricalEvents; }, [fetchHistoricalEvents]);

    const connectWs = useCallback(() => {
        if (!isMounted.current) return;

        // Clean up any stale socket
        if (ws.current) {
            ws.current.onclose = null;
            ws.current.close();
        }
        if (pingInterval.current) clearInterval(pingInterval.current);

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname;
        const port = window.location.port ? `:${window.location.port}` : '';
        const wsUrl = `${protocol}//${host}${port}/api/v1/audit/stream`;

        console.log('[Monitor] Connecting WS to:', wsUrl);
        setWsStatus('connecting');

        const socket = new WebSocket(wsUrl);
        ws.current = socket;

        socket.onopen = () => {
            if (!isMounted.current) return;
            console.log('[Monitor] WS Connected');
            setWsStatus('live');
            // Keep-alive ping every 20s
            pingInterval.current = setInterval(() => {
                if (socket.readyState === WebSocket.OPEN) {
                    socket.send('ping');
                }
            }, 20000);
        };

        socket.onmessage = (event) => {
            if (!isMounted.current) return;
            try {
                const data: AuditEvent = JSON.parse(event.data);
                console.log('[Monitor] WS Event received:', data.event_type);
                setEvents(prev => [data, ...prev].slice(0, 1000));
                setLiveNotification(data);
            } catch {
                // Not a JSON event — likely a ping echo
            }
        };

        socket.onerror = (e) => {
            console.error('[Monitor] WS error', e);
            setWsStatus('error');
        };

        socket.onclose = (e) => {
            console.warn('[Monitor] WS disconnected. Code:', e.code, '— will reconnect in 4s');
            if (pingInterval.current) clearInterval(pingInterval.current);
            if (!isMounted.current) return;
            setWsStatus('error');
            reconnectTimer.current = setTimeout(() => {
                if (isMounted.current) {
                    // Re-fetch historical events after reconnect so list is never wiped
                    fetchRef.current?.();
                    connectWs();
                }
            }, 4000);
        };
    }, []);

    
    const fetchTelemetry = useCallback(async () => {
        try {
            const token = sessionStorage.getItem('token');
            if (!token) return;
            const res = await axios.get('/api/v1/superadmin/telemetry', {
                headers: { Authorization: `Bearer ${token}` }
            });
            if (isMounted.current) {
                setTelemetry(res.data);
            }
        } catch (err) {
            console.error("Failed to fetch telemetry", err);
        }
    }, []);

    useEffect(() => {
        isMounted.current = true;
        fetchHistoricalEvents();
        connectWs();
        fetchTelemetry();

        // Also poll REST API every 30s to catch any events that may have been missed
        const pollTimer = setInterval(fetchHistoricalEvents, 30000);
        // Poll telemetry every 5 seconds for visually active metrics
        const telemetryTimer = setInterval(fetchTelemetry, 5000);

        return () => {

            isMounted.current = false;
            if (ws.current) {
                ws.current.onclose = null;
                ws.current.close();
            }
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
            
            if (pingInterval.current) clearInterval(pingInterval.current);
            clearInterval(pollTimer);
            clearInterval(telemetryTimer);
        };
    }, [fetchHistoricalEvents, connectWs, fetchTelemetry]);

    const handleCloseNotification = () => setLiveNotification(null);

    const statusColor = wsStatus === 'live' ? 'success' : wsStatus === 'connecting' ? 'warning' : 'error';
    const statusLabel = wsStatus === 'live' ? 'Live' : wsStatus === 'connecting' ? 'Connecting...' : 'Reconnecting...';

    return (
        <Container maxWidth={false} sx={{ mt: 3, mb: 4 }}>
            {/* Header */}
            <Card sx={{ mb: 3, background: 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%)', color: 'white' }}>
                <CardContent sx={{ py: 2, px: 3 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <DashboardIcon sx={{ fontSize: 36, color: '#60a5fa' }} />
                            <Box>
                                <Typography variant="h5" fontWeight="bold" color="white">
                                    Real-Time System Monitor
                                </Typography>
                                <Typography variant="body2" sx={{ color: '#94a3b8' }}>
                                    Live event stream — all system activity
                                </Typography>
                            </Box>
                        </Box>

                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Chip
                                icon={<LiveIcon sx={{ fontSize: 10, animation: wsStatus === 'live' ? 'pulse 1.5s infinite' : 'none' }} />}
                                label={statusLabel}
                                color={statusColor}
                                size="small"
                                variant="filled"
                                sx={{ fontWeight: 'bold' }}
                            />
                            <Chip
                                label={`${events.length} events`}
                                color="primary"
                                size="small"
                                variant="outlined"
                                sx={{ color: 'white', borderColor: '#60a5fa' }}
                            />
                        </Box>
                    </Box>

                    {wsStatus === 'connecting' && (
                        <LinearProgress sx={{ mt: 1.5, borderRadius: 1, bgcolor: 'rgba(255,255,255,0.1)' }} />
                    )}
                </CardContent>
            </Card>

            
            {/* System Telemetry Dashboard */}
            {telemetry && (
                <Card sx={{ mb: 4, bgcolor: '#f8fafc', border: '1px solid #e2e8f0', boxShadow: 'none' }}>
                    <CardContent>
                        <Typography variant="h6" fontWeight="bold" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                            <ServerIcon /> Host / Infrastructure Health
                        </Typography>
                        <Grid container spacing={2}>
                            <Grid item xs={6} md={3} lg={2}>
                                <Paper sx={{ p: 2, textAlign: 'center', border: '1px solid #e2e8f0', boxShadow: 'none' }}>
                                    <CpuIcon sx={{ color: telemetry.cpu_usage_percent > 80 ? '#ef4444' : '#3b82f6', mb: 1 }} />
                                    <Typography variant="body2" color="textSecondary">CPU Usage</Typography>
                                    <Typography variant="h5" fontWeight="bold">
                                        {telemetry.cpu_usage_percent}%
                                    </Typography>
                                </Paper>
                            </Grid>
                            <Grid item xs={6} md={3} lg={2}>
                                <Paper sx={{ p: 2, textAlign: 'center', border: '1px solid #e2e8f0', boxShadow: 'none' }}>
                                    <RamIcon sx={{ color: telemetry.memory_usage_percent > 80 ? '#ef4444' : '#8b5cf6', mb: 1 }} />
                                    <Typography variant="body2" color="textSecondary">Memory</Typography>
                                    <Typography variant="h5" fontWeight="bold">
                                        {telemetry.memory_usage_percent}%
                                    </Typography>
                                </Paper>
                            </Grid>
                            <Grid item xs={6} md={3} lg={2}>
                                <Paper sx={{ p: 2, textAlign: 'center', border: '1px solid #e2e8f0', boxShadow: 'none' }}>
                                    <StorageIcon sx={{ color: telemetry.disk_usage_percent > 90 ? '#ef4444' : '#10b981', mb: 1 }} />
                                    <Typography variant="body2" color="textSecondary">Disk</Typography>
                                    <Typography variant="h5" fontWeight="bold">
                                        {telemetry.disk_usage_percent}%
                                    </Typography>
                                </Paper>
                            </Grid>
                            <Grid item xs={6} md={3} lg={2}>
                                <Paper sx={{ p: 2, textAlign: 'center', border: '1px solid #e2e8f0', boxShadow: 'none' }}>
                                    <DbIcon sx={{ color: telemetry.db_connection_status === 'online' ? '#10b981' : '#ef4444', mb: 1 }} />
                                    <Typography variant="body2" color="textSecondary">PostgreSQL</Typography>
                                    <Typography variant="h6" fontWeight="bold" sx={{ textTransform: 'uppercase' }}>
                                        {telemetry.db_connection_status}
                                    </Typography>
                                </Paper>
                            </Grid>
                            <Grid item xs={6} md={3} lg={2}>
                                <Paper sx={{ p: 2, textAlign: 'center', border: '1px solid #e2e8f0', boxShadow: 'none' }}>
                                    <ServerIcon sx={{ color: telemetry.redis_status === 'online' ? '#10b981' : '#ef4444', mb: 1 }} />
                                    <Typography variant="body2" color="textSecondary">Redis & Celery</Typography>
                                    <Typography variant="h6" fontWeight="bold">
                                        {telemetry.active_solver_jobs} Jobs
                                    </Typography>
                                </Paper>
                            </Grid>
                            <Grid item xs={6} md={3} lg={2}>
                                <Paper sx={{ p: 2, textAlign: 'center', border: '1px solid #e2e8f0', boxShadow: 'none' }}>
                                    <DashboardIcon sx={{ color: '#64748b', mb: 1 }} />
                                    <Typography variant="body2" color="textSecondary">Uptime</Typography>
                                    <Typography variant="h6" fontWeight="bold">
                                        {telemetry.system_uptime_hours}h
                                    </Typography>
                                </Paper>
                            </Grid>
                        </Grid>
                    </CardContent>
                </Card>
            )}

            {/* Main Grid Layout */}

            <Grid container spacing={3}>

                {/* Panel 1: Authentication — top left */}
                <Grid item xs={12} md={6}>
                    <MonitorWidget
                        title="Authentication & Security"
                        icon={<SecurityIcon sx={{ color: '#3b82f6' }} />}
                        events={events}
                        filterFn={(e) =>
                            e.event_type.startsWith('LOGIN') ||
                            e.event_type.startsWith('LOGOUT') ||
                            e.action === 'LOGIN' ||
                            e.action === 'LOGOUT'
                        }
                    />
                </Grid>

                {/* Panel 2: Bulk Uploads — top right */}
                <Grid item xs={12} md={6}>
                    <MonitorWidget
                        title="File Uploads & Imports"
                        icon={<UploadIcon sx={{ color: '#8b5cf6' }} />}
                        events={events}
                        filterFn={(e) =>
                            e.event_type.startsWith('BULK_UPLOAD') ||
                            e.event_type.startsWith('IMPORT') ||
                            e.action === 'IMPORT' ||
                            e.resource === 'timetable_import'
                        }
                    />
                </Grid>

                {/* Panel 3: AI Generation — bottom left */}
                <Grid item xs={12} md={6}>
                    <MonitorWidget
                        title="AI Engine Generations"
                        icon={<GenerateIcon sx={{ color: '#10b981' }} />}
                        events={events}
                        filterFn={(e) =>
                            e.event_type === 'GENERATE_TIMETABLE' ||
                            e.action === 'GENERATE' ||
                            e.resource === 'timetable_generation'
                        }
                    />
                </Grid>

                {/* Panel 4: Views & Exports — bottom right */}
                <Grid item xs={12} md={6}>
                    <MonitorWidget
                        title="Active Views & Exports"
                        icon={<ViewIcon sx={{ color: '#f59e0b' }} />}
                        events={events}
                        filterFn={(e) =>
                            e.event_type === 'VIEW_TIMETABLE' ||
                            e.event_type === 'EXPORT_TIMETABLE' ||
                            e.action === 'VIEW' ||
                            e.action === 'EXPORT'
                        }
                    />
                </Grid>

            </Grid>

            <Grid container spacing={3} sx={{ mt: 0 }}>
                {/* Panel 5: Data Modifications (CRUD) */}
                <Grid item xs={12} md={6}>
                    <MonitorWidget
                        title="Data Modifications"
                        icon={<StorageIcon sx={{ color: '#ec4899' }} />}
                        events={events}
                        filterFn={(e) =>
                            e.event_type.startsWith('CREATE_') ||
                            e.event_type.startsWith('UPDATE_') ||
                            e.event_type.startsWith('DELETE_') ||
                            ['CREATE', 'UPDATE', 'DELETE', 'BLOCKED', 'UNBLOCKED'].includes(e.action)
                        }
                    />
                </Grid>

                {/* Panel 6: System Errors & Anomalies */}
                <Grid item xs={12} md={6}>
                    <MonitorWidget
                        title="System Errors & Anomalies"
                        icon={<WarningIcon sx={{ color: '#ef4444' }} />}
                        events={events}
                        filterFn={(e) =>
                            e.event_type === 'SYSTEM_ERROR' ||
                            !e.success ||
                            e.action === 'ERROR'
                        }
                    />
                </Grid>
            </Grid>

            {/* Live Pop-Up Alert */}
            <Snackbar
                open={Boolean(liveNotification)}
                autoHideDuration={4000}
                onClose={handleCloseNotification}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            >
                {liveNotification ? (
                    <Alert
                        onClose={handleCloseNotification}
                        severity={liveNotification.success ? 'success' : 'error'}
                        variant="filled"
                        sx={{ width: '100%', boxShadow: 6 }}
                    >
                        <strong>{liveNotification.event_type}</strong>
                        {' — '}
                        {liveNotification.username || 'System'}
                        {' '}
                        {liveNotification.success ? 'succeeded' : 'failed'}
                    </Alert>
                ) : <Box />}
            </Snackbar>

        </Container>
    );
};

export default SystemMonitorPage;
