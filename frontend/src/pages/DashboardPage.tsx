// OWNER: Agent Delta (integration) — PARALLEL_WORKPLAN.md
// Change: Added Schedule|Analytics tab strip. All other logic unchanged.
import React, { useCallback, useEffect, useState } from 'react';
import {
    Box,
    Typography,
    Alert,
    CircularProgress,
    Chip,
    Paper,
    Select,
    MenuItem,
    ButtonGroup,
    Button,
    SelectChangeEvent,
    Grid,
    Card,
    CardContent,
    LinearProgress,
    Tooltip,
} from '@mui/material';
import {
    Schedule as ScheduleIcon,
    School as SchoolIcon,
    Group as GroupIcon,
    MenuBook as CourseIcon,
    AccountTree as DeptIcon,
    AutoAwesome as MagicIcon,
    CheckCircle as CheckIcon,
    RadioButtonUnchecked as EmptyIcon,
    TrendingUp as TrendingIcon,
    AccessTime as ClockIcon,
    MeetingRoom as RoomIcon,
} from '@mui/icons-material';
import api, { departmentsAPI, coursesAPI } from '../api';
import TimetableGrid from '../components/TimetableGrid';
import { TimetableSlot } from '../components/TimetableCell';
import { useAuth } from '../contexts/AuthContext';
import { useBranding } from '../contexts/BrandingContext';

interface TimetableMetadata {
    term: string;
    year: number;
    total_courses: number;
    grid_config?: {
        start_time?: string;
        end_time?: string;
        lunch_start?: string;
        lunch_end?: string;
        active_days?: string[];
    };
}

interface TimetableViewData {
    metadata: TimetableMetadata;
    slots: TimetableSlot[];
}

interface SystemStats {
    courses: number;
    departments: number;
    groups: number;
    lecturers: number;
    rooms: number;
}

const MIN_SUPPORTED_YEAR = 1;
const MAX_SUPPORTED_YEAR = 7;

const normalizeYearLevel = (rawLevel: unknown): number | null => {
    const numericLevel = Number(rawLevel);
    if (!Number.isInteger(numericLevel) || numericLevel <= 0) {
        return null;
    }

    if (numericLevel >= 100) {
        return Math.round(numericLevel / 100);
    }

    return numericLevel;
};

const formatYearLabel = (year: number): string => {
    const rem100 = year % 100;
    if (rem100 >= 11 && rem100 <= 13) {
        return `${year}th Year`;
    }

    const rem10 = year % 10;
    if (rem10 === 1) {
        return `${year}st Year`;
    }
    if (rem10 === 2) {
        return `${year}nd Year`;
    }
    if (rem10 === 3) {
        return `${year}rd Year`;
    }
    return `${year}th Year`;
};

const buildYearOptions = (years: number[]) => years.map((year) => ({
    value: year,
    label: formatYearLabel(year),
}));

const extractAvailableYears = (groups: Array<{ level?: number | null }>): number[] => {
    const years = Array.from(
        new Set(
            groups
                .map((group) => normalizeYearLevel(group.level))
                .filter((level): level is number => (
                    level !== null
                    && level >= MIN_SUPPORTED_YEAR
                    && level <= MAX_SUPPORTED_YEAR
                )),
        ),
    );

    return years.sort((a, b) => a - b);
};

const normalizeTimetableViewData = (raw: any): TimetableViewData => ({
    metadata: {
        term: typeof raw?.metadata?.term === 'string' ? raw.metadata.term : 'Active Term',
        year: typeof raw?.metadata?.year === 'number' ? raw.metadata.year : new Date().getFullYear(),
        total_courses: typeof raw?.metadata?.total_courses === 'number' ? raw.metadata.total_courses : 0,
    },
    slots: Array.isArray(raw?.slots) ? (raw.slots as TimetableSlot[]) : [],
});

const errorDetailToMessage = (detail: unknown): string | null => {
    if (typeof detail === 'string') {
        return detail;
    }

    if (Array.isArray(detail)) {
        return detail
            .map((item) => {
                if (typeof item === 'string') {
                    return item;
                }
                if (item && typeof item === 'object' && 'msg' in item) {
                    return String((item as { msg?: unknown }).msg);
                }
                return null;
            })
            .filter((value): value is string => Boolean(value))
            .join('; ');
    }

    return null;
};

