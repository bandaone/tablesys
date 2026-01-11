import React, { useEffect, useState } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Paper,
} from '@mui/material';
import {
  Book as BookIcon,
  Person as PersonIcon,
  Room as RoomIcon,
  Group as GroupIcon,
} from '@mui/icons-material';
import { coursesAPI, lecturersAPI, roomsAPI, groupsAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';

const DashboardPage: React.FC = () => {
  const [stats, setStats] = useState({
    courses: 0,
    lecturers: 0,
    rooms: 0,
    groups: 0,
  });

  const { user } = useAuth();

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const [courses, lecturers, rooms, groups] = await Promise.all([
        coursesAPI.getAll(),
        lecturersAPI.getAll(),
        roomsAPI.getAll(),
        groupsAPI.getAll(),
      ]);

      setStats({
        courses: courses.length,
        lecturers: lecturers.length,
        rooms: rooms.length,
        groups: groups.length,
      });
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  const statCards = [
    { title: 'Courses', value: stats.courses, icon: <BookIcon sx={{ fontSize: 40 }} />, color: '#003366' },
    { title: 'Lecturers', value: stats.lecturers, icon: <PersonIcon sx={{ fontSize: 40 }} />, color: '#FF8C00' },
    { title: 'Rooms', value: stats.rooms, icon: <RoomIcon sx={{ fontSize: 40 }} />, color: '#4A90E2' },
    { title: 'Student Groups', value: stats.groups, icon: <GroupIcon sx={{ fontSize: 40 }} />, color: '#2e7d32' },
  ];

  return (
    <Box>
      <Typography variant="h4" fontWeight="bold" gutterBottom>
        Welcome, {user?.full_name}!
      </Typography>
      <Typography variant="body1" color="text.secondary" gutterBottom sx={{ mb: 4 }}>
        University of Zambia Timetable Management System
      </Typography>

      <Grid container spacing={3}>
        {statCards.map((card) => (
          <Grid item xs={12} sm={6} md={3} key={card.title}>
            <Card sx={{ height: '100%', bgcolor: card.color, color: 'white' }}>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Box>
                    <Typography variant="h3" fontWeight="bold">
                      {card.value}
                    </Typography>
                    <Typography variant="h6">
                      {card.title}
                    </Typography>
                  </Box>
                  <Box sx={{ opacity: 0.8 }}>
                    {card.icon}
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Paper sx={{ p: 3, mt: 4 }}>
        <Typography variant="h5" fontWeight="bold" gutterBottom>
          About TABLESYS
        </Typography>
        <Typography variant="body1" paragraph>
          TABLESYS is a comprehensive timetable generation and management system designed
          specifically for the University of Zambia. The system uses advanced constraint
          programming to generate optimal timetables that satisfy all requirements.
        </Typography>
        
        <Typography variant="h6" fontWeight="bold" gutterBottom sx={{ mt: 3 }}>
          Key Features:
        </Typography>
        <Box component="ul" sx={{ pl: 2 }}>
          <Typography component="li" variant="body1" paragraph>
            <strong>Level-Based Generation:</strong> Timetables are generated progressively
            from 5th year down to 2nd year, ensuring optimal resource allocation.
          </Typography>
          <Typography component="li" variant="body1" paragraph>
            <strong>Real-Time Progress:</strong> Track timetable generation with live
            updates and percentage progress indicators.
          </Typography>
          <Typography component="li" variant="body1" paragraph>
            <strong>Role-Based Access:</strong> Clear separation between Coordinator and
            HOD privileges for better security and workflow management.
          </Typography>
          <Typography component="li" variant="body1" paragraph>
            <strong>Bulk Import:</strong> Efficiently upload courses, lecturers, rooms,
            and groups using Excel or CSV files.
          </Typography>
        </Box>
      </Paper>
    </Box>
  );
};

export default DashboardPage;
