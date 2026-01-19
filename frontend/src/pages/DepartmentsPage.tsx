import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  Alert,
  Chip,
} from '@mui/material';
import {
  Engineering as EngineeringIcon,
  School as SchoolIcon,
} from '@mui/icons-material';
import { departmentsAPI } from '../api';
import { useNavigate } from 'react-router-dom';

interface Department {
  id: number;
  code: string;
  name: string;
}

const DepartmentsPage: React.FC = () => {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    void fetchDepartments();
  }, []);

  const fetchDepartments = async () => {
    try {
      const data = await departmentsAPI.getAll();
      setDepartments(data);
    } catch (err) {
      setError('Failed to load departments');
    }
  };

  const getDepartmentColor = (code: string) => {
    const colors: Record<string, string> = {
      'AEN': '#4caf50',
      'MEC': '#2196f3',
      'EEE': '#ff9800',
      'CEE': '#9c27b0',
      'GEE': '#f44336',
      'GEN': '#607d8b',
    };
    return colors[code] || '#757575';
  };

  return (
    <Box>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" fontWeight="bold" gutterBottom>
          Departments
        </Typography>
        <Typography variant="body1" color="text.secondary">
          School of Engineering departments at the University of Zambia
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => { setError(''); }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {departments.map((dept) => (
          <Grid item xs={12} sm={6} md={4} key={dept.id}>
            <Card
              elevation={3}
              onClick={() => { navigate(`/courses?dept=${dept.id}`); }}
              sx={{
                height: '100%',
                borderTop: `4px solid ${getDepartmentColor(dept.code)}`,
                transition: 'transform 0.2s',
                cursor: 'pointer',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: 6,
                }
              }}
            >
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <EngineeringIcon
                    sx={{
                      fontSize: 40,
                      color: getDepartmentColor(dept.code),
                      mr: 2
                    }}
                  />
                  <Chip
                    label={dept.code}
                    sx={{
                      backgroundColor: getDepartmentColor(dept.code),
                      color: 'white',
                      fontWeight: 'bold'
                    }}
                  />
                </Box>
                <Typography variant="h6" fontWeight="bold" gutterBottom>
                  {dept.name}
                </Typography>
                <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <SchoolIcon fontSize="small" color="action" />
                  <Typography variant="body2" color="text.secondary">
                    School of Engineering
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {departments.length === 0 && !error && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            No departments found. Please contact the system administrator.
          </Typography>
        </Paper>
      )}

      <Box sx={{ mt: 4 }}>
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" fontWeight="bold" gutterBottom>
            About the Departments
          </Typography>
          <Typography variant="body2" paragraph>
            The School of Engineering at the University of Zambia comprises five academic departments and a general studies unit:
          </Typography>
          <ul>
            <li>
              <Typography variant="body2">
                <strong>GEN</strong> - General: Courses shared across multiple departments or foundational engineering courses.
              </Typography>
            </li>
            <li>
              <Typography variant="body2">
                <strong>AEN</strong> - Agricultural Engineering: Focuses on the application of engineering principles to agricultural production and processing.
              </Typography>
            </li>
            <li>
              <Typography variant="body2">
                <strong>MEC</strong> - Mechanical Engineering: Covers design, manufacturing, and maintenance of mechanical systems.
              </Typography>
            </li>
            <li>
              <Typography variant="body2">
                <strong>EEE</strong> - Electrical and Electronics Engineering: Specializes in electrical systems, electronics, and power systems.
              </Typography>
            </li>
            <li>
              <Typography variant="body2">
                <strong>CEE</strong> - Civil and Environmental Engineering: Deals with infrastructure design, construction, and environmental systems.
              </Typography>
            </li>
            <li>
              <Typography variant="body2">
                <strong>GEE</strong> - Geomatic Engineering: Focuses on surveying, mapping, and geospatial technologies.
              </Typography>
            </li>
          </ul>
        </Paper>
      </Box>
    </Box>
  );
};

export default DepartmentsPage;
