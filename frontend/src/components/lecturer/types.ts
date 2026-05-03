export interface LecturerProfile {
  id: number;
  staff_number: string;
  full_name: string;
  email: string | null;
  department_id: number | null;
  max_hours_per_week: number | null;
}

export interface LecturerTimetableSlot {
  id: number;
  course_code: string;
  course_name: string;
  group_id: number;
  session_type: string;
  day_of_week: string;
  start_time: string;
  end_time: string;
  room_number: string;
  building: string;
}

export interface LecturerDashboardSummary {
  total_courses: number;
  total_sessions: number;
  daily_session_count: number;
  daily_teaching_hours: number;
  weekly_load_hours: number;
  max_hours_per_week: number;
  weekly_load_percent: number | null;
  next_session: {
    id: number;
    day: string;
    start_time: string;
    end_time: string;
    course_id: number;
    course_code: string | null;
    course_name: string | null;
    room_id: number;
    minutes_until_start: number;
  } | null;
}

export interface LecturerCourseWorkload {
  course_id: number;
  course_code: string | null;
  course_name: string | null;
  sessions: number;
  hours: number;
}

export interface LecturerDashboardResponse {
  profile: Partial<LecturerProfile>;
  summary: LecturerDashboardSummary;
  course_workload: LecturerCourseWorkload[];
}

export interface LecturerTimetableResponse {
  profile: Partial<LecturerProfile>;
  timetable: {
    id: number | null;
    name: string | null;
    semester: string | null;
    year: number | null;
  };
  sessions: LecturerTimetableSlot[];
  total_sessions: number;
}

export interface LecturerCourse {
  id: number;
  code: string;
  name: string;
  level: number;
  assignment: {
    session_type: string | null;
    room_preference: string | null;
    expertise_level: string | null;
  };
}
