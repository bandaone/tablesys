import React, { useState } from 'react';
import {
  Box,
  Button,
  Container,
  Paper,
  TextField,
  Typography,
  Alert,
  Stepper,
  Step,
  StepLabel,
  InputAdornment,
  CircularProgress,
  Grid,
  Link,
} from '@mui/material';
import {
  Business as BusinessIcon,
  Person as PersonIcon,
  Lock as LockIcon,
  Email as EmailIcon,
  Language as DomainIcon,
  CheckCircle as CheckCircleIcon,
  ArrowForward as ArrowForwardIcon,
  ArrowBack as ArrowBackIcon,
  TableChart as TableChartIcon,
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import { publicAPI } from '../api';
import { useNavigate } from 'react-router-dom';

const steps = ['Organization', 'Admin Profile', 'Security'];

/* ─── Shared field style ──────────────────────────────────────────────────── */
const fieldSx = {
  '& .MuiOutlinedInput-root': {
    borderRadius: '12px',
    background: 'rgba(255,255,255,0.06)',
    color: '#ffffff',
    '& input': {
      color: '#ffffff',
      WebkitTextFillColor: '#ffffff',
      '&::placeholder': { color: 'rgba(255,255,255,0.35)', opacity: 1 },
    },
    '& fieldset': { borderColor: 'rgba(255,255,255,0.18)', borderWidth: '1.5px' },
    '&:hover fieldset': { borderColor: 'rgba(255,255,255,0.45)' },
    '&.Mui-focused': {
      background: 'rgba(255,255,255,0.1)',
      '& fieldset': { borderColor: '#818cf8', borderWidth: '2px' },
    },
  },
  '& .MuiInputLabel-root': {
    color: 'rgba(255,255,255,0.55)',
    '&.Mui-focused': { color: '#a5b4fc' },
    '&.MuiFormLabel-filled': { color: 'rgba(255,255,255,0.8)' },
  },
  '& .MuiFormHelperText-root': { color: 'rgba(255,255,255,0.4)', mt: 0.5 },
  '& .MuiInputAdornment-root .MuiSvgIcon-root': { color: 'rgba(255,255,255,0.5)' },
};

const stepVariants = {
  hidden: { opacity: 0, x: 40 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.35 } },
  exit: { opacity: 0, x: -40, transition: { duration: 0.25 } },
};

