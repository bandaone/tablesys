import React from 'react';
import {
  AccessTime as AccessTimeIcon,
  CalendarMonth as CalendarMonthIcon,
  PlaceOutlined as PlaceOutlinedIcon,
  Download as DownloadIcon,
  WorkRounded as WorkIcon,
  TrendingUpRounded as TrendingUpIcon,
  SchoolRounded as SchoolIcon,
  TimerRounded as TimerIcon,
  AssignmentRounded as AssignmentIcon,
} from '@mui/icons-material';
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  Paper,
  Stack,
  TextField,
  Typography,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  IconButton,
} from '@mui/material';
import {
  CampaignRounded as CampaignIcon,
  DeleteOutline as DeleteIcon,
} from '@mui/icons-material';
import { lecturerPortalApi } from '../../lecturerPortalApi';
import { alpha } from '@mui/material/styles';
import type {
  LecturerCourse,
  LecturerCourseWorkload,
  LecturerDashboardSummary,
  LecturerProfile,
  LecturerTimetableSlot,
} from './types';
import {
  DAY_ORDER,
  formatDayLabel,
  formatTimeRange,
  formatDuration,
  normalizeSessionType,
  getSessionTypeChipColor,
  formatSessionTypeLabel,
  getMinutesFromTime,
  getDaySortIndex,
  type LecturerPortalTab,
} from './lecturerUtils';

// ── Helpers (local only) ──────────────────────────────────────────────────

const formatLocation = (room: string | undefined, building: string | undefined): string => {
  const clean = (v: any) => {
    const s = String(v ?? '').trim();
    return s === '' || s === '0' || s.toLowerCase() === 'tba' || s.toLowerCase() === 'null'
      ? null
      : s;
  };
  const r = clean(room);
  const b = clean(building);
  if (!r && !b) return 'Venue TBA';
  if (!r) return b!;
  if (!b) return r;
  return `${r} · ${b}`;
};

const COURSE_PALETTE = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ef4444'];

// ── LecturerCourseAnnouncements ─────────────────────────────────────────────

