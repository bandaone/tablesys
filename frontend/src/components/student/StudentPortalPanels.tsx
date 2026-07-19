import React from 'react';
import {
  AccessTime as AccessTimeIcon,
  CalendarMonth as CalendarMonthIcon,
  Download as DownloadIcon,
  PlaceOutlined as PlaceOutlinedIcon,
} from '@mui/icons-material';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Collapse,
  Divider,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Paper,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import { alpha, type SxProps, type Theme } from '@mui/material/styles';
import type { Course, FreeRoomsData, LookupDetail, LookupResult, TimetableSlot } from './types';

/** Sanitize room display — hides missing/zero/TBA values gracefully */
const formatLocation = (room: string | number | undefined, building: string | number | undefined): string => {
  const clean = (v: any) => {
    const s = String(v ?? '').trim();
    return s === '' || s === '0' || s.toLowerCase() === 'tba' || s.toLowerCase() === 'null' ? null : s;
  };
  const r = clean(room);
  const b = clean(building);
  if (!r && !b) return 'Venue TBA';
  if (!r) return b!;
  if (!b) return r;
  return `${r} · ${b}`;
};

const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

/** Convert numeric day index (0-6) to a proper day name; pass valid strings through */
const formatDayLabel = (day: string | number | undefined): string => {
  if (day === undefined || day === null) return '';
  const n = Number(day);
  if (!isNaN(n) && n >= 0 && n <= 6) return DAY_NAMES[n];
  const s = String(day).trim();
  if (s.length <= 2 || /^\d+$/.test(s)) return ''; // Discard garbage numeric values
  return s;
};

export type SessionFilter = string;

interface SessionCardProps {
  slot: TimetableSlot;
  currentDay: string;
  currentMinutes: number;
  formatTimeRange: (slot: TimetableSlot) => string;
  getSessionTone: (
    slot: TimetableSlot,
    currentDay: string,
    currentMinutes: number,
  ) => { label: string; color: 'success' | 'warning' | 'default' };
  formatSessionTypeLabel: (value?: string) => string;
  getSessionTypeChipSx: (slot: TimetableSlot) => SxProps<Theme>;
}

