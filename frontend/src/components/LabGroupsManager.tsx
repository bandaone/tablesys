import React, { useState, useEffect } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    Typography,
    Box,
    CircularProgress,
    List,
    ListItem,
    ListItemText,
    Divider,
    Grid,
    Alert
} from '@mui/material';
import { groupsAPI } from '../api';

interface LabGroupsManagerProps {
    open: boolean;
    onClose: () => void;
    groupId: number;
    groupName: string;
}

export const LabGroupsManager: React.FC<LabGroupsManagerProps> = ({ open, onClose, groupId, groupName }) => {
    const [subgroups, setSubgroups] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [error, setError] = useState('');

    // Form state
    const [prefix, setPrefix] = useState('A');
    const [count, setCount] = useState(2);
    const [sizePerGroup, setSizePerGroup] = useState(10);

    useEffect(() => {
        if (open && groupId) {
            fetchSubgroups();
        }
    }, [open, groupId]);

    const fetchSubgroups = async () => {
        try {
            setLoading(true);
            setError('');
            const data = await groupsAPI.getSubgroups(groupId);
            setSubgroups(data);
        } catch (err: any) {
            setError('Failed to load lab groups.');
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleGenerate = async () => {
        try {
            setGenerating(true);
            setError('');
            await groupsAPI.generateSubgroups(groupId, {
                prefix,
                count: Number(count),
                size_per_group: Number(sizePerGroup),
                group_type: 'lab_group'
            });
            await fetchSubgroups();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to generate lab groups.');
        } finally {
            setGenerating(false);
        }
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle>Manage Lab Groups for {groupName}</DialogTitle>
            <DialogContent dividers>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                <Box sx={{ mb: 4 }}>
                    <Typography variant="h6" gutterBottom>Generate New Subgroups</Typography>
                    <Grid container spacing={2} alignItems="center">
                        <Grid item xs={12} sm={4}>
                            <TextField
                                fullWidth
                                label="Prefix (e.g., A, B, L)"
                                value={prefix}
                                onChange={(e) => setPrefix(e.target.value)}
                                size="small"
                            />
                        </Grid>
                        <Grid item xs={12} sm={4}>
                            <TextField
                                fullWidth
                                type="number"
                                label="Number of Groups"
                                value={count}
                                onChange={(e) => setCount(Number(e.target.value))}
                                inputProps={{ min: 1, max: 20 }}
                                size="small"
                            />
                        </Grid>
                        <Grid item xs={12} sm={4}>
                            <TextField
                                fullWidth
                                type="number"
                                label="Size per Group"
                                value={sizePerGroup}
                                onChange={(e) => setSizePerGroup(Number(e.target.value))}
                                inputProps={{ min: 1, max: 100 }}
                                size="small"
                            />
                        </Grid>
                        <Grid item xs={12}>
                            <Button
                                variant="contained"
                                color="primary"
                                onClick={handleGenerate}
                                disabled={generating || !prefix}
                                fullWidth
                            >
                                {generating ? <CircularProgress size={24} /> : 'Generate Groups'}
                            </Button>
                        </Grid>
                    </Grid>
                </Box>

                <Divider sx={{ my: 2 }} />

                <Typography variant="h6" gutterBottom>Existing Subgroups</Typography>
                {loading ? (
                    <CircularProgress />
                ) : subgroups.length === 0 ? (
                    <Typography color="textSecondary">No lab groups have been created yet.</Typography>
                ) : (
                    <List dense>
                        {subgroups.map((sg) => (
                            <ListItem key={sg.id} divider>
                                <ListItemText
                                    primary={sg.name}
                                    secondary={`Size: ${sg.size} | Type: ${sg.group_type}`}
                                />
                            </ListItem>
                        ))}
                    </List>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} color="inherit">Close</Button>
            </DialogActions>
        </Dialog>
    );
};
