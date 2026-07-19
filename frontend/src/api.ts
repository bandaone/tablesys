import axios from 'axios';

export const API_BASE_URL = '/api/v1';

export interface User {
  id: number;
  email: string;
  username: string;
  full_name: string;
  role: 'superadmin' | 'tenant_admin' | 'school_coordinator' | 'coordinator' | 'hod' | 'lab_coordinator' | 'lecturer' | 'student';
  university_id?: number;
  school_id?: number | null;
  department_id?: number;
  is_active: boolean;
}

export interface School {
  id: number;
  university_id: number;
  name: string;
  code: string;
  description?: string | null;
  academic_calendar_id?: number | null;
  scheduling_policy?: Record<string, unknown> | null;
  is_active: boolean;
}

export interface SchoolProfileUploadPreviewRow {
  row_number: number;
  school: string;
  programme: string;
  year_level: number;
  course_code: string;
  course_name: string;
  lecturer_name?: string | null;
  status: string;
  can_apply: boolean;
  department_name: string;
  department_code?: string | null;
  department_action: string;
  course_action: string;
  lecturer_action: string;
  assignment_action: string;
  issues: string[];
}

export interface SchoolProfileUploadPreviewSummary {
  total_rows: number;
  ready_rows: number;
  conflicted_rows: number;
  skipped_rows: number;
  departments_to_create: number;
  departments_reused: number;
  courses_to_create: number;
  courses_to_update: number;
  courses_unchanged: number;
  lecturers_to_create: number;
  lecturers_reused: number;
  assignments_to_create: number;
  assignments_reused: number;
}

export interface SchoolProfileUploadPreviewResponse {
  school_id: number;
  fingerprint: string;
  expires_at: string;
  rows: SchoolProfileUploadPreviewRow[];
  summary: SchoolProfileUploadPreviewSummary;
}

export interface SchoolProfileUploadApplyResponse {
  school_id: number;
  created_departments: number;
  created_courses: number;
  updated_courses: number;
  created_lecturers: number;
  reused_lecturers: number;
  created_assignments: number;
  skipped_rows: number;
  issues: string[];
}

export interface LoginRequest {
  username: string;
  password: string;
  university_id?: number;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface ImpersonationResponse {
  access_token: string;
  token_type: string;
  user: User;
}

const api = axios.create({
  baseURL: API_BASE_URL,
});

// Add token to requests
api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('token') || localStorage.getItem('token');

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  
  const universityId = localStorage.getItem('university_id');
  if (universityId) {
    config.headers['X-University-ID'] = universityId;
  }
  
  return config;
}, (error) => {
  return Promise.reject(error);
});

// Resiliency: Global Response Interceptor
api.interceptors.response.use(
  (response) => {
     return response;
  },
  (error) => {
    if (error.response) {
      // Token expiration or unauthorized access
      if (error.response.status === 401) {
        if (sessionStorage.getItem('token')) {
          sessionStorage.removeItem('token');
          sessionStorage.removeItem('user');
          window.location.href = '/login?session_expired=1';
        }
      }
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await axios.post(`${API_BASE_URL}/auth/login`, data, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.data;
  },
};

export const coursesAPI = {
  getAll: async () => {
    const response = await api.get('/courses/?limit=1000');
    return response.data;
  },

  create: async (data: Record<string, unknown>) => {
    const response = await api.post('/courses/', data);
    return response.data;
  },

  update: async (id: number, data: Record<string, unknown>) => {
    const response = await api.put(`/courses/${id}`, data);
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/courses/${id}`);
  },

  bulkUpload: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/courses/bulk-upload', formData);
    return response.data;
  },

  deleteAll: async () => {
    const response = await api.delete('/courses/');
    return response.data;
  },

  getEnrollmentMap: async (courseId: number) => {
    const response = await api.get(`/courses/${courseId}/enrollment-map`);
    return response.data;
  },

  updateEnrollmentMap: async (courseId: number, data: { group_ids: number[]; lecture_mode: 'shared' | 'separate' }) => {
    const response = await api.put(`/courses/${courseId}/enrollment-map`, data);
    return response.data;
  },

};

export const lecturersAPI = {
  getAll: async () => {
    const response = await api.get('/lecturers/');
    return response.data;
  },

  create: async (data: any) => {
    const response = await api.post('/lecturers/', data);
    return response.data;
  },

  update: async (id: number, data: any) => {
    const response = await api.put(`/lecturers/${id}`, data);
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/lecturers/${id}`);
  },

  bulkUpload: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/lecturers/bulk-upload', formData);
    return response.data;
  },

  bulkAssignCourses: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/lecturers/bulk-assign-courses', formData);
    return response.data;
  },

  deleteAll: async () => {
    const response = await api.delete('/lecturers/');
    return response.data;
  },
};

