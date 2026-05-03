import React from 'react';
import { Container } from '@mui/material';
import TimetableAnalytics from '../components/TimetableAnalytics';

const AnalyticsPage: React.FC = () => {
    return (
        <Container maxWidth={false} sx={{ mt: 3, mb: 4 }}>
            <TimetableAnalytics />
        </Container>
    );
};

export default AnalyticsPage;
