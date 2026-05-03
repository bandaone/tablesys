import React, { useState, useEffect } from 'react';
import {
    Box,
    Card,
    CardContent,
    Typography,
    IconButton,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    Chip,
    Dialog,
    DialogTitle,
    DialogContent,
    Badge,
    Tooltip,
} from '@mui/material';
import {
    Fullscreen as FullscreenIcon,
    CheckCircle as SuccessIcon,
    Error as ErrorIcon,
    Info as InfoIcon,
    Close as CloseIcon,
} from '@mui/icons-material';

interface AuditEvent {
    id?: number;
    timestamp: string;
    event_type: string;
    user_id: number | null;
    username: string | null;
    resource: string;
    action: string;
    success: boolean;
    details: any;
}

interface MonitorWidgetProps {
    title: string;
    icon: React.ReactNode;
    events: AuditEvent[];
    filterFn: (e: AuditEvent) => boolean;
}

export const MonitorWidget: React.FC<MonitorWidgetProps> = ({ title, icon, events, filterFn }) => {
    const [isFullscreen, setIsFullscreen] = useState(false);

    // Filter events specific to this widget
    const widgetEvents = events.filter(filterFn);

    // Analytics
    const successes = widgetEvents.filter(e => e.success).length;
    const failures = widgetEvents.filter(e => !e.success).length;

    const renderEventList = (limit?: number) => {
        const displayEvents = limit ? widgetEvents.slice(0, limit) : widgetEvents;

        if (displayEvents.length === 0) {
            return (
                <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', mt: 4 }}>
                    No recent activity
                </Typography>
            );
        }

        return (
            <List dense sx={{ width: '100%', bgcolor: 'background.paper', overflow: 'auto', maxHeight: limit ? 400 : '70vh' }}>
                {displayEvents.map((event, index) => {
                    const date = new Date(event.timestamp);
                    const timeStr = isNaN(date.getTime()) ? 'Just now' : date.toLocaleTimeString();

                    return (
                        <ListItem
                            key={event.id ? `evt-${event.id}` : `ts-${event.timestamp}-${index}`}
                            divider
                            sx={{
                                borderLeft: `4px solid ${event.success ? '#4caf50' : '#f44336'}`,
                                mb: 0.5,
                                bgcolor: event.success ? 'rgba(76, 175, 80, 0.04)' : 'rgba(244, 67, 54, 0.04)',
                            }}
                        >
                            <ListItemIcon sx={{ minWidth: 36 }}>
                                {event.success ? (
                                    <SuccessIcon color="success" fontSize="small" />
                                ) : (
                                    <ErrorIcon color="error" fontSize="small" />
                                )}
                            </ListItemIcon>
                            <ListItemText
                                primary={
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <Typography variant="body2" fontWeight="bold">
                                            {event.event_type}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {timeStr}
                                        </Typography>
                                    </Box>
                                }
                                secondary={
                                    <Box sx={{ mt: 0.5 }}>
                                        <Typography variant="caption" display="block">
                                            <strong>User:</strong> {event.username || 'System'}
                                        </Typography>
                                        {event.details && event.details.message && (
                                            <Typography variant="caption" color="text.secondary" display="block">
                                                {event.details.message}
                                            </Typography>
                                        )}
                                        {event.details && event.details.error && (
                                            <Typography variant="caption" color="error" display="block">
                                                Err: {event.details.error}
                                            </Typography>
                                        )}
                                    </Box>
                                }
                            />
                        </ListItem>
                    );
                })}
            </List>
        );
    };

    return (
        <>
            <Card
                sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
                    borderTop: '4px solid #1976d2'
                }}
            >
                <CardContent sx={{ flexGrow: 1, p: 2, display: 'flex', flexDirection: 'column' }}>
                    {/* Header */}
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {icon}
                            <Typography variant="h6" component="div" fontWeight="bold">
                                {title}
                            </Typography>
                        </Box>
                        <Tooltip title="Expand to Fullscreen">
                            <IconButton size="small" onClick={() => setIsFullscreen(true)}>
                                <FullscreenIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                    </Box>

                    {/* Analytics Overview */}
                    <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                        <Chip
                            icon={<InfoIcon />}
                            label={`Total: ${widgetEvents.length}`}
                            size="small"
                            color="primary"
                            variant="outlined"
                        />
                        <Chip
                            label={`Success: ${successes}`}
                            size="small"
                            color="success"
                        />
                        {failures > 0 && (
                            <Chip
                                label={`Failed: ${failures}`}
                                size="small"
                                color="error"
                            />
                        )}
                    </Box>

                    {/* Scrolling Feed Container */}
                    <Box sx={{ flexGrow: 1, overflow: 'hidden', borderTop: '1px solid #eee', pt: 1 }}>
                        {renderEventList(150)}
                    </Box>
                </CardContent>
            </Card>

            {/* Fullscreen Dialog */}
            <Dialog
                fullScreen
                open={isFullscreen}
                onClose={() => setIsFullscreen(false)}
            >
                <DialogTitle sx={{ m: 0, p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #ddd' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {icon}
                        <Typography variant="h5">{title} - Detailed View</Typography>
                    </Box>
                    <IconButton onClick={() => setIsFullscreen(false)}>
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>
                <DialogContent sx={{ p: 0, bgcolor: '#f5f5f5' }}>
                    <Box sx={{ p: 3, maxWidth: 1200, margin: '0 0' }}>
                        <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
                            <Card sx={{ p: 2, minWidth: 200, textAlign: 'center', borderLeft: '4px solid #1976d2' }}>
                                <Typography variant="subtitle2" color="text.secondary">Total Events</Typography>
                                <Typography variant="h3">{widgetEvents.length}</Typography>
                            </Card>
                            <Card sx={{ p: 2, minWidth: 200, textAlign: 'center', borderLeft: '4px solid #4caf50' }}>
                                <Typography variant="subtitle2" color="text.secondary">Successful</Typography>
                                <Typography variant="h3" color="success.main">{successes}</Typography>
                            </Card>
                            <Card sx={{ p: 2, minWidth: 200, textAlign: 'center', borderLeft: '4px solid #f44336' }}>
                                <Typography variant="subtitle2" color="text.secondary">Failed</Typography>
                                <Typography variant="h3" color="error.main">{failures}</Typography>
                            </Card>
                        </Box>

                        <Card sx={{ p: 0 }}>
                            {renderEventList()}
                        </Card>
                    </Box>
                </DialogContent>
            </Dialog>
        </>
    );
};