export const roomsAPI = {
  getAll: async () => {
    const response = await api.get('/rooms/');
    return response.data;
  },

  create: async (data: any) => {
    const response = await api.post('/rooms/', data);
    return response.data;
  },

  update: async (id: number, data: any) => {
    const response = await api.put(`/rooms/${id}`, data);
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/rooms/${id}`);
  },

  toggleBlock: async (id: number) => {
    const response = await api.patch(`/rooms/${id}/block`);
    return response.data;
  },

  bulkUpload: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/rooms/bulk-upload', formData);
    return response.data;
  },

  deleteAll: async () => {
    const response = await api.delete('/rooms/');
    return response.data;
  },
};


export const groupsAPI = {
  getAll: async () => {
    const response = await api.get('/groups/');
    return response.data;
  },

  getCourseMap: async (groupId: number) => {
    const response = await api.get(`/groups/${groupId}/course-map`);
    return response.data;
  },

  getAssignedCourses: async (groupId: number) => {
    const response = await api.get(`/groups/${groupId}/courses`);
    return response.data;
  },

  assignCourses: async (groupId: number, courseIds: number[]) => {
    const response = await api.post(`/groups/${groupId}/courses`, { course_ids: courseIds });
    return response.data;
  },

  getByTier: async (tier: 'main' | 'stream' | 'lab', departmentId?: number) => {
    const params: any = { tier };
    if (departmentId) params.department_id = departmentId;
    const response = await api.get('/groups/', { params });
    return response.data;
  },

  create: async (data: any) => {
    const payload = { ...data };
    if (payload.group_name !== undefined && payload.name === undefined) {
      payload.name = payload.group_name;
      delete payload.group_name;
    }
    const response = await api.post('/groups/', payload);
    return response.data;
  },

  update: async (id: number, data: any) => {
    const payload = { ...data };
    if (payload.group_name !== undefined && payload.name === undefined) {
      payload.name = payload.group_name;
      delete payload.group_name;
    }
    const response = await api.put(`/groups/${id}`, payload);
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/groups/${id}`);
  },

  bulkUpload: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/groups/bulk-upload', formData);
    return response.data;
  },

  getSubgroups: async (groupId: number) => {
    const response = await api.get(`/groups/${groupId}/subgroups`);
    return response.data;
  },

  getStreams: async (groupId: number) => {
    const response = await api.get(`/groups/${groupId}/streams`);
    return response.data;
  },

  generateSubgroups: async (groupId: number, data: {
    prefix?: string;
    count: number;
    size_per_group: number;
    group_type?: string;
    naming_mode?: 'alpha' | 'numeric' | 'custom';
    custom_names?: string[];
  }) => {
    const response = await api.post(`/groups/${groupId}/subgroups/bulk`, data);
    return response.data;
  },

  deleteSubgroup: async (groupId: number, subgroupId: number) => {
    await api.delete(`/groups/${groupId}/subgroups/${subgroupId}`);
  },

  deleteAllSubgroups: async (groupId: number) => {
    const response = await api.delete(`/groups/${groupId}/subgroups`);
    return response.data;
  },
};

