import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { generateTheme } from './theme';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { BrandingProvider, useBranding } from './contexts/BrandingContext';
import { CircularProgress, Box, Typography, ThemeProvider as MuiThemeProvider } from '@mui/material';

// Core layout/critical path imports
import LoginPage from './pages/LoginPage';
import LegacyAccess from './pages/LegacyAccess';
import OnboardingPage from './pages/OnboardingPage';
import DashboardLayout from './components/DashboardLayout';
import StudentPortal from './pages/StudentPortal';
import SuperAdminPage from './pages/SuperAdminPage';
import RegistrationPage from './pages/RegistrationPage';
import VerificationPage from './pages/VerificationPage';
import SSOCallback from './pages/SSOCallback';

// Lazy loaded page components
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const CoursesPage = lazy(() => import('./pages/CoursesPage'));
const TimetablesPage = lazy(() => import('./pages/TimetablesPage'));
const ExamTimetablesPage = lazy(() => import('./pages/ExamTimetablesPage'));
const LecturersPage = lazy(() => import('./pages/LecturersPage'));
import LecturerLogin from './pages/LecturerLogin';
import LecturerPortal from './pages/LecturerPortal';
const RoomsPage = lazy(() => import('./pages/RoomsPage'));
const GroupsPage = lazy(() => import('./pages/GroupsPage'));
const DepartmentsPage = lazy(() => import('./pages/DepartmentsPage'));
const SchoolsPage = lazy(() => import('./pages/SchoolsPage'));
const TimetableViewPage = lazy(() => import('./pages/TimetableViewPage'));
const UsersPage = lazy(() => import('./pages/UsersPage'));
const PrintSchedulePage = lazy(() => import('./pages/PrintSchedulePage'));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));
const ReportsPage = lazy(() => import('./pages/ReportsPage'));
const AuditLogsPage = lazy(() => import('./pages/AuditLogsPage'));
const HelpPage = lazy(() => import('./pages/HelpPage'));
const SystemMonitorPage = lazy(() => import('./pages/SystemMonitorPage'));
const LabSchedulingPage = lazy(() => import('./pages/LabSchedulingPage'));
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'));
const BillingUsagePage = lazy(() => import('./pages/BillingUsagePage'));
const InstitutionSetupPage = lazy(() => import('./pages/InstitutionSetupPage'));

// Protected Route Component
const ProtectedRoute: React.FC<{ children: React.ReactElement }> = ({ children }) => {
    const { token, user } = useAuth();
    const location = useLocation();

    if (!token) {
      return <Navigate to="/login" replace />;
    }

    const safeRole = user?.role?.toUpperCase();

    // Normal users shouldn't access the superadmin dashboard
    if (location.pathname.startsWith('/superadmin') && safeRole !== 'SUPERADMIN') {
       return <Navigate to="/dashboard" replace />;
    }

    const superadminAllowedSharedRoutes = ['/monitor', '/audit', '/help'];
    const isSuperadminSharedRoute = superadminAllowedSharedRoutes.some((path) =>
      location.pathname.startsWith(path)
    );

    // Superadmins shouldn't access normal university views (since they have no university_id)
    // except shared owner/support routes like monitor, audit, and help.
    if (!location.pathname.startsWith('/superadmin') && safeRole === 'SUPERADMIN' && !isSuperadminSharedRoute) {
       return <Navigate to="/superadmin" replace />;
    }

    return children;
};

const LoadingFallback = () => (
  <Box sx={{ display: 'flex', height: '100vh', width: '100%', alignItems: 'center', justifyContent: 'center' }}>
    <CircularProgress />
  </Box>
);

