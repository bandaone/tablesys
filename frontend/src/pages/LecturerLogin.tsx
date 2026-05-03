import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { alpha } from '@mui/material/styles';
import {
  Alert,
  Avatar,
  Box,
  Button,
  CircularProgress,
  Container,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { ArrowForwardRounded as ArrowForwardIcon, WorkRounded as WorkIcon } from '@mui/icons-material';
import { useBranding } from '../contexts/BrandingContext';
import { lecturerPortalApi } from '../lecturerPortalApi';

const LecturerLogin: React.FC = () => {
  const [staffNumber, setStaffNumber] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { branding } = useBranding();

  const primaryColor = branding.primary_color || '#1976d2';
  const secondaryColor = branding.secondary_color || '#ff8c00';
  const brandName = branding.short_name || branding.name || 'TABLESYS';

  const submit = async () => {
    if (!staffNumber.trim()) return;
    setError(null);
    setLoading(true);
    try {
      const data = await lecturerPortalApi.login(staffNumber.trim());
      localStorage.setItem('lecturer_token', data.access_token);
      localStorage.setItem('lecturer_meta', JSON.stringify(data.lecturer || {}));
      navigate('/lecturer');
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(detail || 'Login failed. Please check your staff number.');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') submit();
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: `radial-gradient(ellipse at top left, ${alpha(secondaryColor, 0.22)} 0%, transparent 50%), radial-gradient(ellipse at bottom right, ${alpha(primaryColor, 0.18)} 0%, transparent 50%), linear-gradient(160deg, #0f172a 0%, ${alpha(primaryColor, 0.92)} 50%, #0f172a 100%)`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
      }}
    >
      <Container maxWidth="sm">
        <Paper
          elevation={0}
          sx={{
            p: { xs: 3, sm: 4 },
            borderRadius: 6,
            border: `1px solid ${alpha('#ffffff', 0.18)}`,
            background: `linear-gradient(135deg, ${alpha('#ffffff', 0.12)} 0%, ${alpha('#ffffff', 0.06)} 100%)`,
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            boxShadow: `0 32px 80px ${alpha('#000000', 0.35)}, inset 0 1px 0 ${alpha('#ffffff', 0.15)}`,
            color: '#fff',
          }}
        >
          <Stack spacing={3.5}>
            {/* Header */}
            <Stack spacing={1.25} alignItems="center" textAlign="center">
              <Avatar
                sx={{
                  bgcolor: alpha('#ffffff', 0.15),
                  width: 64,
                  height: 64,
                  backdropFilter: 'blur(8px)',
                  border: `1px solid ${alpha('#ffffff', 0.2)}`,
                }}
              >
                <WorkIcon sx={{ fontSize: 30, color: '#fff' }} />
              </Avatar>
              <Box>
                <Typography variant="h5" fontWeight={800} sx={{ color: '#fff' }}>
                  Lecturer Portal
                </Typography>
                <Typography variant="body2" sx={{ color: alpha('#fff', 0.7) }}>
                  {brandName} · Sign in with your staff number
                </Typography>
              </Box>
            </Stack>

            {error && <Alert severity="error" sx={{ borderRadius: 3 }}>{error}</Alert>}

            <Stack spacing={2.5}>
              <TextField
                label="Staff Number"
                value={staffNumber}
                onChange={(e) => setStaffNumber(e.target.value)}
                onKeyDown={handleKeyDown}
                fullWidth
                autoFocus
                disabled={loading}
                sx={{
                  '& .MuiInputLabel-root': { color: alpha('#fff', 0.65) },
                  '& .MuiInputLabel-root.Mui-focused': { color: '#fff' },
                  '& .MuiOutlinedInput-root': {
                    color: '#fff',
                    borderRadius: 3,
                    backgroundColor: alpha('#ffffff', 0.06),
                    backdropFilter: 'blur(8px)',
                    '& fieldset': { borderColor: alpha('#ffffff', 0.2) },
                    '&:hover fieldset': { borderColor: alpha('#ffffff', 0.4) },
                    '&.Mui-focused fieldset': { borderColor: '#fff' },
                  },
                }}
              />

              <Button
                variant="contained"
                size="large"
                onClick={submit}
                disabled={!staffNumber.trim() || loading}
                endIcon={loading ? <CircularProgress size={18} color="inherit" /> : <ArrowForwardIcon />}
                sx={{
                  py: 1.6,
                  borderRadius: 3,
                  fontWeight: 700,
                  fontSize: '1rem',
                  bgcolor: alpha('#ffffff', 0.18),
                  color: '#fff',
                  backdropFilter: 'blur(8px)',
                  border: `1px solid ${alpha('#ffffff', 0.25)}`,
                  boxShadow: `0 8px 32px ${alpha('#000', 0.2)}`,
                  '&:hover': {
                    bgcolor: alpha('#ffffff', 0.28),
                    boxShadow: `0 12px 40px ${alpha('#000', 0.3)}`,
                  },
                  '&.Mui-disabled': {
                    bgcolor: alpha('#ffffff', 0.06),
                    color: alpha('#ffffff', 0.3),
                    border: `1px solid ${alpha('#ffffff', 0.08)}`,
                  },
                }}
              >
                {loading ? 'Signing in…' : 'Open My Timetable'}
              </Button>
            </Stack>
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
};

export default LecturerLogin;