export const StudentSessionCard: React.FC<SessionCardProps> = ({
  slot,
  currentDay,
  currentMinutes,
  formatTimeRange,
  getSessionTone,
  formatSessionTypeLabel,
  getSessionTypeChipSx,
}) => {
  const tone = getSessionTone(slot, currentDay, currentMinutes);

  return (
    <Card
      sx={{
        borderRadius: 4,
        border: '1px solid',
        borderColor: 'divider',
        boxShadow: '0 14px 34px rgba(0,0,0,0.05)',
      }}
    >
      <CardContent sx={{ p: 2.25 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1.5}>
          <BoxText code={slot.course_code} title={slot.course_name} />
          <Stack spacing={0.8} alignItems="flex-end">
            <Chip label={tone.label} color={tone.color} size="small" />
            <Chip
              label={formatSessionTypeLabel(slot.activity_display_name || slot.activity_type_key || slot.session_type)}
              sx={getSessionTypeChipSx(slot)}
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
          <Typography variant="body2" color="text.secondary">
            {slot.lecturer_name}
          </Typography>
        </Stack>
      </CardContent>
    </Card>
  );
};

const BoxText: React.FC<{ code: string; title: string }> = ({ code, title }) => (
  <div>
    <Typography variant="overline" sx={{ letterSpacing: 1.1, color: 'text.secondary' }}>
      {code}
    </Typography>
    <Typography variant="subtitle1" fontWeight={800} sx={{ lineHeight: 1.25 }}>
      {title}
    </Typography>
  </div>
);

export const StudentQuickActionCard: React.FC<{
  label: string;
  helper: string;
  onClick: () => void;
}> = ({ label, helper, onClick }) => (
  <Button
    onClick={onClick}
    variant="outlined"
    sx={{
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      textAlign: 'left',
      borderRadius: 3,
      p: 1.5,
      minHeight: 88,
      textTransform: 'none',
    }}
    fullWidth
  >
    <div>
      <Typography variant="body2" fontWeight={700}>
        {label}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        {helper}
      </Typography>
    </div>
  </Button>
);

export const SessionFilterChips: React.FC<{
  filters: SessionFilter[];
  activeFilter: SessionFilter;
  onChange: (filter: SessionFilter) => void;
  getFilterLabel: (filter: SessionFilter) => string;
  getFilterChipSx: (filter: SessionFilter) => SxProps<Theme>;
}> = ({ filters, activeFilter, onChange, getFilterLabel, getFilterChipSx }) => (
  <Stack direction="row" spacing={1} sx={{ overflowX: 'auto', pb: 0.5 }}>
    {filters.map((filter) => (
      <Chip
        key={filter}
        label={getFilterLabel(filter)}
        sx={activeFilter === filter ? getFilterChipSx(filter) : undefined}
        variant={activeFilter === filter ? 'filled' : 'outlined'}
        onClick={() => onChange(filter)}
        clickable
      />
    ))}
  </Stack>
);

export const StudentHomePanel: React.FC<{
  currentSlot: TimetableSlot | null;
  nextSlot: TimetableSlot | null;
  gapUntilNext: number | null;
  weeklyHours: number;
  firstTodaySlot: TimetableSlot | null;
  lastTodaySlot: TimetableSlot | null;
  currentDay: string;
  currentMinutes: number;
  formatDuration: (minutes: number) => string;
  formatTimeRange: (slot: TimetableSlot) => string;
  exportTimetable: () => void;
  openSearchWithPreset: (query: string) => void;
  setActiveTab: (tab: 'today' | 'week' | 'more' | 'search') => void;
}> = ({
  currentSlot,
  nextSlot,
  gapUntilNext,
  weeklyHours,
  firstTodaySlot,
  lastTodaySlot,
  currentDay,
  currentMinutes,
  formatDuration,
  formatTimeRange,
  exportTimetable,
  openSearchWithPreset,
  setActiveTab,
}) => (
  <Stack spacing={2.2}>
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' },
        gap: 2,
      }}
    >
    <Card sx={{ borderRadius: 5, minHeight: { md: 250 } }}>
      <CardContent sx={{ p: 2.5 }}>
        <Stack spacing={1.8}>
          <div>
            <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: 1.1 }}>
              NOW
            </Typography>
            {currentSlot ? (
              <>
                <Typography variant="h6" fontWeight={800}>
                  {currentSlot.course_code}
                </Typography>
                <Typography variant="body1" color="text.secondary">
                  {currentSlot.course_name}
                </Typography>
              </>
            ) : (
              <>
                <Typography variant="h6" fontWeight={800}>
                  No class right now
                </Typography>
                <Typography variant="body1" color="text.secondary">
                  {gapUntilNext 
                    ? `Free for the next ${formatDuration(gapUntilNext)}` 
                    : nextSlot && nextSlot.day_of_week !== currentDay 
                      ? 'Free for the rest of today.' 
                      : 'You are free at the moment.'}
                </Typography>
              </>
            )}
          </div>

          {currentSlot ? (
            <Stack spacing={1.2}>
              <Stack direction="row" spacing={1} alignItems="center">
                <AccessTimeIcon fontSize="small" color="primary" />
                <Typography variant="body2">{formatTimeRange(currentSlot)}</Typography>
              </Stack>
              <Stack direction="row" spacing={1} alignItems="center">
                <PlaceOutlinedIcon fontSize="small" color="primary" />
                <Typography variant="body2">
                    {formatLocation(currentSlot.room_number, currentSlot.building)}
                  </Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary">
                {currentSlot.lecturer_name}
              </Typography>
            </Stack>
          ) : (
            <Alert severity="info" sx={{ borderRadius: 3 }}>
              No live class at the moment. Your next session appears below if one is scheduled.
            </Alert>
          )}
        </Stack>
      </CardContent>
    </Card>

    <Card sx={{ borderRadius: 5, minHeight: { md: 250 } }}>
      <CardContent sx={{ p: 2.5 }}>
        <Stack spacing={1.6}>
          <div>
            <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: 1.1 }}>
              NEXT
            </Typography>
            {nextSlot ? (
              <>
                <Typography variant="h6" fontWeight={800}>
                  {nextSlot.course_code}
                </Typography>
                <Typography variant="body1" color="text.secondary">
                  {nextSlot.course_name}
                </Typography>
              </>
            ) : (
              <>
                <Typography variant="h6" fontWeight={800}>
                  Nothing else scheduled
                </Typography>
                <Typography variant="body1" color="text.secondary">
                  Your timetable has no upcoming session right now.
                </Typography>
              </>
            )}
          </div>

          {nextSlot && (
            <>
              <Stack direction="row" spacing={1} alignItems="center">
                <CalendarMonthIcon fontSize="small" color="primary" />
                <Typography variant="body2">
                  {formatDayLabel(nextSlot.day_of_week) ? `${formatDayLabel(nextSlot.day_of_week)} · ` : ''}{formatTimeRange(nextSlot)}
                </Typography>
              </Stack>
              <Stack direction="row" spacing={1} alignItems="center">
                <PlaceOutlinedIcon fontSize="small" color="primary" />
                <Typography variant="body2">
                    {formatLocation(nextSlot.room_number, nextSlot.building)}
                  </Typography>
              </Stack>
              <Typography variant="body2" color="text.secondary">
                {nextSlot.lecturer_name}
              </Typography>
            </>
          )}
        </Stack>
      </CardContent>
    </Card>
    </Box>

    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: '1.4fr 1fr' },
        gap: 2,
      }}
    >
    <Card sx={{ borderRadius: 5 }}>
      <CardContent sx={{ p: 2.5 }}>
        <Typography variant="h6" fontWeight={800}>
          Today insights
        </Typography>
        <Stack spacing={1.2} sx={{ mt: 1.5 }}>
          <Typography variant="body2" color="text.secondary">
            Weekly contact hours: {weeklyHours ? weeklyHours.toFixed(1) : '0.0'}h
          </Typography>
          <Typography variant="body2" color="text.secondary">
            First class: {firstTodaySlot ? `${formatTimeRange(firstTodaySlot)} · ${firstTodaySlot.course_code}` : 'No class today'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Last class: {lastTodaySlot ? `${formatTimeRange(lastTodaySlot)} · ${lastTodaySlot.course_code}` : 'No class today'}
          </Typography>
        </Stack>
      </CardContent>
    </Card>

    <Card sx={{ borderRadius: 5 }}>
      <CardContent sx={{ p: 2.5 }}>
        <Typography variant="h6" fontWeight={800}>
          Quick actions
        </Typography>
        <Stack spacing={1.1} sx={{ mt: 1.4 }}>
          <StudentQuickActionCard
            label="Open Today"
            helper="View current day sessions"
            onClick={() => setActiveTab('today')}
          />
          <StudentQuickActionCard
            label="Open Week"
            helper="Browse the full week layout"
            onClick={() => setActiveTab('week')}
          />
          <StudentQuickActionCard
            label="Search Rooms/Lecturers"
            helper="Find free rooms and people"
            onClick={() => openSearchWithPreset('')}
          />
          <StudentQuickActionCard
            label="Download Offline Copy"
            helper="Export current timetable JSON"
            onClick={exportTimetable}
          />
        </Stack>
      </CardContent>
    </Card>
    </Box>
  </Stack>
);

