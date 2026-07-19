import React, { useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Container,
    Divider,
    Grid,
    Stack,
    Typography,
    Tabs,
    Tab,
} from '@mui/material';
import {
    AutoGraph as AutoGraphIcon,
    Bolt as BoltIcon,
    CheckCircle as CheckCircleIcon,
    ErrorOutline as ErrorOutlineIcon,
    Schedule as ScheduleIcon,
    Speed as SpeedIcon,
    WarningAmber as WarningAmberIcon,
    Assessment as AssessmentIcon,
    HealthAndSafety as HealthAndSafetyIcon,
} from '@mui/icons-material';
import api from '../api';
import { useAuth } from '../contexts/AuthContext';
import { useBranding } from '../contexts/BrandingContext';
import TimetableAnalytics from '../components/TimetableAnalytics';

interface ObservabilityRun {
    timetable_id: number;
    timetable_name: string;
    status: string;
    started_at?: string | null;
    completed_at?: string | null;
    duration_ms?: number | null;
    saved_slot_count: number;
    fallback_used: boolean;
    solver_status_by_level: Record<string, string>;
    error_message?: string | null;
}

interface ObservabilityEndpoint {
    endpoint: string;
    count: number;
    status_codes: number[];
}

interface ObservabilityResponse {
    tenant_id: number;
    period: string;
    generation: {
        attempts: number;
        successes: number;
        failures: number;
        success_rate_percent: number;
        average_duration_ms?: number | null;
        total_duration_ms: number;
        fallback_runs: number;
        timeout_runs: number;
        generated_timetables: number;
        draft_timetables: number;
        last_completed_at?: string | null;
        recent_runs: ObservabilityRun[];
    };
    api: {
        requests: number;
        avg_response_ms?: number | null;
        server_errors: number;
        client_errors: number;
        total_errors: number;
        error_rate_percent: number;
        sla_target_ms: number;
        sla_breaches: number;
        sla_compliance_percent: number;
        top_failure_endpoints: ObservabilityEndpoint[];
    };
}

const EMPTY_OBSERVABILITY: ObservabilityResponse = {
    tenant_id: 0,
    period: 'Current window',
    generation: {
        attempts: 0,
        successes: 0,
        failures: 0,
        success_rate_percent: 0,
        average_duration_ms: null,
        total_duration_ms: 0,
        fallback_runs: 0,
        timeout_runs: 0,
        generated_timetables: 0,
        draft_timetables: 0,
        last_completed_at: null,
        recent_runs: [],
    },
    api: {
        requests: 0,
        avg_response_ms: null,
        server_errors: 0,
        client_errors: 0,
        total_errors: 0,
        error_rate_percent: 0,
        sla_target_ms: 2500,
        sla_breaches: 0,
        sla_compliance_percent: 100,
        top_failure_endpoints: [],
    },
};

const formatDuration = (value?: number | null) => {
    if (!value) return 'n/a';
    if (value >= 60000) return `${(value / 60000).toFixed(1)} min`;
    return `${(value / 1000).toFixed(1)} sec`;
};

const normalizeObservability = (raw: Partial<ObservabilityResponse> | null | undefined): ObservabilityResponse => ({
    tenant_id: raw?.tenant_id ?? EMPTY_OBSERVABILITY.tenant_id,
    period: raw?.period ?? EMPTY_OBSERVABILITY.period,
    generation: {
        attempts: raw?.generation?.attempts ?? 0,
        successes: raw?.generation?.successes ?? 0,
        failures: raw?.generation?.failures ?? 0,
        success_rate_percent: raw?.generation?.success_rate_percent ?? 0,
        average_duration_ms: raw?.generation?.average_duration_ms ?? null,
        total_duration_ms: raw?.generation?.total_duration_ms ?? 0,
        fallback_runs: raw?.generation?.fallback_runs ?? 0,
        timeout_runs: raw?.generation?.timeout_runs ?? 0,
        generated_timetables: raw?.generation?.generated_timetables ?? 0,
        draft_timetables: raw?.generation?.draft_timetables ?? 0,
        last_completed_at: raw?.generation?.last_completed_at ?? null,
        recent_runs: Array.isArray(raw?.generation?.recent_runs) ? raw!.generation!.recent_runs : [],
    },
    api: {
        requests: raw?.api?.requests ?? 0,
        avg_response_ms: raw?.api?.avg_response_ms ?? null,
        server_errors: raw?.api?.server_errors ?? 0,
        client_errors: raw?.api?.client_errors ?? 0,
        total_errors: raw?.api?.total_errors ?? 0,
        error_rate_percent: raw?.api?.error_rate_percent ?? 0,
        sla_target_ms: raw?.api?.sla_target_ms ?? 2500,
        sla_breaches: raw?.api?.sla_breaches ?? 0,
        sla_compliance_percent: raw?.api?.sla_compliance_percent ?? 100,
        top_failure_endpoints: Array.isArray(raw?.api?.top_failure_endpoints) ? raw!.api!.top_failure_endpoints : [],
    },
});

