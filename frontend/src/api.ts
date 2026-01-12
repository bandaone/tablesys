import axios from 'axios';

const API_BASE_URL = '/api';

export interface User {
  id: number;
  email: string;
  username: string;
  full_name: string;
  role: 'coordinator' | 'hod';
  department_id?: number;
  is_active: boolean;
}

export interface LoginRequest {
  username: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

const api = axios.create({
  baseURL: API_BASE_URL,
});

// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

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
    const response = await api.get('/courses/');
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
    const response = await api.post('/courses/bulk-upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
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
    const response = await api.post('/lecturers/bulk-upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
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
  
  bulkUpload: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/rooms/bulk-upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
};

export const groupsAPI = {
  getAll: async () => {
    const response = await api.get('/groups/');
    return response.data;
  },
  
  create: async (data: any) => {
    const response = await api.post('/groups/', data);
    return response.data;
  },
  
  update: async (id: number, data: any) => {
    const response = await api.put(`/groups/${id}`, data);
    return response.data;
  },
  
  delete: async (id: number) => {
    await api.delete(`/groups/${id}`);
  },
  
  bulkUpload: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/groups/bulk-upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
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
};

export default api;