export const labCoordinatorAPI = {
  getRooms: async () => {
    const response = await api.get('/lab-coordinator/rooms');
    return response.data;
  },

  getRoomAllocations: async () => {
    const response = await api.get('/lab-coordinator/room-allocations');
    return response.data;
  },

  setRoomAllocations: async (room_ids: number[]) => {
    const response = await api.put('/lab-coordinator/room-allocations', { room_ids });
    return response.data;
  },

  createRoom: async (data: any) => {
    const response = await api.post('/lab-coordinator/rooms', data);
    return response.data;
  },

  deleteRoom: async (id: number) => {
    const response = await api.delete(`/lab-coordinator/rooms/${id}`);
    return response.data;
  },
  
  getGroups: async () => {
    const response = await api.get('/lab-coordinator/groups');
    return response.data;
  },

  getCourses: async () => {
    const response = await api.get('/lab-coordinator/courses');
    return response.data;
  },
  
  getSessions: async () => {
    const response = await api.get('/lab-coordinator/sessions');
    return response.data;
  },
  
  getSummary: async () => {
    const response = await api.get('/lab-coordinator/summary');
    return response.data;
  },
  
  createSession: async (data: Record<string, any>) => {
    const response = await api.post('/lab-coordinator/sessions', data);
    return response.data;
  },
  
  updateSession: async (id: number, data: Record<string, any>) => {
    const response = await api.patch(`/lab-coordinator/sessions/${id}`, data);
    return response.data;
  },

  publishSession: async (id: number) => {
    const response = await api.post(`/lab-coordinator/sessions/${id}/publish`);
    return response.data;
  },

  unpublishSession: async (id: number) => {
    const response = await api.post(`/lab-coordinator/sessions/${id}/unpublish`);
    return response.data;
  },
  
  deleteSession: async (id: number) => {
    await api.delete(`/lab-coordinator/sessions/${id}`);
  },
  
  smartSchedule: async (data: {
    course_id: number;
    parent_group_id: number;
    group_ids: number[];
    room_ids: number[];
    duration_minutes: number;
    frequency_weeks: number;
    subgroups_per_session: number;
    session_type: string;
    preferred_days?: number[];
    start_hour?: number;
    end_hour?: number;
  }) => {
    const response = await api.post('/lab-coordinator/smart-schedule', data);
    return response.data;
  },
};

export const departmentsAPI = {
  getAll: async () => {
    const response = await api.get('/departments/');
    return response.data;
  },

  create: async (data: any) => {
    const response = await api.post('/departments/', data);
    return response.data;
  },

  update: async (id: number, data: any) => {
    const response = await api.put(`/departments/${id}`, data);
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/departments/${id}`);
  },
};

export const timetablesAPI = {
  getAll: async () => {
    const response = await api.get('/timetables/');
    return response.data;
  },

  get: async (id: number) => {
    const response = await api.get(`/timetables/${id}`);
    return response.data;
  },

  create: async (data: any) => {
    const response = await api.post('/timetables/', data);
    return response.data;
  },

  activate: async (id: number) => {
    const response = await api.post(`/timetables/${id}/activate`);
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/timetables/${id}`);
  },

  assignSlot: async (slotId: number, data: { lecturer_id?: number; group_id?: number }) => {
    const response = await api.post(`/timetables/slots/${slotId}/assign`, data);
    return response.data;
  },

  createManualSlot: async (timetableId: number, data: any) => {
    const response = await api.post(`/timetables/${timetableId}/slots/manual`, data);
    return response.data;
  },
};

export const schoolsAPI = {
  getAll: async (): Promise<School[]> => {
    const response = await api.get('/schools/');
    return response.data;
  },
  create: async (data: Partial<School>) => {
    const response = await api.post('/schools/', data);
    return response.data;
  },
  update: async (id: number, data: Partial<School>) => {
    const response = await api.put(`/schools/${id}`, data);
    return response.data;
  },
  delete: async (id: number) => {
    await api.delete(`/schools/${id}`);
  },
  previewProfileUpload: async (schoolId: number, file: File): Promise<SchoolProfileUploadPreviewResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post(`/schools/${schoolId}/profile-upload/preview`, formData);
    return response.data;
  },
  applyProfileUpload: async (schoolId: number, data: {
    fingerprint: string;
    expires_at: string;
    rows: SchoolProfileUploadPreviewRow[];
  }): Promise<SchoolProfileUploadApplyResponse> => {
    const response = await api.post(`/schools/${schoolId}/profile-upload/apply`, data);
    return response.data;
  },
};

export const activityTypesAPI = {
  list: async () => {
    const response = await api.get('/activity-types/');
    return response.data;
  },
  create: async (data: Record<string, unknown>) => {
    const response = await api.post('/activity-types/', data);
    return response.data;
  },
  update: async (id: number, data: Record<string, unknown>) => {
    const response = await api.put(`/activity-types/${id}`, data);
    return response.data;
  },
  remove: async (id: number) => {
    await api.delete(`/activity-types/${id}`);
  },
};

export const institutionSetupAPI = {
  getTemplates: async () => {
    const response = await api.get('/institution-setup/templates');
    return response.data;
  },
  getCurrent: async () => {
    const response = await api.get('/institution-setup/');
    return response.data;
  },
  save: async (data: Record<string, unknown>) => {
    const response = await api.put('/institution-setup/', data);
    return response.data;
  },
};

export interface ExamConstraintSettings {
  preferred_max_papers_per_day: number;
  hard_max_papers_per_day: number;
  min_gap_hours: number;
  allow_same_day_multiple_papers: boolean;
}

