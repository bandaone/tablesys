import React from 'react';
import {
  Grid,
  Card,
  CardContent,
  Skeleton,
  Box,
} from '@mui/material';

const DashboardSkeleton: React.FC = () => {
  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      {/* Header Skeleton */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 4 }}>
        <Skeleton variant="text" width="30%" height={60} />
      </Box>

      {/* Stats Cards Skeleton */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {[1, 2, 3, 4].map((item) => (
          <Grid item xs={12} sm={6} md={3} key={item}>
            <Card>
              <CardContent sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box sx={{ width: '100%' }}>
                  <Skeleton variant="text" width="60%" height={30} sx={{ mb: 1 }} />
                  <Skeleton variant="text" width="40%" height={50} />
                </Box>
                <Skeleton variant="circular" width={50} height={50} />
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Main Content Area Skeleton */}
      <Grid container spacing={3}>
        <Grid item xs={12} lg={8}>
          <Card sx={{ height: 400 }}>
            <CardContent>
              <Skeleton variant="text" width="40%" height={40} sx={{ mb: 2 }} />
              <Skeleton variant="rectangular" width="100%" height={300} />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} lg={4}>
          <Card sx={{ height: 400 }}>
            <CardContent>
              <Skeleton variant="text" width="50%" height={40} sx={{ mb: 2 }} />
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {[1, 2, 3, 4, 5].map((item) => (
                   <Box key={item} sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                       <Skeleton variant="circular" width={40} height={40} />
                       <Box sx={{ flexGrow: 1 }}>
                           <Skeleton variant="text" width="80%" height={20} />
                           <Skeleton variant="text" width="60%" height={15} />
                       </Box>
                   </Box>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardSkeleton;