const RegistrationPage: React.FC = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [isNavigating, setIsNavigating] = useState(false);

  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    organization_name: '',
    subdomain: '',
    admin_username: '',
    admin_full_name: '',
    admin_email: '',
    admin_password: '',
    confirm_password: '',
  });

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  const getPasswordStrength = (pw: string): { score: number; label: string; color: string } => {
    let score = 0;
    if (pw.length >= 8) score++;
    if (/[A-Z]/.test(pw)) score++;
    if (/[a-z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;
    if (score <= 2) return { score, label: 'Weak', color: '#ef4444' };
    if (score <= 3) return { score, label: 'Fair', color: '#f59e0b' };
    if (score <= 4) return { score, label: 'Strong', color: '#22c55e' };
    return { score, label: 'Excellent', color: '#10b981' };
  };

  const handleChange = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) => {
    let value = e.target.value;
    if (field === 'subdomain') value = value.toLowerCase().replace(/[^a-z0-9-]/g, '');
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleNext = () => {
    setError('');
    if (activeStep === 0) {
      if (formData.organization_name.trim().length < 2) { setError('Organization Name must be at least 2 characters.'); return; }
      if (formData.subdomain.length < 3) { setError('Subdomain must be at least 3 characters (letters, numbers, hyphens only).'); return; }
    }
    if (activeStep === 1) {
      if (formData.admin_full_name.trim().length < 2) { setError('Full Name must be at least 2 characters.'); return; }
      if (formData.admin_username.trim().length < 3) { setError('Username must be at least 3 characters.'); return; }
    }
    setActiveStep((p) => p + 1);
  };

  const handleBack = () => { setError(''); setActiveStep((p) => p - 1); };

  const handleSubmit = async () => {
    setError('');
    if (!emailRegex.test(formData.admin_email)) { setError('Please provide a valid email address.'); return; }
    if (formData.admin_password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    if (!/[A-Z]/.test(formData.admin_password)) { setError('Password must contain at least one uppercase letter.'); return; }
    if (!/[a-z]/.test(formData.admin_password)) { setError('Password must contain at least one lowercase letter.'); return; }
    if (!/[0-9]/.test(formData.admin_password)) { setError('Password must contain at least one digit.'); return; }
    if (formData.admin_password !== formData.confirm_password) { setError('Passwords do not match.'); return; }
    setLoading(true);
    try {
      await publicAPI.registerTenant(formData);
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleLoginClick = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsNavigating(true);
    setTimeout(() => {
      navigate('/login');
    }, 450);
  };

  /* Default Platform Colors for Registration */
  const activeColors = {
    primaryDark: '#0d47a1',
    primaryLight: '#1976d2',
    secondary: '#9c27b0',
    accent: '#7b1fa2',
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        backgroundColor: activeColors.primaryDark,
        background: `linear-gradient(135deg, ${activeColors.primaryDark} 0%, ${activeColors.primaryLight} 55%, ${activeColors.secondary} 100%)`,
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        py: 6,
        overflow: 'hidden',
        '&::before': {
          content: '""',
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.4)',
          backdropFilter: 'blur(10px)',
          zIndex: 0
        },
        '@keyframes fadeIn': {
          '0%': { opacity: 0 },
          '100%': { opacity: 1 },
        },
        animation: 'fadeIn 1s ease-out',
        '& > *': { position: 'relative', zIndex: 1 }
      }}
    >
      <Container maxWidth="sm" sx={{ position: 'relative', zIndex: 1 }}>
        <motion.div
          initial={{ opacity: 0, y: 36, filter: 'blur(8px)', scale: 0.95 }}
          animate={{ 
            opacity: isNavigating ? 0 : 1, 
            y: isNavigating ? -20 : 0, 
            filter: isNavigating ? 'blur(8px)' : 'blur(0px)',
            scale: isNavigating ? 0.98 : 1
          }}
          transition={{ duration: 0.45, ease: 'easeInOut' }}
        >
          {/* Brand header above card */}
          <Box display="flex" alignItems="center" justifyContent="center" gap={1.5} mb={4}>
            <Box
              sx={{
                width: 42, height: 42, borderRadius: '12px',
                background: 'linear-gradient(135deg, #1976d2, #9c27b0)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: '0 8px 24px rgba(0,104,55,0.35)',
              }}
            >
              <TableChartIcon sx={{ color: 'white', fontSize: 22 }} />
            </Box>
            <Typography variant="h5" fontWeight={800} letterSpacing={2} sx={{ color: '#fff', fontFamily: '"Inter", sans-serif' }}>
              TABLESYS
            </Typography>
          </Box>

          <Paper
            elevation={24}
            sx={{
              p: { xs: 4, sm: 6, md: 5 },
              borderRadius: '32px',
              background: 'rgba(255, 255, 255, 0.05)',
              backdropFilter: 'blur(40px) saturate(150%)',
              WebkitBackdropFilter: 'blur(40px) saturate(150%)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              boxShadow: '0 25px 60px rgba(0, 0, 0, 0.4)',
            }}
          >
            {/* ── Card header ── */}
            <Box textAlign="center" mb={4}>
              <Typography
                variant="h4"
                fontWeight={800}
                mb={0.75}
                sx={{ color: '#fff', letterSpacing: '-0.5px', fontFamily: '"Inter", sans-serif' }}
              >
                {success ? '🎉 You\'re Almost In!' : 'Create Your Workspace'}
              </Typography>
              <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.5)' }}>
                {success
                  ? 'A verification link has been sent to your email.'
                  : 'Enterprise-grade timetabling.'}
              </Typography>
            </Box>

            {success ? (
              /* ── Success state ── */
              <motion.div
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ type: 'spring', stiffness: 180, damping: 18 }}
              >
                <Box
                  sx={{
                    textAlign: 'center', py: 4, px: 2,
                    background: 'rgba(74,222,128,0.06)',
                    borderRadius: '16px',
                    border: '1px solid rgba(74,222,128,0.2)',
                  }}
                >
                  <CheckCircleIcon sx={{ fontSize: 80, color: '#4ade80', mb: 2 }} />
                  <Typography variant="h6" fontWeight={700} mb={1} sx={{ color: '#fff' }}>
                    Verification Email Sent
                  </Typography>
                  <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.6)', lineHeight: 1.7 }}>
                    We sent a magic link to{' '}
                    <Box component="span" sx={{ color: '#a5b4fc', fontWeight: 600 }}>
                      {formData.admin_email}
                    </Box>
                    .<br />Click it to activate your workspace and sign in automatically.
                  </Typography>
                </Box>
              </motion.div>
            ) : (
              <>
                {/* ── Step indicator ── */}
                <Stepper
                  activeStep={activeStep}
                  alternativeLabel
                  sx={{
                    mb: 4,
                    '& .MuiStepLabel-label': { color: 'rgba(255,255,255,0.4)', fontSize: '0.75rem', mt: 0.5 },
                    '& .MuiStepLabel-label.Mui-active': { color: '#9c27b0', fontWeight: 700 },
                    '& .MuiStepLabel-label.Mui-completed': { color: '#4ade80' },
                    '& .MuiStepIcon-root': { color: 'rgba(255,255,255,0.15)' },
                    '& .MuiStepIcon-root.Mui-active': { color: '#1976d2' },
                    '& .MuiStepIcon-root.Mui-completed': { color: '#4ade80' },
                    '& .MuiStepConnector-line': { borderColor: 'rgba(255,255,255,0.12)' },
                  }}
                >
                  {steps.map((label) => (
                    <Step key={label}>
                      <StepLabel>{label}</StepLabel>
                    </Step>
                  ))}
                </Stepper>

                {/* ── Error banner ── */}
                <AnimatePresence>
                  {error && (
                    <motion.div
                      key="err"
                      initial={{ opacity: 0, y: -8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                    >
                      <Alert
                        severity="error"
                        sx={{
                          mb: 3, borderRadius: '12px',
                          background: 'rgba(239,68,68,0.12)',
                          color: '#fca5a5',
                          border: '1px solid rgba(239,68,68,0.25)',
                          '& .MuiAlert-icon': { color: '#f87171' },
                        }}
                      >
                        {error}
                      </Alert>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* ── Step panels ── */}
                <Box sx={{ minHeight: 240, position: 'relative', overflow: 'hidden' }}>
                  <AnimatePresence mode="wait">

                    {/* STEP 1 — Organization */}
                    {activeStep === 0 && (
                      <motion.div key="s1" variants={stepVariants} initial="hidden" animate="visible" exit="exit" style={{ paddingTop: '10px' }}>
                        <Grid container spacing={2.5}>
                          <Grid item xs={12}>
                            <TextField
                              fullWidth
                              label="Organization Name"
                              variant="outlined"
                              value={formData.organization_name}
                              onChange={handleChange('organization_name')}
                              InputProps={{
                                startAdornment: (
                                  <InputAdornment position="start">
                                    <BusinessIcon />
                                  </InputAdornment>
                                ),
                              }}
                              sx={fieldSx}
                            />
                          </Grid>
                          <Grid item xs={12}>
                            <TextField
                              fullWidth
                              label="Workspace Subdomain"
                              variant="outlined"
                              value={formData.subdomain}
                              onChange={handleChange('subdomain')}
                              helperText="Lowercase letters, numbers, and hyphens only."
                              InputProps={{
                                startAdornment: (
                                  <InputAdornment position="start">
                                    <DomainIcon />
                                  </InputAdornment>
                                ),
                                endAdornment: (
                                  <InputAdornment position="end">
                                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.35)', whiteSpace: 'nowrap' }}>
                                      .tablesys.com
                                    </Typography>
                                  </InputAdornment>
                                ),
                              }}
                              sx={fieldSx}
                            />
                          </Grid>
                        </Grid>
                      </motion.div>
                    )}

                    {/* STEP 2 — Admin profile */}
                    {activeStep === 1 && (
                      <motion.div key="s2" variants={stepVariants} initial="hidden" animate="visible" exit="exit" style={{ paddingTop: '10px' }}>
                        <Grid container spacing={2.5}>
                          <Grid item xs={12}>
                            <TextField
                              fullWidth
                              label="Admin Full Name"
                              variant="outlined"
                              value={formData.admin_full_name}
                              onChange={handleChange('admin_full_name')}
                              InputProps={{
                                startAdornment: (
                                  <InputAdornment position="start"><PersonIcon /></InputAdornment>
                                ),
                              }}
                              sx={fieldSx}
                            />
                          </Grid>
                          <Grid item xs={12}>
                            <TextField
                              fullWidth
                              label="Admin Username"
                              variant="outlined"
                              value={formData.admin_username}
                              onChange={handleChange('admin_username')}
                              helperText="Used to sign in no spaces."
                              InputProps={{
                                startAdornment: (
                                  <InputAdornment position="start"><PersonIcon /></InputAdornment>
                                ),
                              }}
                              sx={fieldSx}
                            />
                          </Grid>
                        </Grid>
                      </motion.div>
                    )}

                    {/* STEP 3 — Security */}
                    {activeStep === 2 && (
                      <motion.div key="s3" variants={stepVariants} initial="hidden" animate="visible" exit="exit" style={{ paddingTop: '10px' }}>
                        <Grid container spacing={2.5}>
                          <Grid item xs={12}>
                            <TextField
                              fullWidth
                              label="Admin Email Address"
                              type="email"
                              variant="outlined"
                              value={formData.admin_email}
                              onChange={handleChange('admin_email')}
                              helperText="A verification link will be sent here."
                              InputProps={{
                                startAdornment: (
                                  <InputAdornment position="start"><EmailIcon /></InputAdornment>
                                ),
                              }}
                              sx={fieldSx}
                            />
                          </Grid>
                          <Grid item xs={12}>
                            <TextField
                              fullWidth
                              label="Master Password"
                              type="password"
                              variant="outlined"
                              value={formData.admin_password}
                              onChange={handleChange('admin_password')}
                              helperText="You can change this anytime from your dashboard."
                              InputProps={{
                                startAdornment: (
                                  <InputAdornment position="start"><LockIcon /></InputAdornment>
                                ),
                              }}
                              sx={fieldSx}
                            />
                            {formData.admin_password.length > 0 && (
                              <Box sx={{ mt: 1, px: 1 }}>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)' }}>
                                    Strength: <span style={{ color: getPasswordStrength(formData.admin_password).color }}>{getPasswordStrength(formData.admin_password).label}</span>
                                  </Typography>
                                </Box>
                                <Box sx={{ display: 'flex', gap: 0.5, height: 4 }}>
                                  {[1, 2, 3, 4].map((level) => (
                                    <Box
                                      key={level}
                                      sx={{
                                        flex: 1,
                                        bgcolor: level <= getPasswordStrength(formData.admin_password).score
                                          ? getPasswordStrength(formData.admin_password).color
                                          : 'rgba(255,255,255,0.1)',
                                        borderRadius: 1,
                                        transition: 'all 0.3s'
                                      }}
                                    />
                                  ))}
                                </Box>
                              </Box>
                            )}
                          </Grid>
                          <Grid item xs={12}>
                            <TextField
                              fullWidth
                              label="Confirm Password"
                              type="password"
                              variant="outlined"
                              value={formData.confirm_password}
                              onChange={handleChange('confirm_password')}
                              error={formData.confirm_password.length > 0 && formData.admin_password !== formData.confirm_password}
                              helperText={formData.confirm_password.length > 0 && formData.admin_password !== formData.confirm_password ? "Passwords do not match." : ""}
                              InputProps={{
                                startAdornment: (
                                  <InputAdornment position="start"><LockIcon /></InputAdornment>
                                ),
                              }}
                              sx={fieldSx}
                            />
                          </Grid>
                        </Grid>
                      </motion.div>
                    )}

                  </AnimatePresence>
                </Box>

                {/* ── Navigation buttons ── */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 4 }}>
                  <Button
                    startIcon={<ArrowBackIcon />}
                    disabled={activeStep === 0 || loading}
                    onClick={handleBack}
                    sx={{
                      color: 'rgba(255,255,255,0.5)',
                      textTransform: 'none',
                      fontWeight: 500,
                      '&:hover': { color: '#fff', background: 'rgba(255,255,255,0.06)' },
                      '&:disabled': { color: 'rgba(255,255,255,0.2)' },
                    }}
                  >
                    Back
                  </Button>

                  {activeStep === steps.length - 1 ? (
                    <Button
                      variant="contained"
                      onClick={handleSubmit}
                      disabled={loading}
                      endIcon={!loading && <ArrowForwardIcon />}
                      sx={{
                        px: 4, py: 1.25,
                        borderRadius: '12px',
                        fontWeight: 700,
                        fontSize: '0.95rem',
                        textTransform: 'none',
                        background: 'linear-gradient(135deg, #1976d2, #9c27b0)',
                        boxShadow: '0 8px 24px rgba(0,104,55,0.35)',
                        '&:hover': {
                          background: 'linear-gradient(135deg, #115293, #7b1fa2)',
                          boxShadow: '0 12px 32px rgba(0,104,55,0.45)',
                          transform: 'translateY(-1px)',
                        },
                        transition: 'all 0.2s',
                      }}
                    >
                      {loading ? <CircularProgress size={22} sx={{ color: 'white' }} /> : 'Create Workspace'}
                    </Button>
                  ) : (
                    <Button
                      variant="contained"
                      onClick={handleNext}
                      endIcon={<ArrowForwardIcon />}
                      sx={{
                        px: 4, py: 1.25,
                        borderRadius: '12px',
                        fontWeight: 700,
                        fontSize: '0.95rem',
                        textTransform: 'none',
                        background: 'linear-gradient(135deg, #1976d2, #9c27b0)',
                        boxShadow: '0 8px 24px rgba(0,104,55,0.35)',
                        '&:hover': {
                          background: 'linear-gradient(135deg, #115293, #7b1fa2)',
                          boxShadow: '0 12px 32px rgba(0,104,55,0.45)',
                          transform: 'translateY(-1px)',
                        },
                        transition: 'all 0.2s',
                      }}
                    >
                      Continue
                    </Button>
                  )}
                </Box>

                {/* ── Footer link ── */}
                <Box textAlign="center" mt={3}>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.35)' }}>
                    Already have a workspace?{' '}
                    <Link 
                      href="/login" 
                      onClick={handleLoginClick}
                      underline="hover" 
                      sx={{ color: '#a5b4fc', fontWeight: 600, cursor: 'pointer' }}
                    >
                      Sign in
                    </Link>
                  </Typography>
                </Box>
              </>
            )}
          </Paper>

          {/* ── Footer text ── */}
          <Box textAlign="center" mt={3}>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.2)' }}>
              By creating a workspace you agree to the TABLESYS Terms of Service & Privacy Policy.
            </Typography>
          </Box>
        </motion.div>
      </Container>
    </Box>
  );
};

export default RegistrationPage;
