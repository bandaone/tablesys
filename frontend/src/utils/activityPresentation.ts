import type { SxProps, Theme } from '@mui/material/styles';

export interface ActivityTypeLike {
  key?: string;
  display_name: string;
  color: string;
}

export interface ActivitySlotLike {
  session_type?: string | null;
  activity_type_key?: string | null;
  activity_display_name?: string | null;
  activity_color?: string | null;
}

export interface ActivityPresentation {
  key: string;
  displayName: string;
  color: string;
}

export interface ActivityFilterOption extends ActivityPresentation {
  filterKey: string;
}

const LEGACY_ACTIVITY_PRESETS: Record<string, ActivityPresentation> = {
  lecture: { key: 'lecture', displayName: 'Lecture', color: '#2563EB' },
  tutorial: { key: 'tutorial', displayName: 'Tutorial', color: '#F59E0B' },
  practical: { key: 'practical', displayName: 'Practical', color: '#16A34A' },
};

const LEGACY_ACTIVITY_ALIASES: Record<string, string> = {
  lab: 'practical',
};

const FALLBACK_COLORS = [
  '#2563EB',
  '#16A34A',
  '#F59E0B',
  '#7C3AED',
  '#DC2626',
  '#0891B2',
  '#D97706',
  '#059669',
];

type ActivityInput = string | ActivitySlotLike | ActivityTypeLike | undefined | null;

const isActivityTypeLike = (input: ActivityInput): input is ActivityTypeLike =>
  Boolean(input && typeof input === 'object' && 'display_name' in input);

const isActivitySlotLike = (input: ActivityInput): input is ActivitySlotLike =>
  Boolean(input && typeof input === 'object' && ('activity_type_key' in input || 'session_type' in input || 'activity_display_name' in input));

const toTitleCase = (value: string): string =>
  value
    .split(' ')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');

const slugifyActivityKey = (value: string): string =>
  value
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_')
    .replace(/[^a-z0-9_]/g, '')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');

const fallbackColorForKey = (key: string): string => {
  if (!key) return '#64748B';
  let hash = 0;
  for (let i = 0; i < key.length; i += 1) {
    hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
  }
  return FALLBACK_COLORS[hash % FALLBACK_COLORS.length];
};

const rawActivityKey = (input: ActivityInput): string => {
  if (!input) return '';
  if (typeof input === 'string') return input;
  if (isActivityTypeLike(input)) {
    return String(input.key || '').trim();
  }
  if (isActivitySlotLike(input)) {
    return String(input.activity_type_key || input.session_type || '').trim();
  }
  return '';
};

export const normalizeActivityKey = (input: ActivityInput): string => {
  const slug = slugifyActivityKey(rawActivityKey(input));
  return LEGACY_ACTIVITY_ALIASES[slug] || slug;
};

export const formatActivityKeyLabel = (key: string): string => {
  if (!key) return 'Session';
  return toTitleCase(key.replace(/[_-]+/g, ' '));
};

export const buildActivityTypesMap = (
  activityTypes: ActivityTypeLike[],
): Record<string, ActivityTypeLike> =>
  activityTypes.reduce<Record<string, ActivityTypeLike>>((acc, activityType) => {
    const normalizedKey = normalizeActivityKey(activityType.key);
    if (normalizedKey) {
      acc[normalizedKey] = {
        ...activityType,
        key: normalizedKey,
      };
    }
    return acc;
  }, {});

export const resolveActivityPresentation = (
  input: ActivityInput,
  activityTypesMap?: Record<string, ActivityTypeLike>,
): ActivityPresentation => {
  const normalizedKey = normalizeActivityKey(input);
  const slotLike = isActivitySlotLike(input) ? input : undefined;
  const typeLike = isActivityTypeLike(input) ? input : undefined;
  const mapped = normalizedKey ? activityTypesMap?.[normalizedKey] : undefined;
  const legacy = normalizedKey ? LEGACY_ACTIVITY_PRESETS[normalizedKey] : undefined;

  const displayName =
    slotLike?.activity_display_name?.trim() ||
    typeLike?.display_name?.trim() ||
    mapped?.display_name?.trim() ||
    legacy?.displayName ||
    formatActivityKeyLabel(normalizedKey);

  const color =
    slotLike?.activity_color?.trim() ||
    typeLike?.color?.trim() ||
    mapped?.color?.trim() ||
    legacy?.color ||
    fallbackColorForKey(normalizedKey);

  return {
    key: normalizedKey || 'session',
    displayName,
    color,
  };
};

export const activityChipSx = (
  input: ActivityInput,
  activityTypesMap?: Record<string, ActivityTypeLike>,
): SxProps<Theme> => {
  const presentation = resolveActivityPresentation(input, activityTypesMap);
  return {
    color: presentation.color,
    bgcolor: `${presentation.color}1a`,
    border: '1px solid',
    borderColor: `${presentation.color}55`,
    fontWeight: 600,
  };
};

export const matchesActivityFilter = (
  input: ActivityInput,
  filter: string,
  activityTypesMap?: Record<string, ActivityTypeLike>,
): boolean => {
  if (filter === 'all') return true;
  return resolveActivityPresentation(input, activityTypesMap).key === filter;
};

export const buildActivityFilterOptions = ({
  activityTypes = [],
  sessionInputs = [],
}: {
  activityTypes?: ActivityTypeLike[];
  sessionInputs?: ActivityInput[];
}): ActivityFilterOption[] => {
  const byKey = new Map<string, ActivityFilterOption>();

  activityTypes.forEach((activityType) => {
    const presentation = resolveActivityPresentation(activityType, buildActivityTypesMap(activityTypes));
    byKey.set(presentation.key, { ...presentation, filterKey: presentation.key });
  });

  sessionInputs.forEach((input) => {
    const presentation = resolveActivityPresentation(input, buildActivityTypesMap(activityTypes));
    if (presentation.key && !byKey.has(presentation.key)) {
      byKey.set(presentation.key, { ...presentation, filterKey: presentation.key });
    }
  });

  if (byKey.size === 0) {
    Object.values(LEGACY_ACTIVITY_PRESETS).forEach((activity) => {
      byKey.set(activity.key, { ...activity, filterKey: activity.key });
    });
  }

  return [
    { key: 'all', filterKey: 'all', displayName: 'All sessions', color: '#64748B' },
    ...Array.from(byKey.values()).sort((a, b) => a.displayName.localeCompare(b.displayName)),
  ];
};
