import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  CircularProgress,
  Grid,
  LinearProgress,
  Typography,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  AccountBalanceWallet as WalletIcon,
  ArrowUpward as ArrowUpwardIcon,
  CalendarMonth as CalendarIcon,
  ContactSupport as ContactSupportIcon,
  People as PeopleIcon,
  Storage as StorageIcon,
} from '@mui/icons-material';
import api from '../api';
import {
  HeroButton,
  HeroGhostButton,
  InsightCard,
  MetricCard,
  StatusBadge,
  TenantPageHero,
} from '../components/tenant/TenantAdminUI';
import { useBranding } from '../contexts/BrandingContext';

interface UsageSummaryMetric {
  metric_key: string;
  total: number;
  limit: number | null;
  percent: number | null;
  status: string;
}

interface UsageSummaryResponse {
  tenant_id: number;
  period: string;
  metrics: UsageSummaryMetric[];
}

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
}

const BillingUsagePage: React.FC = () => {
  const { branding } = useBranding();
  const primaryColor = branding.primary_color || '#1976d2';
  const secondaryColor = branding.secondary_color || '#9c27b0';

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<UsageSummaryResponse | null>(null);
  const [observability, setObservability] = useState<ObservabilityResponse | null>(null);

  useEffect(() => {
    const fetchUsage = async () => {
      try {
        setLoading(true);
        const [summaryResponse, observabilityResponse] = await Promise.all([
          api.get('/usage/summary'),
          api.get('/usage/observability'),
        ]);
        setSummary(summaryResponse.data);
        setObservability(observabilityResponse.data);
        setError(null);
      } catch (err: any) {
        console.error('Failed to fetch usage summary:', err);
        setError(err.response?.data?.detail || 'Failed to load usage data. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    void fetchUsage();
  }, []);

  const getMetricIcon = (key: string) => {
    switch (key) {
      case 'seats_active':
        return <PeopleIcon />;
      case 'timetable_generations':
        return <CalendarIcon />;
      case 'storage_bytes':
        return <StorageIcon />;
      default:
        return <ArrowUpwardIcon />;
    }
  };

  const formatMetricName = (key: string) => key.split('_').map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');

  const formatValue = (key: string, value: number) => {
    if (key === 'storage_bytes') {
      return `${(value / (1024 * 1024)).toFixed(2)} MB`;
    }
    return value.toLocaleString();
  };

  const formatDuration = (value?: number | null) => {
    if (!value) return 'n/a';
    if (value >= 60000) return `${(value / 60000).toFixed(1)} min`;
    return `${(value / 1000).toFixed(1)} sec`;
  };

  const getStatusTone = (status: string) => {
    switch (status) {
      case 'exceeded':
        return 'danger' as const;
      case 'warning':
        return 'warning' as const;
      case 'ok':
        return 'success' as const;
      default:
        return 'default' as const;
    }
  };

  if (loading) {
    return (
      <Box sx={{ minHeight: '60vh', display: 'grid', placeItems: 'center' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  if (!summary) {
    return <Alert severity="info">No usage data available at this time.</Alert>;
  }

  // Rich shell background so glass cards are visible against something dark/colourful
  const shellBg = [
    `radial-gradient(ellipse at 0% 0%, ${alpha(primaryColor, 0.22)} 0%, transparent 38%)`,
    `radial-gradient(ellipse at 100% 100%, ${alpha(secondaryColor, 0.18)} 0%, transparent 38%)`,
    'linear-gradient(160deg, #0f172a 0%, #1e293b 55%, #0f172a 100%)',
  ].join(', ');

  return (
    <Box
      sx={{
        background: shellBg,
        borderRadius: 5,
        p: { xs: 2, sm: 3 },
        minHeight: '80vh',
      }}
    >
      <TenantPageHero
        title="Billing & Usage"
        description="Track plan consumption, generation reliability, and resource pressure without losing the branded identity of the tenant-admin suite."
        eyebrow="Commercial Operations"
        icon={<WalletIcon />}
        primaryColor={primaryColor}
        secondaryColor={secondaryColor}
        meta={(
          <>
            <StatusBadge label={(branding.plan_tier || 'Free').toUpperCase()} tone="success" subtle />
            <Typography variant="body2" sx={{ color: '#fff' }}>Current period: {summary.period}</Typography>
          </>
        )}
        actions={(
          <>
            <HeroButton
              startIcon={<ArrowUpwardIcon />}
              onClick={() => { window.location.href = `mailto:support@tablesys.cloud?subject=Upgrade Plan for ${branding.domain}`; }}
            >
              Upgrade Plan
            </HeroButton>
            <HeroGhostButton
              startIcon={<ContactSupportIcon />}
              onClick={() => { window.location.href = `mailto:support@tablesys.cloud?subject=Billing Inquiry for ${branding.domain}`; }}
            >
              Contact Support
            </HeroGhostButton>
          </>
        )}
      />

      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        {summary.metrics.map((metric) => (
          <Grid item xs={12} md={6} lg={4} key={metric.metric_key}>
            <MetricCard
              label={formatMetricName(metric.metric_key)}
              value={formatValue(metric.metric_key, metric.total)}
              helper={metric.limit ? `of ${formatValue(metric.metric_key, metric.limit)}` : 'Unlimited or unmetered'}
              icon={getMetricIcon(metric.metric_key)}
              tone={getStatusTone(metric.status)}
              primaryColor={primaryColor}
              secondaryColor={secondaryColor}
            />
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} lg={7}>
          <InsightCard
            title={`Usage detail for ${summary.period}`}
            description="Each usage line stays branded, but the actual capacity reading is kept calm and readable."
            icon={<StorageIcon />}
            dark
            primaryColor={primaryColor}
            secondaryColor={secondaryColor}
          >
            <Box sx={{ display: 'grid', gap: 2 }}>
              {summary.metrics.map((metric) => (
                <Box key={metric.metric_key}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 2, mb: 0.75 }}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 800, color: 'rgba(255,255,255,0.92)' }}>{formatMetricName(metric.metric_key)}</Typography>
                    <StatusBadge label={metric.status.toUpperCase()} tone={getStatusTone(metric.status)} subtle />
                  </Box>
                  <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.58)', mb: 0.75 }}>
                    {formatValue(metric.metric_key, metric.total)}
                    {metric.limit ? ` of ${formatValue(metric.metric_key, metric.limit)}` : ' in an unmetered bucket'}
                  </Typography>
                  {metric.limit && metric.percent !== null ? (
                    <LinearProgress
                      variant="determinate"
                      value={Math.min(metric.percent, 100)}
                      sx={{
                        height: 10,
                        borderRadius: 999,
                        bgcolor: 'rgba(255,255,255,0.08)',
                        '& .MuiLinearProgress-bar': {
                          borderRadius: 999,
                          background: `linear-gradient(90deg, ${primaryColor}, ${secondaryColor})`,
                        },
                      }}
                    />
                  ) : (
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.48)' }}>Unlimited</Typography>
                  )}
                </Box>
              ))}
            </Box>
          </InsightCard>
        </Grid>

        <Grid item xs={12} lg={5}>
          <InsightCard
            title="Generation Health"
            description="Observability for timetable creation during the current period."
            icon={<CalendarIcon />}
            badge={observability ? <StatusBadge label={`${observability.generation.success_rate_percent.toFixed(1)}% success`} tone="success" subtle /> : undefined}
            dark
            primaryColor={primaryColor}
            secondaryColor={secondaryColor}
          >
            {observability && (
              <Grid container spacing={2}>
                {[
                  { label: 'Attempts', value: observability.generation.attempts },
                  { label: 'Average Duration', value: formatDuration(observability.generation.average_duration_ms) },
                  { label: 'Fallback Runs', value: observability.generation.fallback_runs },
                  { label: 'Draft Timetables', value: observability.generation.draft_timetables },
                ].map((item) => (
                  <Grid item xs={6} key={item.label}>
                    <Box sx={{
                      p: 2,
                      borderRadius: 3,
                      background: `linear-gradient(135deg, ${alpha(primaryColor, 0.18)}, ${alpha(secondaryColor, 0.12)})`,
                      border: `1px solid ${alpha('#fff', 0.1)}`,
                    }}>
                      <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', fontWeight: 700 }}>{item.label}</Typography>
                      <Typography variant="h5" sx={{ fontWeight: 900, mt: 0.5, color: '#fff' }}>{item.value}</Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>
            )}
          </InsightCard>
        </Grid>
      </Grid>

      {observability && (
        <Grid container spacing={3} sx={{ mt: 0.5 }}>
          {observability.generation.recent_runs.map((run) => (
            <Grid item xs={12} md={6} key={`${run.timetable_id}-${run.completed_at || run.started_at || run.status}`}>
              <InsightCard
                title={run.timetable_name}
                description={`Duration ${formatDuration(run.duration_ms)} • Saved slots ${run.saved_slot_count}`}
                badge={<StatusBadge label={run.status.toUpperCase()} tone={run.status === 'success' ? 'success' : run.status === 'running' ? 'warning' : 'danger'} subtle />}
                dark
                primaryColor={primaryColor}
                secondaryColor={secondaryColor}
              >
                <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.62)' }}>
                  Fallback used: {run.fallback_used ? 'Yes' : 'No'}
                </Typography>
                {run.completed_at && (
                  <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.5)', mt: 0.5 }}>
                    Completed: {new Date(run.completed_at).toLocaleString()}
                  </Typography>
                )}
                {run.error_message && (
                  <Alert severity="warning" sx={{ mt: 1.5 }}>
                    {run.error_message}
                  </Alert>
                )}
              </InsightCard>
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );
};

export default BillingUsagePage;
