// ─────────────────────────────────────────────────────────────────────────────
//  DashboardLayout – Collapsed icon-only rail with hover pill labels
//  Fresh build v2 — fixes overflow clipping & hover pill rendering
// ─────────────────────────────────────────────────────────────────────────────
import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Avatar,
  Menu,
  MenuItem,
  Divider,
  ListItemIcon,
  Badge,
  IconButton,
  Chip,
  Button,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Book as BookIcon,
  Person as PersonIcon,
  Room as RoomIcon,
  Group as GroupIcon,
  CalendarMonth as CalendarIcon,
  School as SchoolIcon,
  AccountCircle,
  Logout,
  Business as BusinessIcon,
  ManageAccounts as ManageAccountsIcon,
  Analytics as AnalyticsIcon,
  Assessment as AssessmentIcon,
  History as HistoryIcon,
  Help as HelpIcon,
  Notifications as NotificationsIcon,
  TableChart as TableChartIcon,
  MonitorHeart as MonitorHeartIcon,
  Science as ScienceIcon,
  AutoGraph as AutoGraphIcon,
  FactCheck as FactCheckIcon,
} from '@mui/icons-material';
import { useNavigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useBranding } from '../contexts/BrandingContext';
import { notificationsAPI, superadminAPI } from '../api';
import { motion, AnimatePresence } from 'framer-motion';

// ── tokens ─────────────────────────────────────────────────────────────────
// These are now defaults, overridden dynamically by the BrandingContext
const DEFAULT_BG = '#0a2e1a';
const DEFAULT_GOLD = '#FDB913';
const DEFAULT_GREEN = '#006837';
const W = 68;            // rail width px

// ── nav manifest ────────────────────────────────────────────────────────────
interface NavItem {
  label: string;
  Icon: React.ComponentType<any>;
  path: string;
  coordinatorOnly?: true;
  adminOnly?: true;
  superadminOnly?: true;
}

const NAV: NavItem[] = [
  { label: 'Platform Console', Icon: BusinessIcon, path: '/superadmin', superadminOnly: true },
  
  { label: 'Dashboard', Icon: DashboardIcon, path: '/dashboard' },
  { label: 'Admin', Icon: AnalyticsIcon, path: '/admin', adminOnly: true },
  { label: 'Analytics', Icon: AutoGraphIcon, path: '/analytics', coordinatorOnly: true },
  
  { label: 'Timetables', Icon: CalendarIcon, path: '/timetables', coordinatorOnly: true },
  { label: 'Exams', Icon: FactCheckIcon, path: '/exam-timetables', coordinatorOnly: true },
  
  { label: 'Departments', Icon: BusinessIcon, path: '/departments', coordinatorOnly: true },
  { label: 'Courses', Icon: BookIcon, path: '/courses' },
  { label: 'Student Groups', Icon: GroupIcon, path: '/groups' },
  { label: 'Lab Groups', Icon: ScienceIcon, path: '/lab-groups' },
  { label: 'Lecturers', Icon: PersonIcon, path: '/lecturers' },
  { label: 'Rooms', Icon: RoomIcon, path: '/rooms', coordinatorOnly: true },
  
  { label: 'Users', Icon: ManageAccountsIcon, path: '/users', coordinatorOnly: true },
  { label: 'Help', Icon: HelpIcon, path: '/help' },
];

// ── Pill component (renders its own label outside the icon button) ───────────
const PillLabel: React.FC<{ label: string; visible: boolean }> = ({ label, visible }) => (
  <Box
    sx={{
      position: 'fixed',         // fixed so it truly escapes overflow clipping
      pointerEvents: 'none',
      opacity: visible ? 1 : 0,
      transform: visible ? 'translateX(0px)' : 'translateX(-8px)',
      transition: 'opacity 0.17s ease, transform 0.17s ease',
      zIndex: 9999,
      display: 'flex',
      alignItems: 'center',
      gap: 0,
    }}
  >
    {/* arrow */}
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
);