export interface ExamSessionWindow {
  id: number;
  exam_period_id: number;
  name: string;
  start_time: string;
  end_time: string;
  allow_weekends: boolean;
  display_order: number;
  is_active: boolean;
}

export interface ExamSeatingProfile {
  id: number;
  name: string;
  description?: string | null;
  capacity_factor: number;
  fixed_capacity?: number | null;
  requires_computers: boolean;
  spacing_strategy: string;
  profile_metadata?: Record<string, unknown> | null;
  is_default: boolean;
}

export interface ExamPaper {
  id: number;
  exam_period_id: number;
  paper_code: string;
  paper_name: string;
  course_id?: number | null;
  duration_minutes: number;
  candidate_count?: number | null;
  group_ids: number[];
  preferred_room_type?: string | null;
  preferred_seating_profile_id?: number | null;
  max_rooms?: number | null;
  allow_custom_window: boolean;
  metadata_json?: Record<string, unknown> | null;
}

export interface ExamPaperCandidateGroup {
  id: number;
  name: string;
  size: number;
  level: number;
  department_id: number;
  department_name?: string | null;
}

export interface ExamPaperCandidate {
  course_id: number;
  course_code: string;
  course_name: string;
  course_level: number;
  department_id: number;
  department_name?: string | null;
  preferred_room_type?: string | null;
  candidate_count: number;
  group_ids: number[];
  groups: ExamPaperCandidateGroup[];
  ownership_kind: string;
  can_manage: boolean;
  already_included: boolean;
  existing_paper_id?: number | null;
  existing_paper_code?: string | null;
  existing_paper_name?: string | null;
  existing_duration_minutes?: number | null;
  existing_max_rooms?: number | null;
  existing_preferred_seating_profile_id?: number | null;
}

export interface ExamSlotRoomAllocation {
  id: number;
  room_id: number;
  seating_profile_id?: number | null;
  allocated_capacity: number;
  allocated_group_ids?: number[] | null;
  sequence_no: number;
  room?: {
    id: number;
    name: string;
    building: string;
    capacity: number;
    room_type: string;
  } | null;
}

export interface ExamSlot {
  id: number;
  exam_period_id: number;
  exam_paper_id: number;
  session_window_id: number;
  seating_profile_id?: number | null;
  exam_date: string;
  start_time: string;
  end_time: string;
  status: string;
  total_allocated_capacity?: number | null;
  notes?: string | null;
  generated_score?: number | null;
  paper?: ExamPaper | null;
  session_window?: ExamSessionWindow | null;
  room_allocations: ExamSlotRoomAllocation[];
}

export interface ExamGenerationFlag {
  slot_id: number;
  paper_id: number;
  paper_code: string;
  paper_name?: string;
  severity: 'info' | 'warning' | string;
  flags: string[];
  summary: string;
  room_count: number;
  capacity_margin: number;
  available_capacity: number;
  same_day_group_count: number;
}

export interface ExamPeriod {
  id: number;
  name: string;
  semester: string;
  year: number;
  start_date: string;
  end_date: string;
  is_published: boolean;
  is_locked: boolean;
  constraint_settings?: ExamConstraintSettings | null;
  generation_metadata?: {
    generated_at?: string;
    scheduled_count?: number;
    unscheduled_count?: number;
    unscheduled_papers?: Array<{
      paper_id: number;
      paper_code: string;
      paper_name?: string;
      reason: string;
      feasible_options: number;
      priority_score?: number;
      candidate_count?: number;
      diagnostics?: Record<string, number>;
    }>;
    scheduled_flags?: ExamGenerationFlag[];
    diagnostics_summary?: {
      scheduled_with_flags?: number;
      multi_room_allocations?: number;
      tight_capacity_fits?: number;
      same_day_pressure_cases?: number;
      compressed_spacing_cases?: number;
      peak_day_usage_cases?: number;
      unscheduled_reasons?: Record<string, number>;
      average_rooms_per_slot?: number;
    };
    strategy?: string;
  } | null;
  session_windows: ExamSessionWindow[];
  papers: ExamPaper[];
  slots: ExamSlot[];
  published_at?: string | null;
}

