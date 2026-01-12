import React, { useState } from 'react';
import {
  Box,
  Container,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
  Chip,
  Grid,
  Avatar,
  Divider,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import { 
  School as SchoolIcon, 
  Engineering as EngineeringIcon,
  ElectricalServices as ElectricalIcon,
  Agriculture as AgricultureIcon,
  Terrain as TerrainIcon,
  LockOpen as LockOpenIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedDept, setSelectedDept] = useState('');
  
  const { login } = useAuth();
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  // UNZA Official Colors
  const unzaColors = {
    primaryDark: '#003366',
    primaryLight: '#0055A4',
    secondary: '#FF8C00',
    accent: '#4A90E2',
    paper: '#FFFFFF',
    border: '#E0E0E0',
    textDark: '#212121',
    textLight: '#757575'
  };

  // School of Engineering Departments
  const departments = [
    { code: 'AEN', name: 'Agricultural Engineering', icon: <AgricultureIcon />, color: '#2E7D32' },
    { code: 'MEC', name: 'Mechanical Engineering', icon: <EngineeringIcon />, color: '#D32F2F' },
    { code: 'EEE', name: 'Electrical & Electronics', icon: <ElectricalIcon />, color: '#1976D2' },
    { code: 'CEE', name: 'Civil & Environmental', icon: <EngineeringIcon />, color: '#F57C00' },
    { code: 'GEE', name: 'Geomatics Engineering', icon: <TerrainIcon />, color: '#7B1FA2' },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(username);
      navigate('/dashboard');
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || 'Login failed. Please check your username.');
    } finally {
      setLoading(false);
    }
  };

  const handleDeptSelect = (deptCode: string) => {
    setSelectedDept(deptCode);
    setUsername(deptCode);
  };

  const handleUserSelect = (user: string) => {
    setUsername(user);
    setSelectedDept(user);
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: `linear-gradient(135deg, ${unzaColors.primaryDark} 0%, ${unzaColors.primaryLight} 100%)`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        py: 4,
        px: 2
      }}
    >
      <Container maxWidth="lg">
        <Grid container spacing={4} alignItems="center">
          {/* Left Panel - UNZA Branding */}
          {!isMobile && (
            <Grid item xs={12} md={6}>
              <Paper
                elevation={0}
                sx={{
                  background: 'transparent',
                  color: 'white',
                  p: 4,
                  textAlign: 'center'
                }}
              >
                <SchoolIcon sx={{ fontSize: 80, mb: 3, opacity: 0.9 }} />
                
                <Typography 
                  variant="h3" 
                  sx={{ 
                    fontWeight: 700,
                    mb: 2,
                    letterSpacing: 1
                  }}
                >
                  UNIVERSITY OF ZAMBIA
                </Typography>
                
                <Divider 
                  sx={{ 
                    my: 3, 
                    borderColor: unzaColors.secondary,
                    borderWidth: 2,
                    width: '60%',
                    mx: 'auto'
                  }} 
                />
                
                <Typography 
                  variant="h5" 
                  sx={{ 
                    fontWeight: 500,
                    mb: 1,
                    fontStyle: 'italic'
                  }}
                >
                  School of Engineering
                </Typography>
                
                <Typography 
                  variant="subtitle1"
                  sx={{ 
                    opacity: 0.9,
                    mb: 4
                  }}
                >
                  Office of the Dean • Great East Road Campus
                </Typography>
                
                <Box sx={{ mt: 6 }}>
                  <Typography variant="h4" sx={{ fontWeight: 600, mb: 2 }}>
                    TABLESYS
                  </Typography>
                  <Typography variant="subtitle1" sx={{ opacity: 0.9 }}>
                    Timetable Management System
                  </Typography>
                </Box>
              </Paper>
            </Grid>
          )}

          {/* Right Panel - Login Card */}
          <Grid item xs={12} md={6}>
            <Paper
              elevation={8}
              sx={{
                p: { xs: 3, sm: 4, md: 5 },
                borderRadius: 2,
                background: unzaColors.paper,
                borderLeft: `6px solid ${unzaColors.secondary}`,
                position: 'relative',
                overflow: 'hidden'
              }}
            >
              {/* UNZA Header Strip */}
              <Box
                sx={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  height: 8,
                  background: unzaColors.primaryDark
                }}
              />
              
              <Box sx={{ textAlign: 'center', mb: 4 }}>
                <LockOpenIcon 
                  sx={{ 
                    fontSize: 48, 
                    color: unzaColors.primaryDark,
                    mb: 2 
                  }} 
                />
                <Typography variant="h5" sx={{ fontWeight: 600, color: unzaColors.textDark }}>
                  System Access Portal
                </Typography>
                <Typography variant="body2" sx={{ color: unzaColors.textLight, mt: 1 }}>
                  No password required • Select your role
                </Typography>
              </Box>

              {error && (
                <Alert severity="error" sx={{ mb: 3 }}>
                  {error}
                </Alert>
              )}

              {/* Login Form */}
              <Box 
                component="form" 
                onSubmit={(e: React.FormEvent) => {
                  e.preventDefault();
                  void handleSubmit(e);
                }}
              >
                <TextField
                  fullWidth
                  label="Username / Department Code"
                  variant="outlined"
                  value={username}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => { setUsername(e.target.value.toUpperCase()); }}
                  sx={{
                    mb: 3,
                    '& .MuiOutlinedInput-root': {
                      '&.Mui-focused fieldset': {
                        borderColor: unzaColors.primaryLight,
                      },
                    },
                  }}
                  InputProps={{
                    startAdornment: (
                      <Avatar sx={{ bgcolor: unzaColors.accent, mr: 2, width: 32, height: 32 }}>
                        <SchoolIcon fontSize="small" />
                      </Avatar>
                    ),
                  }}
                />

                {/* Department Quick Select */}
                <Typography variant="subtitle2" sx={{ mb: 2, color: unzaColors.textDark, fontWeight: 500 }}>
                  Quick Select Department:
                </Typography>
                <Grid container spacing={1} sx={{ mb: 4 }}>
                  {departments.map((dept) => (
                    <Grid item key={dept.code}>
                      <Chip
                        icon={dept.icon}
                        label={dept.code}
                        onClick={() => { handleDeptSelect(dept.code); }}
                        sx={{
                          bgcolor: selectedDept === dept.code ? unzaColors.primaryLight : 'transparent',
                          color: selectedDept === dept.code ? 'white' : unzaColors.primaryDark,
                          border: `1px solid ${dept.color}`,
                          fontWeight: 500,
                          '&:hover': {
                            bgcolor: unzaColors.primaryLight,
                            color: 'white'
                          }
                        }}
                      />
                    </Grid>
                  ))}
                </Grid>

                {/* Available Users */}
                <Typography variant="subtitle2" sx={{ mb: 2, color: unzaColors.textDark, fontWeight: 500 }}>
                  Available Users:
                </Typography>
                <Grid container spacing={1} sx={{ mb: 4 }}>
                  {['coordinator', 'admin', 'AEN', 'MEC', 'EEE', 'CEE', 'GEE'].map((user) => (
                    <Grid item key={user}>
                      <Chip
                        label={user}
                        size="small"
                        onClick={() => { handleUserSelect(user); }}
                        sx={{
                          bgcolor: username === user ? unzaColors.secondary : unzaColors.accent + '20',
                          color: username === user ? 'white' : unzaColors.primaryDark,
                          fontWeight: username === user ? 600 : 400,
                          '&:hover': {
                            bgcolor: unzaColors.secondary,
                            color: 'white'
                          }
                        }}
                      />
                    </Grid>
                  ))}
                </Grid>

                <Button
                  fullWidth
                  type="submit"
                  variant="contained"
                  disabled={!username.trim() || loading}
                  sx={{
                    py: 1.5,
                    bgcolor: unzaColors.primaryDark,
                    '&:hover': {
                      bgcolor: unzaColors.primaryLight,
                    },
                    fontSize: '1rem',
                    fontWeight: 600,
                    textTransform: 'none',
                    borderRadius: 1
                  }}
                >
                  {loading ? 'Signing in...' : 'Access System'}
                </Button>
              </Box>

              {/* Footer Note */}
              <Alert 
                severity="info" 
                sx={{ 
                  mt: 4,
                  bgcolor: unzaColors.accent + '20',
                  border: `1px solid ${unzaColors.accent}`,
                  color: unzaColors.primaryDark
                }}
              >
                <Typography variant="caption">
                  <strong>Note:</strong> Coordinators have full system access. HODs can only manage their respective departments.
                </Typography>
              </Alert>

              <Box sx={{ mt: 3, textAlign: 'center' }}>
                <Typography variant="caption" sx={{ color: unzaColors.textLight }}>
                  University of Zambia • School of Engineering • 2026
                </Typography>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
};

export default LoginPage;
