import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Box, Paper, Typography, CircularProgress, Button } from '@mui/material';
import { CheckCircleOutline, ErrorOutline } from '@mui/icons-material';
import { publicAPI } from '../api';
import axios from 'axios';
import { motion } from 'framer-motion';

const VerificationPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) {
      setStatus('error');
      setErrorMessage('Missing verification token.');
      return;
    }

    const verifyToken = async () => {
      try {
        const response = await publicAPI.verifyTenant(token);
        const accessToken = response.access_token;
        
        // Fetch user data directly to populate session
        const userResponse = await axios.get('/api/v1/auth/me', {
          headers: { Authorization: `Bearer ${accessToken}` },
        });

        // Setup session identically to AuthContext login flow
        sessionStorage.setItem('token', accessToken);
        sessionStorage.setItem('user', JSON.stringify(userResponse.data));

        setStatus('success');
        
        // Short delay for visual polish before jump
        setTimeout(() => {
          window.location.href = '/dashboard';
        }, 1500);

      } catch (err: any) {
        setStatus('error');
        setErrorMessage(err.response?.data?.detail || 'Verification failed. The link may be expired.');
      }
    };

    verifyToken();
  }, [searchParams]);

  // Default Platform Colors
  const activeColors = {
    primaryDark: '#0f172a',
    primaryLight: '#334155',
    secondary: '#6366f1',
    accent: '#8b5cf6',
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        backgroundColor: activeColors.primaryDark,
        background: `linear-gradient(135deg, ${activeColors.primaryDark} 0%, #5c35cc 55%, #7c3aed 100%)`,
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        py: 4,
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
          color: 'white',
          textAlign: 'center',
          maxWidth: 400,
          width: '100%',
        }}
        component={motion.div}
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
      >
        {status === 'loading' && (
          <Box display="flex" flexDirection="column" alignItems="center" gap={3}>
            <CircularProgress size={50} sx={{ color: '#6366f1' }} />
            <Typography variant="h6">Verifying your workspace...</Typography>
            <Typography variant="body2" color="rgba(255,255,255,0.6)">Please wait a moment.</Typography>
          </Box>
        )}

        {status === 'success' && (
          <Box display="flex" flexDirection="column" alignItems="center" gap={2}>
            <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring' }}>
              <CheckCircleOutline sx={{ fontSize: 60, color: '#4caf50' }} />
            </motion.div>
            <Typography variant="h5" fontWeight="bold">Verification Complete!</Typography>
            <Typography variant="body2" color="rgba(255,255,255,0.7)">
              Redirecting you to your enterprise dashboard...
            </Typography>
          </Box>
        )}

        {status === 'error' && (
          <Box display="flex" flexDirection="column" alignItems="center" gap={3}>
            <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring' }}>
              <ErrorOutline sx={{ fontSize: 60, color: '#f44336' }} />
            </motion.div>
            <Typography variant="h6" fontWeight="bold">Verification Failed</Typography>
            <Typography variant="body2" color="rgba(255,255,255,0.7)">{errorMessage}</Typography>
            <Button
              variant="contained"
              onClick={() => window.location.href = '/register'}
              sx={{ mt: 2, bgcolor: '#6366f1', '&:hover': { bgcolor: '#4f46e5' } }}
            >
              Return to Registration
            </Button>
          </Box>
        )}
      </Paper>
    </Box>
  );
};

export default VerificationPage;
