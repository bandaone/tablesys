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
  Stack,
} from '@mui/material';
import { School, Login as LoginIcon } from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(username);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed. Please check your username.');
    } finally {
      setLoading(false);
    }
  };

  const quickLogin = (user: string) => {
    setUsername(user);
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        background: 'linear-gradient(135deg, #003366 0%, #1a4d7a 100%)',
      }}
    >
      <Container maxWidth="sm">
        <Paper
          elevation={6}
          sx={{
            p: 4,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            borderRadius: 2,
          }}
        >
          <School sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
          
          <Typography variant="h4" component="h1" gutterBottom fontWeight="bold">
            TABLESYS
          </Typography>
          
          <Typography variant="body1" color="text.secondary" gutterBottom sx={{ mb: 1 }}>
            University of Zambia Timetable Management System
          </Typography>

          <Alert severity="info" sx={{ width: '100%', mb: 3 }}>
            Simple Access - Just enter your username, no password required!
          </Alert>

          {error && (
            <Alert severity="error" sx={{ width: '100%', mb: 2 }}>
              {error}
            </Alert>
          )}

          <Box component="form" onSubmit={handleSubmit} sx={{ width: '100%' }}>
            <TextField
              margin="normal"
              required
              fullWidth
              id="username"
              label="Username"
              name="username"
              autoComplete="username"
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value.toUpperCase())}
              placeholder="e.g., COORDINATOR, MEC, CS"
              helperText="Enter your username (case-insensitive)"
            />

            <Button
              type="submit"
              fullWidth
              variant="contained"
              sx={{ mt: 3, mb: 3, py: 1.5 }}
              disabled={loading}
              startIcon={<LoginIcon />}
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </Button>
          </Box>

          <Typography variant="subtitle2" gutterBottom sx={{ mt: 2, mb: 1 }}>
            Quick Access:
          </Typography>
          
          <Stack direction="row" spacing={1} flexWrap="wrap" justifyContent="center" sx={{ mb: 2 }}>
            <Chip 
              label="coordinator" 
              onClick={() => quickLogin('coordinator')} 
              color="primary"
              sx={{ cursor: 'pointer' }}
            />
            <Chip 
              label="MEC" 
              onClick={() => quickLogin('MEC')} 
              color="secondary"
              sx={{ cursor: 'pointer' }}
            />
            <Chip 
              label="CS" 
              onClick={() => quickLogin('CS')} 
              color="secondary"
              sx={{ cursor: 'pointer' }}
            />
            <Chip 
              label="MATH" 
              onClick={() => quickLogin('MATH')} 
              color="secondary"
              sx={{ cursor: 'pointer' }}
            />
          </Stack>

          <Box sx={{ bgcolor: 'grey.100', p: 2, borderRadius: 1, width: '100%', mt: 2 }}>
            <Typography variant="caption" color="text.secondary" component="div">
              <strong>Available Users:</strong><br />
              • coordinator, admin (Full Access)<br />
              • CS, MATH, MEC, ELE, CIV, PHY, CHEM, BIO (Department HODs)
            </Typography>
          </Box>

          <Typography variant="caption" color="text.secondary" sx={{ mt: 3 }}>
            © 2026 University of Zambia. All rights reserved.
          </Typography>
        </Paper>
      </Container>
    </Box>
  );
};

export default LoginPage;