const LecturerCourseAnnouncements: React.FC<{ course: LecturerCourse }> = ({ course }) => {
  const [open, setOpen] = React.useState(false);
  const [announcements, setAnnouncements] = React.useState<any[]>([]);
  const [type, setType] = React.useState('general');
  const [title, setTitle] = React.useState('');
  const [message, setMessage] = React.useState('');
  const [targetDate, setTargetDate] = React.useState('');
  const [venue, setVenue] = React.useState('');
  const [loading, setLoading] = React.useState(false);

  // Venue search state
  const [startTime, setStartTime] = React.useState('');
  const [endTime, setEndTime] = React.useState('');
  const [capacity, setCapacity] = React.useState<number | ''>('');
  const [availableVenues, setAvailableVenues] = React.useState<any[]>([]);
  const [defaultRoomInfo, setDefaultRoomInfo] = React.useState<any>(null);
  const [selectedRoomId, setSelectedRoomId] = React.useState<number | null>(null);
  const [useDefaultRoom, setUseDefaultRoom] = React.useState(false);
  const [searchingVenues, setSearchingVenues] = React.useState(false);
  const [venueSearchDone, setVenueSearchDone] = React.useState(false);
  const [venueSearchError, setVenueSearchError] = React.useState<string | null>(null);

  React.useEffect(() => {
    lecturerPortalApi.getAnnouncements(course.id).then(setAnnouncements).catch(console.error);
  }, [course.id]);

  const handleSearchVenues = async () => {
    if (!targetDate || !startTime || !endTime) return;
    setSearchingVenues(true);
    setVenueSearchDone(false);
    setVenueSearchError(null);
    setAvailableVenues([]);
    setDefaultRoomInfo(null);
    setSelectedRoomId(null);
    setUseDefaultRoom(false);
    try {
      const result = await lecturerPortalApi.getAvailableVenues({
        date: targetDate,
        start_time: startTime,
        end_time: endTime,
        capacity: capacity ? Number(capacity) : 0,
        course_id: course.id,
      });
      // New API returns { rooms: [...], default_room: {...} | null }
      const rooms = result.rooms ?? result; // graceful fallback if old shape
      const defRoom = result.default_room ?? null;
      setAvailableVenues(rooms);
      setDefaultRoomInfo(defRoom);
      setVenueSearchDone(true);
    } catch (e: any) {
      console.error(e);
      setVenueSearchError(e.response?.data?.detail || 'Failed to search venues. Please try again.');
      setVenueSearchDone(true);
    } finally {
      setSearchingVenues(false);
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      if (type === 'test_scheduled') {
        if (!targetDate || !startTime || !endTime) {
          alert("Date, start time, and end time are required.");
          setLoading(false);
          return;
        }
        await lecturerPortalApi.scheduleTest({
          course_id: course.id,
          date: targetDate,
          start_time: startTime,
          end_time: endTime,
          // useDefaultRoom = lecturer clicked the default room card (confirmed free by search)
          // In that case send no room_id so the backend auto-resolves to the lecture room
          room_id: useDefaultRoom ? undefined : (selectedRoomId ?? undefined),
          title,
          message,
          capacity: capacity ? Number(capacity) : undefined,
        });
      } else {
        await lecturerPortalApi.createAnnouncement({
          course_id: course.id,
          title,
          message,
          announcement_type: type,
          target_date: targetDate || undefined,
          venue: venue || undefined
        });
      }
      const updated = await lecturerPortalApi.getAnnouncements(course.id);
      setAnnouncements(updated);
      setOpen(false);
      setTitle('');
      setMessage('');
      setTargetDate('');
      setVenue('');
      setStartTime('');
      setEndTime('');
      setCapacity('');
      setAvailableVenues([]);
      setDefaultRoomInfo(null);
      setSelectedRoomId(null);
      setUseDefaultRoom(false);
      setVenueSearchDone(false);
      setVenueSearchError(null);
    } catch (e: any) {
      console.error(e);
      alert(e.response?.data?.detail || "Action failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm("Are you sure you want to delete this announcement?")) return;
    try {
      await lecturerPortalApi.deleteAnnouncement(id);
      setAnnouncements(prev => prev.filter(a => a.id !== id));
    } catch (e) {
      console.error(e);
      alert("Failed to delete announcement.");
    }
  };

  return (
    <Box sx={{ mt: 3, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1.5}>
        <Typography variant="subtitle2" fontWeight={700}>Announcements</Typography>
        <Button size="small" variant="outlined" startIcon={<CampaignIcon />} onClick={() => setOpen(true)} sx={{ borderRadius: 2 }}>
          New Notice
        </Button>
      </Stack>
      
      {announcements.length === 0 ? (
        <Typography variant="caption" color="text.secondary">No announcements made yet.</Typography>
      ) : (
        <Stack spacing={1}>
          {announcements.slice(0, 3).map(a => (
            <Paper key={a.id} elevation={0} sx={{ p: 1.5, bgcolor: alpha('#000', 0.03), borderRadius: 2 }}>
              <Stack direction="row" spacing={1} mb={0.5} alignItems="flex-start" justifyContent="space-between">
                 <Stack direction="row" spacing={1} alignItems="center">
                   <Chip size="small" label={a.type.replace('_', ' ')} color={a.type === 'class_cancelled' ? 'error' : a.type === 'test_scheduled' ? 'secondary' : 'default'} sx={{ textTransform: 'capitalize' }} />
                   <Typography variant="body2" fontWeight={600} noWrap title={a.title}>{a.title}</Typography>
                 </Stack>
                 <IconButton size="small" onClick={() => handleDelete(a.id)} sx={{ p: 0.25, mt: -0.25, mr: -0.25 }} title="Clear notice">
                   <DeleteIcon fontSize="small" sx={{ color: 'text.secondary', opacity: 0.6, '&:hover': { opacity: 1, color: 'error.main' } }} />
                 </IconButton>
              </Stack>
              <Typography variant="body2" sx={{ opacity: 0.8 }} display="block">{a.message}</Typography>
              {(a.target_date || a.venue) && (
                <Stack direction="row" spacing={2} sx={{ mt: 1, color: 'text.secondary', '& svg': { fontSize: 16 } }}>
                  {a.target_date && <Typography variant="caption" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}><CalendarMonthIcon /> {new Date(a.target_date).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short', year: 'numeric' })}</Typography>}
                  {a.venue && <Typography variant="caption" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}><PlaceOutlinedIcon /> {a.venue}</Typography>}
                </Stack>
              )}
            </Paper>
          ))}
          {announcements.length > 3 && <Typography variant="caption" color="text.secondary">...and {announcements.length - 3} more.</Typography>}
        </Stack>
      )}

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>New Announcement for {course.code}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Notice Type</InputLabel>
              <Select value={type} label="Notice Type" onChange={(e) => setType(e.target.value)}>
                <MenuItem value="general">General Broadcast</MenuItem>
                <MenuItem value="test_scheduled">Schedule a Test</MenuItem>
                <MenuItem value="class_cancelled">Cancel a Class</MenuItem>
              </Select>
            </FormControl>
            <TextField label="Title" value={title} onChange={(e) => setTitle(e.target.value)} size="small" fullWidth />
            {type === 'class_cancelled' && (
               <Stack direction="row" spacing={2}>
                 <TextField label="Target Date" type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} size="small" fullWidth InputLabelProps={{ shrink: true }} />
                 <TextField label="Venue (Optional)" value={venue} onChange={(e) => setVenue(e.target.value)} size="small" fullWidth />
               </Stack>
            )}
            {type === 'test_scheduled' && (
               <Stack spacing={2}>
                 {/* Row 1: Date + Capacity */}
                 <Stack direction="row" spacing={2}>
                   <TextField label="Test Date" type="date" value={targetDate} onChange={(e) => { setTargetDate(e.target.value); setVenueSearchDone(false); setAvailableVenues([]); setSelectedRoomId(null); }} size="small" fullWidth InputLabelProps={{ shrink: true }} required />
                   <TextField label="Min. Capacity" type="number" value={capacity} onChange={(e) => { setCapacity(e.target.value ? Number(e.target.value) : ''); setVenueSearchDone(false); setAvailableVenues([]); setSelectedRoomId(null); }} size="small" fullWidth inputProps={{ min: 0 }} placeholder="Any" />
                 </Stack>
                 {/* Row 2: Times */}
                 <Stack direction="row" spacing={2}>
                   <TextField label="Start Time" type="time" value={startTime} onChange={(e) => { setStartTime(e.target.value); setVenueSearchDone(false); setAvailableVenues([]); setSelectedRoomId(null); }} size="small" fullWidth InputLabelProps={{ shrink: true }} required />
                   <TextField label="End Time" type="time" value={endTime} onChange={(e) => { setEndTime(e.target.value); setVenueSearchDone(false); setAvailableVenues([]); setSelectedRoomId(null); }} size="small" fullWidth InputLabelProps={{ shrink: true }} required />
                 </Stack>
                 {/* Row 3: Search button */}
                 <Button
                   variant="outlined"
                   onClick={handleSearchVenues}
                   disabled={searchingVenues || !targetDate || !startTime || !endTime}
                   startIcon={searchingVenues ? <CircularProgress size={14} /> : <PlaceOutlinedIcon />}
                   sx={{ alignSelf: 'flex-start', borderRadius: 2 }}
                 >
                   {searchingVenues ? 'Searching venues…' : 'Find Available Venues'}
                 </Button>

                 {/* Venue search results */}
                 {venueSearchDone && !venueSearchError && availableVenues.length === 0 && !defaultRoomInfo?.available && (
                   <Alert severity="warning" sx={{ borderRadius: 2 }}>
                     No rooms are free on {new Date(targetDate + 'T00:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short' })} between {startTime} – {endTime}{capacity ? ` with capacity ≥ ${capacity}` : ''}. Please adjust the date or time and search again.
                   </Alert>
                 )}

                 {venueSearchError && (
                   <Alert severity="error" sx={{ borderRadius: 2 }}>{venueSearchError}</Alert>
                 )}

                 {/* Default room availability notice */}
                 {venueSearchDone && !venueSearchError && defaultRoomInfo && !defaultRoomInfo.available && (
                   <Alert severity="info" sx={{ borderRadius: 2 }}>
                     <strong>Default room not available:</strong> {defaultRoomInfo.name} ({defaultRoomInfo.building}) is occupied at this time by another booking. Select an alternative below.
                   </Alert>
                 )}

                 {venueSearchDone && !venueSearchError && (availableVenues.length > 0 || defaultRoomInfo?.available) && (
                   <Box>
                     <Typography variant="caption" color="text.secondary" sx={{ mb: 0.75, display: 'block' }}>
                       {availableVenues.length} alternative venue{availableVenues.length !== 1 ? 's' : ''} available
                       {defaultRoomInfo?.available ? ' · default lecture room is also free.' : '.'}
                     </Typography>
                     <Stack spacing={0.75}>
                       {/* "Use default" option — only shown when backend confirms it's free */}
                       {defaultRoomInfo?.available && (
                         <Paper
                           elevation={0}
                           onClick={() => { setUseDefaultRoom(true); setSelectedRoomId(null); }}
                           sx={{
                             p: 1.25, borderRadius: 2, cursor: 'pointer', border: '1.5px solid',
                             borderColor: useDefaultRoom ? 'primary.main' : 'divider',
                             bgcolor: useDefaultRoom ? alpha('#3b82f6', 0.06) : 'transparent',
                           }}
                         >
                           <Stack direction="row" justifyContent="space-between" alignItems="center">
                             <Box>
                               <Typography variant="body2" fontWeight={700}>
                                 {defaultRoomInfo.name}
                                 <Chip label="Default room" size="small" sx={{ ml: 1, fontSize: 10 }} />
                               </Typography>
                               <Typography variant="caption" color="text.secondary">
                                 {defaultRoomInfo.building} · Cap: {defaultRoomInfo.capacity}{defaultRoomInfo.has_projector ? ' · Projector' : ''} · Free at this time
                               </Typography>
                             </Box>
                             {useDefaultRoom && <Chip label="Selected" size="small" color="primary" />}
                           </Stack>
                         </Paper>
                       )}
                       {availableVenues
                         .filter((v) => !v.is_default_venue) // avoid duplicate if default also appears
                         .map((v) => (
                         <Paper
                           key={v.id}
                           elevation={0}
                           onClick={() => { setSelectedRoomId(v.id); setUseDefaultRoom(false); }}
                           sx={{
                             p: 1.25, borderRadius: 2, cursor: 'pointer', border: '1.5px solid',
                             borderColor: selectedRoomId === v.id ? 'primary.main' : 'divider',
                             bgcolor: selectedRoomId === v.id ? alpha('#3b82f6', 0.06) : 'transparent',
                           }}
                         >
                           <Stack direction="row" justifyContent="space-between" alignItems="center">
                             <Box>
                               <Typography variant="body2" fontWeight={700}>{v.name}</Typography>
                               <Typography variant="caption" color="text.secondary">{v.building} · Cap: {v.capacity}{v.has_projector ? ' · Projector' : ''} · {v.type?.replace('_', ' ')}</Typography>
                             </Box>
                             {selectedRoomId === v.id && (
                               <Chip label="Selected" size="small" color="primary" />
                             )}
                           </Stack>
                         </Paper>
                       ))}
                     </Stack>
                   </Box>
                 )}
               </Stack>
            )}
            <TextField label="Message" value={message} onChange={(e) => setMessage(e.target.value)} multiline rows={3} size="small" fullWidth />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSubmit} disabled={loading || !title || !message}>
            {loading ? 'Sending...' : 'Broadcast'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

// ── LecturerSessionCard ────────────────────────────────────────────────────

interface SessionCardProps {
  slot: LecturerTimetableSlot;
  currentDay: string;
  currentMinutes: number;
  isLive?: boolean;
}

export const LecturerSessionCard: React.FC<SessionCardProps> = ({
  slot,
  currentDay,
  currentMinutes,
  isLive,
}) => {
  const startMin = getMinutesFromTime(slot.start_time);
  const endMin = getMinutesFromTime(slot.end_time);

  let toneLabel = slot.day_of_week;
  let toneColor: 'success' | 'warning' | 'default' = 'default';
  if (slot.day_of_week === currentDay) {
    if (currentMinutes >= startMin && currentMinutes < endMin) {
      toneLabel = 'Live now';
      toneColor = 'success';
    } else if (startMin > currentMinutes && startMin - currentMinutes <= 30) {
      toneLabel = `Starts in ${startMin - currentMinutes} min`;
      toneColor = 'warning';
    } else {
      toneLabel = 'Today';
    }
  }

  return (
    <Card
      sx={{
        borderRadius: 4,
        border: '1px solid',
        borderColor: isLive ? 'success.light' : 'divider',
        boxShadow: isLive ? '0 8px 24px rgba(16,185,129,0.12)' : '0 14px 34px rgba(0,0,0,0.05)',
      }}
    >
      <CardContent sx={{ p: 2.25 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1.5}>
          <div>
            <Typography variant="overline" sx={{ letterSpacing: 1.1, color: 'text.secondary' }}>
              {slot.course_code}
            </Typography>
            <Typography variant="subtitle1" fontWeight={800} sx={{ lineHeight: 1.25 }}>
              {slot.course_name}
            </Typography>
          </div>
          <Stack spacing={0.8} alignItems="flex-end">
            <Chip label={toneLabel} color={toneColor} size="small" />
            <Chip
              label={formatSessionTypeLabel(slot.session_type)}
              color={getSessionTypeChipColor(slot.session_type)}
              size="small"
            />
          </Stack>
        </Stack>

        <Stack spacing={1.2} sx={{ mt: 1.8 }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <AccessTimeIcon fontSize="small" color="primary" />
            <Typography variant="body2">{formatTimeRange(slot)}</Typography>
          </Stack>
          <Stack direction="row" spacing={1} alignItems="center">
            <PlaceOutlinedIcon fontSize="small" color="primary" />
            <Typography variant="body2">
              {formatLocation(slot.room_number, slot.building)}
            </Typography>
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
};

// ── LecturerHomePanel ──────────────────────────────────────────────────────

export const LecturerHomePanel: React.FC<{
  profile: LecturerProfile | null;
  summary: LecturerDashboardSummary | null;
  sessions: LecturerTimetableSlot[];
  courseWorkload: LecturerCourseWorkload[];
  currentDay: string;
  currentMinutes: number;
  setActiveTab: (tab: LecturerPortalTab) => void;
}> = ({ profile, summary, sessions, courseWorkload, currentDay, currentMinutes, setActiveTab }) => {
  const currentSession =
    sessions.find((s) => {
      if (s.day_of_week !== currentDay) return false;
      const start = getMinutesFromTime(s.start_time);
      const end = getMinutesFromTime(s.end_time);
      return currentMinutes >= start && currentMinutes < end;
    }) || null;

  const todayIndex = getDaySortIndex(currentDay);
  const nextSession =
    sessions
      .map((s) => ({
        s,
        dayIndex: getDaySortIndex(s.day_of_week),
        startMin: getMinutesFromTime(s.start_time),
      }))
      .sort((a, b) =>
        a.dayIndex !== b.dayIndex ? a.dayIndex - b.dayIndex : a.startMin - b.startMin,
      )
      .find(
        ({ dayIndex, startMin }) =>
          dayIndex > todayIndex ||
          (dayIndex === todayIndex && startMin > currentMinutes),
      )?.s || null;

  const weeklyHours = summary?.weekly_load_hours ?? 0;
  const maxHours = summary?.max_hours_per_week ?? 0;
  const weeklyPercent = summary?.weekly_load_percent ?? null;
  const loadProgressValue =
    weeklyPercent !== null ? Math.min(Math.max(weeklyPercent, 0), 100) : 0;
  const dailyHours = summary?.daily_teaching_hours ?? 0;
  const dailySessionCount = summary?.daily_session_count ?? 0;

  return (
    <Stack spacing={2.2}>
      {/* NOW / NEXT Hero Cards */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' },
          gap: 2,
        }}
      >
        {/* NOW */}
        <Card sx={{ borderRadius: 5, minHeight: { md: 230 } }}>
          <CardContent sx={{ p: 2.5 }}>
            <Stack spacing={1.8}>
              <div>
                <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: 1.1 }}>
                  NOW
                </Typography>
                {currentSession ? (
                  <>
                    <Typography variant="h6" fontWeight={800}>
                      {currentSession.course_code}
                    </Typography>
                    <Typography variant="body1" color="text.secondary">
                      {currentSession.course_name}
                    </Typography>
                  </>
                ) : (
                  <>
                    <Typography variant="h6" fontWeight={800}>
                      No class right now
                    </Typography>
                    <Typography variant="body1" color="text.secondary">
                      You are currently between sessions.
                    </Typography>
                  </>
                )}
              </div>
              {currentSession ? (
                <Stack spacing={1.2}>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <AccessTimeIcon fontSize="small" color="primary" />
                    <Typography variant="body2">{formatTimeRange(currentSession)}</Typography>
                  </Stack>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <PlaceOutlinedIcon fontSize="small" color="primary" />
                    <Typography variant="body2">
                      {formatLocation(currentSession.room_number, currentSession.building)}
                    </Typography>
                  </Stack>
                </Stack>
              ) : (
                <Alert severity="info" sx={{ borderRadius: 3 }}>
                  No live class at the moment. Your next session appears below if scheduled.
                </Alert>
              )}
            </Stack>
          </CardContent>
        </Card>

        {/* NEXT */}
        <Card sx={{ borderRadius: 5, minHeight: { md: 230 } }}>
          <CardContent sx={{ p: 2.5 }}>
            <Stack spacing={1.6}>
              <div>
                <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: 1.1 }}>
                  NEXT
                </Typography>
                {nextSession ? (
                  <>
                    <Typography variant="h6" fontWeight={800}>
                      {nextSession.course_code}
                    </Typography>
                    <Typography variant="body1" color="text.secondary">
                      {nextSession.course_name}
                    </Typography>
                  </>
                ) : (
                  <>
                    <Typography variant="h6" fontWeight={800}>
                      Nothing else scheduled
                    </Typography>
                    <Typography variant="body1" color="text.secondary">
                      No upcoming session found in your timetable.
                    </Typography>
                  </>
                )}
              </div>
              {nextSession && (
                <>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <CalendarMonthIcon fontSize="small" color="primary" />
                    <Typography variant="body2">
                      {formatDayLabel(nextSession.day_of_week)
                        ? `${formatDayLabel(nextSession.day_of_week)} · `
                        : ''}
                      {formatTimeRange(nextSession)}
                    </Typography>
                  </Stack>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <PlaceOutlinedIcon fontSize="small" color="primary" />
                    <Typography variant="body2">
                      {formatLocation(nextSession.room_number, nextSession.building)}
                    </Typography>
                  </Stack>
                </>
              )}
            </Stack>
          </CardContent>
        </Card>
      </Box>

      {/* Metrics row */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '1.4fr 1fr' },
          gap: 2,
        }}
      >
        {/* Workload card */}
        <Card sx={{ borderRadius: 5 }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography variant="h6" fontWeight={800}>
              Teaching load
            </Typography>
            <Stack spacing={1.5} sx={{ mt: 1.5 }}>
              <Stack direction="row" alignItems="center" spacing={1.25}>
                <Avatar sx={{ bgcolor: 'primary.main', width: 36, height: 36 }}>
                  <WorkIcon fontSize="small" />
                </Avatar>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Today
                  </Typography>
                  <Typography variant="body2" fontWeight={700}>
                    {dailySessionCount} session{dailySessionCount === 1 ? '' : 's'} ·{' '}
                    {dailyHours.toFixed(1)}h
                  </Typography>
                </Box>
              </Stack>
              <Stack direction="row" alignItems="center" spacing={1.25}>
                <Avatar sx={{ bgcolor: 'success.main', width: 36, height: 36 }}>
                  <TrendingUpIcon fontSize="small" />
                </Avatar>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    Weekly load
                  </Typography>
                  <Typography variant="body2" fontWeight={700}>
                    {weeklyHours.toFixed(1)}h
                    {maxHours > 0 ? ` / ${maxHours}h max` : ''}
                  </Typography>
                  {maxHours > 0 && (
                    <LinearProgress
                      variant="determinate"
                      value={loadProgressValue}
                      sx={{ mt: 0.5, borderRadius: 999, height: 6 }}
                    />
                  )}
                </Box>
              </Stack>
            </Stack>
          </CardContent>
        </Card>

        {/* Quick actions */}
        <Card sx={{ borderRadius: 5 }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography variant="h6" fontWeight={800}>
              Quick actions
            </Typography>
            <Stack spacing={1.1} sx={{ mt: 1.4 }}>
              {(
                [
                  { label: 'View Today', helper: 'Sessions for today', tab: 'today' },
                  { label: 'View Week', helper: 'Full week layout', tab: 'week' },
                  { label: 'Search Sessions', helper: 'Find rooms and courses', tab: 'search' },
                  { label: 'My Courses', helper: 'Assigned course list', tab: 'courses' },
                ] as { label: string; helper: string; tab: LecturerPortalTab }[]
              ).map((action) => (
                <Button
                  key={action.tab}
                  onClick={() => setActiveTab(action.tab)}
                  variant="outlined"
                  fullWidth
                  sx={{
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    textAlign: 'left',
                    borderRadius: 3,
                    p: 1.5,
                    textTransform: 'none',
                  }}
                >
                  <div>
                    <Typography variant="body2" fontWeight={700}>
                      {action.label}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {action.helper}
                    </Typography>
                  </div>
                </Button>
              ))}
            </Stack>
          </CardContent>
        </Card>
      </Box>

      {/* Course workload breakdown */}
      {courseWorkload.length > 0 && (
        <Card sx={{ borderRadius: 5 }}>
          <CardContent sx={{ p: 2.5 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
              <Typography variant="h6" fontWeight={800}>
                Course breakdown
              </Typography>
              <Chip label={courseWorkload.length} size="small" />
            </Stack>
            <List disablePadding>
              {courseWorkload.map((course, index) => {
                const color = COURSE_PALETTE[index % COURSE_PALETTE.length];
                return (
                  <React.Fragment key={course.course_id}>
                    <ListItem disableGutters sx={{ py: 1.1 }}>
                      <Avatar sx={{ bgcolor: color, width: 38, height: 38, mr: 1.5, fontSize: 14, fontWeight: 800 }}>
                        {course.course_code?.slice(0, 2) ?? <AssignmentIcon fontSize="small" />}
                      </Avatar>
                      <ListItemText
                        primary={
                          <Typography variant="body2" fontWeight={700}>
                            {course.course_code}
                          </Typography>
                        }
                        secondary={course.course_name}
                      />
                      <Stack direction="row" spacing={0.75} alignItems="center">
                        <Chip
                          label={`${course.sessions} session${course.sessions === 1 ? '' : 's'}`}
                          size="small"
                          variant="outlined"
                        />
                        <Chip
                          label={`${course.hours.toFixed(1)}h`}
                          size="small"
                          sx={{ bgcolor: alpha(color, 0.1), color, borderColor: alpha(color, 0.18) }}
                          variant="outlined"
                        />
                      </Stack>
                    </ListItem>
                    {index < courseWorkload.length - 1 && <Divider />}
                  </React.Fragment>
                );
              })}
            </List>
          </CardContent>
        </Card>
      )}
    </Stack>
  );
};

// ── LecturerTodayPanel ─────────────────────────────────────────────────────

export const LecturerTodayPanel: React.FC<{
  currentDay: string;
  currentMinutes: number;
  sessions: LecturerTimetableSlot[];
}> = ({ currentDay, currentMinutes, sessions }) => {
  const todaySlots = sessions
    .filter((s) => s.day_of_week === currentDay)
    .sort((a, b) => getMinutesFromTime(a.start_time) - getMinutesFromTime(b.start_time));

  return (
    <Stack spacing={2}>
      <div>
        <Typography variant="h6" fontWeight={800}>
          Today
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Your sessions for {currentDay}.
        </Typography>
      </div>
      {todaySlots.length ? (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, minmax(0, 1fr))' },
            gap: 2,
          }}
        >
          {todaySlots.map((slot) => {
            const startMin = getMinutesFromTime(slot.start_time);
            const endMin = getMinutesFromTime(slot.end_time);
            const isLive = currentMinutes >= startMin && currentMinutes < endMin;
            return (
              <LecturerSessionCard
                key={slot.id}
                slot={slot}
                currentDay={currentDay}
                currentMinutes={currentMinutes}
                isLive={isLive}
              />
            );
          })}
        </Box>
      ) : (
        <Alert severity="info" sx={{ borderRadius: 3 }}>
          No sessions scheduled for today ({currentDay}).
        </Alert>
      )}
    </Stack>
  );
};

