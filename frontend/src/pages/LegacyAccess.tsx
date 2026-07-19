import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Box, Typography, CircularProgress } from '@mui/material';

const LegacyAccess: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) {
      setError('No access token provided.');
      return;
    }

    const validateToken = async () => {
      try {
        const response = await axios.get(`/api/v1/public/legacy-access?token=${token}`);
        if (response.data && response.data.university_id) {
          localStorage.setItem('university_id', String(response.data.university_id));
          navigate('/login', { replace: true });
        } else {
          setError('Invalid response from server.');
        }
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to validate legacy access token.');
      }
    };

    validateToken();
  }, [searchParams, navigate]);

  if (error) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', flexDirection: 'column' }}>
        <Typography variant="h5" color="error">{error}</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', flexDirection: 'column' }}>
      <CircularProgress sx={{ mb: 2 }} />
      <Typography>Authenticating workspace access...</Typography>
    </Box>
  );
};

export default LegacyAccess;