export const StudentTodayPanel: React.FC<{
  currentDay: string;
  filters: SessionFilter[];
  todayFilter: SessionFilter;
  onFilterChange: (filter: SessionFilter) => void;
  filteredTodaySlots: TimetableSlot[];
  currentMinutes: number;
  formatTimeRange: (slot: TimetableSlot) => string;
  getSessionTone: SessionCardProps['getSessionTone'];
  formatSessionTypeLabel: SessionCardProps['formatSessionTypeLabel'];
  getSessionTypeChipSx: SessionCardProps['getSessionTypeChipSx'];
  getFilterLabel: (filter: SessionFilter) => string;
  getFilterChipSx: (filter: SessionFilter) => SxProps<Theme>;
}> = ({
  currentDay,
  filters,
  todayFilter,
  onFilterChange,
  filteredTodaySlots,
  currentMinutes,
  formatTimeRange,
  getSessionTone,
  formatSessionTypeLabel,
  getSessionTypeChipSx,
  getFilterLabel,
  getFilterChipSx,
}) => (
  <Stack spacing={2}>
    <div>
      <Typography variant="h6" fontWeight={800}>
        Today
      </Typography>
      <Typography variant="body2" color="text.secondary">
        Your sessions for {currentDay}.
      </Typography>
    </div>

    <SessionFilterChips
      filters={filters}
      activeFilter={todayFilter}
      onChange={onFilterChange}
      getFilterLabel={getFilterLabel}
      getFilterChipSx={getFilterChipSx}
    />

    {filteredTodaySlots.length ? (
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, minmax(0, 1fr))' },
          gap: 2,
        }}
      >
        {filteredTodaySlots.map((slot) => (
          <StudentSessionCard
            key={slot.id}
            slot={slot}
            currentDay={currentDay}
            currentMinutes={currentMinutes}
            formatTimeRange={formatTimeRange}
            getSessionTone={getSessionTone}
            formatSessionTypeLabel={formatSessionTypeLabel}
            getSessionTypeChipSx={getSessionTypeChipSx}
          />
        ))}
      </Box>
    ) : (
      <Alert severity="info" sx={{ borderRadius: 3 }}>
        No {todayFilter === 'all' ? '' : `${getFilterLabel(todayFilter)} `}sessions scheduled for today.
      </Alert>
    )}
  </Stack>
);