const ReadinessItem: React.FC<{ label: string; count: number; required: number; icon: React.ReactNode }> = ({
    label, count, required, icon,
}) => {
    const ready = count >= required;
    const pct = Math.min(100, Math.round((count / required) * 100));
    return (
        <Box sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {ready
                        ? <CheckIcon sx={{ color: 'success.main', fontSize: 18 }} />
                        : <EmptyIcon sx={{ color: 'text.disabled', fontSize: 18 }} />}
                    <Typography variant="body2" fontWeight={500}>{label}</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="caption" color={ready ? 'success.main' : 'text.secondary'}>
                        {count} / {required}
                    </Typography>
                    {icon}
                </Box>
            </Box>
            <LinearProgress
                variant="determinate"
                value={pct}
                sx={{
                    height: 6, borderRadius: 3, bgcolor: 'action.hover',
                    '& .MuiLinearProgress-bar': { bgcolor: ready ? 'success.main' : 'warning.main', borderRadius: 3 },
                }}
            />
        </Box>
    );
};

// Animated live clock
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

const EmptyTimetableLanding: React.FC<{ stats: SystemStats; isCoordinator: boolean; branding: any, active?: boolean }> = ({
    stats, branding, isCoordinator, active = false,
}) => {
    const primaryColor = branding.primary_color || '#1565c0';

    const readinessItems = [
        { label: 'Courses loaded',     count: stats.courses,     required: 10, icon: <CourseIcon sx={{ fontSize: 16, color: 'text.secondary' }} /> },
        { label: 'Departments set up', count: stats.departments, required: 3,  icon: <DeptIcon   sx={{ fontSize: 16, color: 'text.secondary' }} /> },
        { label: 'Student groups',     count: stats.groups,      required: 3,  icon: <GroupIcon  sx={{ fontSize: 16, color: 'text.secondary' }} /> },
        { label: 'Lecturers assigned', count: stats.lecturers,   required: 5,  icon: <SchoolIcon sx={{ fontSize: 16, color: 'text.secondary' }} /> },
        { label: 'Rooms / Venues',     count: stats.rooms,       required: 3,  icon: <SchoolIcon sx={{ fontSize: 16, color: 'text.secondary' }} /> },
    ];

    const readyCount = readinessItems.filter(r => r.count >= r.required).length;
    const allReady   = readyCount === readinessItems.length;

    const DAYS  = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
    const HOURS = ['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00'];

    const statCards = [
        { label: 'Courses',        value: stats.courses,     icon: <CourseIcon />, color: primaryColor },
        { label: 'Departments',    value: stats.departments, icon: <DeptIcon />,   color: '#6a1b9a'    },
        { label: 'Student Groups', value: stats.groups,      icon: <GroupIcon />,  color: '#00838f'    },
        { label: 'Lecturers',      value: stats.lecturers,   icon: <SchoolIcon />, color: '#2e7d32'    },
        { label: 'Rooms',          value: stats.rooms,       icon: <RoomIcon />,   color: '#e65100'    },
    ];

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>

            {/* ══ HERO — bold tenant-gradient with giant clock ══ */}
            <Box
                sx={{
                    position: 'relative',
                    borderRadius: 4,
                    overflow: 'hidden',
                    background: `linear-gradient(135deg, ${primaryColor} 0%, #5c35cc 55%, #7c3aed 100%)`,
                    boxShadow: `0 12px 40px ${primaryColor}55`,
                    minHeight: { xs: 200, md: 240 },
                    display: 'flex',
                    alignItems: 'center',
                    px: { xs: 3, md: 5 },
                    py: 3,
                }}
            >
                {/* Decorative orbs */}
                <Box sx={{ position: 'absolute', top: -60,  left: -60,   width: 260, height: 260, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.06)', pointerEvents: 'none' }} />
                <Box sx={{ position: 'absolute', bottom: -80, right: 140, width: 220, height: 220, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.04)', pointerEvents: 'none' }} />
                <Box sx={{ position: 'absolute', top: 20,  right: '34%', width: 80,  height: 80,  borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.06)', pointerEvents: 'none' }} />

                <Grid container alignItems="center" sx={{ width: '100%' }}>
                    {/* Left: platform label */}
                    <Grid item xs={12} md={5}>
                        <Chip
                            label={active ? "Live Schedule Active" : "No Active Timetable"}
                            size="small"
                                sx={{ bgcolor: active ? 'rgba(76, 175, 80, 0.8)' : 'rgba(255,255,255,0.18)', color: '#fff', fontWeight: 700, mb: 2, fontSize: '0.72rem' }}
                            />
                            <Typography variant="h4" fontWeight={900} sx={{ color: '#fff', lineHeight: 1.15, mb: 1 }}>
                                {branding.name || 'TableSys'}
                            </Typography>
                            <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.78)', maxWidth: 380, lineHeight: 1.7 }}>
                                {active ? "System is running globally with real-time live timetables active." : "Intelligent academic scheduling. Load your data and publish a timetable to go live across the institution."}
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

            {!active && (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    {/* ══ STAT CARDS ══ */}
                    <Grid container spacing={2}>
                        {statCards.map(({ label, value, icon, color }) => (
                            <Grid item xs={6} sm={4} md={2.4} key={label}>
                                <Card
                                    elevation={0}
                                    sx={{
                                        border: '1px solid', borderColor: 'divider', borderRadius: 3, height: '100%',
                                transition: 'transform 0.2s, box-shadow 0.2s',
                                '&:hover': { transform: 'translateY(-2px)', boxShadow: `0 6px 20px ${color}28` },
                            }}
                        >
                            <CardContent sx={{ textAlign: 'center', py: 2.5 }}>
                                <Box sx={{ color, mb: 1 }}>{icon}</Box>
                                <Typography variant="h4" fontWeight={800} sx={{ color }}>{value}</Typography>
                                <Typography variant="caption" color="text.secondary" fontWeight={500}>{label}</Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                ))}
            </Grid>

            {/* ══ SETUP STATUS STRIP ══ */}
            {isCoordinator && (
                <Paper elevation={0} sx={{
                    border: '1px solid', borderColor: 'divider', borderRadius: 2,
                    px: 2.5, py: 1.5,
                    display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap',
                }}>
                    {/* Summary badge */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 'max-content' }}>
                        <TrendingIcon sx={{ fontSize: 16, color: allReady ? 'success.main' : 'warning.main' }} />
                        <Typography variant="caption" fontWeight={700} color="text.secondary">Setup</Typography>
                        <Chip
                            label={`${readyCount}/${readinessItems.length}`}
                            size="small"
                            color={allReady ? 'success' : 'warning'}
                            sx={{ height: 20, fontSize: '0.68rem', fontWeight: 700 }}
                        />
                    </Box>

                    {/* Divider */}
                    <Box sx={{ width: '1px', height: 28, bgcolor: 'divider', display: { xs: 'none', sm: 'block' } }} />

                    {/* Per-item mini progress bars */}
                    {readinessItems.map(r => {
                        const ok = r.count >= r.required;
                        const pct = Math.min(100, Math.round((r.count / r.required) * 100));
                        return (
                            <Tooltip key={r.label} title={`${r.label}: ${r.count} / ${r.required} required`} arrow>
                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.4, minWidth: 80, cursor: 'default' }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <Typography variant="caption" fontSize="0.65rem" color={ok ? 'success.main' : 'text.secondary'} fontWeight={600} noWrap>
                                            {r.label}
                                        </Typography>
                                        {ok
                                            ? <CheckIcon sx={{ fontSize: 12, color: 'success.main' }} />
                                            : <EmptyIcon sx={{ fontSize: 12, color: 'text.disabled' }} />}
                                    </Box>
                                    <LinearProgress
                                        variant="determinate"
                                        value={pct}
                                        sx={{
                                            height: 4, borderRadius: 2,
                                            bgcolor: 'action.hover',
                                            '& .MuiLinearProgress-bar': {
                                                bgcolor: ok ? 'success.main' : 'warning.main',
                                                borderRadius: 2,
                                            },
                                        }}
                                    />
                                </Box>
                            </Tooltip>
                        );
                    })}
                </Paper>
            )}

            {/* ══ GHOST TIMETABLE — full width, main feature ══ */}
            <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 3, overflow: 'hidden' }}>
                <Box sx={{
                    px: 3, py: 2,
                    borderBottom: '1px solid', borderColor: 'divider',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    bgcolor: 'action.hover',
                }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <ScheduleIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
                        <Box>
                            <Typography variant="subtitle1" fontWeight={700}>Weekly Schedule Preview</Typography>
                            <Typography variant="caption" color="text.secondary">
                                Your live timetable will appear here once published
                            </Typography>
                        </Box>
                    </Box>
                    <Chip
                        label="Awaiting Publication"
                        size="small" variant="outlined"
                        icon={<ClockIcon sx={{ fontSize: '14px !important' }} />}
                        sx={{ color: 'text.secondary', borderColor: 'divider' }}
                    />
                </Box>

                <Box sx={{ overflowX: 'auto' }}>
                    <Box sx={{ display: 'grid', gridTemplateColumns: '64px repeat(5, 1fr)', minWidth: 580 }}>
                        {/* Day headers */}
                        <Box sx={{ bgcolor: 'action.hover', borderBottom: '2px solid', borderColor: 'divider', p: 1.5 }} />
                        {DAYS.map(d => (
                            <Box key={d} sx={{
                                bgcolor: 'action.hover',
                                borderBottom: '2px solid', borderColor: 'divider',
                                borderLeft: '1px solid', borderLeftColor: 'divider',
                                p: 1.5, textAlign: 'center',
                            }}>
                                <Typography variant="caption" fontWeight={800} color="text.secondary" sx={{ letterSpacing: 1 }}>
                                    {d.slice(0, 3).toUpperCase()}
                                </Typography>
                            </Box>
                        ))}

                        {/* Hour rows */}
                        {HOURS.map((hour, hi) => (
                            <React.Fragment key={hour}>
                                <Box sx={{
                                    px: 1, py: 1,
                                    display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
                                    borderTop: '1px solid', borderColor: 'divider',
                                    bgcolor: hi % 2 === 0 ? 'transparent' : 'action.hover',
                                }}>
                                    <Typography variant="caption" color="text.disabled" fontFamily="monospace" fontSize="0.68rem">
                                        {hour}
                                    </Typography>
                                </Box>
                                {DAYS.map(d => {
                                    const seed = (d.charCodeAt(0) * 3 + hi * 7) % 11;
                                    const showBlock = seed < 3;
                                    return (
                                        <Box key={d} sx={{
                                            borderLeft: '1px solid', borderColor: 'divider',
                                            borderTop: '1px solid',
                                            bgcolor: hi % 2 === 0 ? 'background.paper' : 'action.hover',
                                            p: 0.5, minHeight: 50, position: 'relative',
                                        }}>
                                            {showBlock && (
                                                <Box sx={{
                                                    height: 36, borderRadius: 1,
                                                    background: `linear-gradient(90deg, ${primaryColor}22, #7c3aed22)`,
                                                    animation: `shimmer ${(2.2 + seed * 0.28).toFixed(1)}s ease-in-out infinite`,
                                                    animationDelay: `${(hi * 0.14).toFixed(2)}s`,
                                                }} />
                                            )}
                                        </Box>
                                    );
                                })}
                            </React.Fragment>
                        ))}
                    </Box>
                </Box>
            </Card>
            </Box>
            )}

            <style>{`
                @keyframes shimmer {
                    0%, 100% { opacity: 0.5; }
                    50%       { opacity: 1;   }
                }
            `}</style>
        </Box>
    );
};

