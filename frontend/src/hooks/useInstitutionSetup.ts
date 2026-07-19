// ─────────────────────────────────────────────────────────────────────────────
//  useInstitutionSetup
//  Fetches the tenant's activity types once per session and exposes them
//  as a stable typed list.  All consumers (CoursesPage, TimetablesPage,
//  TimetableViewPage, DashboardPage, TimetableCell) import this hook so
//  the network call happens only once.
// ─────────────────────────────────────────────────────────────────────────────
import { useState, useEffect } from 'react';
import { institutionSetupAPI } from '../api';

export interface ActivityType {
  id: number;
  key: string;
  display_name: string;
  color: string;
  default_duration_periods: number;
  default_frequency_per_week: number;
  requires_subgroups: boolean;
  resource_tags_required: string[];
  counts_toward_contact_hours: boolean;
  is_active: boolean;
}

// Derive a consistent set of cell colours from an ActivityType's hex colour.
// The intent is to match the existing SESSION_COLOR_MAP pattern used in
// TimetableCell (light pastel bg, medium border, dark text).
export function activityTypeColors(hex: string): {
  bg: string;
  border: string;
  text: string;
} {
  const safe = hex?.startsWith('#') ? hex : '#3B82F6';
  return {
    bg: `${safe}1a`,      // ~10 % opacity
    border: `${safe}88`,  // ~53 % opacity
    text: safe,           // full colour for text / icon
  };
}

interface UseInstitutionSetupReturn {
  activityTypes: ActivityType[];
  /** Keyed by activity key for O(1) look‑ups */
  activityTypesByKey: Record<string, ActivityType>;
  loading: boolean;
}

const cache: { data: ActivityType[] | null } = { data: null };

export function useInstitutionSetup(): UseInstitutionSetupReturn {
  const [activityTypes, setActivityTypes] = useState<ActivityType[]>(
    cache.data ?? [],
  );
  const [loading, setLoading] = useState(!cache.data);

  useEffect(() => {
    if (cache.data) return;

    let cancelled = false;
    const load = async () => {
      try {
        const res = await institutionSetupAPI.getCurrent();
        const types: ActivityType[] = (res.activity_types ?? []).filter(
          (t: ActivityType) => t.is_active,
        );
        cache.data = types;
        if (!cancelled) {
          setActivityTypes(types);
        }
      } catch {
        // Non‑fatal — pages fall back to hardcoded defaults.
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const activityTypesByKey = activityTypes.reduce<Record<string, ActivityType>>(
    (acc, t) => {
      acc[t.key] = t;
      return acc;
    },
    {},
  );

  return { activityTypes, activityTypesByKey, loading };
}
