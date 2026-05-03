import React from 'react';
import {
  Box,
  Grid,
  Paper,
  Skeleton,
  Stack,
} from '@mui/material';

const AnalyticsSkeleton: React.FC = () => {
  return (
    <Box sx={{ pb: 4 }}>
      <Paper
        elevation={0}
        sx={{
          mb: 3,
          p: 3,
          borderRadius: 4,
          border: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 2,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, minWidth: 280 }}>
            <Skeleton variant="rounded" width={56} height={56} />
            <Box sx={{ flexGrow: 1 }}>
              <Skeleton variant="text" width="65%" height={34} />
              <Skeleton variant="text" width="88%" height={20} />
            </Box>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Skeleton variant="rounded" width={170} height={28} />
            <Skeleton variant="rounded" width={190} height={28} />
            <Skeleton variant="rounded" width={36} height={36} />
          </Box>
        </Box>
      </Paper>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        {Array.from({ length: 6 }).map((_, index) => (
          <Grid item xs={6} sm={4} md={2} key={index}>
            <Paper elevation={0} sx={{ p: 2, borderRadius: 3, border: '1px solid', borderColor: 'divider' }}>
              <Skeleton variant="text" width="70%" height={20} />
              <Skeleton variant="text" width="55%" height={34} sx={{ mb: 1 }} />
              <Skeleton variant="text" width="90%" height={16} />
            </Paper>
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={3}>
        {Array.from({ length: 4 }).map((_, index) => (
          <Grid item xs={12} lg={6} key={index}>
            <Paper elevation={0} sx={{ p: 3, borderRadius: 3, border: '1px solid', borderColor: 'divider' }}>
              <Skeleton variant="text" width="45%" height={28} sx={{ mb: 2 }} />
              <Stack spacing={1.25}>
                {Array.from({ length: 6 }).map((__, rowIndex) => (
                  <Skeleton key={rowIndex} variant="rounded" width="100%" height={18} />
                ))}
              </Stack>
            </Paper>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default AnalyticsSkeleton;