// ── Single rail icon button ──────────────────────────────────────────────────
const RailBtn: React.FC<{
  label: string;
  Icon: React.ComponentType<any>;
  active: boolean;
  onClick: () => void;
  primaryColor: string;
}> = ({ label, Icon, active, onClick, primaryColor }) => {
  const [hovered, setHovered] = useState(false);
  const [pillStyle, setPillStyle] = useState<{ top: number; left: number }>({ top: 0, left: 0 });

  const handleMouseEnter = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setPillStyle({ top: rect.top + rect.height / 2 - 14, left: rect.right + 6 });
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
              ? 'rgba(255,255,255,0.10)'
              : 'transparent',
          boxShadow: active ? `inset 3px 0 0 ${primaryColor}` : 'none',
          transition: 'background 0.17s, box-shadow 0.17s',
        }}
      >
        <Icon
          sx={{
            fontSize: 21,
            color: active ? primaryColor : hovered ? '#fff' : 'rgba(255,255,255,0.45)',
            transition: 'color 0.17s',
          }}
        />
      </Box>

      {/* Pill label — rendered via portal-style fixed position */}
      {hovered && (
        <Box
          sx={{
            position: 'fixed',
            top: pillStyle.top,
            left: pillStyle.left,
            pointerEvents: 'none',
            display: 'flex',
            alignItems: 'center',
            zIndex: 9999,
            animation: 'pillIn 0.17s ease forwards',
            '@keyframes pillIn': {
              from: { opacity: 0, transform: 'translateX(-6px)' },
              to: { opacity: 1, transform: 'translateX(0)' },
            },
          }}
        >
          <Box sx={{ width: 0, height: 0, borderTop: '5px solid transparent', borderBottom: '5px solid transparent', borderRight: '6px solid #1c2b3a' }} />
          <Box sx={{ bgcolor: '#1c2b3a', border: '1px solid rgba(255,255,255,0.13)', borderRadius: '8px', px: 1.5, py: 0.6, boxShadow: '0 4px 20px rgba(0,0,0,0.45)' }}>
            <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: '#fff', letterSpacing: 0.3, whiteSpace: 'nowrap' }}>
              {label}
            </Typography>
          </Box>
        </Box>
      )}
    </Box>
  );
};

