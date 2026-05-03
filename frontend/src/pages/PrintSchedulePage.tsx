import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Button,
  CircularProgress,
  Alert,
} from '@mui/material';
import { Print as PrintIcon, ArrowBack as ArrowBackIcon } from '@mui/icons-material';
import api from '../api';
import { useBranding } from '../contexts/BrandingContext';

interface PrintScheduleData {
  metadata?: {
    school_name?: string;
  };
  lecturer?: {
    full_name: string;
    staff_number: string;
    email: string;
    department: string;
  };
  group?: {
    group_name: string;
    level: number;
    size: number;
    department: string;
  };
  room?: {
    name: string;
    building: string;
    capacity: number;
    room_type: string;
  };
  timetable: {
    name: string;
    semester: string;
    year: number;
  };
  schedule: Array<{
    day: string;
    start_time: string;
    end_time: string;
    course_code: string;
    course_name: string;
    room?: string;
    lecturer?: string;
    group?: string;
    level?: number;
  }>;
  total_hours?: number;
  utilization_percentage?: number;
}

const PrintSchedulePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { branding } = useBranding();
  const [data, setData] = useState<PrintScheduleData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const type = searchParams.get('type'); // 'lecturer', 'group', 'room'
  const id = searchParams.get('id');

  useEffect(() => {
    if (type && id) {
      fetchScheduleData();
    } else {
      setError('Invalid print parameters');
      setLoading(false);
    }
  }, [type, id]);

  const fetchScheduleData = async () => {
    try {
      setLoading(true);
      let response;
      
      if (type === 'lecturer') {
        response = await api.get(`/print/lecturer/${id}`);
      } else if (type === 'group') {
        response = await api.get(`/print/group/${id}`);
      } else if (type === 'room') {
        response = await api.get(`/print/room/${id}`);
      } else {
        throw new Error('Invalid print type');
      }
      
      setData(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load schedule');
    } finally {
      setLoading(false);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  const groupScheduleByDay = () => {
    if (!data?.schedule) return {};
    
    const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
    const grouped: Record<string, typeof data.schedule> = {};
    
    days.forEach(day => {
      grouped[day] = data.schedule.filter(slot => slot.day === day)
        .sort((a, b) => a.start_time.localeCompare(b.start_time));
    });
    
    return grouped;
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !data) {
    return (
      <Box sx={{ p: 4 }}>
        <Alert severity="error">{error || 'No data available'}</Alert>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mt: 2 }}>
          Go Back
        </Button>
      </Box>
    );
  }

  const scheduleByDay = groupScheduleByDay();

  return (
    <>
      {/* Print styles */}
      <style>{`
        @media print {
          body * {
            visibility: hidden;
          }
          #print-content, #print-content * {
            visibility: visible;
          }
          #print-content {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
          }
          .no-print {
            display: none !important;
          }
          @page {
            size: A4 portrait;
            margin: 1.5cm;
          }
          table {
            page-break-inside: auto;
          }
          tr {
            page-break-inside: avoid;
            page-break-after: auto;
          }
          thead {
            display: table-header-group;
          }
        }
      `}</style>

      {/* Action buttons (hidden on print) */}
      <Box className="no-print" sx={{ p: 2, display: 'flex', gap: 2, justifyContent: 'flex-end', bgcolor: '#f5f5f5' }}>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate(-1)}
        >
          Back
        </Button>
        <Button
          variant="contained"
          startIcon={<PrintIcon />}
          onClick={handlePrint}
        >
          Print
        </Button>
      </Box>

      {/* Print content */}
      <Box id="print-content" sx={{ p: 4, bgcolor: 'white' }}>
        {/* Header */}
        <Box sx={{ textAlign: 'center', mb: 4, borderBottom: `3px solid ${branding.primary_color || '#1976d2'}`, pb: 2 }}>
          <Typography variant="h4" fontWeight="bold" color={branding.primary_color || '#1976d2'}>
            {branding.name?.toUpperCase() || 'UNIVERSITY'}
          </Typography>
          <Typography variant="h6" color={branding.secondary_color || '#FF8C00'}>
            {data.metadata?.school_name || 'Academic Faculty'}
          </Typography>
          <Typography variant="h5" fontWeight="bold" sx={{ mt: 2 }}>
            {type === 'lecturer' && 'Lecturer Teaching Schedule'}
            {type === 'group' && 'Student Group Timetable'}
            {type === 'room' && 'Room Utilization Schedule'}
          </Typography>
          <Typography variant="subtitle1" color="text.secondary">
            {data.timetable.name} - {data.timetable.semester} {data.timetable.year}
          </Typography>
        </Box>

        {/* Entity Details */}
        <Box sx={{ mb: 4, p: 2, bgcolor: '#f8f9fa', borderRadius: 1 }}>
          {data.lecturer && (
            <Box>
              <Typography variant="h6" gutterBottom><strong>Lecturer Information</strong></Typography>
              <Typography><strong>Name:</strong> {data.lecturer.full_name}</Typography>
              <Typography><strong>Staff Number:</strong> {data.lecturer.staff_number}</Typography>
              <Typography><strong>Department:</strong> {data.lecturer.department}</Typography>
              <Typography><strong>Email:</strong> {data.lecturer.email}</Typography>
              {data.total_hours && (
                <Typography><strong>Total Contact Hours:</strong> {data.total_hours.toFixed(1)} hours/week</Typography>
              )}
            </Box>
          )}
          {data.group && (
            <Box>
              <Typography variant="h6" gutterBottom><strong>Group Information</strong></Typography>
              <Typography><strong>Group:</strong> {data.group.group_name}</Typography>
              <Typography><strong>Level:</strong> Year {data.group.level}</Typography>
              <Typography><strong>Size:</strong> {data.group.size} students</Typography>
              <Typography><strong>Department:</strong> {data.group.department}</Typography>
              {data.total_hours && (
                <Typography><strong>Total Contact Hours:</strong> {data.total_hours.toFixed(1)} hours/week</Typography>
              )}
            </Box>
          )}
          {data.room && (
            <Box>
              <Typography variant="h6" gutterBottom><strong>Room Information</strong></Typography>
              <Typography><strong>Room:</strong> {data.room.name}</Typography>
              <Typography><strong>Building:</strong> {data.room.building}</Typography>
              <Typography><strong>Capacity:</strong> {data.room.capacity} students</Typography>
              <Typography><strong>Type:</strong> {data.room.room_type}</Typography>
              {data.utilization_percentage && (
                <Typography><strong>Utilization:</strong> {data.utilization_percentage.toFixed(1)}%</Typography>
              )}
            </Box>
          )}
        </Box>

        {/* Schedule by Day */}
        {Object.entries(scheduleByDay).map(([day, slots]) => (
          <Box key={day} sx={{ mb: 3 }}>
            <Typography variant="h6" sx={{ bgcolor: branding.primary_color || '#1976d2', color: 'white', p: 1, mb: 1 }}>
              {day}
            </Typography>
            {slots.length === 0 ? (
              <Typography color="text.secondary" sx={{ pl: 2, fontStyle: 'italic' }}>
                No classes scheduled
              </Typography>
            ) : (
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor: '#f5f5f5' }}>
                      <TableCell width="15%"><strong>Time</strong></TableCell>
                      <TableCell width="15%"><strong>Code</strong></TableCell>
                      <TableCell width="30%"><strong>Course</strong></TableCell>
                      {type === 'lecturer' && <TableCell width="15%"><strong>Room</strong></TableCell>}
                      {type === 'lecturer' && <TableCell width="25%"><strong>Group</strong></TableCell>}
                      {type === 'group' && <TableCell width="15%"><strong>Room</strong></TableCell>}
                      {type === 'group' && <TableCell width="25%"><strong>Lecturer</strong></TableCell>}
                      {type === 'room' && <TableCell width="20%"><strong>Lecturer</strong></TableCell>}
                      {type === 'room' && <TableCell width="20%"><strong>Group</strong></TableCell>}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {slots.map((slot, idx) => (
                      <TableRow key={idx}>
                        <TableCell>{slot.start_time} - {slot.end_time}</TableCell>
                        <TableCell><strong>{slot.course_code}</strong></TableCell>
                        <TableCell>{slot.course_name}</TableCell>
                        {type === 'lecturer' && <TableCell>{slot.room || 'TBA'}</TableCell>}
                        {type === 'lecturer' && <TableCell>{slot.group || 'N/A'}</TableCell>}
                        {type === 'group' && <TableCell>{slot.room || 'TBA'}</TableCell>}
                        {type === 'group' && <TableCell>{slot.lecturer || 'TBA'}</TableCell>}
                        {type === 'room' && <TableCell>{slot.lecturer || 'TBA'}</TableCell>}
                        {type === 'room' && <TableCell>{slot.group || 'N/A'}</TableCell>}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Box>
        ))}

        {/* Footer */}
        <Box sx={{ mt: 4, pt: 2, borderTop: '1px solid #ddd', textAlign: 'center' }}>
          <Typography variant="caption" color="text.secondary">
            Generated on {new Date().toLocaleString()} | Total Classes: {data.schedule.length}
          </Typography>
        </Box>
      </Box>
    </>
  );
};

export default PrintSchedulePage;
