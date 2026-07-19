import axios from 'axios';

const LECTURER_API_BASE_URL = '/api/v1/lecturer';
const LECTURER_TOKEN_KEY = 'lecturer_token';

export const lecturerApi = axios.create({
  baseURL: LECTURER_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to attach the token
lecturerApi.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(LECTURER_TOKEN_KEY);
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Interceptor to handle 401s (token expiry)
lecturerApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem(LECTURER_TOKEN_KEY);
      localStorage.removeItem('lecturer_meta');
      window.location.href = '/lecturer/login';
    }
    return Promise.reject(error);
  },
);

export const lecturerPortalApi = {
  login: async (staff_number: string) => {
    const response = await axios.post(`${LECTURER_API_BASE_URL}/login`, { staff_number });
    return response.data;
  },
  getMe: async () => {
    const response = await lecturerApi.get('/me');
    return response.data;
  },
  getTimetable: async () => {
    const response = await lecturerApi.get('/timetable');
    return response.data;
  },
  getDashboard: async () => {
    const response = await lecturerApi.get('/dashboard');
    return response.data;
  },
  getCourses: async () => {
    const response = await lecturerApi.get('/courses');
    return response.data;
  },
  getAnnouncements: async (courseId?: number) => {
    const params = courseId ? { course_id: courseId } : {};
    const response = await lecturerApi.get('/announcements', { params });
    return response.data;
  },
  createAnnouncement: async (data: { course_id: number; title: string; message: string; announcement_type?: string; target_date?: string; venue?: string }) => {
    const response = await lecturerApi.post('/announcements', data);
    return response.data;
  },
  deleteAnnouncement: async (announcementId: number) => {
    const response = await lecturerApi.delete(`/announcements/${announcementId}`);
    return response.data;
  },
  getAvailableVenues: async (params: { date: string; start_time: string; end_time: string; capacity?: number; course_id?: number }) => {
    const response = await lecturerApi.get('/venues/available', { params });
    return response.data;
  },
  scheduleTest: async (data: { course_id: number; date: string; start_time: string; end_time: string; room_id?: number; title?: string; message?: string; capacity?: number }) => {
    const response = await lecturerApi.post('/tests', data);
    return response.data;
  },
  getExamTimetable: async () => {
    const response = await lecturerApi.get('/exam-timetable');
    return response.data;
  },
  logout: () => {
    localStorage.removeItem(LECTURER_TOKEN_KEY);
    localStorage.removeItem('lecturer_meta');
  },
};