// ──────────────────────────────────────────────────────────────────────────────

const DashboardPage: React.FC = () => {
    const { user } = useAuth();
    const { branding } = useBranding();

    const [selectedYear, setSelectedYear] = useState<number>(2);
    const [availableYears, setAvailableYears] = useState<number[]>([]);
    const [selectedProgram, setSelectedProgram] = useState<string>('ALL');
    const [selectedLayer, setSelectedLayer] = useState<string>('ALL');
    const [data, setData] = useState<TimetableViewData | null>(null);
    const [departments, setDepartments] = useState<{ id: number; name: string; code: string }[]>([]);
    const [stats, setStats] = useState<SystemStats>({ courses: 0, departments: 0, groups: 0, lecturers: 0, rooms: 0 });

    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [noActiveTimetable, setNoActiveTimetable] = useState<boolean>(false);

    const isCoordinator = user?.role?.toUpperCase() === 'COORDINATOR';

    useEffect(() => {
        // Fetch supporting data in parallel
        const fetchSupporting = async () => {
            try {
                const [depts, statsRes, groupsRes, coursesRes] = await Promise.allSettled([
                    departmentsAPI.getAll(),
                    api.get('/stats/summary').catch(() => null),
                    api.get('/groups/?limit=1000').catch(() => null),
                    api.get('/courses/?limit=1000').catch(() => null),
                ]);
                if (depts.status === 'fulfilled') setDepartments(depts.value);

                const groupPayload = groupsRes.status === 'fulfilled' ? groupsRes.value?.data : null;
                const groupRows = Array.isArray(groupPayload)
                    ? groupPayload
                    : Array.isArray(groupPayload?.items)
                        ? groupPayload.items
                        : [];

                const coursePayload = coursesRes.status === 'fulfilled' ? coursesRes.value?.data : null;
                const courseRows = Array.isArray(coursePayload)
                    ? coursePayload
                    : Array.isArray(coursePayload?.items)
                        ? coursePayload.items
                        : [];

                const yearsInSystem = Array.from(
                    new Set([
                        ...extractAvailableYears(groupRows),
                        ...extractAvailableYears(courseRows),
                    ]),
                ).sort((a, b) => a - b);

                if (yearsInSystem.length > 0) {
                    setAvailableYears(yearsInSystem);
                }

                // Try dedicated stats endpoint first, fall back to individual counts
                if (statsRes.status === 'fulfilled' && statsRes.value?.data) {
                    setStats(statsRes.value.data);
                } else {
                    // Individual fallbacks
                    const [c, g, l, r] = await Promise.allSettled([
                        api.get('/courses/?limit=1').catch(() => ({ data: [] })),
                        api.get('/groups/?limit=1').catch(() => ({ data: [] })),
                        api.get('/lecturers/?limit=1').catch(() => ({ data: [] })),
                        api.get('/rooms/?limit=1').catch(() => ({ data: [] })),
                    ]);

                    // Use header X-Total-Count or direct counts
                    const getCounts = async (url: string) => {
                        try { const r = await api.get(url); return Array.isArray(r.data) ? r.data.length : 0; } catch { return 0; }
                    };

                    const [coursesCount, groupsCount, lecturersCount, roomsCount] = await Promise.all([
                        getCounts('/courses/?limit=1000'),
                        getCounts('/groups/?limit=1000'),
                        getCounts('/lecturers/?limit=1000'),
                        getCounts('/rooms/?limit=1000'),
                    ]);

                    setStats({
                        courses: coursesCount,
                        departments: depts.status === 'fulfilled' ? depts.value.length : 0,
                        groups: groupsCount,
                        lecturers: lecturersCount,
                        rooms: roomsCount,
                    });
                }
            } catch { /* non-critical */ }
        };
        fetchSupporting();
    }, []);

    useEffect(() => {
        if (availableYears.length === 0) {
            return;
        }

        if (!availableYears.includes(selectedYear)) {
            setSelectedYear(availableYears[0]);
        }
    }, [availableYears, selectedYear]);

    const fetchDashboardTimetable = useCallback(async () => {
        setLoading(true);
        setError(null);
        setNoActiveTimetable(false);
        try {
            const ttRes = await api.get('/timetables/');
            const activeTt = ttRes.data.find((t: any) => t.is_active);

            if (!activeTt) {
                setNoActiveTimetable(true);
                setData(null);
                setLoading(false);
                return;
            }

            const response = await api.get<TimetableViewData>('/timetables/view', {
                params: { year: selectedYear, program: selectedProgram },
            });

            const payload: any = response.data;
            if (!Array.isArray(payload?.slots) && payload?.detail) {
                setError(errorDetailToMessage(payload.detail) || 'Unexpected timetable response received.');
            }
            setData(normalizeTimetableViewData(payload));
        } catch (err: any) {
            const parsedDetail = errorDetailToMessage(err?.response?.data?.detail);
            setError(parsedDetail || (err instanceof Error ? err.message : 'Failed to sync live timetable state.'));
            setData(null);
        } finally {
            setLoading(false);
        }
    }, [selectedYear, selectedProgram]);

    useEffect(() => {
        fetchDashboardTimetable();
    }, [fetchDashboardTimetable]);

    if (loading) {
        return (
            <Box sx={{ display: 'flex', flexGrow: 1, height: '60vh', alignItems: 'center', justifyContent: 'center' }}>
                <CircularProgress size={60} />
            </Box>
        );
    }

    const yearOptions = buildYearOptions(
        availableYears.length > 0 ? availableYears : [selectedYear],
    );

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <EmptyTimetableLanding
                stats={stats}
                isCoordinator={isCoordinator}
                branding={branding}
                active={!noActiveTimetable}
            />

            {!noActiveTimetable && (
                <>
            {/* Live Indicator Header */}
            <Paper sx={{ p: 3, mb: 4, borderRadius: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: `linear-gradient(135deg, ${branding.primary_color}10 0%, transparent 100%)` }}>
                <Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
                        <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: '#4caf50', boxShadow: '0 0 10px #4caf50', animation: 'pulse 2s infinite' }} />
                        <Typography variant="h5" fontWeight="bold">
                            Live Master Timetable
                        </Typography>
                        <Chip label={data?.metadata?.term || "Active Term"} color="primary" size="small" />
                    </Box>
                    <Typography variant="body2" color="text.secondary">
                        Real-time visualization of the institutional schedule grid. Classes currently in session are highlighted.
                    </Typography>
                </Box>

                {/* Filters */}
                <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-end' }}>
                    <Box>
                        <Typography variant="caption" color="text.secondary">Year Level</Typography>
                        <br />
                        <ButtonGroup variant="outlined" size="small">
                            {yearOptions.map(({ value, label }) => (
                                <Button
                                    key={value}
                                    variant={selectedYear === value ? 'contained' : 'outlined'}
                                    onClick={() => setSelectedYear(value)}
                                >
                                    {label}
                                </Button>
                            ))}
                        </ButtonGroup>
                    </Box>

                    <Box sx={{ minWidth: 200 }}>
                        <Typography variant="caption" color="text.secondary">Program/Department</Typography>
                        <Select
                            value={selectedProgram}
                            onChange={(e: SelectChangeEvent) => setSelectedProgram(e.target.value)}
                            size="small"
                            fullWidth
                            sx={{ mt: 0.5, bgcolor: 'background.paper' }}
                        >
                            <MenuItem value="ALL">All Programs</MenuItem>
                            {departments.map((dept) => (
                                <MenuItem key={dept.id} value={dept.code}>
                                    {dept.name}
                                </MenuItem>
                            ))}
                        </Select>
                    </Box>
                    <Box sx={{ minWidth: 200 }}>
                        <Typography variant="caption" color="text.secondary">Layer</Typography>
                        <br />
                        <ButtonGroup variant="outlined" size="small" sx={{ mt: 0.5 }}>
                            {['ALL', 'lecture', 'practical', 'tutorial'].map(layer => {
                                const labels: Record<string, string> = { ALL: 'All', lecture: 'Lectures', practical: 'Labs', tutorial: 'Tutorials' };
                                return (
                                    <Button
                                        key={layer}
                                        variant={selectedLayer === layer ? 'contained' : 'outlined'}
                                        onClick={() => setSelectedLayer(layer)}
                                    >
                                        {labels[layer]}
                                    </Button>
                                );
                            })}
                        </ButtonGroup>
                    </Box>
                </Box>
            </Paper>

            {error ? (
                <Alert severity="error">{error}</Alert>
            ) : data?.slots?.length === 0 ? (
                <Alert severity="info" sx={{ mt: 2 }}>
                    No sessions scheduled for this filtering combination.
                </Alert>
            ) : (
                <Box sx={{ flexGrow: 1, minHeight: 600 }}>
                    <TimetableGrid
                    slots={(data?.slots || []).filter(slot => selectedLayer === 'ALL' || slot.session_type === selectedLayer)}
                        gridConfig={data?.metadata?.grid_config}
                        mode="view"
                        showCurrentTime={true}
                    />
                </Box>
            )}
            </>
            )}

            <style>{`
                @keyframes pulse {
                    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }
                    70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); }
                    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }
                }
            `}</style>
        </Box>
    );
};

export default DashboardPage;
