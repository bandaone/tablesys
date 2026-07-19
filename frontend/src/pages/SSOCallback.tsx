/**
 * SSOCallback.tsx — Agent Alpha (SSO)
 *
 * The backend redirects here after a successful OAuth2 exchange:
 *   /sso/callback?token=<jwt>
 * or on error:
 *   /sso/callback?error=<reason>
 *
 * Responsibilities:
 *  1. Read `?token` from the URL query string
 *  2. Call loginWithToken() to persist the session in AuthContext
 *  3. Immediately strip the token from the URL (prevent leakage in history)
 *  4. Navigate to /dashboard (or /superadmin for superadmins)
 *  5. On error — show a clean, friendly message with a link back to /login
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Box, CircularProgress, Typography, Button, Alert, Paper } from '@mui/material';
import { CheckCircle as CheckCircleIcon, Error as ErrorIcon, TableChart as TableChartIcon } from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { motion } from 'framer-motion';

const SSO_ERROR_MESSAGES: Record<string, string> = {
  no_code:              'The authentication provider did not return a code. Please try again.',
  invalid_state:        'The login session expired or was tampered with. Please try again.',
  token_exchange_failed:'Could not verify your identity with the provider. Please try again.',
  email_not_verified:   'Your email address is not verified with the provider. Please verify and retry.',
  institution_not_found:'Your institution is not yet registered on TABLESYS. Contact your IT administrator.',
  account_inactive:     'Your account has been deactivated. Contact your coordinator.',
  access_denied:        'You cancelled the sign-in. Click below to try again.',
};

const SSOCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { loginWithToken } = useAuth();

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    const run = async () => {
      const error = searchParams.get('error');
      const token = searchParams.get('token');

      // ── Strip sensitive params from the URL immediately ──────────────────
      // Use replaceState so the token never appears in browser history
      window.history.replaceState({}, document.title, window.location.pathname);

      if (error) {
        setErrorMsg(SSO_ERROR_MESSAGES[error] ?? `Authentication failed: ${error}`);
        setStatus('error');
        return;
      }

      if (!token) {
        setErrorMsg('No authentication token was received. Please try logging in again.');
        setStatus('error');
        return;
      }

      try {
        const user = await loginWithToken(token);
        setStatus('success');

        // Brief success flash, then navigate
        await new Promise(r => setTimeout(r, 850));

        if (user?.role?.toUpperCase() === 'SUPERADMIN') {
          navigate('/superadmin', { replace: true });
        } else {
          navigate('/dashboard', { replace: true });
        }
      } catch {
        setErrorMsg('Could not load your account details. Please try again or contact support.');
        setStatus('error');
      }
    };

    void run();
    // Only run once on mount — searchParams intentionally excluded
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #0d47a1 0%, #1976d2 55%, #9c27b0 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
      }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.92 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
      >
        {/* Brand mark */}
        <Box display="flex" alignItems="center" justifyContent="center" gap={1.5} mb={3}>
          <Box
            sx={{
              width: 40, height: 40, borderRadius: '10px',
              background: 'linear-gradient(135deg, #1976d2, #9c27b0)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 6px 20px rgba(99,102,241,0.45)',
            }}
          >
            <TableChartIcon sx={{ color: 'white', fontSize: 20 }} />
          </Box>
          <Typography variant="h6" fontWeight={800} letterSpacing={2} sx={{ color: '#fff' }}>
            TABLESYS
          </Typography>
        </Box>

        <Paper
          elevation={24}
          sx={{
            p: { xs: 4, sm: 5 },
            borderRadius: '24px',
            background: 'rgba(255,255,255,0.06)',
            backdropFilter: 'blur(40px)',
            border: '1px solid rgba(255,255,255,0.12)',
            minWidth: { xs: 0, sm: 420 },
            textAlign: 'center',
          }}
        >
          {/* ── Loading ── */}
          {status === 'loading' && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              <CircularProgress
                size={56}
                thickness={3}
                sx={{ color: '#9c27b0', mb: 3 }}
              />
              <Typography variant="h6" fontWeight={700} sx={{ color: '#fff', mb: 1 }}>
                Signing you in…
              </Typography>
              <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.5)' }}>
                Verifying your identity with your institution
              </Typography>
            </motion.div>
          )}

          {/* ── Success ── */}
          {status === 'success' && (
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ type: 'spring', stiffness: 200, damping: 18 }}
            >
              <CheckCircleIcon sx={{ fontSize: 64, color: '#4ade80', mb: 2 }} />
              <Typography variant="h6" fontWeight={700} sx={{ color: '#fff', mb: 1 }}>
                Authenticated!
              </Typography>
              <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.55)' }}>
                Redirecting to your dashboard…
              </Typography>
            </motion.div>
          )}

          {/* ── Error ── */}
          {status === 'error' && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35 }}
            >
              <ErrorIcon sx={{ fontSize: 56, color: '#f87171', mb: 2 }} />
              <Typography variant="h6" fontWeight={700} sx={{ color: '#fff', mb: 2 }}>
                Sign-in Failed
              </Typography>
              <Alert
                severity="error"
                sx={{
                  mb: 3, borderRadius: '12px', textAlign: 'left',
                  background: 'rgba(239,68,68,0.12)',
                  color: '#fca5a5',
                  border: '1px solid rgba(239,68,68,0.25)',
                  '& .MuiAlert-icon': { color: '#f87171' },
                }}
              >
                {errorMsg}
              </Alert>
              <Button
                variant="contained"
                fullWidth
                onClick={() => navigate('/login')}
                sx={{
                  py: 1.25, borderRadius: '12px', fontWeight: 700,
                  textTransform: 'none',
                  background: 'linear-gradient(135deg, #1976d2, #9c27b0)',
                  '&:hover': { background: 'linear-gradient(135deg, #115293, #7b1fa2)' },
                }}
              >
                Back to Sign In
              </Button>
            </motion.div>
          )}
        </Paper>
      </motion.div>
    </Box>
  );
};

export default SSOCallback;