export const StudentWeekPanel: React.FC<{
  currentDay: string;
  filters: SessionFilter[];
  weekFilter: SessionFilter;
  onFilterChange: (filter: SessionFilter) => void;
  filteredWeekGroups: Record<string, TimetableSlot[]>;
  dayOrder: string[];
  formatTimeRange: (slot: TimetableSlot) => string;
  formatSessionTypeLabel: (value?: string) => string;
  getSessionTypeChipSx: (slot: TimetableSlot) => SxProps<Theme>;
  getFilterLabel: (filter: SessionFilter) => string;
  getFilterChipSx: (filter: SessionFilter) => SxProps<Theme>;
  primaryColor: string;
}> = ({
  currentDay,
  filters,
  weekFilter,
  onFilterChange,
  filteredWeekGroups,
  dayOrder,
  formatTimeRange,
  formatSessionTypeLabel,
  getSessionTypeChipSx,
  getFilterLabel,
  getFilterChipSx,
  primaryColor,
}) => (
  <Stack spacing={2}>
    <div>
      <Typography variant="h6" fontWeight={800}>
        This week
      </Typography>
      <Typography variant="body2" color="text.secondary">
        The complete week view
      </Typography>
    </div>

    <SessionFilterChips
      filters={filters}
      activeFilter={weekFilter}
      onChange={onFilterChange}
      getFilterLabel={getFilterLabel}
      getFilterChipSx={getFilterChipSx}
    />

    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' },
        gap: 2,
      }}
    >
      {dayOrder.filter((day) => filteredWeekGroups[day]?.length).map((day) => (
        <Card key={day} sx={{ borderRadius: 5 }}>
          <CardContent sx={{ p: 2.5 }}>
            <Stack spacing={1.5}>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography variant="subtitle1" fontWeight={800}>
                  {day}
                </Typography>
                <Chip label={`${filteredWeekGroups[day].length} classes`} size="small" />
              </Stack>
              <Stack spacing={1.2}>
                {filteredWeekGroups[day].map((slot) => (
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
                        label={formatSessionTypeLabel(slot.activity_display_name || slot.activity_type_key || slot.session_type)}
                        size="small"
                        sx={getSessionTypeChipSx(slot)}
                      />
                    </Stack>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.4 }}>
                      {formatTimeRange(slot)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" display="block">
                      {formatLocation(slot.room_number, slot.building)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {slot.lecturer_name}
                    </Typography>
                  </Paper>
                ))}
              </Stack>
            </Stack>
          </CardContent>
        </Card>
      ))}
    </Box>
  </Stack>
);