// ── LecturerWeekPanel ──────────────────────────────────────────────────────

export const LecturerWeekPanel: React.FC<{
  currentDay: string;
  sessions: LecturerTimetableSlot[];
  primaryColor: string;
}> = ({ currentDay, sessions, primaryColor }) => {
  const groupedSlots = sessions.reduce<Record<string, LecturerTimetableSlot[]>>((groups, slot) => {
    const day = slot.day_of_week;
    if (!groups[day]) groups[day] = [];
    groups[day].push(slot);
    return groups;
  }, {});

  DAY_ORDER.forEach((day) => {
    if (groupedSlots[day]) {
      groupedSlots[day].sort(
        (a, b) => getMinutesFromTime(a.start_time) - getMinutesFromTime(b.start_time),
      );
    }
  });

  const activeDays = DAY_ORDER.filter((day) => groupedSlots[day]?.length);

  return (
    <Stack spacing={2}>
      <div>
        <Typography variant="h6" fontWeight={800}>
          This week
        </Typography>
        <Typography variant="body2" color="text.secondary">
          All scheduled sessions grouped by day.
        </Typography>
      </div>
      {activeDays.length ? (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' },
            gap: 2,
          }}
        >
          {activeDays.map((day) => (
            <Card key={day} sx={{ borderRadius: 5 }}>
              <CardContent sx={{ p: 2.5 }}>
                <Stack spacing={1.5}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="subtitle1" fontWeight={800}>
                      {day}
                    </Typography>
                    <Chip label={`${groupedSlots[day].length} classes`} size="small" />
                  </Stack>
                  <Stack spacing={1.2}>
                    {groupedSlots[day].map((slot) => (
                      <Paper
                        key={slot.id}
                        elevation={0}
                        sx={{
                          p: 1.5,
                          borderRadius: 3,
                          border: '1px solid',
                          borderColor: 'divider',
                          backgroundColor: alpha(primaryColor, day === currentDay ? 0.05 : 0.02),
                        }}
                      >
                        <Stack direction="row" justifyContent="space-between" spacing={1.5}>
                          <Typography variant="body2" fontWeight={800}>
                            {slot.course_code} • {slot.course_name}
                          </Typography>
                          <Chip
                            label={formatSessionTypeLabel(slot.session_type)}
                            size="small"
                            color={getSessionTypeChipColor(slot.session_type)}
                          />
                        </Stack>
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          display="block"
                          sx={{ mt: 0.4 }}
                        >
                          {formatTimeRange(slot)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" display="block">
                          {formatLocation(slot.room_number, slot.building)}
                        </Typography>
                      </Paper>
                    ))}
                  </Stack>
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Box>
      ) : (
        <Alert severity="info" sx={{ borderRadius: 3 }}>
          No sessions are currently in your timetable.
        </Alert>
      )}
    </Stack>
  );
};

// ── LecturerSearchPanel ────────────────────────────────────────────────────

export const LecturerSearchPanel: React.FC<{
  sessions: LecturerTimetableSlot[];
  courses: LecturerCourse[];
  searchQuery: string;
  onSearchChange: (value: string) => void;
  primaryColor: string;
}> = ({ sessions, courses, searchQuery, onSearchChange, primaryColor }) => {
  const query = searchQuery.trim().toLowerCase();
  const filteredSessions = query.length >= 2
    ? sessions.filter(
        (s) =>
          s.course_code.toLowerCase().includes(query) ||
          s.course_name.toLowerCase().includes(query) ||
          s.room_number?.toLowerCase().includes(query) ||
          s.building?.toLowerCase().includes(query) ||
          s.day_of_week.toLowerCase().includes(query) ||
          s.session_type?.toLowerCase().includes(query),
      )
    : [];

  const sortedResults = [...filteredSessions].sort(
    (a, b) => getDaySortIndex(a.day_of_week) - getDaySortIndex(b.day_of_week) || getMinutesFromTime(a.start_time) - getMinutesFromTime(b.start_time),
  );

  return (
    <Stack spacing={2}>
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', lg: '1.15fr 0.85fr' },
          gap: 2,
        }}
      >
        <Card sx={{ borderRadius: 5 }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography variant="h6" fontWeight={800}>
              Search your timetable
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
              Search by course code, room, building, day, or session type.
            </Typography>
            <TextField
              fullWidth
              placeholder="Search course, room, building…"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
            />
          </CardContent>
        </Card>

        <Card sx={{ borderRadius: 5 }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography variant="h6" fontWeight={800}>
              Quick stats
            </Typography>
            <Stack spacing={1.2} sx={{ mt: 1.5 }}>
              <Typography variant="body2" color="text.secondary">
                Total sessions: {sessions.length}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Assigned courses: {courses.length}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Days with classes: {DAY_ORDER.filter((d) => sessions.some((s) => s.day_of_week === d)).length}
              </Typography>
            </Stack>
          </CardContent>
        </Card>
      </Box>

      {query.length >= 2 && (
        sortedResults.length ? (
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, minmax(0, 1fr))' },
              gap: 2,
            }}
          >
            {sortedResults.map((slot) => (
              <Card
                key={slot.id}
                sx={{
                  borderRadius: 4,
                  border: '1px solid',
                  borderColor: 'divider',
                  boxShadow: '0 14px 34px rgba(0,0,0,0.05)',
                }}
              >
                <CardContent sx={{ p: 2.25 }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1.5}>
                    <div>
                      <Typography variant="overline" sx={{ letterSpacing: 1.1, color: 'text.secondary' }}>
                        {slot.course_code}
                      </Typography>
                      <Typography variant="subtitle1" fontWeight={800} sx={{ lineHeight: 1.25 }}>
                        {slot.course_name}
                      </Typography>
                    </div>
                    <Chip
                      label={formatSessionTypeLabel(slot.session_type)}
                      size="small"
                      color={getSessionTypeChipColor(slot.session_type)}
                    />
                  </Stack>
                  <Stack spacing={0.8} sx={{ mt: 1.5 }}>
                    <Typography variant="body2" color="text.secondary">
                      {slot.day_of_week} · {formatTimeRange(slot)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {formatLocation(slot.room_number, slot.building)}
                    </Typography>
                  </Stack>
                </CardContent>
              </Card>
            ))}
          </Box>
        ) : (
          <Alert severity="info" sx={{ borderRadius: 3 }}>
            No sessions match "{searchQuery}".
          </Alert>
        )
      )}
    </Stack>
  );
};

