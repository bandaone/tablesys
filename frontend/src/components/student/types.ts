export interface TimetableSlot {
  id: number;
  day_of_week: string;
  start_time: string;
  end_time: string;
  session_type?: string;
  activity_type_key?: string;
  activity_display_name?: string;
  activity_color?: string;
  course_code: string;
  course_name: string;
  lecturer_name: string;
  room_number: string;
  building: string;
}

export interface Course {
  id: number;
  code: string;
  name: string;
  credit_hours: number;
  course_type: string;
  lecturer?: {
    name: string;
    email: string;
  };
}

export interface LookupResult {
  type: 'lecturer' | 'room' | 'group' | 'course';
  id: number;
  title: string;
  subtitle: string;
  meta?: string;
}

export interface LookupDetail {
  entity: LookupResult;
  availability: {
    today_name: string;
    is_busy_now: boolean;
    current_session: TimetableSlot | null;
    next_session: TimetableSlot | null;
    today_sessions: TimetableSlot[];
  };
  sessions: TimetableSlot[];
}

export interface FreeRoom {
  id: number;
  name: string;
  building: string;
  capacity: number;
  room_type: string;
}

export interface FreeRoomsData {
  today_name: string;
  checked_at: string;
  total_rooms: number;
  occupied_rooms: number;
  free_rooms: FreeRoom[];
}
