import axios from 'axios';

/**
 * Student Portal API — Anonymous (No-Login) Access
 *
 * All calls go to /api/v1/mobile/public/* and require a `group_id`
 * query parameter.  The group_id is stored in localStorage after the
 * student completes the onboarding wizard.
 *
 * JWT tokens are NOT used — no Authorization header is injected.
 */

const STUDENT_API_BASE_URL = '/api/v1';
const GROUP_ID_KEY = 'student_selected_group_id';
const VIEWER_ID_KEY = 'student_public_viewer_id';
const LAB_SUBGROUPS_KEY = 'student_selected_lab_subgroups';
const ACADEMIC_WEEK_KEY = 'student_academic_week';

const studentApi = axios.create({
  baseURL: STUDENT_API_BASE_URL,
});

const ensureViewerId = (): string => {
  const existing = localStorage.getItem(VIEWER_ID_KEY);
  if (existing) {
    return existing;
  }

  const generated =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `viewer-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

  localStorage.setItem(VIEWER_ID_KEY, generated);
  return generated;
};

// ── ETag helpers ───────────────────────────────────────────────────────────

const ETAG_SUFFIX = ':etag';

export type EtagFetchSource = 'network' | 'cache-304';

export interface EtagFetchResult<T> {
  data: T;
  source: EtagFetchSource;
  etag?: string;
}

const readCachedJson = <T,>(key: string): T | null => {
  const rawValue = localStorage.getItem(key);
  if (!rawValue) {
    return null;
  }

  try {
    return JSON.parse(rawValue) as T;
  } catch {
    localStorage.removeItem(key);
    return null;
  }
};

const getWithEtag = async <T = any,>(
  url: string,
  cacheKey: string,
  params?: Record<string, string>,
): Promise<EtagFetchResult<T>> => {
  const etagKey = `${cacheKey}${ETAG_SUFFIX}`;
  const cachedEtag = localStorage.getItem(etagKey);
  const cachedPayload = readCachedJson<T>(cacheKey);

  const response = await studentApi.get(url, {
    params,
    headers: cachedEtag ? { 'If-None-Match': cachedEtag } : undefined,
    validateStatus: (status) => status >= 200 && status < 400,
  });

  if (response.status === 304 && cachedPayload) {
    return {
      data: cachedPayload,
      source: 'cache-304',
      etag: cachedEtag || undefined,
    };
  }

  const payload = response.data as T;
  localStorage.setItem(cacheKey, JSON.stringify(payload));

  const responseEtag = response.headers.etag as string | undefined;
  if (responseEtag) {
    localStorage.setItem(etagKey, responseEtag);
  }

  return {
    data: payload,
    source: 'network',
    etag: responseEtag,
  };
};

// ── University ID pass-through (for onboarding) ───────────────────────────

studentApi.interceptors.request.use(
  (config) => {
    const universityId = localStorage.getItem('university_id');
    if (universityId) {
      config.headers['X-University-ID'] = universityId;
    }
    config.headers['X-Viewer-ID'] = ensureViewerId();
    return config;
  },
  (error) => Promise.reject(error),
);

// ── Helper: read config from localStorage ───────────────────────────────

const getGroupId = (): string | null => localStorage.getItem(GROUP_ID_KEY);

const readLabSubgroups = (): string | null => localStorage.getItem(LAB_SUBGROUPS_KEY);

const getAcademicWeek = (): string | null => localStorage.getItem(ACADEMIC_WEEK_KEY);

const requireGroupId = (): string => {
  const gid = getGroupId();
  if (!gid) {
    throw new Error('No group selected. Please complete the onboarding wizard.');
  }
  return gid;
};

const getCommonParams = (): Record<string, string> => {
  const params: Record<string, string> = { group_id: requireGroupId() };
  const week = getAcademicWeek();
  const labSubgroups = readLabSubgroups();
  if (week) params.academic_week = week;
  if (labSubgroups) params.lab_subgroup_ids = labSubgroups;
  return params;
};

// ── Public API ─────────────────────────────────────────────────────────────

export const studentPortalApi = {
  /** Persist the selected group_id to localStorage. */
  setGroupId: (groupId: number) => {
    localStorage.setItem(GROUP_ID_KEY, String(groupId));
  },

  /** Read the persisted group_id. */
  getGroupId: (): number | null => {
    const raw = getGroupId();
    return raw ? Number(raw) : null;
  },

  /** Clear the persisted group selection (used for "Change Group"). */
  clearGroupId: () => {
    localStorage.removeItem(GROUP_ID_KEY);
    localStorage.removeItem(LAB_SUBGROUPS_KEY);
  },

  /** Check if a group has been selected. */
  hasGroup: (): boolean => !!getGroupId(),

  setLabSubgroups: (subgroupIds: number[]) => {
    localStorage.setItem(LAB_SUBGROUPS_KEY, subgroupIds.join(','));
  },

  getStoredLabSubgroups: (): number[] => {
    const raw = readLabSubgroups();
    return raw ? raw.split(',').map(Number) : [];
  },

  setAcademicWeek: (week: number) => {
    localStorage.setItem(ACADEMIC_WEEK_KEY, String(week));
  },

  getAcademicWeek: (): number => {
    const raw = getAcademicWeek();
    return raw ? Number(raw) : 1;
  },

  /** Fetch the onboarding wizard data (departments → levels → groups). */
  getOnboardingGroups: async (universityId?: number) => {
    const params: Record<string, string> = {};
    if (universityId) {
      params.university_id = String(universityId);
    }
    const response = await studentApi.get('/mobile/public/onboarding-groups', { params });
    return response.data;
  },

  /** Fetch the main dashboard (Now / Next / Today). */
  getDashboard: async () => {
    return getWithEtag('/mobile/public/dashboard', 'student_portal_dashboard', getCommonParams());
  },

  /** Fetch the "Now" card. */
  getNow: async () => {
    return getWithEtag('/mobile/public/now', 'student_portal_now', getCommonParams());
  },

  /** Fetch today's sessions. */
  getToday: async () => {
    return getWithEtag('/mobile/public/today', 'student_portal_today', getCommonParams());
  },

  /** Fetch the full week view. */
  getWeek: async () => {
    return getWithEtag('/mobile/public/week', 'student_portal_timetable', getCommonParams());
  },

  /** Fetch the list of courses for this group. */
  getCourses: async () => {
    const gid = requireGroupId();
    const response = await studentApi.get('/mobile/public/courses', {
      params: { group_id: gid },
    });
    return response.data;
  },

  /** Fetch the available rotating lab subgroups for the selected group. */
  getLabSubgroups: async (academicWeek?: number) => {
    const gid = requireGroupId();
    const params: Record<string, string> = { group_id: gid };
    const week = academicWeek ?? getAcademicWeek();
    if (week) {
      params.academic_week = String(week);
    }
    const response = await studentApi.get('/mobile/public/lab-subgroups', {
      params,
    });
    return response.data;
  },

  /** Search for lecturers, rooms, groups, or courses. */
  lookup: async (query: string) => {
    const gid = requireGroupId();
    const response = await studentApi.get('/mobile/public/lookup', {
      params: { q: query, group_id: gid },
    });
    return response.data;
  },

  /** Fetch detail for a specific search result. */
  getLookupDetail: async (entityType: string, entityId: number) => {
    const gid = requireGroupId();
    const response = await studentApi.get(
      `/mobile/public/lookup/${entityType}/${entityId}`,
      { params: { group_id: gid } },
    );
    return response.data;
  },

  /** Fetch currently free rooms. */
  getFreeRoomsNow: async (building?: string) => {
    const gid = requireGroupId();
    const trimmedBuilding = building?.trim();
    const cacheKey = trimmedBuilding
      ? `student_portal_free_rooms_${trimmedBuilding.toLowerCase()}`
      : 'student_portal_free_rooms_default';

    const params: Record<string, string> = { group_id: gid };
    if (trimmedBuilding) {
      params.building = trimmedBuilding;
    }

    return getWithEtag('/mobile/public/rooms/free-now', cacheKey, params);
  },

  /** Fetch active announcements. */
  getAnnouncements: async () => {
    const gid = requireGroupId();
    return getWithEtag('/mobile/public/announcements', 'student_portal_announcements', {
      group_id: gid,
    });
  },

  /** Fetch published exam timetable for the student's group. */
  getExamTimetable: async () => {
    const gid = requireGroupId();
    return getWithEtag('/mobile/public/exam-timetable', 'student_portal_exam_timetable', {
      group_id: gid,
    });
  },
};
