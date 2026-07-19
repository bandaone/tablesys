import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Button,
  Container,
  Typography,
  TextField,
  Paper,
  Alert,
  Chip,
  Grid,
  Avatar,
  Divider,
  useTheme,
  useMediaQuery,
  CircularProgress,
  InputAdornment,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import {
  School as SchoolIcon,
  ElectricalServices as ElectricalIcon,
  LockOpen as LockOpenIcon,
  CheckCircle as CheckCircleIcon,
  RadioButtonUnchecked as RadioButtonUncheckedIcon,
  Visibility,
  VisibilityOff,
  Business as BusinessIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useBranding } from '../contexts/BrandingContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

// Password validation requirements
interface PasswordRequirement {
  id: string;
  label: string;
  validator: (password: string) => boolean;
}

const passwordRequirements: PasswordRequirement[] = [
  { id: 'minLength', label: 'At least 8 characters', validator: (pwd) => pwd.length >= 8 },
];

const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [shake, setShake] = useState(false);
  const [autoLoginTriggered, setAutoLoginTriggered] = useState(false);
  const [ssoProviders, setSsoProviders] = useState({ google: false, microsoft: false });

  const { login } = useAuth();
  const { branding, loading: brandingLoading } = useBranding();
  const navigate = useNavigate();

  // Fetch which SSO providers are enabled from the backend (once)
  useEffect(() => {
    axios.get('/api/v1/auth/sso/providers')
      .then(r => setSsoProviders({ google: r.data.google, microsoft: r.data.microsoft }))
      .catch(() => { /* SSO unavailable — silently hide buttons */ });
  }, []);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const autoLoginTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Default Platform Colors (used if no ?school param is present)
  const defaultColors = {
    primaryDark: '#0a2e1a',
    primaryLight: '#006837',
    secondary: '#FDB913',
    accent: '#c58f00',
  };

  // The active colours dynamically switch to the school if loaded
  const activeColors = branding.university_id !== 0 ? {
    primaryDark: branding.primary_color,
    primaryLight: branding.primary_color,
    secondary: branding.secondary_color,
    accent: branding.secondary_color,
  } : defaultColors;



  // Validation state
  const isUsernameValid = username.trim().length >= 3;
  const passwordValidationState = passwordRequirements.map(req => ({
    ...req,
    isValid: req.validator(password)
  }));
  const allPasswordRequirementsMet = passwordValidationState.every(req => req.isValid);
  const isFormValid = isUsernameValid && allPasswordRequirementsMet;

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await performLogin();
  };

  const performLogin = async () => {
    setError('');
    setLoading(true);
    setShake(false);

    try {
      const loggedUser = await login(username, password);
      if (loggedUser?.role?.toUpperCase() === 'SUPERADMIN') {
        navigate('/superadmin');
      } else {
        navigate('/dashboard');
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || 'Login failed. Please check your credentials.');

      // Shake animation and clear password on error
      setShake(true);
      setTimeout(() => setShake(false), 500);
      setPassword('');
      setAutoLoginTriggered(false);

      // Focus back on password field
      const passwordField = document.getElementById('password-field');
      if (passwordField) {
        passwordField.focus();
      }
    } finally {
      setLoading(false);
    }
  };

  /* Animation Keyframes */
  const animations = {
    fadeIn: {
      '@keyframes fadeIn': {
        '0%': { opacity: 0 },
        '100%': { opacity: 1 },
      },
    },
    slideUp: {
      '@keyframes slideUp': {
        '0%': { opacity: 0, transform: 'translateY(20px)' },
        '100%': { opacity: 1, transform: 'translateY(0)' },
      },
    },
    float: {
      '@keyframes float': {
        '0%': { transform: 'translateY(0px)' },
        '50%': { transform: 'translateY(-10px)' },
        '100%': { transform: 'translateY(0px)' },
      },
    },
    pulse: {
      '@keyframes pulse': {
        '0%': { boxShadow: '0 0 0 0 rgba(255, 255, 255, 0.4)' },
        '70%': { boxShadow: '0 0 0 10px rgba(255, 255, 255, 0)' },
        '100%': { boxShadow: '0 0 0 0 rgba(255, 255, 255, 0)' },
      },
    },
    shake: {
      '@keyframes shake': {
        '0%, 100%': { transform: 'translateX(0)' },
        '10%, 30%, 50%, 70%, 90%': { transform: 'translateX(-10px)' },
        '20%, 40%, 60%, 80%': { transform: 'translateX(10px)' },
      },
    },
  };



  return (
    <Box
      sx={{
        minHeight: '100vh',
        backgroundColor: activeColors.primaryDark,
        background: `linear-gradient(135deg, ${activeColors.primaryDark} 0%, ${activeColors.primaryLight} 52%, ${activeColors.secondary} 130%)`,
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        py: 4,
        px: 2,
        overflow: 'hidden',
        isolation: 'isolate',
        '&::before': {
          content: '""',
          position: 'absolute',
          inset: 0,
          background: `radial-gradient(circle at 90% 12%, rgba(255,255,255,0.14) 0 105px, rgba(255,255,255,0.075) 106px 235px, transparent 236px), radial-gradient(circle at 7% 93%, rgba(255,255,255,0.11) 0 82px, rgba(255,255,255,0.055) 83px 195px, transparent 196px), radial-gradient(circle at 72% 86%, rgba(255,255,255,0.055) 0 58px, transparent 59px)`,
          zIndex: 0
        },
        '&::after': {
          content: '""',
          position: 'absolute',
          width: 520,
          height: 520,
          right: -250,
          top: -270,
          borderRadius: '50%',
          border: '1px solid rgba(255,255,255,0.16)',
          boxShadow: '0 0 0 62px rgba(255,255,255,0.035), 0 0 0 145px rgba(255,255,255,0.025)',
          zIndex: 0,
        },
        ...animations.fadeIn,
        ...animations.shake,
        animation: 'fadeIn 1s ease-out',
        '& > *': { position: 'relative', zIndex: 1 }
      }}
    >
      <Container maxWidth="lg" sx={{ position: 'relative', zIndex: 1 }}>
        <Grid container spacing={4} alignItems="stretch" sx={{ minHeight: '80vh' }}>
          {/* Left Panel - Dynamic Branding */}
          {!isMobile && (
            <Grid item xs={12} md={6} sx={{ display: 'flex' }}>
              <Paper
                elevation={0}
                sx={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  backdropFilter: 'blur(30px) saturate(150%)',
                  WebkitBackdropFilter: 'blur(30px) saturate(150%)',
                  color: 'white',
                  p: 5,
                  textAlign: 'center',
                  borderRadius: '32px',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  boxShadow: '0 20px 50px rgba(0, 0, 0, 0.3)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center',
                  alignItems: 'center',
                  width: '100%',
                  ...animations.slideUp,
                  animation: 'slideUp 0.8s ease-out 0.2s backwards'
                }}
              >
                <Box sx={{
                  display: 'flex',
                  justifyContent: 'center',
                  width: '100%',
                  ...animations.float,
                  animation: 'float 6s ease-in-out infinite'
                }}>
                  {branding.logo_url ? (
                    <Box 
                      component="img" 
                      src={`/media/logos/${branding.university_id}/logo.png`} 
                      alt="Logo" 
                      sx={{ width: 140, height: 140, objectFit: 'contain', mb: 3, filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.3))' }} 
                    />
                  ) : (
                    <SchoolIcon sx={{ fontSize: 100, mb: 3, filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.3))' }} />
                  )}
                </Box>

                <Typography
                  variant="h3"
                  sx={{
                    fontWeight: 800,
                    mb: 1,
                    letterSpacing: 2,
                    color: '#ffffff',
                    textShadow: '0 3px 14px rgba(0,0,0,0.38)',
                    fontFamily: '"Montserrat", sans-serif'
                  }}
                >
                  {branding.short_name || branding.name || 'TABLESYS'}
                </Typography>
                
                {branding.name && branding.short_name && (
                   <Typography variant="h6" sx={{ mb: 4, color: '#ffffff', opacity: 0.94, fontWeight: 300, textShadow: '0 2px 10px rgba(0,0,0,0.28)' }}>
                     {branding.name}
                   </Typography>
                )}

                <Divider sx={{ width: '60%', mb: 4, bgcolor: 'rgba(255,255,255,0.3)' }} />

                <Box sx={{ textAlign: 'center', width: '100%' }}>
                  <Typography variant="h5" sx={{ color: '#ffffff', fontWeight: 700, mb: 2, letterSpacing: 2, textShadow: '0 2px 10px rgba(0,0,0,0.28)' }}>
                    {branding.tagline || 'MULTI-UNIVERSITY TIMETABLE PLATFORM'}
                  </Typography>
                </Box>
              </Paper>
            </Grid>
          )}

          {/* Right Panel - Login Card */}
          <Grid item xs={12} md={6} sx={{ display: 'flex' }}>
            <Paper
              elevation={24}
              sx={{
                p: { xs: 4, sm: 6, md: 8 },
                borderRadius: '32px',
                background: 'rgba(255, 255, 255, 0.05)',
                backdropFilter: 'blur(40px) saturate(150%)',
                WebkitBackdropFilter: 'blur(40px) saturate(150%)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                boxShadow: '0 25px 60px rgba(0, 0, 0, 0.4)',
                position: 'relative',
                overflow: 'hidden',
                width: '100%',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                ...animations.slideUp,
                animation: shake ? 'shake 0.5s' : 'slideUp 0.8s ease-out 0.4s backwards'
              }}
            >
              <Box sx={{ textAlign: 'center', mb: 4 }}>
                <Avatar
                  sx={{
                    bgcolor: 'rgba(255,255,255,0.2)',
                    width: 70,
                    height: 70,
                    mx: 'auto',
                    mb: 2,
                    border: '2px solid rgba(255,255,255,0.5)',
                    ...animations.pulse,
                    animation: 'pulse 2s infinite'
                  }}
                >
                  <LockOpenIcon sx={{ fontSize: 35, color: '#fff' }} />
                </Avatar>
                <Typography variant="h4" sx={{ fontWeight: 700, color: '#fff', mb: 1, textShadow: '0 2px 4px rgba(0,0,0,0.2)' }}>
                  Welcome
                </Typography>
                <Typography variant="body1" sx={{ color: 'rgba(255,255,255,0.8)' }}>
                  {loading ? 'Signing you in...' : 'Sign in to access your dashboard'}
                </Typography>
              </Box>

              {error && (
                <Alert
                  severity="error"
                  sx={{
                    mb: 3,
                    borderRadius: 2,
                    background: 'rgba(211, 47, 47, 0.1)',
                    color: '#ffcdd2',
                    border: '1px solid rgba(211, 47, 47, 0.3)'
                  }}
                >
                  {error}
                </Alert>
              )}

              {/* Login Form */}
              <Box
                component="form"
                autoComplete="off"
                onSubmit={(e: React.FormEvent) => {
                  e.preventDefault();
                  void handleManualSubmit(e);
                }}
              >
                <TextField
                  fullWidth
                  label="Username"
                  placeholder="Enter your username"
                  variant="outlined"
                  value={username}
                  autoComplete="new-password"
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => { setUsername(e.target.value); }}
                  sx={{
                    mb: 3,
                    '& .MuiOutlinedInput-root': {
                      background: 'rgba(255, 255, 255, 0.1)',
                      borderRadius: 3,
                      color: '#fff',
                      transition: 'all 0.3s ease',
                      '& fieldset': { borderColor: 'rgba(255, 255, 255, 0.3)' },
                      '&:hover fieldset': { borderColor: 'rgba(255, 255, 255, 0.5)' },
                      '&.Mui-focused': {
                        background: 'rgba(255, 255, 255, 0.2)',
                        '& fieldset': { borderColor: '#fff' },
                      },
                    },
                    '& .MuiInputLabel-root': { color: 'rgba(255, 255, 255, 0.7)' },
                    '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                  }}
                  InputProps={{
                    startAdornment: (
                      <SchoolIcon sx={{ color: 'rgba(255,255,255,0.7)', mr: 1.5 }} />
                    ),
                    endAdornment: isUsernameValid ? (
                      <InputAdornment position="end">
                        <CheckCircleIcon sx={{ color: '#4caf50' }} />
                      </InputAdornment>
                    ) : null,
                  }}
                />

                <TextField
                  fullWidth
                  id="password-field"
                  label="Password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Enter your password"
                  autoComplete="new-password"
                  variant="outlined"
                  value={password}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                    setPassword(e.target.value);
                    setAutoLoginTriggered(false); // Reset auto-login trigger on password change
                  }}
                  sx={{
                    mb: 2,
                    '& .MuiOutlinedInput-root': {
                      background: 'rgba(255, 255, 255, 0.1)',
                      borderRadius: 3,
                      color: '#fff',
                      transition: 'all 0.3s ease',
                      '& fieldset': { borderColor: 'rgba(255, 255, 255, 0.3)' },
                      '&:hover fieldset': { borderColor: 'rgba(255, 255, 255, 0.5)' },
                      '&.Mui-focused': {
                        background: 'rgba(255, 255, 255, 0.2)',
                        '& fieldset': { borderColor: '#fff' },
                      },
                    },
                    '& .MuiInputLabel-root': { color: 'rgba(255, 255, 255, 0.7)' },
                    '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                  }}
                  InputProps={{
                    startAdornment: (
                      <LockOpenIcon sx={{ color: 'rgba(255,255,255,0.7)', mr: 1.5 }} />
                    ),
                    endAdornment: (
                      <InputAdornment position="end">
                        <Box
                          onClick={() => setShowPassword(!showPassword)}
                          sx={{ cursor: 'pointer', display: 'flex', alignItems: 'center', color: 'rgba(255,255,255,0.7)' }}
                        >
                          {showPassword ? <VisibilityOff /> : <Visibility />}
                        </Box>
                      </InputAdornment>
                    ),
                  }}
                />

                {/* Password Requirements Checklist */}
                {password.length > 0 && (
                  <Box sx={{ mb: 3, p: 2, background: 'rgba(255, 255, 255, 0.05)', borderRadius: 2 }}>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', mb: 1, display: 'block', fontWeight: 600 }}>
                      PASSWORD REQUIREMENTS
                    </Typography>
                    <List dense sx={{ py: 0 }}>
                      {passwordValidationState.map((req) => (
                        <ListItem key={req.id} sx={{ py: 0.5, px: 0 }}>
                          <ListItemIcon sx={{ minWidth: 32 }}>
                            {req.isValid ? (
                              <CheckCircleIcon sx={{ color: '#4caf50', fontSize: 20 }} />
                            ) : (
                              <RadioButtonUncheckedIcon sx={{ color: 'rgba(255,255,255,0.3)', fontSize: 20 }} />
                            )}
                          </ListItemIcon>
                          <ListItemText
                            primary={req.label}
                            sx={{
                              '& .MuiListItemText-primary': {
                                fontSize: '0.875rem',
                                color: req.isValid ? '#4caf50' : 'rgba(255,255,255,0.6)',
                                textDecoration: req.isValid ? 'line-through' : 'none',
                                transition: 'all 0.3s ease',
                              }
                            }}
                          />
                        </ListItem>
                      ))}
                    </List>
                  </Box>
                )}



                {/* Auto-login status indicator */}
                {loading && (
                  <Box sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 2,
                    py: 3,
                    px: 4,
                    borderRadius: 3,
                    background: 'rgba(255, 255, 255, 0.1)',
                    backdropFilter: 'blur(10px)',
                    border: '1px solid rgba(255, 255, 255, 0.2)'
                  }}>
                    <CircularProgress size={24} sx={{ color: '#4caf50' }} />
                    <Typography variant="body1" sx={{ color: '#fff', fontWeight: 600 }}>
                      Signing you in...
                    </Typography>
                  </Box>
                )}

                <Button
                  type="submit"
                  fullWidth
                  variant="contained"
                  disabled={!isFormValid || loading}
                  sx={{
                    mt: 2,
                    py: 1.5,
                    bgcolor: activeColors.secondary,
                    color: '#fff',
                    borderRadius: 3,
                    fontWeight: 700,
                    letterSpacing: 1,
                    '&:hover': {
                      bgcolor: activeColors.accent,
                      transform: 'translateY(-2px)',
                      boxShadow: '0 8px 20px rgba(0,0,0,0.3)'
                    },
                    '&:disabled': {
                      bgcolor: 'rgba(255,255,255,0.1)',
                      color: 'rgba(255,255,255,0.3)'
                    },
                    transition: 'all 0.3s ease'
                  }}
                >
                  {loading ? 'Authenticating...' : 'Sign In'}
                </Button>

                {/* ── SSO Divider + Buttons ─────────────────────────────── */}
                {(ssoProviders.google || ssoProviders.microsoft) && (
                  <>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, my: 2.5 }}>
                      <Box sx={{ flex: 1, height: '1px', bgcolor: 'rgba(255,255,255,0.15)' }} />
                      <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.4)', whiteSpace: 'nowrap', fontWeight: 600 }}>
                        or continue with
                      </Typography>
                      <Box sx={{ flex: 1, height: '1px', bgcolor: 'rgba(255,255,255,0.15)' }} />
                    </Box>

                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                      {ssoProviders.google && (
                        <Button
                          id="sso-google-btn"
                          fullWidth
                          variant="outlined"
                          onClick={() => { window.location.href = '/api/v1/auth/sso/google/authorize'; }}
                          startIcon={
                            <Box component="img"
                              src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg"
                              alt="Google"
                              sx={{ width: 18, height: 18 }}
                            />
                          }
                          sx={{
                            py: 1.25, borderRadius: 3, fontWeight: 600,
                            textTransform: 'none', fontSize: '0.9rem',
                            bgcolor: '#fff', color: '#374151',
                            border: '1px solid rgba(255,255,255,0.3)',
                            '&:hover': { bgcolor: '#f3f4f6', borderColor: '#fff', transform: 'translateY(-1px)', boxShadow: '0 4px 12px rgba(0,0,0,0.2)' },
                            transition: 'all 0.2s',
                          }}
                        >
                          Continue with Google
                        </Button>
                      )}

                      {ssoProviders.microsoft && (
                        <Button
                          id="sso-microsoft-btn"
                          fullWidth
                          variant="outlined"
                          onClick={() => { window.location.href = '/api/v1/auth/sso/microsoft/authorize'; }}
                          startIcon={
                            <Box component="img"
                              src="https://learn.microsoft.com/en-us/azure/active-directory/develop/media/howto-add-app-roles-in-apps/icon-microsoft.png"
                              alt="Microsoft"
                              sx={{ width: 18, height: 18 }}
                            />
                          }
                          sx={{
                            py: 1.25, borderRadius: 3, fontWeight: 600,
                            textTransform: 'none', fontSize: '0.9rem',
                            bgcolor: '#fff', color: '#374151',
                            border: '1px solid rgba(255,255,255,0.3)',
                            '&:hover': { bgcolor: '#f3f4f6', borderColor: '#fff', transform: 'translateY(-1px)', boxShadow: '0 4px 12px rgba(0,0,0,0.2)' },
                            transition: 'all 0.2s',
                          }}
                        >
                          Continue with Microsoft
                        </Button>
                      )}
                    </Box>
                  </>
                )}
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
};

export default LoginPage;