export const StudentSearchPanel: React.FC<{
  searchQuery: string;
  onSearchChange: (value: string) => void;
  searchLoading: boolean;
  searchResults: LookupResult[];
  onSelectLookup: (result: LookupResult) => void;
  selectedLookup: LookupDetail | null;
  getLookupChipColor: (type: LookupResult['type']) => 'primary' | 'secondary' | 'success' | 'warning';
  primaryColor: string;
  secondaryColor: string;
  formatTimeRange: (slot: TimetableSlot) => string;
  freeRoomsData: FreeRoomsData | null;
  freeRoomsLoading: boolean;
  freeRoomsSource: string | null;
}> = ({
  searchQuery,
  onSearchChange,
  searchLoading,
  searchResults,
  onSelectLookup,
  selectedLookup,
  getLookupChipColor,
  primaryColor,
  secondaryColor,
  formatTimeRange,
  freeRoomsData,
  freeRoomsLoading,
  freeRoomsSource,
}) => (
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
            Search timetable entities
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
            Search lecturer, room, course, or group and check availability immediately.
          </Typography>
          <TextField
            fullWidth
            placeholder="Search lecturer, room, course, or group"
            value={searchQuery}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </CardContent>
      </Card>

      <Card sx={{ borderRadius: 5 }}>
        <CardContent sx={{ p: 2.5 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <div>
              <Typography variant="h6" fontWeight={800}>
                Free rooms now
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Quick campus availability snapshot.
              </Typography>
            </div>
            {freeRoomsSource && <Chip label={freeRoomsSource === 'network' ? 'Live' : 'Cached'} size="small" />}
          </Stack>

          {freeRoomsLoading ? (
            <CircularProgress sx={{ mt: 2 }} />
          ) : freeRoomsData ? (
            <Stack spacing={1} sx={{ mt: 2 }}>
              <Typography variant="caption" color="text.secondary">
                {freeRoomsData.free_rooms.length} free out of {freeRoomsData.total_rooms} rooms checked.
              </Typography>
              {freeRoomsData.free_rooms.slice(0, 6).map((room) => (
                <Paper key={room.id} elevation={0} sx={{ p: 1.25, borderRadius: 3, border: '1px solid', borderColor: 'divider' }}>
                  <Typography variant="body2" fontWeight={700}>
                    {room.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {room.building} • Capacity {room.capacity}
                  </Typography>
                </Paper>
              ))}
            </Stack>
          ) : (
            <Alert severity="info" sx={{ mt: 2, borderRadius: 3 }}>
              Free room availability is not available right now.
            </Alert>
          )}
        </CardContent>
      </Card>
    </Box>

    {searchLoading && <CircularProgress sx={{ alignSelf: 'center' }} />}

    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' },
        gap: 2,
        alignItems: 'start',
      }}
    >
      {!searchLoading && searchQuery.trim().length >= 2 && (
        <Stack spacing={1.25}>
          {searchResults.length ? (
            searchResults.map((result) => (
              <Card key={`${result.type}-${result.id}`} sx={{ borderRadius: 4, cursor: 'pointer' }} onClick={() => onSelectLookup(result)}>
                <CardContent sx={{ p: 2 }}>
                  <Stack direction="row" justifyContent="space-between" spacing={1.5}>
                    <div>
                      <Typography variant="body1" fontWeight={800}>
                        {result.title}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {result.subtitle}
                      </Typography>
                      {result.meta && (
                        <Typography variant="caption" color="text.secondary">
                          {result.meta}
                        </Typography>
                      )}
                    </div>
                    <Chip label={result.type} color={getLookupChipColor(result.type)} size="small" />
                  </Stack>
                </CardContent>
              </Card>
            ))
          ) : (
            <Alert severity="info" sx={{ borderRadius: 3 }}>
              No matches found for that search.
            </Alert>
          )}
        </Stack>
      )}

      {selectedLookup && (
        <Card sx={{ borderRadius: 5 }}>
          <CardContent sx={{ p: 2.5 }}>
            <Stack spacing={1.4}>
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1.5}>
                <div>
                  <Typography variant="h6" fontWeight={800}>
                    {selectedLookup.entity.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {selectedLookup.entity.subtitle}
                  </Typography>
                  {selectedLookup.entity.meta && (
                    <Typography variant="caption" color="text.secondary">
                      {selectedLookup.entity.meta}
                    </Typography>
                  )}
                </div>
                <Chip
                  label={selectedLookup.availability.is_busy_now ? 'Busy now' : 'Free now'}
                  color={selectedLookup.availability.is_busy_now ? 'warning' : 'success'}
                  size="small"
                />
              </Stack>

              {selectedLookup.availability.current_session ? (
                <Paper elevation={0} sx={{ p: 1.5, borderRadius: 3, bgcolor: alpha(primaryColor, 0.06) }}>
                  <Typography variant="caption" color="text.secondary">
                    Current session
                  </Typography>
                  <Typography variant="body2" fontWeight={700}>
                    {selectedLookup.availability.current_session.course_code} • {selectedLookup.availability.current_session.course_name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {formatDayLabel(selectedLookup.availability.current_session.day_of_week) ? `${formatDayLabel(selectedLookup.availability.current_session.day_of_week)} · ` : ''}{formatTimeRange(selectedLookup.availability.current_session)}
                  </Typography>
                </Paper>
              ) : (
                <Alert severity="success" sx={{ borderRadius: 3 }}>
                  Nothing is scheduled right now for this selection.
                </Alert>
              )}

              {selectedLookup.availability.next_session && (
                <Paper elevation={0} sx={{ p: 1.5, borderRadius: 3, bgcolor: alpha(secondaryColor, 0.1) }}>
                  <Typography variant="caption" color="text.secondary">
                    Next session
                  </Typography>
                  <Typography variant="body2" fontWeight={700}>
                    {selectedLookup.availability.next_session.course_code} • {selectedLookup.availability.next_session.course_name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {formatDayLabel(selectedLookup.availability.next_session.day_of_week) ? `${formatDayLabel(selectedLookup.availability.next_session.day_of_week)} · ` : ''}{formatTimeRange(selectedLookup.availability.next_session)}
                  </Typography>
                </Paper>
              )}
            </Stack>
          </CardContent>
        </Card>
      )}
    </Box>
  </Stack>
);

export const StudentMorePanel: React.FC<{
  timetableGroup: string;
  timetableSemester?: string;
  timetableDepartment?: string;
  lastSyncedAt: string | null;
  weeklyHours: number;
  remindersEnabled: boolean;
  reminderMinutes: number;
  onReminderToggle: () => void;
  onReminderMinutesChange: (minutes: number) => void;
  courses: Course[];
  exportTimetable: () => void;
  exportCalendar: () => void;
}> = ({
  timetableGroup,
  timetableSemester,
  timetableDepartment,
  lastSyncedAt,
  weeklyHours,
  remindersEnabled,
  reminderMinutes,
  onReminderToggle,
  onReminderMinutesChange,
  courses,
  exportTimetable,
  exportCalendar,
}) => (
  <Stack spacing={2}>
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
            Timetable status
          </Typography>
          <Stack spacing={1.2} sx={{ mt: 1.5 }}>
            <Typography variant="body2" color="text.secondary">
              Group: {timetableGroup || 'Not assigned'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Semester: {timetableSemester || 'Not available'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Department: {timetableDepartment || 'Not available'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Last synced: {lastSyncedAt || 'Waiting for sync'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Weekly contact hours: {weeklyHours ? weeklyHours.toFixed(1) : '0.0'}h
            </Typography>
          </Stack>
        </CardContent>
      </Card>

      <Card sx={{ borderRadius: 5 }}>
        <CardContent sx={{ p: 2.5 }}>
          <Typography variant="h6" fontWeight={800}>
            Reminder settings
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
            Device reminders help with your next same-day class while this portal is open.
          </Typography>

          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ 
            p: 1.5, 
            borderRadius: 3, 
            bgcolor: alpha('#ffffff', 0.03),
            border: '1px solid',
            borderColor: 'divider'
          }}>
            <div>
              <Typography variant="subtitle2" fontWeight={700}>Enable reminders</Typography>
              <Typography variant="caption" color="text.secondary">Get notified before class</Typography>
            </div>
            <Switch checked={remindersEnabled} onChange={onReminderToggle} color="primary" />
          </Stack>

          <Collapse in={remindersEnabled}>
            <Stack sx={{ mt: 1.5 }}>
              <TextField
                select
                label="Lead time"
                value={String(reminderMinutes)}
                onChange={(event) => onReminderMinutesChange(Number(event.target.value))}
                size="small"
                fullWidth
                sx={{
                  '& .MuiOutlinedInput-root': { borderRadius: 3 }
                }}
              >
                {[10, 15, 30].map((minutes) => (
                  <MenuItem key={minutes} value={String(minutes)}>
                    {minutes} minutes before
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
          </Collapse>
        </CardContent>
      </Card>
    </Box>

    <Card sx={{ borderRadius: 5 }}>
      <CardContent sx={{ p: 2.5 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
          <Typography variant="h6" fontWeight={800}>
            My courses
          </Typography>
          <Chip label={courses.length} size="small" />
        </Stack>
        {courses.length ? (
          <List disablePadding>
            {courses.map((course, index) => (
              <React.Fragment key={course.id}>
                <ListItem disableGutters sx={{ py: 1.1 }}>
                  <ListItemText
                    primary={
                      <Typography variant="body2" fontWeight={700}>
                        {course.code} • {course.name}
                      </Typography>
                    }
                    secondary={
                      <>
                        <Typography variant="caption" color="text.secondary" display="block">
                          {course.credit_hours} credit hours • {course.course_type.replace('_', ' ')}
                        </Typography>
                        {course.lecturer?.name && (
                          <Typography variant="caption" color="text.secondary">
                            {course.lecturer.name}
                          </Typography>
                        )}
                      </>
                    }
                  />
                </ListItem>
                {index < courses.length - 1 && <Divider />}
              </React.Fragment>
            ))}
          </List>
        ) : (
          <Alert severity="info" sx={{ borderRadius: 3 }}>
            No courses available for your current profile.
          </Alert>
        )}
      </CardContent>
    </Card>

    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.25}>
      <Button variant="contained" startIcon={<DownloadIcon />} onClick={exportTimetable} sx={{ py: 1.35, flex: 1 }}>
        Download Offline Copy
      </Button>
      <Button variant="outlined" startIcon={<CalendarMonthIcon />} onClick={exportCalendar} sx={{ py: 1.35, flex: 1 }}>
        Export Calendar
      </Button>
    </Stack>
  </Stack>
);

export const StudentExamsPanel: React.FC<{
  loading: boolean;
  exams: any[];
  period: any;
}> = ({ loading, exams, period }) => {
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!period) {
    return (
      <Alert severity="info" sx={{ borderRadius: 3 }}>
        No published exam timetable is currently available.
      </Alert>
    );
  }

  return (
    <Stack spacing={2}>
      <div>
        <Typography variant="h6" fontWeight={800}>
          {period.name}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {new Date(period.start_date).toLocaleDateString()} - {new Date(period.end_date).toLocaleDateString()}
        </Typography>
      </div>

      {exams.length === 0 ? (
        <Alert severity="info" sx={{ borderRadius: 3 }}>
          You have no exams scheduled in this period.
        </Alert>
      ) : (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, minmax(0, 1fr))' },
            gap: 2,
          }}
        >
          {exams.map((exam) => (
            <Card
              key={exam.id}
              sx={{
                borderRadius: 4,
                border: '1px solid',
                borderColor: 'divider',
                boxShadow: '0 14px 34px rgba(0,0,0,0.05)',
              }}
            >
              <CardContent sx={{ p: 2.25 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1.5}>
                  <BoxText code={exam.paper_code} title={exam.course_name || exam.paper_name} />
                  <Chip label={exam.day_of_week} color="primary" size="small" />
                </Stack>

                <Stack spacing={1.2} sx={{ mt: 1.8 }}>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <CalendarMonthIcon fontSize="small" color="primary" />
                    <Typography variant="body2">{new Date(exam.exam_date).toLocaleDateString()} • {exam.start_time} - {exam.end_time}</Typography>
                  </Stack>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <PlaceOutlinedIcon fontSize="small" color="primary" />
                    <Typography variant="body2">
                      {exam.rooms.join(', ')}
                    </Typography>
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    Invigilator: {exam.chief_invigilator}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Duration: {exam.duration_minutes} min
                  </Typography>
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Box>
      )}
    </Stack>
  );
};