const formatHealthTone = (observability: ObservabilityResponse) => {
    const { api, generation } = observability;
    if (api.error_rate_percent > 5 || api.sla_compliance_percent < 95 || generation.success_rate_percent < 80) {
        return {
            label: 'Needs Attention',
            color: '#d32f2f',
            bg: 'rgba(211, 47, 47, 0.10)',
        };
    }
    if (api.error_rate_percent > 2 || api.sla_compliance_percent < 98 || generation.fallback_runs > 0) {
        return {
            label: 'Watch Closely',
            color: '#ed6c02',
            bg: 'rgba(237, 108, 2, 0.10)',
        };
    }
    return {
        label: 'Healthy',
        color: '#2e7d32',
        bg: 'rgba(46, 125, 50, 0.10)',
    };
};

const LiveClock: React.FC<{ color?: string }> = ({ color = '#ffffff' }) => {
    const [time, setTime] = useState(new Date());
    useEffect(() => {
        const id = setInterval(() => setTime(new Date()), 1000);
        return () => clearInterval(id);
    }, []);
    return (
        <Typography
            fontWeight={800}
            fontFamily="monospace"
            sx={{
                fontSize: { xs: '2.6rem', md: '3.6rem' },
                letterSpacing: 6,
                color,
                lineHeight: 1,
                textShadow: '0 2px 24px rgba(0,0,0,0.20)',
            }}
        >
            {time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </Typography>
    );
};

const AnalyticsPage: React.FC = () => {
    const { branding } = useBranding();
    const { isTenantAdmin, isSuperadmin } = useAuth();
    const canViewTenantHealth = isTenantAdmin || isSuperadmin;
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [observability, setObservability] = useState<ObservabilityResponse | null>(null);
    const [activeTab, setActiveTab] = useState(0);

    useEffect(() => {
        const fetchObservability = async () => {
            if (!canViewTenantHealth) {
                setLoading(false);
                return;
            }
            try {
                setLoading(true);
                const response = await api.get('/usage/observability');
                setObservability(normalizeObservability(response.data));
                setError(null);
            } catch (err: any) {
                console.error('Failed to load tenant analytics observability:', err);
                setError(err.response?.data?.detail || 'Failed to load tenant health metrics.');
            } finally {
                setLoading(false);
            }
        };

        fetchObservability();
    }, [canViewTenantHealth]);

    const safeObservability = useMemo(
        () => normalizeObservability(observability),
        [observability]
    );

    const healthTone = useMemo(
        () => formatHealthTone(safeObservability),
        [safeObservability]
    );

    if (loading) {
        return (
            <Box sx={{ p: 3, display: 'flex', justifyContent: 'center', minHeight: '60vh', alignItems: 'center' }}>
                <CircularProgress />
            </Box>
        );
    }

    if (error) {
        return (
            <Container maxWidth={false} sx={{ mt: 3, mb: 4 }}>
                <Alert severity="error">{error}</Alert>
            </Container>
        );
    }

    const primaryColor = branding?.primary_color || '#1565c0';

    return (
        <Container maxWidth={false} sx={{ mt: 3, mb: 4 }}>
            {healthTone && (
                <Box sx={{ mb: 4 }}>
                    <Box
                        sx={{
                            position: 'relative',
                            borderRadius: 4,
                            overflow: 'hidden',
                            background: `linear-gradient(135deg, ${primaryColor} 0%, #1976d2 55%, #9c27b0 100%)`,
                            boxShadow: `0 12px 40px ${primaryColor}55`,
                            minHeight: { xs: 200, md: 240 },
                            display: 'flex',
                            alignItems: 'center',
                            px: { xs: 3, md: 5 },
                            py: 3,
                            mb: 3,
                        }}
                    >
                        <Box sx={{ position: 'absolute', top: -60,  left: -60,   width: 260, height: 260, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.06)', pointerEvents: 'none' }} />
                        <Box sx={{ position: 'absolute', bottom: -80, right: 140, width: 220, height: 220, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.04)', pointerEvents: 'none' }} />
                        <Box sx={{ position: 'absolute', top: 20,  right: '34%', width: 80,  height: 80,  borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.06)', pointerEvents: 'none' }} />

                        <Grid container alignItems="center" sx={{ width: '100%', position: 'relative', zIndex: 1 }}>
                            <Grid item xs={12} md={5}>
                                <Chip
                                    icon={<CheckCircleIcon sx={{ color: `${healthTone.color} !important`, fontSize: '16px !important' }} />}
                                    label={`System Status: ${healthTone.label}`}
                                    size="small"
                                    sx={{ bgcolor: '#fff', color: healthTone.color, fontWeight: 700, mb: 2, fontSize: '0.75rem', px: 0.5 }}
                                />
                                <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 1 }}>
                                    <Typography variant="h4" fontWeight={900} sx={{ color: '#fff', lineHeight: 1.15 }}>
                                        {canViewTenantHealth ? 'Tenant Health & Analytics' : 'School Timetable Analytics'}
                                    </Typography>
                                </Stack>
                                <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.78)', maxWidth: 380, lineHeight: 1.7 }}>
                                    {canViewTenantHealth
                                        ? 'Monitor timetable analytics and system health metrics for your institution.'
                                        : 'Review timetable analytics for your school.'}
                                </Typography>
                            </Grid>
                            <Grid item xs={12} md={7} sx={{ display: 'flex', flexDirection: 'column', alignItems: { xs: 'flex-start', md: 'center' }, mt: { xs: 3, md: 0 } }}>
                                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.55)', letterSpacing: 4, textTransform: 'uppercase', mb: 1.5 }}>
                                    Current Time
                                </Typography>
                                <LiveClock color="#ffffff" />
                                <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.50)', mt: 1.5, letterSpacing: 0.5 }}>
                                    {new Date().toLocaleDateString([], { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                                </Typography>
                            </Grid>
                        </Grid>
                    </Box>

                    <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
                        <Tabs value={activeTab} onChange={(e, val) => setActiveTab(val)} aria-label="analytics tabs">
                            <Tab icon={<AssessmentIcon />} iconPosition="start" label="Timetable Analytics" sx={{ fontWeight: 600, minHeight: 64 }} />
                            {canViewTenantHealth && <Tab icon={<HealthAndSafetyIcon />} iconPosition="start" label="System Health Analytics" sx={{ fontWeight: 600, minHeight: 64 }} />}
                        </Tabs>
                    </Box>

                    {activeTab === 1 && (
                        <Box>
                            <Grid container spacing={2.5} sx={{ mb: 3 }}>
                        {[
                            {
                                label: 'API Avg Response',
                                value: safeObservability.api.avg_response_ms ? `${safeObservability.api.avg_response_ms.toFixed(0)} ms` : 'n/a',
                                helper: `${safeObservability.api.requests.toLocaleString()} requests this period`,
                                icon: <SpeedIcon sx={{ color: '#1565c0' }} />,
                                tone: '#1565c0',
                                bg: 'rgba(21, 101, 192, 0.08)',
                            },
                            {
                                label: 'API Error Rate',
                                value: `${safeObservability.api.error_rate_percent.toFixed(2)}%`,
                                helper: `${safeObservability.api.total_errors} total errors`,
                                icon: <ErrorOutlineIcon sx={{ color: '#d32f2f' }} />,
                                tone: '#d32f2f',
                                bg: 'rgba(211, 47, 47, 0.08)',
                            },
                            {
                                label: 'SLA Compliance',
                                value: `${safeObservability.api.sla_compliance_percent.toFixed(1)}%`,
                                helper: `${safeObservability.api.sla_breaches} breaches`,
                                icon: <CheckCircleIcon sx={{ color: '#2e7d32' }} />,
                                tone: '#2e7d32',
                                bg: 'rgba(46, 125, 50, 0.08)',
                            },
                            {
                                label: 'Generation Success',
                                value: `${safeObservability.generation.success_rate_percent.toFixed(1)}%`,
                                helper: `${safeObservability.generation.successes} of ${safeObservability.generation.attempts} runs`,
                                icon: <BoltIcon sx={{ color: '#6a1b9a' }} />,
                                tone: '#6a1b9a',
                                bg: 'rgba(106, 27, 154, 0.08)',
                            },
                            {
                                label: 'Generation Duration',
                                value: formatDuration(safeObservability.generation.average_duration_ms),
                                helper: `${safeObservability.generation.timeout_runs} timeout-like runs`,
                                icon: <ScheduleIcon sx={{ color: '#ed6c02' }} />,
                                tone: '#ed6c02',
                                bg: 'rgba(237, 108, 2, 0.08)',
                            },
                            {
                                label: 'Fallback Runs',
                                value: safeObservability.generation.fallback_runs.toLocaleString(),
                                helper: `${safeObservability.generation.generated_timetables} generated timetables`,
                                icon: <WarningAmberIcon sx={{ color: '#ad6800' }} />,
                                tone: '#ad6800',
                                bg: 'rgba(173, 104, 0, 0.08)',
                            },
                        ].map((item) => (
                            <Grid item xs={12} sm={6} lg={4} key={item.label}>
                                <Card sx={{ height: '100%', borderRadius: 3, boxShadow: '0 10px 24px rgba(15, 23, 42, 0.08)' }}>
                                    <CardContent sx={{ p: 2.5 }}>
                                        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 2 }}>
                                            <Box>
                                                <Typography variant="body2" sx={{ color: 'text.secondary', mb: 0.5 }}>
                                                    {item.label}
                                                </Typography>
                                                <Typography variant="h4" sx={{ fontWeight: 800, color: 'text.primary' }}>
                                                    {item.value}
                                                </Typography>
                                            </Box>
                                            <Box sx={{ bgcolor: item.bg, borderRadius: 2, p: 1 }}>
                                                {item.icon}
                                            </Box>
                                        </Stack>
                                        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                                            {item.helper}
                                        </Typography>
                                    </CardContent>
                                </Card>
                            </Grid>
                        ))}
                    </Grid>

                    <Grid container spacing={2.5} sx={{ mb: 4 }}>
                        <Grid item xs={12} lg={7}>
                            <Card sx={{ borderRadius: 3, height: '100%', boxShadow: '0 10px 24px rgba(15, 23, 42, 0.08)' }}>
                                <CardContent sx={{ p: 3 }}>
                                    <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.75 }}>
                                        Recent Generation Runs
                                    </Typography>
                                    <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2.5 }}>
                                        Recent timetable generation outcomes for this tenant, including failures, durations, and fallback signals.
                                    </Typography>
                                    <Stack spacing={1.5}>
                                        {safeObservability.generation.recent_runs.length > 0 ? safeObservability.generation.recent_runs.map((run) => (
                                            <Box
                                                key={`${run.timetable_id}-${run.completed_at || run.started_at || run.status}`}
                                                sx={{
                                                    border: '1px solid rgba(15, 23, 42, 0.08)',
                                                    borderRadius: 2.5,
                                                    p: 2,
                                                    bgcolor: run.status === 'completed' ? '#f8fbff' : '#fff8f7',
                                                }}
                                            >
                                                <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" spacing={1.5}>
                                                    <Box>
                                                        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                                                            {run.timetable_name}
                                                        </Typography>
                                                        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                                                            {run.completed_at
                                                                ? `Completed ${new Date(run.completed_at).toLocaleString()}`
                                                                : run.started_at
                                                                    ? `Started ${new Date(run.started_at).toLocaleString()}`
                                                                    : 'Run time unavailable'}
                                                        </Typography>
                                                    </Box>
                                                    <Stack direction="row" spacing={1} flexWrap="wrap">
                                                        <Chip
                                                            size="small"
                                                            label={run.status.replace(/_/g, ' ')}
                                                            color={run.status === 'completed' ? 'success' : run.status === 'failed' ? 'error' : 'warning'}
                                                        />
                                                        {run.fallback_used && <Chip size="small" label="Fallback used" color="warning" variant="outlined" />}
                                                    </Stack>
                                                </Stack>
                                                <Stack direction="row" spacing={2} flexWrap="wrap" sx={{ mt: 1.5 }}>
                                                    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                                                        Duration: <strong>{formatDuration(run.duration_ms)}</strong>
                                                    </Typography>
                                                    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                                                        Slots saved: <strong>{run.saved_slot_count}</strong>
                                                    </Typography>
                                                </Stack>
                                                {run.error_message && (
                                                    <Alert severity="warning" sx={{ mt: 1.5, borderRadius: 2 }}>
                                                        {run.error_message}
                                                    </Alert>
                                                )}
                                            </Box>
                                        )) : (
                                            <Alert severity="info">No generation runs have been recorded for this period yet.</Alert>
                                        )}
                                    </Stack>
                                </CardContent>
                            </Card>
                        </Grid>

                        <Grid item xs={12} lg={5}>
                            <Card sx={{ borderRadius: 3, height: '100%', boxShadow: '0 10px 24px rgba(15, 23, 42, 0.08)' }}>
                                <CardContent sx={{ p: 3 }}>
                                    <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.75 }}>
                                        API Reliability Snapshot
                                    </Typography>
                                    <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2.5 }}>
                                        This shows where tenant-facing API problems are concentrating, so the tenant admin can spot recurring failures quickly.
                                    </Typography>

                                    <Stack spacing={2}>
                                        <Box sx={{ p: 2, borderRadius: 2.5, bgcolor: healthTone.bg }}>
                                            <Typography variant="subtitle2" sx={{ fontWeight: 700, color: healthTone.color, mb: 0.5 }}>
                                                Current tenant health
                                            </Typography>
                                            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                                                {safeObservability.api.total_errors} errors across {safeObservability.api.requests.toLocaleString()} requests.
                                                {` `}
                                                SLA compliance is {safeObservability.api.sla_compliance_percent.toFixed(1)}% with a target of {safeObservability.api.sla_target_ms.toLocaleString()} ms.
                                            </Typography>
                                        </Box>

                                        <Divider />

                                        <Box>
                                            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
                                                Top failure endpoints
                                            </Typography>
                                            <Stack spacing={1.25}>
                                                {safeObservability.api.top_failure_endpoints.length > 0 ? safeObservability.api.top_failure_endpoints.map((endpoint) => (
                                                    <Box
                                                        key={endpoint.endpoint}
                                                        sx={{
                                                            border: '1px solid rgba(15, 23, 42, 0.08)',
                                                            borderRadius: 2,
                                                            p: 1.75,
                                                        }}
                                                    >
                                                        <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5 }}>
                                                            {endpoint.endpoint}
                                                        </Typography>
                                                        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                                                            {endpoint.count} failures
                                                            {endpoint.status_codes.length > 0 ? ` • status codes: ${endpoint.status_codes.join(', ')}` : ''}
                                                        </Typography>
                                                    </Box>
                                                )) : (
                                                    <Alert severity="success">No error hotspots detected for this tenant in the current window.</Alert>
                                                )}
                                            </Stack>
                                        </Box>
                                    </Stack>
                                </CardContent>
                            </Card>
                        </Grid>
                    </Grid>

                            {safeObservability.api.requests === 0 && safeObservability.generation.attempts === 0 && (
                                <Alert severity="info" sx={{ mb: 3 }}>
                                    Tenant health metrics will populate as new API traffic and timetable generations occur.
                                </Alert>
                            )}
                        </Box>
                    )}
                </Box>
            )}

            {activeTab === 0 && (
                <TimetableAnalytics />
            )}
        </Container>
    );
};

export default AnalyticsPage;