const TenantEnforcer: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { tenantError, loading } = useBranding();
  
  if (loading) return <LoadingFallback />;
  
  const isGlobalRoute = window.location.pathname.startsWith('/register') || window.location.pathname.startsWith('/verify') || window.location.pathname.startsWith('/sso');
  
  if (tenantError && !isGlobalRoute) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100%', alignItems: 'center', justifyContent: 'center', textAlign: 'center', bgcolor: '#f5f5f5' }}>
        <Typography variant="h1" color="primary" fontWeight="bold">404</Typography>
        <Typography variant="h5" mt={2}>Workspace Not Found</Typography>
        <Typography variant="body1" color="text.secondary" mt={1}>
          We couldn't resolve the tenant for this domain. Please check the URL and try again.
        </Typography>
      </Box>
    );
  }
  
  return <>{children}</>;
};

const DynamicThemeWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { branding } = useBranding();
  const theme = React.useMemo(() => 
    generateTheme(branding.primary_color, branding.secondary_color), 
    [branding.primary_color, branding.secondary_color]
  );

  return (
    <MuiThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </MuiThemeProvider>
  );
};

const RoleBasedRedirect: React.FC = () => {
  const { isTenantAdmin, isLabCoordinator } = useAuth();
  if (isTenantAdmin) {
     return <Navigate to="/admin" replace />;
  }
  if (isLabCoordinator) {
     return <Navigate to="/lab-scheduling" replace />;
  }
  return <Navigate to="/dashboard" replace />;
};

const App: React.FC = () => {
  return (
    <BrandingProvider>
      <DynamicThemeWrapper>
        <AuthProvider>
          <TenantEnforcer>
            <BrowserRouter>
              <Suspense fallback={<LoadingFallback />}>
                <Routes>
                  <Route path="/legacy-access" element={<LegacyAccess />} />
                  <Route path="/onboarding" element={<OnboardingPage />} />
                  <Route path="/login" element={<LoginPage />} />
                  <Route path="/sso/callback" element={<SSOCallback />} />
                  <Route path="/register" element={<RegistrationPage />} />
                  <Route path="/verify" element={<VerificationPage />} />
                  <Route path="/student" element={<StudentPortal />} />
                  <Route path="/lecturer/login" element={<LecturerLogin />} />
                  <Route path="/lecturer" element={<LecturerPortal />} />
                  
                  {/* Platform Management Route */}
                  <Route 
                    path="/superadmin" 
                    element={
                      <ProtectedRoute>
                        <SuperAdminPage />
                      </ProtectedRoute>
                    } 
                  />
                  
                  <Route
                    path="/"
                    element={
                      <ProtectedRoute>
                        <DashboardLayout />
                      </ProtectedRoute>
                    }
                  >
                    <Route index element={<RoleBasedRedirect />} />
                    <Route path="dashboard" element={<DashboardPage />} />
                    <Route path="analytics" element={<AnalyticsPage />} />
                    <Route path="courses" element={<CoursesPage />} />
                    <Route path="timetables" element={<TimetablesPage />} />
                    <Route path="exam-timetables" element={<ExamTimetablesPage />} />
                    <Route path="timetables/view" element={<TimetableViewPage />} />
                    <Route path="timetables/:id/view" element={<TimetableViewPage />} />
                    <Route path="lecturers" element={<LecturersPage />} />
                    <Route path="rooms" element={<RoomsPage />} />
                    <Route path="groups" element={<GroupsPage />} />
                    <Route path="departments" element={<DepartmentsPage />} />
                    <Route path="schools" element={<SchoolsPage />} />
                    <Route path="setup" element={<InstitutionSetupPage />} />
                    <Route path="users" element={<UsersPage />} />
                    <Route path="print" element={<PrintSchedulePage />} />
                    <Route path="admin" element={<AdminDashboard />} />
                    <Route path="monitor" element={<SystemMonitorPage />} />
                    <Route path="reports" element={<ReportsPage />} />
                    <Route path="audit" element={<AuditLogsPage />} />
                    <Route path="help" element={<HelpPage />} />
                    <Route path="lab-scheduling" element={<LabSchedulingPage />} />
                    <Route path="billing" element={<BillingUsagePage />} />
                  </Route>
                </Routes>
              </Suspense>
            </BrowserRouter>
          </TenantEnforcer>
        </AuthProvider>
      </DynamicThemeWrapper>
    </BrandingProvider>
  );
};

export default App;