export const examTimetablesAPI = {
  getPeriods: async (): Promise<ExamPeriod[]> => {
    const response = await api.get('/exam-timetables/periods');
    return response.data;
  },

  getPeriod: async (periodId: number): Promise<ExamPeriod> => {
    const response = await api.get(`/exam-timetables/periods/${periodId}`);
    return response.data;
  },

  createPeriod: async (data: Record<string, unknown>): Promise<ExamPeriod> => {
    const response = await api.post('/exam-timetables/periods', data);
    return response.data;
  },

  updatePeriod: async (periodId: number, data: Record<string, unknown>): Promise<ExamPeriod> => {
    const response = await api.put(`/exam-timetables/periods/${periodId}`, data);
    return response.data;
  },

  deletePeriod: async (periodId: number): Promise<void> => {
    await api.delete(`/exam-timetables/periods/${periodId}`);
  },

  getSeatingProfiles: async (): Promise<ExamSeatingProfile[]> => {
    const response = await api.get('/exam-timetables/seating-profiles');
    return response.data;
  },

  createSeatingProfile: async (data: Record<string, unknown>): Promise<ExamSeatingProfile> => {
    const response = await api.post('/exam-timetables/seating-profiles', data);
    return response.data;
  },

  updateSeatingProfile: async (profileId: number, data: Record<string, unknown>): Promise<ExamSeatingProfile> => {
    const response = await api.put(`/exam-timetables/seating-profiles/${profileId}`, data);
    return response.data;
  },

  createSessionWindow: async (periodId: number, data: Record<string, unknown>): Promise<ExamSessionWindow> => {
    const response = await api.post(`/exam-timetables/periods/${periodId}/session-windows`, data);
    return response.data;
  },

  updateSessionWindow: async (sessionWindowId: number, data: Record<string, unknown>): Promise<ExamSessionWindow> => {
    const response = await api.put(`/exam-timetables/session-windows/${sessionWindowId}`, data);
    return response.data;
  },

  createPaper: async (periodId: number, data: Record<string, unknown>): Promise<ExamPaper> => {
    const response = await api.post(`/exam-timetables/periods/${periodId}/papers`, data);
    return response.data;
  },

  updatePaper: async (paperId: number, data: Record<string, unknown>): Promise<ExamPaper> => {
    const response = await api.put(`/exam-timetables/papers/${paperId}`, data);
    return response.data;
  },

  getPaperCandidates: async (periodId: number): Promise<ExamPaperCandidate[]> => {
    const response = await api.get(`/exam-timetables/periods/${periodId}/paper-candidates`);
    return response.data;
  },

  syncPapers: async (
    periodId: number,
    data: {
      course_ids: number[];
      default_duration_minutes: number;
      default_max_rooms: number;
      preferred_seating_profile_id?: number | null;
      allow_custom_window: boolean;
    },
  ): Promise<{ selected_count: number; created_count: number; updated_count: number; removed_count: number }> => {
    const response = await api.post(`/exam-timetables/periods/${periodId}/sync-papers`, data);
    return response.data;
  },

  getSlots: async (periodId: number): Promise<ExamSlot[]> => {
    const response = await api.get(`/exam-timetables/periods/${periodId}/slots`);
    return response.data;
  },

  clearDraft: async (periodId: number): Promise<void> => {
    await api.delete(`/exam-timetables/periods/${periodId}/slots`);
  },

  generate: async (periodId: number, replaceExisting: boolean = true) => {
    const response = await api.post(`/exam-timetables/periods/${periodId}/generate`, {
      replace_existing: replaceExisting,
    });
    return response.data;
  },

  publish: async (periodId: number, lockAfterPublish: boolean = true): Promise<ExamPeriod> => {
    const response = await api.post(`/exam-timetables/periods/${periodId}/publish`, {
      lock_after_publish: lockAfterPublish,
    });
    return response.data;
  },

  unpublish: async (periodId: number): Promise<ExamPeriod> => {
    const response = await api.post(`/exam-timetables/periods/${periodId}/unpublish`);
    return response.data;
  },
};

