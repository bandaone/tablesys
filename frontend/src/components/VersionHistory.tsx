import React, { useEffect, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    IconButton,
    List,
    ListItem,
    ListItemText,
    Snackbar,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    History as HistoryIcon,
    Restore as RestoreIcon,
    Delete as DeleteIcon,
    Save as SaveIcon,
    Close as CloseIcon,
} from '@mui/icons-material';
import api from '../api';

interface Version {
    id: number;
    version_number: number;
    description: string;
    created_at: string;
    created_by: {
        id: number;
        username: string;
        full_name: string;
    };
    slot_count: number;
}

interface VersionHistoryProps {
    timetableId: number;
    timetableName: string;
    onVersionRestored?: () => void;
}

const VersionHistory: React.FC<VersionHistoryProps> = ({
    timetableId,
    timetableName,
    onVersionRestored,
}) => {
    const [versions, setVersions] = useState<Version[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [createDialogOpen, setCreateDialogOpen] = useState(false);
    const [restoreDialogOpen, setRestoreDialogOpen] = useState(false);
    const [selectedVersion, setSelectedVersion] = useState<Version | null>(null);
    const [description, setDescription] = useState('');

    const fetchVersions = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await api.get(`/api/v1/timetables/${timetableId}/versions`);
            setVersions(response.data.versions || []);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load version history');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (timetableId) {
            fetchVersions();
        }
    }, [timetableId]);

    const handleCreateVersion = async () => {
        if (!description.trim()) {
            setError('Please provide a description for the version');
            return;
        }

        setLoading(true);
        setError(null);
        try {
            await api.post(`/api/v1/timetables/${timetableId}/versions`, null, {
                params: { description: description.trim() },
            });
            setSuccess('Version created successfully');
            setCreateDialogOpen(false);
            setDescription('');
            fetchVersions();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to create version');
        } finally {
            setLoading(false);
        }
    };

    const handleRestoreVersion = async () => {
        if (!selectedVersion) return;

        setLoading(true);
        setError(null);
        try {
            const response = await api.post(
                `/api/v1/timetables/${timetableId}/versions/${selectedVersion.id}/restore`
            );
            setSuccess(response.data.message || 'Version restored successfully');
            setRestoreDialogOpen(false);
            setSelectedVersion(null);
            fetchVersions();
            if (onVersionRestored) {
                onVersionRestored();
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to restore version');
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteVersion = async (versionId: number) => {
        if (!window.confirm('Are you sure you want to delete this version?')) {
            return;
        }

        setLoading(true);
        setError(null);
        try {
            await api.delete(`/api/v1/timetables/${timetableId}/versions/${versionId}`);
            setSuccess('Version deleted successfully');
            fetchVersions();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to delete version');
        } finally {
            setLoading(false);
        }
    };

    const formatDate = (isoString: string) => {
        const date = new Date(isoString);
        return date.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    return (
        <Card>
            <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <HistoryIcon color="primary" />
                        <Typography variant="h6">Version History</Typography>
                        <Chip label={versions.length} size="small" color="primary" />
                    </Box>
                    <Button
                        variant="contained"
                        startIcon={<SaveIcon />}
                        onClick={() => setCreateDialogOpen(true)}
                        disabled={loading}
                    >
                        Create Version
                    </Button>
                </Box>

                <Divider sx={{ mb: 2 }} />

                {error && (
                    <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                        {error}
                    </Alert>
                )}

                {versions.length === 0 ? (
                    <Typography color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                        No versions yet. Create your first version to start tracking changes.
                    </Typography>
                ) : (
                    <List sx={{ maxHeight: 400, overflow: 'auto' }}>
                        {versions.map((version, index) => (
                            <ListItem
                                key={version.id}
                                sx={{
                                    border: '1px solid',
                                    borderColor: 'divider',
                                    borderRadius: 1,
                                    mb: 1,
                                    bgcolor: index === 0 ? 'action.hover' : 'background.paper',
                                }}
                                secondaryAction={
                                    <Box sx={{ display: 'flex', gap: 1 }}>
                                        <Tooltip title="Restore this version">
                                            <IconButton
                                                edge="end"
                                                color="primary"
                                                onClick={() => {
                                                    setSelectedVersion(version);
                                                    setRestoreDialogOpen(true);
                                                }}
                                                disabled={loading}
                                            >
                                                <RestoreIcon />
                                            </IconButton>
                                        </Tooltip>
                                        <Tooltip title="Delete version">
                                            <IconButton
                                                edge="end"
                                                color="error"
                                                onClick={() => handleDeleteVersion(version.id)}
                                                disabled={loading || index === 0}
                                            >
                                                <DeleteIcon />
                                            </IconButton>
                                        </Tooltip>
                                    </Box>
                                }
                            >
                                <ListItemText
                                    primary={
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Typography variant="subtitle1" fontWeight="bold">
                                                Version {version.version_number}
                                            </Typography>
                                            {index === 0 && <Chip label="Latest" size="small" color="success" />}
                                        </Box>
                                    }
                                    secondary={
                                        <>
                                            <Typography component="span" variant="body2" display="block">
                                                {version.description}
                                            </Typography>
                                            <Typography component="span" variant="caption" color="text.secondary">
                                                {formatDate(version.created_at)} • {version.created_by?.full_name} •{' '}
                                                {version.slot_count} slots
                                            </Typography>
                                        </>
                                    }
                                />
                            </ListItem>
                        ))}
                    </List>
                )}
            </CardContent>

            {/* Create Version Dialog */}
            <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>
                    Create New Version
                    <IconButton
                        sx={{ position: 'absolute', right: 8, top: 8 }}
                        onClick={() => setCreateDialogOpen(false)}
                    >
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>
                <DialogContent>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Create a snapshot of the current timetable state. This allows you to rollback to this point
                        later if needed.
                    </Typography>
                    <TextField
                        label="Version Description"
                        fullWidth
                        multiline
                        rows={3}
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="e.g., Before midterm adjustments"
                        autoFocus
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
                    <Button
                        variant="contained"
                        onClick={handleCreateVersion}
                        disabled={loading || !description.trim()}
                    >
                        Create Version
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Restore Version Dialog */}
            <Dialog open={restoreDialogOpen} onClose={() => setRestoreDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>
                    Restore Version
                    <IconButton
                        sx={{ position: 'absolute', right: 8, top: 8 }}
                        onClick={() => setRestoreDialogOpen(false)}
                    >
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>
                <DialogContent>
                    <Alert severity="warning" sx={{ mb: 2 }}>
                        This will replace the current timetable with the selected version. A backup of the current
                        state will be created automatically.
                    </Alert>
                    {selectedVersion && (
                        <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                            <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                                Version {selectedVersion.version_number}
                            </Typography>
                            <Typography variant="body2" gutterBottom>
                                {selectedVersion.description}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                Created: {formatDate(selectedVersion.created_at)}
                                <br />
                                By: {selectedVersion.created_by?.full_name}
                                <br />
                                Slots: {selectedVersion.slot_count}
                            </Typography>
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setRestoreDialogOpen(false)}>Cancel</Button>
                    <Button variant="contained" color="warning" onClick={handleRestoreVersion} disabled={loading}>
                        Restore Version
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Success Snackbar */}
            <Snackbar
                open={!!success}
                autoHideDuration={4000}
                onClose={() => setSuccess(null)}
                message={success}
            />
        </Card>
    );
};

export default VersionHistory;