// ── LecturerCoursesPanel (includes profile + export) ───────────────────────

export const LecturerCoursesPanel: React.FC<{
  courses: LecturerCourse[];
  courseWorkload: LecturerCourseWorkload[];
  profile: LecturerProfile | null;
  summary: LecturerDashboardSummary | null;
  sessions: LecturerTimetableSlot[];
  exportTimetable: () => void;
}> = ({ courses, courseWorkload, profile, summary, sessions, exportTimetable }) => {
  const workloadMap = Object.fromEntries(
    courseWorkload.map((cw) => [cw.course_id, cw]),
  );

  const weeklyHours = summary?.weekly_load_hours ?? 0;
  const maxHours = summary?.max_hours_per_week ?? 0;
  const totalCourses = summary?.total_courses ?? 0;
  const totalSessions = summary?.total_sessions ?? sessions.length;

  return (
    <Stack spacing={2}>
      <div>
        <Typography variant="h6" fontWeight={800}>
          My courses
        </Typography>
        <Typography variant="body2" color="text.secondary">
          All courses currently assigned to your profile.
        </Typography>
      </div>
      {courses.length ? (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, minmax(0, 1fr))' },
            gap: 2,
          }}
        >
          {courses.map((course, index) => {
            const color = COURSE_PALETTE[index % COURSE_PALETTE.length];
            const cw = workloadMap[course.id];
            return (
              <Card key={course.id} sx={{ borderRadius: 5 }}>
                <CardContent sx={{ p: 2.25 }}>
                  <Stack
                    direction="row"
                    justifyContent="space-between"
                    alignItems="flex-start"
                    spacing={1.5}
                  >
                    <Stack direction="row" spacing={1.5} alignItems="flex-start">
                      <Avatar
                        sx={{
                          bgcolor: color,
                          width: 44,
                          height: 44,
                          fontSize: 13,
                          fontWeight: 800,
                          flexShrink: 0,
                        }}
                      >
                        {course.code?.slice(0, 2)}
                      </Avatar>
                      <Box>
                        <Typography variant="overline" sx={{ letterSpacing: 1.1, color: 'text.secondary' }}>
                          {course.code}
                        </Typography>
                        <Typography variant="subtitle1" fontWeight={800} sx={{ lineHeight: 1.25 }}>
                          {course.name}
                        </Typography>
                      </Box>
                    </Stack>
                    {course.assignment?.session_type && (
                      <Chip label={course.assignment.session_type} size="small" variant="outlined" />
                    )}
                  </Stack>
                  {cw && (
                    <Stack direction="row" spacing={0.75} sx={{ mt: 1.5 }}>
                      <Chip
                        label={`${cw.sessions} session${cw.sessions === 1 ? '' : 's'}`}
                        size="small"
                        variant="outlined"
                      />
                      <Chip
                        label={`${cw.hours.toFixed(1)}h / week`}
                        size="small"
                        sx={{
                          bgcolor: alpha(color, 0.1),
                          color,
                          borderColor: alpha(color, 0.2),
                        }}
                        variant="outlined"
                      />
                    </Stack>
                  )}
                  <LecturerCourseAnnouncements course={course} />
                </CardContent>
              </Card>
            );
          })}
        </Box>
      ) : (
        <Alert severity="info" sx={{ borderRadius: 3 }}>
          No courses are assigned to your profile yet. Contact your coordinator.
        </Alert>
      )}

      {/* Profile + Export */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' },
          gap: 2,
        }}
      >
        <Card sx={{ borderRadius: 5 }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography variant="h6" fontWeight={800}>
              Profile summary
            </Typography>
            <Stack spacing={1.2} sx={{ mt: 1.5 }}>
              <Typography variant="body2" color="text.secondary">
                Name: {profile?.full_name || 'N/A'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Staff number: {profile?.staff_number || 'N/A'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Email: {profile?.email || 'Not set'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Courses assigned: {totalCourses}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Total sessions: {totalSessions}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Weekly load: {weeklyHours.toFixed(1)}h{maxHours > 0 ? ` of ${maxHours}h max` : ''}
              </Typography>
            </Stack>
          </CardContent>
        </Card>

        <Card sx={{ borderRadius: 5 }}>
          <CardContent sx={{ p: 2.5 }}>
            <Typography variant="h6" fontWeight={800}>
              Export
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
              Download your timetable data for offline reference.
            </Typography>
            <Button
              variant="contained"
              startIcon={<DownloadIcon />}
              onClick={exportTimetable}
              fullWidth
              sx={{ py: 1.35, borderRadius: 3 }}
            >
              Download Timetable (JSON)
            </Button>
          </CardContent>
        </Card>
      </Box>
    </Stack>
  );
};