export const usersAPI = {
  getAll: async () => {
    const response = await api.get('/users/');
    return response.data;
  },

  getById: async (id: number) => {
    const response = await api.get(`/users/${id}`);
    return response.data;
  },

  create: async (data: any) => {
    const response = await api.post('/users/', data);
    return response.data;
  },

  update: async (id: number, data: any) => {
    const response = await api.put(`/users/${id}`, data);
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/users/${id}`);
  },

  resetPassword: async (id: number, newPassword: string) => {
    const response = await api.post(`/users/${id}/reset-password`, {
      new_password: newPassword,
    });
    return response.data;
  },

  changeOwnPassword: async (currentPassword: string, newPassword: string) => {
    const response = await api.post('/users/me/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return response.data;
  },

  updateOwnProfile: async (data: { email?: string; full_name?: string }) => {
    const response = await api.put('/users/me/profile', data);
    return response.data;
  },
};

export const notificationsAPI = {
  getAll: async (unreadOnly: boolean = false, limit: number = 50) => {
    const response = await api.get('/notifications/', { params: { unread_only: unreadOnly, limit } });
    return response.data;
  },

  getUnreadCount: async () => {
    const response = await api.get('/notifications/unread-count');
    return response.data;
  },

  markAsRead: async (id: number) => {
    const response = await api.post(`/notifications/${id}/read`);
    return response.data;
  },

  markAllRead: async () => {
    const response = await api.post('/notifications/mark-all-read');
    return response.data;
  }
};

export const superadminAPI = {
  getStats: async () => {
    const response = await api.get('/superadmin/stats');
    return response.data;
  },
  
  getUniversities: async (skip: number = 0, limit: number = 100, search?: string) => {
    const params: any = { skip, limit };
    if (search) params.search = search;
    const response = await api.get('/superadmin/universities', { params });
    return response.data;
  },

  registerUniversity: async (data: any) => {
    const response = await api.post('/superadmin/universities', data);
    return response.data;
  },

  updateUniversity: async (id: number, data: any) => {
    const response = await api.patch(`/superadmin/universities/${id}`, data);
    return response.data;
  },

  suspendUniversity: async (id: number) => {
    await api.delete(`/superadmin/universities/${id}`);
  },

  wipeUniversity: async (id: number) => {
    await api.delete(`/superadmin/universities/${id}/wipe`);
  },

  getTelemetry: async () => {
    const response = await api.get('/superadmin/telemetry');
    return response.data;
  },

  getAnalytics: async () => {
    const response = await api.get('/superadmin/analytics');
    return response.data;
  },

  getTenantDashboardMetrics: async (id: number) => {
    const response = await api.get(`/superadmin/universities/${id}/dashboard-metrics`);
    return response.data;
  },

  getTenantObservability: async (tenantId: number, period?: string) => {
    const response = await api.get('/usage/observability', {
      params: { tenant_id: tenantId, period }
    });
    return response.data;
  },

  getPerformanceOverview: async (windowDays: number = 30) => {
    const response = await api.get('/superadmin/performance', {
      params: { window_days: windowDays }
    });
    return response.data;
  },

  getBusinessMetricsOverview: async (windowDays: number = 30) => {
    const response = await api.get('/superadmin/business-metrics', {
      params: { window_days: windowDays }
    });
    return response.data;
  },

  getOperationalMetricsOverview: async (windowDays: number = 30) => {
    const response = await api.get('/superadmin/operational-metrics', {
      params: { window_days: windowDays }
    });
    return response.data;
  },

  impersonateUniversity: async (id: number): Promise<ImpersonationResponse> => {
    const response = await api.post(`/superadmin/universities/${id}/impersonate`);
    return response.data;
  },

  revertImpersonation: async (): Promise<LoginResponse> => {
    const response = await api.post('/superadmin/revert-impersonation');
    return response.data;
  }
};

// ── Agent Gamma: SIS Integration API ─────────────────────────────────────────
export interface SisApiKey {
  id: number;
  university_id: number;
  label: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
  notes: string | null;
}

export interface SisApiKeyCreated extends SisApiKey {
  raw_key: string;
}

export const sisAPI = {
  listKeys: async (): Promise<SisApiKey[]> => {
    const response = await api.get('/sis/keys');
    return response.data;
  },

  generateKey: async (data: { label: string; notes?: string }): Promise<SisApiKeyCreated> => {
    const response = await api.post('/sis/keys', data);
    return response.data;
  },

  revokeKey: async (keyId: number): Promise<{ detail: string }> => {
    const response = await api.delete(`/sis/keys/${keyId}`);
    return response.data;
  },
};

export const brandingAPI = {
  getMyBranding: async () => {
    const response = await api.get('/universities/me/branding');
    return response.data;
  }
};

export const publicAPI = {
  getUniversityBranding: async (domain: string) => {
    const response = await api.get('/public/university', { params: { domain } });
    return response.data;
  },
  
  registerTenant: async (data: Record<string, string>) => {
    const response = await api.post('/public/register', data);
    return response.data;
  },

  verifyTenant: async (token: string) => {
    const response = await api.post('/public/verify', { token });
    return response.data;
  }
};

export default api;
