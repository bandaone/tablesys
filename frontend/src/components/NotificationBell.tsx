import React, { useEffect, useState } from 'react';
import {
    Badge,
    Box,
    Button,
    Divider,
    IconButton,
    List,
    ListItem,
    ListItemText,
    Menu,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    Notifications as NotificationsIcon,
    CheckCircle as CheckCircleIcon,
    Warning as WarningIcon,
    Info as InfoIcon,
    Error as ErrorIcon,
    DoneAll as DoneAllIcon,
    Delete as DeleteIcon,
} from '@mui/icons-material';
import api from '../api';
import { useAuth } from '../contexts/AuthContext';

interface Notification {
    id: number;
    title: string;
    message: string;
    type: 'info' | 'success' | 'warning' | 'error';
    is_read: boolean;
    created_at: string;
    read_at: string | null;
    action_link: string | null;
}

const NotificationBell: React.FC = () => {
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [unreadCount, setUnreadCount] = useState(0);
    const [loading, setLoading] = useState(false);
    const { user } = useAuth();

    const open = Boolean(anchorEl);

    const fetchUnreadCount = async () => {
        // Do not poll if the user is not logged in — avoids 401 log spam
        if (!user || !sessionStorage.getItem('token')) return;
        try {
            const response = await api.get('/notifications/unread-count');
            setUnreadCount(response.data.unread_count ?? 0);
        } catch (err: any) {
            // Silently ignore 401 (e.g. session just expired) — no console noise
            if (err?.response?.status !== 401) {
                console.error('Error fetching unread count:', err);
            }
        }
    };

    const fetchNotifications = async () => {
        if (!user || !sessionStorage.getItem('token')) return;
        setLoading(true);
        try {
            const response = await api.get('/notifications', {
                params: { limit: 20 },
            });
            setNotifications(response.data.notifications);
        } catch (err: any) {
            if (err?.response?.status !== 401) {
                console.error('Error fetching notifications:', err);
            }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        // Only start polling once the user is authenticated
        if (!user) {
            setUnreadCount(0);
            setNotifications([]);
            return;
        }
        fetchUnreadCount();
        const interval = setInterval(fetchUnreadCount, 30_000);
        return () => clearInterval(interval);
    }, [user]); // Re-runs when auth state changes

    const handleClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
        fetchNotifications();
    };

    const handleClose = () => {
        setAnchorEl(null);
    };

    const handleMarkAsRead = async (notificationId: number) => {
        try {
            await api.post(`/notifications/${notificationId}/read`);
            setNotifications((prev) =>
                prev.map((n) => (n.id === notificationId ? { ...n, is_read: true } : n))
            );
            setUnreadCount((prev) => Math.max(0, prev - 1));
        } catch (err) {
            console.error('Error marking notification as read:', err);
        }
    };

    const handleMarkAllRead = async () => {
        try {
            await api.post('/notifications/mark-all-read');
            setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
            setUnreadCount(0);
        } catch (err) {
            console.error('Error marking all as read:', err);
        }
    };

    const handleDelete = async (notificationId: number) => {
        try {
            await api.delete(`/notifications/${notificationId}`);
            setNotifications((prev) => prev.filter((n) => n.id !== notificationId));
            fetchUnreadCount();
        } catch (err) {
            console.error('Error deleting notification:', err);
        }
    };

    const getNotificationIcon = (type: string) => {
        switch (type) {
            case 'success':
                return <CheckCircleIcon color="success" />;
            case 'warning':
                return <WarningIcon color="warning" />;
            case 'error':
                return <ErrorIcon color="error" />;
            default:
                return <InfoIcon color="info" />;
        }
    };

    const formatTime = (isoString: string) => {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    };

    return (
        <>
            <Tooltip title="Notifications">
                <IconButton color="inherit" onClick={handleClick}>
                    <Badge badgeContent={unreadCount} color="error">
                        <NotificationsIcon />
                    </Badge>
                </IconButton>
            </Tooltip>

            <Menu
                anchorEl={anchorEl}
                open={open}
                onClose={handleClose}
                PaperProps={{
                    sx: {
                        width: 400,
                        maxHeight: 600,
                    },
                }}
                transformOrigin={{ horizontal: 'right', vertical: 'top' }}
                anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
            >
                <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="h6">Notifications</Typography>
                    {unreadCount > 0 && (
                        <Button
                            size="small"
                            startIcon={<DoneAllIcon />}
                            onClick={handleMarkAllRead}
                        >
                            Mark all read
                        </Button>
                    )}
                </Box>
                <Divider />

                {loading ? (
                    <Box sx={{ p: 3, textAlign: 'center' }}>
                        <Typography color="text.secondary">Loading...</Typography>
                    </Box>
                ) : notifications.length === 0 ? (
                    <Box sx={{ p: 3, textAlign: 'center' }}>
                        <Typography color="text.secondary">No notifications</Typography>
                    </Box>
                ) : (
                    <List sx={{ p: 0, maxHeight: 400, overflow: 'auto' }}>
                        {notifications.map((notification) => (
                            <ListItem
                                key={notification.id}
                                sx={{
                                    bgcolor: notification.is_read ? 'transparent' : 'action.hover',
                                    borderLeft: notification.is_read ? 'none' : '4px solid',
                                    borderLeftColor:
                                        notification.type === 'success' ? 'success.main' :
                                            notification.type === 'warning' ? 'warning.main' :
                                                notification.type === 'error' ? 'error.main' :
                                                    'info.main',
                                    '&:hover': {
                                        bgcolor: 'action.selected',
                                    },
                                }}
                                secondaryAction={
                                    <Box>
                                        {!notification.is_read && (
                                            <Tooltip title="Mark as read">
                                                <IconButton
                                                    edge="end"
                                                    size="small"
                                                    onClick={() => handleMarkAsRead(notification.id)}
                                                >
                                                    <CheckCircleIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                        )}
                                        <Tooltip title="Delete">
                                            <IconButton
                                                edge="end"
                                                size="small"
                                                onClick={() => handleDelete(notification.id)}
                                            >
                                                <DeleteIcon fontSize="small" />
                                            </IconButton>
                                        </Tooltip>
                                    </Box>
                                }
                            >
                                <Box sx={{ display: 'flex', alignItems: 'flex-start', mr: 6 }}>
                                    <Box sx={{ mr: 1.5, mt: 0.5 }}>
                                        {getNotificationIcon(notification.type)}
                                    </Box>
                                    <ListItemText
                                        primary={
                                            <Typography variant="subtitle2" fontWeight={notification.is_read ? 'normal' : 'bold'}>
                                                {notification.title}
                                            </Typography>
                                        }
                                        secondary={
                                            <>
                                                <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                                                    {notification.message}
                                                </Typography>
                                                <Typography variant="caption" color="text.secondary">
                                                    {formatTime(notification.created_at)}
                                                </Typography>
                                            </>
                                        }
                                    />
                                </Box>
                            </ListItem>
                        ))}
                    </List>
                )}
            </Menu>
        </>
    );
};

export default NotificationBell;
