import React, { useState } from 'react';
import { 
  Box, 
  Button, 
  Typography, 
  TextField, 
  Paper, 
  Container, 
  Alert,
  Stepper,
  Step,
  StepLabel
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { API_BASE_URL } from '../api';

const steps = ['University Details', 'Administrator Account'];

const OnboardingPage: React.FC = () => {
  const navigate = useNavigate();
  const [activeStep, setActiveStep] = useState(0);
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [success, setSuccess] = useState<boolean>(false);

  // Form Data
  const [formData, setFormData] = useState({
    university_name: '',
    domain: '',
    timezone: 'Africa/Harare',
    admin_user: {
      full_name: '',
      username: '',
      email: '',
      password: '',
      confirmPassword: ''
    }
  });

  const handleUnivChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleUserChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      admin_user: {
        ...formData.admin_user,
        [e.target.name]: e.target.value
      }
    });
  };

  const validateStep = () => {
    if (activeStep === 0) {
      if (!formData.university_name || !formData.domain || !formData.timezone) {
        setError("Please fill in all university fields");
        return false;
      }
    } else if (activeStep === 1) {
      if (!formData.admin_user.full_name || !formData.admin_user.username || 
          !formData.admin_user.email || !formData.admin_user.password) {
        setError("Please fill in all administrator fields");
        return false;
      }
      if (formData.admin_user.password !== formData.admin_user.confirmPassword) {
        setError("Passwords do not match");
        return false;
      }
    }
    setError("");
    return true;
  };

  const handleNext = () => {
    if (validateStep()) {
      setActiveStep((prevActiveStep) => prevActiveStep + 1);
    }
  };

  const handleBack = () => {
    setActiveStep((prevActiveStep) => prevActiveStep - 1);
    setError("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateStep()) return;

    setLoading(true);
    setError('');

    try {
      const payload = {
        university_name: formData.university_name,
        domain: formData.domain,
        timezone: formData.timezone,
        admin_user: {
          username: formData.admin_user.username,
          email: formData.admin_user.email,
          full_name: formData.admin_user.full_name,
          password: formData.admin_user.password
        }
      };

      await axios.post(`${API_BASE_URL}/onboarding/`, payload);
      setSuccess(true);
      setTimeout(() => navigate('/login'), 3000);
    } catch (err: any) {
      setError(
        err.response?.data?.detail?.[0]?.msg || 
        err.response?.data?.detail || 
        "Failed to register university. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <Container component="main" maxWidth="sm">
        <Box sx={{ marginTop: 8, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <Alert severity="success" sx={{ width: '100%', mb: 2 }}>
            University successfully registered! Validating instance... Redirecting to login...
          </Alert>
        </Box>
      </Container>
    );
  }

  return (
    <Container component="main" maxWidth="sm">
      <Paper elevation={3} sx={{ p: 4, mt: 8, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <Typography component="h1" variant="h5" sx={{ mb: 3 }}>
          Welcome to TableSys
        </Typography>
        <Typography variant="body2" color="textSecondary" sx={{ mb: 4, textAlign: 'center' }}>
          Set up your university workspace to begin generating professional timetables.
        </Typography>

        <Stepper activeStep={activeStep} sx={{ width: '100%', mb: 4 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {error && <Alert severity="error" sx={{ width: '100%', mb: 2 }}>{error}</Alert>}

        <Box component="form" noValidate sx={{ width: '100%' }}>
          {activeStep === 0 && (
            <Box>
              <TextField
                margin="normal"
                required
                fullWidth
                id="university_name"
                label="University Name"
                name="university_name"
                value={formData.university_name}
                onChange={handleUnivChange}
                autoFocus
              />
              <TextField
                margin="normal"
                required
                fullWidth
                id="domain"
                label="Primary Domain (e.g. university.edu)"
                name="domain"
                value={formData.domain}
                onChange={handleUnivChange}
                helperText="This domain will be used to identify your organizational tenant."
              />
              <TextField
                margin="normal"
                required
                fullWidth
                id="timezone"
                label="Timezone"
                name="timezone"
                defaultValue="Africa/Harare"
                value={formData.timezone}
                onChange={handleUnivChange}
              />
            </Box>
          )}

          {activeStep === 1 && (
            <Box>
              <TextField
                margin="normal"
                required
                fullWidth
                id="full_name"
                label="Admin Full Name"
                name="full_name"
                value={formData.admin_user.full_name}
                onChange={handleUserChange}
                autoFocus
              />
              <TextField
                margin="normal"
                required
                fullWidth
                id="username"
                label="Admin Username"
                name="username"
                value={formData.admin_user.username}
                onChange={handleUserChange}
              />
              <TextField
                margin="normal"
                required
                fullWidth
                id="email"
                label="Admin Email Address"
                name="email"
                type="email"
                value={formData.admin_user.email}
                onChange={handleUserChange}
              />
              <TextField
                margin="normal"
                required
                fullWidth
                name="password"
                label="Password"
                type="password"
                id="password"
                value={formData.admin_user.password}
                onChange={handleUserChange}
              />
              <TextField
                margin="normal"
                required
                fullWidth
                name="confirmPassword"
                label="Confirm Password"
                type="password"
                id="confirmPassword"
                value={formData.admin_user.confirmPassword}
                onChange={handleUserChange}
              />
            </Box>
          )}

          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 3 }}>
            <Button
              color="inherit"
              disabled={activeStep === 0 || loading}
              onClick={handleBack}
              sx={{ mr: 1 }}
            >
              Back
            </Button>
            {activeStep === steps.length - 1 ? (
              <Button
                variant="contained"
                onClick={handleSubmit}
                disabled={loading}
              >
                {loading ? 'Registering...' : 'Register Workspace'}
              </Button>
            ) : (
              <Button
                variant="contained"
                onClick={handleNext}
              >
                Next
              </Button>
            )}
          </Box>
        </Box>
      </Paper>
    </Container>
  );
};

export default OnboardingPage;
