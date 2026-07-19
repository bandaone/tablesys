import React, { useEffect, useMemo, useState } from 'react';
import {
  Avatar,
  Badge,
  Box,
  Button,
  Chip,
  Divider,
  IconButton,
  ListItemIcon,
  Menu,
  MenuItem,
  Typography,
} from '@mui/material';
import {
  AccountBalanceWallet as AccountBalanceWalletIcon,
  AccountCircle,
  Analytics as AnalyticsIcon,
  AutoGraph as AutoGraphIcon,
  Book as BookIcon,
  Business as BusinessIcon,
  CalendarMonth as CalendarIcon,
  Dashboard as DashboardIcon,
  FactCheck as FactCheckIcon,
  Group as GroupIcon,
  Help as HelpIcon,
  History as HistoryIcon,
  Logout,
  ManageAccounts as ManageAccountsIcon,
  MonitorHeart as MonitorHeartIcon,
  Notifications as NotificationsIcon,
  Person as PersonIcon,
  Room as RoomIcon,
  School as SchoolIcon,
  Science as ScienceIcon,
  SettingsSuggest as SettingsSuggestIcon,
} from '@mui/icons-material';
import { AnimatePresence, motion } from 'framer-motion';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { notificationsAPI, superadminAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';
import { useBranding } from '../contexts/BrandingContext';

const RAIL_WIDTH = 68;

interface NavItem {
  label: string;
  Icon: React.ComponentType<any>;
  path: string;
  coordinatorOnly?: true;
  tenantAdminOnly?: true;
  superadminOnly?: true;
  labCoordinatorOnly?: true;
  labViewerOnly?: true;
}

const NAV: NavItem[] = [
  { label: 'Admin Dashboard', Icon: DashboardIcon, path: '/admin', tenantAdminOnly: true },
  { label: 'Dashboard', Icon: DashboardIcon, path: '/dashboard', coordinatorOnly: true },
  { label: 'Timetables', Icon: CalendarIcon, path: '/timetables', coordinatorOnly: true },
  { label: 'Exams', Icon: FactCheckIcon, path: '/exam-timetables', coordinatorOnly: true },
  { label: 'Courses', Icon: BookIcon, path: '/courses', coordinatorOnly: true },
  { label: 'Student Groups', Icon: GroupIcon, path: '/groups', coordinatorOnly: true },
  { label: 'Lab Scheduling', Icon: ScienceIcon, path: '/lab-scheduling', labViewerOnly: true },
  { label: 'Lecturers', Icon: PersonIcon, path: '/lecturers', coordinatorOnly: true },
  { label: 'Rooms', Icon: RoomIcon, path: '/rooms', coordinatorOnly: true },
  { label: 'Departments', Icon: BusinessIcon, path: '/departments', coordinatorOnly: true },
  { label: 'Schools', Icon: SchoolIcon, path: '/schools', tenantAdminOnly: true },
  { label: 'Users', Icon: ManageAccountsIcon, path: '/users', coordinatorOnly: true },
  { label: 'Analytics', Icon: AutoGraphIcon, path: '/analytics', coordinatorOnly: true },
  { label: 'Institution Setup', Icon: SettingsSuggestIcon, path: '/setup', tenantAdminOnly: true },
  { label: 'Billing & Usage', Icon: AccountBalanceWalletIcon, path: '/billing', tenantAdminOnly: true },
  { label: 'Audit Logs', Icon: HistoryIcon, path: '/audit', tenantAdminOnly: true },
  { label: 'Platform Console', Icon: BusinessIcon, path: '/superadmin', superadminOnly: true },
  { label: 'System Monitor', Icon: MonitorHeartIcon, path: '/monitor', superadminOnly: true },
  { label: 'Help', Icon: HelpIcon, path: '/help' },
];

const RailBtn: React.FC<{
  label: string;
  Icon: React.ComponentType<any>;
  active: boolean;
  onClick: () => void;
  primaryColor: string;
}> = ({ label, Icon, active, onClick, primaryColor }) => {
  const [hovered, setHovered] = useState(false);
  const [pillPosition, setPillPosition] = useState({ top: 0, left: 0 });

  const handleMouseEnter = (event: React.MouseEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setPillPosition({
      top: rect.top + rect.height / 2 - 14,
      left: rect.right + 6,
    });
    setHovered(true);
  };

  return (
    <Box sx={{ position: 'relative', width: '100%', display: 'flex', justifyContent: 'center', mb: 0.5 }}>
      <Box
        onClick={onClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={() => setHovered(false)}
        sx={{
          width: 44,
          height: 44,
          borderRadius: '12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          bgcolor: active
            ? `${primaryColor}28`
            : hovered
              ? 'rgba(255,255,255,0.1)'
              : 'transparent',
          boxShadow: active ? `inset 3px 0 0 ${primaryColor}` : 'none',
          transition: 'background 0.17s ease, box-shadow 0.17s ease',
        }}
      >
        <Icon
          sx={{
            fontSize: 21,
            color: active ? primaryColor : hovered ? '#fff' : 'rgba(255,255,255,0.45)',
            transition: 'color 0.17s ease',
          }}
        />
      </Box>

      {hovered && (
        <Box
          sx={{
            position: 'fixed',
            top: pillPosition.top,
            left: pillPosition.left,
            pointerEvents: 'none',
            display: 'flex',
            alignItems: 'center',
            zIndex: 9999,
            animation: 'railPillIn 0.17s ease forwards',
            '@keyframes railPillIn': {
              from: { opacity: 0, transform: 'translateX(-6px)' },
              to: { opacity: 1, transform: 'translateX(0)' },
            },
          }}
        >
          <Box
            sx={{
              width: 0,
              height: 0,
              borderTop: '5px solid transparent',
              borderBottom: '5px solid transparent',
              borderRight: '6px solid #1c2b3a',
            }}
          />
          <Box
            sx={{
              bgcolor: '#1c2b3a',
              border: '1px solid rgba(255,255,255,0.13)',
              borderRadius: '8px',
              px: 1.5,
              py: 0.6,
              boxShadow: '0 4px 20px rgba(0,0,0,0.45)',
            }}
          >
            <Typography
              sx={{
                fontSize: '0.78rem',
                fontWeight: 600,
                color: '#fff',
                letterSpacing: 0.3,
                whiteSpace: 'nowrap',
              }}
            >
              {label}
            </Typography>
          </Box>
        </Box>
      )}
    </Box>
  );
};

const DashboardLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout, isCoordinator, isTenantAdmin, isSuperadmin, isLabCoordinator, isSchoolCoordinator } = useAuth();
  const { branding } = useBranding();

  const [profileAnchor, setProfileAnchor] = useState<null | HTMLElement>(null);
  const [notificationAnchor, setNotificationAnchor] = useState<null | HTMLElement>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<any[]>([]);

  useEffect(() => {
    const fetchUnread = async () => {
      if (!user || !sessionStorage.getItem('token')) {
        setUnreadCount(0);
        setNotifications([]);
        return;
      }

      try {
        const [countRes, notifs] = await Promise.all([
          notificationsAPI.getUnreadCount(),
          notificationsAPI.getAll(false, 10),
        ]);
        setUnreadCount(countRes.unread_count || 0);
        setNotifications(notifs?.notifications || []);
      } catch (error: any) {
        if (error?.response?.status !== 401) {
          console.error('Failed to fetch unread notifications', error);
        }
      }
    };

    fetchUnread();
    const interval = setInterval(fetchUnread, 30000);
    return () => clearInterval(interval);
  }, [user]);

  const visibleNav = useMemo(() => (
    NAV.filter((item) => {
      if (isSuperadmin) {
        return item.superadminOnly || item.label === 'Help' || item.label === 'Audit Logs';
      }
      if (item.superadminOnly) return false;
      if (item.tenantAdminOnly && !isTenantAdmin) return false;
      // Lab scheduling belongs to departmental lab operations. School
      // coordinators manage the academic structure, not lab-room allocation
      // or rotating lab delivery.
      if (item.labViewerOnly && !isLabCoordinator) return false;
      if (item.coordinatorOnly && !isCoordinator) return false;
      return true;
    })
  ), [isCoordinator, isSchoolCoordinator, isSuperadmin, isTenantAdmin, isLabCoordinator]);

  const isActive = (path: string) => (
    location.pathname === path || (path !== '/dashboard' && location.pathname.startsWith(path))
  );

  const roleLabel = user?.role?.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()) || 'User';
  const primaryColor = branding.primary_color || '#1976d2';

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: '#f8fafc' }}>
      <Box
        component="nav"
        sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: RAIL_WIDTH,
          height: '100vh',
          bgcolor: '#070b14',
          display: { xs: 'none', sm: 'flex' },
          flexDirection: 'column',
          alignItems: 'center',
          zIndex: 1300,
          boxShadow: '4px 0 24px rgba(0,0,0,0.4)',
          overflowY: 'auto',
          scrollbarWidth: 'none',
          '&::-webkit-scrollbar': { display: 'none' },
          py: 2,
          borderRight: '1px solid rgba(255,255,255,0.05)',
        }}
      >
        <Box
          sx={{
            width: 38,
            height: 38,
            borderRadius: '11px',
            bgcolor: primaryColor,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: `0 0 0 2px ${(branding.secondary_color || '#9c27b0')}55`,
            mb: 2.5,
            flexShrink: 0,
            overflow: 'hidden',
          }}
        >
          {branding.logo_url ? (
            <img
              src={`/media/logos/${branding.university_id}/logo.png`}
              alt="Logo"
              width="100%"
              height="100%"
              style={{ objectFit: 'cover' }}
            />
          ) : (
            <SchoolIcon sx={{ color: '#fff', fontSize: 20 }} />
          )}
        </Box>

        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%', mb: 'auto' }}>
          {visibleNav.map((item) => (
            <RailBtn
              key={item.path}
              label={item.label}
              Icon={item.Icon}
              active={isActive(item.path)}
              onClick={() => navigate(item.path)}
              primaryColor={primaryColor}
            />
          ))}
        </Box>

        <Box sx={{ width: 36, height: 1, bgcolor: 'rgba(255,255,255,0.1)', my: 1 }} />
      </Box>

      <Menu
        anchorEl={profileAnchor}
        open={Boolean(profileAnchor)}
        onClose={() => setProfileAnchor(null)}
        onClick={() => setProfileAnchor(null)}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        PaperProps={{
          sx: {
            bgcolor: '#0d1f2d',
            color: '#fff',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 2,
            minWidth: 200,
            boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
            '& .MuiMenuItem-root': {
              fontSize: '0.88rem',
              gap: 1.5,
              py: 1,
              '&:hover': { bgcolor: 'rgba(255,255,255,0.07)' },
            },
          },
        }}
      >
        <Box sx={{ px: 2, py: 1.5, borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
          <Typography variant="body2" fontWeight={700}>{user?.full_name}</Typography>
          <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.45)' }}>{roleLabel}</Typography>
        </Box>
        <MenuItem>
          <ListItemIcon sx={{ color: 'rgba(255,255,255,0.55)', minWidth: 'unset' }}>
            <AccountCircle fontSize="small" />
          </ListItemIcon>
          Profile
        </MenuItem>
        <Divider sx={{ borderColor: 'rgba(255,255,255,0.08)' }} />
        <MenuItem
          onClick={() => {
            logout();
            navigate('/login');
          }}
          sx={{ color: '#ff6b6b !important' }}
        >
          <ListItemIcon sx={{ color: '#ff6b6b', minWidth: 'unset' }}>
            <Logout fontSize="small" />
          </ListItemIcon>
          Sign out
        </MenuItem>
      </Menu>

      <Menu
        anchorEl={notificationAnchor}
        open={Boolean(notificationAnchor)}
        onClose={() => setNotificationAnchor(null)}
        onClick={() => setNotificationAnchor(null)}
        transformOrigin={{ horizontal: 'left', vertical: 'bottom' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        PaperProps={{
          sx: {
            bgcolor: '#0d1f2d',
            color: '#fff',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 2,
            minWidth: 280,
            boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
            '& .MuiMenuItem-root': {
              fontSize: '0.88rem',
              gap: 1.5,
              py: 1.5,
              borderBottom: '1px solid rgba(255,255,255,0.05)',
              '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' },
            },
          },
        }}
      >
        <Box sx={{ px: 2, py: 1.5, borderBottom: '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="body2" fontWeight={700}>Notifications</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Chip label={`${unreadCount} New`} size="small" sx={{ height: 20, fontSize: '0.7rem', bgcolor: 'rgba(255,255,255,0.1)', color: '#fff' }} />
            {unreadCount > 0 && (
              <Button
                size="small"
                sx={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.55)', py: 0, px: 0.5, minWidth: 0, textTransform: 'none', '&:hover': { color: '#fff' } }}
                onClick={async (event) => {
                  event.stopPropagation();
                  await notificationsAPI.markAllRead();
                  setUnreadCount(0);
                  setNotifications((prev) => prev.map((item) => ({ ...item, is_read: true })));
                }}
              >
                Mark all read
              </Button>
            )}
          </Box>
        </Box>

        {notifications.length === 0 ? (
          <Box sx={{ px: 2, py: 4, textAlign: 'center' }}>
            <NotificationsIcon sx={{ fontSize: 40, color: 'rgba(255,255,255,0.2)', mb: 1 }} />
            <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.5)' }}>
              You have no new notifications.
            </Typography>
          </Box>
        ) : (
          <Box sx={{ maxHeight: 320, overflow: 'auto' }}>
            {notifications.map((notification) => (
              <MenuItem
                key={notification.id}
                onClick={async () => {
                  if (!notification.is_read) {
                    await notificationsAPI.markAsRead(notification.id);
                    setUnreadCount((prev) => Math.max(0, prev - 1));
                    setNotifications((prev) => prev.map((item) => (
                      item.id === notification.id ? { ...item, is_read: true } : item
                    )));
                  }
                }}
                sx={{
                  bgcolor: notification.is_read ? 'transparent' : 'rgba(255, 64, 129, 0.05)',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                }}
              >
                <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', mb: 0.5 }}>
                  <Typography variant="caption" sx={{ color: notification.is_read ? 'text.secondary' : '#ff4081', fontWeight: 'bold' }}>
                    {notification.type?.toUpperCase() || 'SYSTEM'}
                  </Typography>
                  {!notification.is_read && <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: '#ff4081' }} />}
                </Box>
                <Typography variant="body2" sx={{ color: notification.is_read ? '#ccc' : '#fff', fontWeight: notification.is_read ? 'normal' : 'bold' }}>
                  {notification.title}
                </Typography>
                <Typography variant="caption" sx={{ color: '#888', whiteSpace: 'normal', lineHeight: 1.2, mt: 0.5 }}>
                  {notification.message}
                </Typography>
              </MenuItem>
            ))}
          </Box>
        )}
      </Menu>

      <Box
        sx={{
          display: { xs: 'flex', sm: 'none' },
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          height: 56,
          bgcolor: '#070b14',
          zIndex: 1200,
          alignItems: 'center',
          px: 2,
          gap: 1.5,
          boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
        }}
      >
        {branding.logo_url ? (
          <img
            src={`/media/logos/${branding.university_id}/logo.png`}
            alt="Logo"
            width={24}
            height={24}
            style={{ borderRadius: 4 }}
          />
        ) : (
          <SchoolIcon sx={{ color: primaryColor, fontSize: 22 }} />
        )}
        <Typography variant="subtitle2" fontWeight={700} sx={{ color: '#fff' }}>
          {branding.short_name || branding.name || 'TableSys'}
        </Typography>
      </Box>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          ml: { xs: 0, sm: `${RAIL_WIDTH}px` },
          mt: { xs: '56px', sm: 0 },
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {sessionStorage.getItem('superadmin_impersonator') === 'true' && user?.role?.toUpperCase() === 'SUPERADMIN' && (
          <Box sx={{ bgcolor: '#d32f2f', color: '#fff', px: 4, py: 1.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'relative', zIndex: 1101 }}>
            <Typography variant="body2" fontWeight={600}>
              You are actively impersonating a tenant.
            </Typography>
            <Button
              size="small"
              variant="contained"
              sx={{ bgcolor: '#fff', color: '#d32f2f', fontWeight: 700, '&:hover': { bgcolor: '#f5f5f5' } }}
              onClick={async () => {
                try {
                  const response = await superadminAPI.revertImpersonation();
                  sessionStorage.setItem('token', response.access_token);
                  sessionStorage.removeItem('superadmin_impersonator');
                  localStorage.removeItem('university_id');
                  window.location.href = '/superadmin';
                } catch (error) {
                  console.error('Failed to revert impersonation', error);
                }
              }}
            >
              Exit Impersonation
            </Button>
          </Box>
        )}

        <Box
          sx={{
            display: { xs: 'none', sm: 'flex' },
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: 2,
            px: 4,
            py: 1.5,
            background: `linear-gradient(90deg, rgba(255,255,255,0.88) 0%, ${primaryColor}10 100%)`,
            backdropFilter: 'blur(20px)',
            borderBottom: '1px solid rgba(0,0,0,0.05)',
            boxShadow: '0 4px 30px rgba(0,0,0,0.03)',
            position: 'sticky',
            top: 0,
            zIndex: 1100,
          }}
        >
          <IconButton
            onClick={(event) => setNotificationAnchor(event.currentTarget)}
            sx={{
              color: 'text.secondary',
              bgcolor: 'rgba(0,0,0,0.03)',
              '&:hover': { bgcolor: 'rgba(0,0,0,0.06)' },
            }}
          >
            <Badge badgeContent={unreadCount} color="error">
              <NotificationsIcon fontSize="small" />
            </Badge>
          </IconButton>

          <Box
            onClick={(event) => setProfileAnchor(event.currentTarget)}
            sx={{ cursor: 'pointer', display: 'flex', alignItems: 'center', ml: 1 }}
          >
            <Avatar
              sx={{
                width: 38,
                height: 38,
                bgcolor: primaryColor,
                color: '#fff',
                fontWeight: 700,
                fontSize: 15,
                border: '2px solid rgba(0,0,0,0.05)',
                transition: 'transform 0.2s ease',
                '&:hover': { transform: 'scale(1.05)' },
              }}
            >
              {user?.full_name?.charAt(0) ?? 'U'}
            </Avatar>
          </Box>
        </Box>

        <Box sx={{ flexGrow: 1, p: { xs: 2, sm: 4 }, display: 'flex', flexDirection: 'column' }}>
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.25, ease: 'easeOut' }}
              style={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </Box>
      </Box>
    </Box>
  );
};

export default DashboardLayout;