// ── Main layout ──────────────────────────────────────────────────────────────
const DashboardLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout, isCoordinator, isAdmin, isSuperadmin } = useAuth();
  const { branding, loading: brandingLoading } = useBranding();
  
  const [profileAnchor, setProfileAnchor] = useState<null | HTMLElement>(null);
  const [notificationAnchor, setNotificationAnchor] = useState<null | HTMLElement>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<any[]>([]);

  useEffect(() => {
    const fetchUnread = async () => {
      // Skip entirely if not authenticated
      if (!user || !sessionStorage.getItem('token')) {
        setUnreadCount(0);
        return;
      }
      try {
        const [countRes, notifs] = await Promise.all([
          notificationsAPI.getUnreadCount(),
          notificationsAPI.getAll(false, 10),
        ]);
        setUnreadCount(countRes.unread_count || 0);
        setNotifications(notifs?.notifications || []);
      } catch (e: any) {
        // Silently ignore 401 — happens briefly during login/logout transitions
        if (e?.response?.status !== 401) {
          console.error('Failed to fetch unread notifications', e);
        }
      }
    };

    if (!user) {
      setUnreadCount(0);
      return; // Don't even start the interval when logged out
    }

    fetchUnread();
    const interval = setInterval(fetchUnread, 30_000);
    return () => clearInterval(interval);
  }, [user]);


  const isActive = (path: string) => location.pathname === path;

  const visibleNav = NAV.filter((item) => {
    // If the user is a superadmin, they should only see platform-level options and help/audit
    if (isSuperadmin) {
      return item.superadminOnly || item.label === 'Help' || item.label === 'Audit Logs';
    }
    
    // Normal user filters
    if (item.superadminOnly) return false;
    if (item.adminOnly && !isAdmin) return false;
    if (item.coordinatorOnly && !isCoordinator) return false;
    return true;
  });

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: '#f8fafc' }}>

      {/* ═══════════════════════════════════════════════╗
          SIDEBAR RAIL — desktop                         ║
      ══════════════════════════════════════════════════╝ */}
      <Box
        component="nav"
        sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: W,
          height: '100vh',
          bgcolor: '#070b14', // Match the dark Superadmin aesthetic
          display: { xs: 'none', sm: 'flex' },
          flexDirection: 'column',
          alignItems: 'center',
          zIndex: 1300,
          boxShadow: '4px 0 24px rgba(0,0,0,0.4)',
          overflowY: 'auto',
          scrollbarWidth: 'none',
          '&::-webkit-scrollbar': { display: 'none' },
          py: 2,
          borderRight: '1px solid rgba(255, 255, 255, 0.05)',
        }}
      >
        {/* ── Logo ── */}
        <Box
          sx={{
            width: 38,
            height: 38,
            borderRadius: '11px',
            bgcolor: branding.primary_color,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: `0 0 0 2px ${branding.secondary_color}55`,
            mb: 2.5,
            flexShrink: 0,
            overflow: 'hidden',
          }}
        >
          {branding.logo_url ? (
            <img src={`/media/logos/${branding.university_id}/logo.png`} alt="Logo" width="100%" height="100%" style={{ objectFit: 'cover' }} />
          ) : (
            <SchoolIcon sx={{ color: '#fff', fontSize: 20 }} />
          )}
        </Box>

        {/* ── Nav icons ── */}
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%', mb: 'auto' }}>
          {visibleNav.map((item) => (
            <RailBtn
              key={item.path}
              label={item.label}
              Icon={item.Icon}
              active={isActive(item.path)}
              onClick={() => navigate(item.path)}
              primaryColor={branding.primary_color}
            />
          ))}
        </Box>

        {/* ── Divider ── */}
        <Box sx={{ width: 36, height: 1, bgcolor: 'rgba(255,255,255,0.10)', my: 1 }} />
      </Box>

      {/* ── Profile dropdown ── */}
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
          <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.4)' }}>
            {user?.role?.toUpperCase()}
          </Typography>
        </Box>
        <MenuItem>
          <ListItemIcon sx={{ color: 'rgba(255,255,255,0.55)', minWidth: 'unset' }}>
            <AccountCircle fontSize="small" />
          </ListItemIcon>
          Profile
        </MenuItem>
        <Divider sx={{ borderColor: 'rgba(255,255,255,0.08)' }} />
        <MenuItem onClick={() => { logout(); navigate('/login'); }} sx={{ color: '#ff6b6b !important' }}>
          <ListItemIcon sx={{ color: '#ff6b6b', minWidth: 'unset' }}>
            <Logout fontSize="small" />
          </ListItemIcon>
          Sign out
        </MenuItem>
      </Menu>

      {/* ── Notifications dropdown ── */}
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
                sx={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.5)', py: 0, px: 0.5, minWidth: 0, textTransform: 'none', '&:hover': { color: '#fff' } }}
                onClick={async (e) => {
                  e.stopPropagation();
                  await notificationsAPI.markAllRead();
                  setUnreadCount(0);
                  setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
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
            <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.5)' }}>You have no new notifications.</Typography>
          </Box>
        ) : (
          <Box sx={{ maxHeight: 320, overflow: 'auto' }}>
            {notifications.map((n) => (
              <MenuItem 
                key={n.id} 
                onClick={async () => {
                  if (!n.is_read) {
                    await notificationsAPI.markAsRead(n.id);
                    setUnreadCount(prev => Math.max(0, prev - 1));
                    setNotifications(prev => prev.map(item => item.id === n.id ? { ...item, is_read: true } : item));
                  }
                }}
                sx={{ 
                  bgcolor: n.is_read ? 'transparent' : 'rgba(255, 64, 129, 0.05)',
                  flexDirection: 'column',
                  alignItems: 'flex-start'
                }}
              >
                <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', mb: 0.5 }}>
                  <Typography variant="caption" sx={{ color: n.is_read ? 'text.secondary' : '#ff4081', fontWeight: 'bold' }}>
                    {n.type?.toUpperCase() || 'SYSTEM'}
                  </Typography>
                  {!n.is_read && <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: '#ff4081' }} />}
                </Box>
                <Typography variant="body2" sx={{ color: n.is_read ? '#ccc' : '#fff', fontWeight: n.is_read ? 'normal' : 'bold' }}>
                  {n.title}
                </Typography>
                <Typography variant="caption" sx={{ color: '#888', whiteSpace: 'normal', lineHeight: 1.2, mt: 0.5 }}>
                  {n.message}
                </Typography>
              </MenuItem>
            ))}
          </Box>
        )}
      </Menu>

      {/* ═══════════════════════════════════════════════╗
          MOBILE top bar                                 ║
      ══════════════════════════════════════════════════╝ */}
      <Box
        sx={{
          display: { xs: 'flex', sm: 'none' },
          position: 'fixed',
          top: 0, left: 0, right: 0,
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
          <img src={`/media/logos/${branding.university_id}/logo.png`} alt="Logo" width={24} height={24} style={{ borderRadius: 4 }} />
        ) : (
          <SchoolIcon sx={{ color: branding.primary_color, fontSize: 22 }} />
        )}
        <Typography variant="subtitle2" fontWeight={700} sx={{ color: '#fff' }}>
          {branding.short_name || branding.name}
        </Typography>
      </Box>

      {/* ═══════════════════════════════════════════════╗
          MAIN CONTENT                                   ║
      ══════════════════════════════════════════════════╝ */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          ml: { xs: 0, sm: `${W}px` },
          mt: { xs: '56px', sm: 0 },
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* ── Impersonation Banner (only for active superadmin sessions) ── */}
        {sessionStorage.getItem('superadmin_impersonator') === 'true' && user?.role?.toUpperCase() === 'SUPERADMIN' && (
          <Box sx={{ bgcolor: '#d32f2f', color: '#fff', px: 4, py: 1.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center', zIndex: 1101, position: 'relative' }}>
            <Typography variant="body2" fontWeight={600}>
              ⚠️ You are actively impersonating a tenant.
            </Typography>
            <Button 
              size="small" 
              variant="contained" 
              sx={{ bgcolor: '#fff', color: '#d32f2f', fontWeight: 700, '&:hover': { bgcolor: '#f5f5f5' } }}
              onClick={async () => {
                try {
                   const res = await superadminAPI.revertImpersonation();
                   sessionStorage.setItem('token', res.access_token);
                   sessionStorage.removeItem('superadmin_impersonator');
                   localStorage.removeItem('university_id');
                   window.location.href = '/superadmin';
                } catch(e) { console.error('Failed to revert impersonation', e); }
              }}
            >
              Exit Impersonation
            </Button>
          </Box>
        )}

        {/* Top header bar */}
        <Box
          sx={{
            display: { xs: 'none', sm: 'flex' },
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: 2,
            px: 4,
            py: 1.5,
            background: `linear-gradient(90deg, rgba(255,255,255,0.85) 0%, ${branding.primary_color}10 100%)`, // dynamic branding splash
            backdropFilter: 'blur(20px)',
            borderBottom: '1px solid rgba(0,0,0,0.05)',
            boxShadow: '0 4px 30px rgba(0,0,0,0.03)',
            position: 'sticky',
            top: 0,
            zIndex: 1100,
          }}
        >
          {/* ── Notifications Top Bar Icon ── */}
          <IconButton
            onClick={(e) => setNotificationAnchor(e.currentTarget)}
            sx={{
              color: 'text.secondary',
              bgcolor: 'rgba(0,0,0,0.03)',
              '&:hover': { bgcolor: 'rgba(0,0,0,0.06)' }
            }}
          >
            <Badge badgeContent={unreadCount} color="error">
              <NotificationsIcon fontSize="small" />
            </Badge>
          </IconButton>
          {/* ── Top Bar Avatar ── */}
          <Box
            onClick={(e) => setProfileAnchor(e.currentTarget)}
            sx={{
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              ml: 1
            }}
          >
            <Avatar
              sx={{
                width: 38,
                height: 38,
                bgcolor: branding.primary_color,
                color: '#fff',
                fontWeight: 700,
                fontSize: 15,
                border: '2px solid rgba(0,0,0,0.05)',
                transition: 'transform 0.2s',
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
              transition={{ duration: 0.25, ease: "easeOut" }}
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
