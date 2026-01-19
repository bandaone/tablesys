import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Paper,
  Typography,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  LinearProgress,
  Alert,
  Card,
  CardContent,
  Grid,
  List,
  ListItem,
  ListItemText,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import {
  Add as AddIcon,
  PlayArrow as PlayIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import { timetablesAPI } from '../api';
import { useAuth } from '../contexts/AuthContext';

interface GenerationProgress {
  level: number;
  status: string;
  percentage: number;
  message: string;
}

interface Timetable {
  id: number;
  name: string;
  semester: string;
  year: number;
  academic_half: string;
  is_active: boolean;
  min_score?: number;
  max_score?: number;
  avg_score?: number;
  generation_metadata?: {
    generated: boolean;
    generated_at?: string;
  };
}

const TimetablesPage: React.FC = () => {
  const [timetables, setTimetables] = useState<Timetable[]>([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [openGenerateDialog, setOpenGenerateDialog] = useState(false);
  const [selectedTimetable, setSelectedTimetable] = useState<Timetable | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    semester: '',
    year: new Date().getFullYear(),
    academic_half: 'first_half',
  });
  const [generationProgress, setGenerationProgress] = useState<GenerationProgress | null>(null);
  const [generationComplete, setGenerationComplete] = useState(false);
  const [generationError, setGenerationError] = useState('');
  const [levelProgress, setLevelProgress] = useState<{ [key: number]: boolean }>({});

  const { isCoordinator } = useAuth();

  useEffect(() => {
    fetchTimetables();
  }, []);

  const fetchTimetables = async () => {
    try {
      const data = await timetablesAPI.getAll();
      setTimetables(data);
    } catch (err) {
      console.error('Error fetching timetables:', err);
    }
  };

  const handleCreateTimetable = async () => {
    try {
      const newTimetable = await timetablesAPI.create(formData);
      setSelectedTimetable(newTimetable);
      setOpenDialog(false);
      setOpenGenerateDialog(true);
      fetchTimetables();
    } catch (err) {
      console.error('Error creating timetable:', err);
    }
  };

  const handleGenerateTimetable = () => {
    if (!selectedTimetable) return;

    setGenerationProgress(null);
    setGenerationComplete(false);
    setGenerationError('');
    setLevelProgress({});

    // Create WebSocket connection
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/timetables/generate/${selectedTimetable.id}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.level) {
        setGenerationProgress(data);

        if (data.status === 'completed') {
          setLevelProgress(prev => ({ ...prev, [data.level]: true }));
        }
      }

      if (data.status === 'success') {
        setGenerationComplete(true);
        setTimeout(() => {
          setOpenGenerateDialog(false);
          fetchTimetables();
        }, 2000);
      } else if (data.status === 'error') {
        setGenerationError(data.message);
      }
    };

    ws.onerror = (error) => {
      setGenerationError('WebSocket error occurred');
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket connection closed');
    };
  };

  const getLevelIcon = (level: number) => {
    if (levelProgress[level]) {
      return <CheckIcon color="success" />;
    }
    return null;
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" fontWeight="bold">
          Timetables
        </Typography>
        {isCoordinator && (
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setOpenDialog(true)}
          >
            Create Timetable
          </Button>
        )}
      </Box>

      <Grid container spacing={3}>
        {timetables.map((timetable) => (
          <Grid item xs={12} md={6} lg={4} key={timetable.id}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 2 }}>
                  <Typography variant="h6" fontWeight="bold">
                    {timetable.name}
                  </Typography>
                  {timetable.is_active && (
                    <Chip label="Active" color="success" size="small" />
                  )}
                </Box>

                <Typography color="text.secondary" gutterBottom>
                  {timetable.semester} {timetable.year}
                </Typography>

                {timetable.generation_metadata?.generated && (
                  <Alert severity="success" sx={{ mt: 2 }}>
                    Timetable generated successfully
                  </Alert>
                )}

                {isCoordinator && !timetable.generation_metadata?.generated && (
                  <Button
                    variant="outlined"
                    startIcon={<PlayIcon />}
                    fullWidth
                    sx={{ mt: 2 }}
                    onClick={() => {
                      setSelectedTimetable(timetable);
                      setOpenGenerateDialog(true);
                    }}
                  >
                    Generate Timetable
                  </Button>
                )}
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Create Timetable Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create New Timetable</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Name"
            fullWidth
            variant="outlined"
            variant="outlined"
            value={formData.name}
            onChange={(e) => { setFormData({ ...formData, name: e.target.value }); }}
          />
          <TextField
            margin="dense"
            label="Semester"
            fullWidth
            variant="outlined"
            placeholder="e.g., Semester 1"
            placeholder="e.g., Semester 1"
            value={formData.semester}
            onChange={(e) => { setFormData({ ...formData, semester: e.target.value }); }}
          />
          <TextField
            margin="dense"
            label="Year"
            type="number"
            fullWidth
            variant="outlined"
            variant="outlined"
            value={formData.year}
            onChange={(e) => { setFormData({ ...formData, year: parseInt(e.target.value) }); }}
          />
          <FormControl fullWidth margin="dense">
            <InputLabel>Academic Half</InputLabel>
            <Select
              value={formData.academic_half}
              label="Academic Half"
              onChange={(e) => { setFormData({ ...formData, academic_half: e.target.value }); }}
            >
              <MenuItem value="first_half">First Half</MenuItem>
              <MenuItem value="second_half">Second Half</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { setOpenDialog(false); }}>Cancel</Button>
          <Button onClick={() => { void handleCreateTimetable(); }} variant="contained">
            Create
          </Button>
        </DialogActions>
      </Dialog>

      {/* Generate Timetable Dialog with Progress */}
      <Dialog
        open={openGenerateDialog}
        onClose={() => !generationProgress && setOpenGenerateDialog(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Generate Timetable</DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 2 }}>
            {!generationProgress && !generationComplete && !generationError && (
              <Alert severity="info">
                Click "Start Generation" to begin creating the timetable. The system will
                generate schedules level by level: 5th year → 4th year → 3rd year → 2nd year.
              </Alert>
            )}

            {generationProgress && (
              <Box>
                <Typography variant="h6" gutterBottom>
                  Generation Progress
                </Typography>

                <Box sx={{ mb: 3 }}>
                  <LinearProgress
                    variant="determinate"
                    value={generationProgress.percentage}
                    sx={{ height: 10, borderRadius: 5 }}
                  />
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1, textAlign: 'center' }}>
                    {Math.round(generationProgress.percentage)}%
                  </Typography>
                </Box>

                <Alert severity="info" sx={{ mb: 2 }}>
                  {generationProgress.message}
                </Alert>

                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="subtitle2" gutterBottom fontWeight="bold">
                    Level Progress:
                  </Typography>
                  <List dense>
                    {[5, 4, 3, 2].map((level) => (
                      <ListItem key={level}>
                        <ListItemText
                          primary={`Level ${level}`}
                          secondary={levelProgress[level] ? 'Completed' : 'Pending'}
                        />
                        {getLevelIcon(level)}
                      </ListItem>
                    ))}
                  </List>
                </Paper>
              </Box>
            )}

            {generationComplete && (
              <Alert severity="success" icon={<CheckIcon />}>
                Timetable generated successfully! All levels have been processed.
              </Alert>
            )}

            {generationError && (
              <Alert severity="error" icon={<ErrorIcon />}>
                {generationError}
              </Alert>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          {!generationProgress && !generationComplete && (
            <>
              <Button onClick={() => setOpenGenerateDialog(false)}>Cancel</Button>
              <Button
                onClick={handleGenerateTimetable}
                variant="contained"
                startIcon={<PlayIcon />}
              >
                Start Generation
              </Button>
            </>
          )}
          {(generationComplete || generationError) && (
            <Button onClick={() => setOpenGenerateDialog(false)} variant="contained">
              Close
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default TimetablesPage;
