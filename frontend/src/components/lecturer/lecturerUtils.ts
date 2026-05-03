/**
 * Lecturer Portal utility constants and functions.
 *
 * Kept separate from LecturerPortalPanels.tsx so that file contains ONLY
 * React component exports — a requirement for Vite Fast Refresh to work
 * correctly (mixing component and non-component exports breaks HMR).
 */

export const DAY_ORDER = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
] as const;

export type LecturerPortalTab = 'home' | 'today' | 'week' | 'search' | 'courses';

export const formatDayLabel = (day: string | number | undefined): string => {
  if (day === undefined || day === null) return '';
  const n = Number(day);
  if (!isNaN(n) && n >= 0 && n <= 6) return DAY_ORDER[n];
  const s = String(day).trim();
  if (s.length <= 2 || /^\d+$/.test(s)) return '';
  return s;
};

export const getDaySortIndex = (day: string): number => {
  const index = DAY_ORDER.indexOf(day as (typeof DAY_ORDER)[number]);
  return index === -1 ? 999 : index;
};

export const getMinutesFromTime = (value: string): number => {
  const [hours, minutes] = value.split(':').map(Number);
  return hours * 60 + minutes;
};

export const normalizeSessionType = (value?: string): 'lecture' | 'tutorial' | 'lab' => {
  const normalized = (value || '').toLowerCase();
  if (normalized.includes('lab')) return 'lab';
  if (normalized.includes('tutorial')) return 'tutorial';
  return 'lecture';
};

export const getSessionTypeChipColor = (
  value?: string,
): 'primary' | 'secondary' | 'success' | 'warning' => {
  switch (normalizeSessionType(value)) {
    case 'lab':
      return 'success';
    case 'tutorial':
      return 'warning';
    default:
      return 'primary';
  }
};

export const formatSessionTypeLabel = (value?: string): string => {
  const n = normalizeSessionType(value);
  return n.charAt(0).toUpperCase() + n.slice(1);
};

export const formatDuration = (minutes: number): string => {
  if (minutes <= 0) return 'Now';
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder === 0 ? `${hours} hr` : `${hours} hr ${remainder} min`;
};

export const formatTimeRange = (slot: { start_time: string; end_time: string }): string =>
  `${slot.start_time} - ${slot.end_time}`;
