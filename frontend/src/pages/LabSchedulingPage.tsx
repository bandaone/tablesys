import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  Grid,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Tab,
  Tabs,
  TextField,
  Stack,
  Typography,
  Tooltip,
} from '@mui/material';
import {
  Add as AddIcon,
  AutoAwesome as AutoAwesomeIcon,
  Delete as DeleteIcon,
  Event as EventIcon,
  Group as GroupIcon,
  Publish as PublishIcon,
  Science as ScienceIcon,
  Unpublished as UnpublishedIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';

import { labCoordinatorAPI, coursesAPI, groupsAPI } from '../api';
import LabGroupsPage from './LabGroupsPage'; // We reuse the tree view here

const isLabCourse = (course: any) => {
  if (!course) return false;
  return (course.practical_hours ?? 0) > 0;
};

const toList = <T,>(value: unknown): T[] => {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === 'object') {
    const maybeObject = value as Record<string, unknown>;
    if (Array.isArray(maybeObject.items)) return maybeObject.items as T[];
    if (Array.isArray(maybeObject.results)) return maybeObject.results as T[];
    if (Array.isArray(maybeObject.data)) return maybeObject.data as T[];
  }
  return [];
};

const LabSchedulingPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Dashboard Summary State
  const [summary, setSummary] = useState({
    total_sessions: 0,
    conflicted_sessions: 0,
    lab_groups: 0,
    lab_rooms: 0,
    conflict_rate: 0,
  });

  // Scheduling State
  const [sessions, setSessions] = useState<any[]>([]);
  const [rooms, setRooms] = useState<any[]>([]);
  const [departmentRoomIds, setDepartmentRoomIds] = useState<number[]>([]);
  const [savingRoomPool, setSavingRoomPool] = useState(false);
  const [labSubgroups, setLabSubgroups] = useState<any[]>([]);
  const [mainGroups, setMainGroups] = useState<any[]>([]);
  const [labCourses, setLabCourses] = useState<any[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [groupCourseMap, setGroupCourseMap] = useState<any | null>(null);
  const [groupAssignedCourseIds, setGroupAssignedCourseIds] = useState<number[]>([]);
  const [groupLoading, setGroupLoading] = useState(false);

  // Smart Scheduler Modal State
  const [smartOpen, setSmartOpen] = useState(false);
  const [smartForm, setSmartForm] = useState({
    room_ids: [] as number[],
    duration_minutes: 120,
    frequency_weeks: 1,
    subgroups_per_session: 1,
    session_type: 'lab',
    preferred_days: [0, 1, 2, 3, 4] as number[],
    start_hour: 7,
    end_hour: 17,
  });
  const [smartGenerating, setSmartGenerating] = useState(false);
  const [publicationActionId, setPublicationActionId] = useState<number | null>(null);

  // Venue Management State
  const [venueForm, setVenueForm] = useState({ name: '', building: '', capacity: 30, room_type: 'lab' });
  const [creatingVenue, setCreatingVenue] = useState(false);

  const handleCreateVenue = async () => {
    if (!venueForm.name) {
      setError("Venue name is required");
      return;
    }
    setCreatingVenue(true);
    try {
      await labCoordinatorAPI.createRoom(venueForm);
      setSuccess("Lab venue created successfully.");
      setVenueForm({ name: '', building: '', capacity: 30, room_type: 'lab' });
      fetchDashboard();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Failed to create venue.");
    } finally {
      setCreatingVenue(false);
    }
  };

  const handleDeleteVenue = async (id: number) => {
    if (!window.confirm("Are you sure you want to delete this lab venue?")) return;
    try {
      await labCoordinatorAPI.deleteRoom(id);
      setSuccess("Lab venue deleted.");
      fetchDashboard();
    } catch (e: any) {
      setError(e.response?.data?.detail || "Failed to delete venue.");
    }
  };

  const saveDepartmentRoomPool = async () => {
    setSavingRoomPool(true);
    setError('');
    try {
      const result = await labCoordinatorAPI.setRoomAllocations(departmentRoomIds);
      setDepartmentRoomIds(result.room_ids || []);
      setSmartForm((current) => ({
        ...current,
        room_ids: current.room_ids.filter((roomId) => (result.room_ids || []).includes(roomId)),
      }));
      setSuccess('Department lab-room pool saved. The scheduler will only use these rooms.');
      await fetchDashboard();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Could not save the department lab-room pool.');
    } finally {
      setSavingRoomPool(false);
    }
  };

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [sumRes, sessRes, roomRes, allocationRes, subgroupRes, mainGroupRes, streamRes, courseRes] = await Promise.allSettled([
        labCoordinatorAPI.getSummary(),
        labCoordinatorAPI.getSessions(),
        labCoordinatorAPI.getRooms(),
        labCoordinatorAPI.getRoomAllocations(),
        labCoordinatorAPI.getGroups(),
        groupsAPI.getByTier('main'),
        groupsAPI.getByTier('stream'),
        coursesAPI.getAll(),
      ]);

      const failures: string[] = [];

      if (sumRes.status === 'fulfilled') setSummary(sumRes.value);
      else failures.push('summary');

      if (sessRes.status === 'fulfilled') setSessions(toList<any>(sessRes.value));
      else failures.push('sessions');

      if (roomRes.status === 'fulfilled') setRooms(toList<any>(roomRes.value));
      else failures.push('rooms');

      if (allocationRes.status === 'fulfilled') {
        const allocated = allocationRes.value?.room_ids || [];
        setDepartmentRoomIds(allocated);
        setSmartForm((current) => current.room_ids.length > 0 ? current : { ...current, room_ids: allocated });
      } else failures.push('room pool');

      if (subgroupRes.status === 'fulfilled') setLabSubgroups(toList<any>(subgroupRes.value));
      else failures.push('subgroups');

      if (mainGroupRes.status === 'fulfilled' || streamRes.status === 'fulfilled') {
        const cohorts = mainGroupRes.status === 'fulfilled' ? toList<any>(mainGroupRes.value) : [];
        const streams = streamRes.status === 'fulfilled' ? toList<any>(streamRes.value) : [];
        setMainGroups([...cohorts, ...streams].sort((a, b) => a.name.localeCompare(b.name)));
      } else failures.push('cohorts and streams');

      if (courseRes.status === 'fulfilled') {
        setLabCourses(toList<any>(courseRes.value).filter(isLabCourse));
      } else {
        failures.push('courses');
      }

      if (failures.length > 0) {
        setError(`Some lab scheduling data could not be loaded (${failures.join(', ')}). The page is still usable with the data that did load.`);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  useEffect(() => {
    if (!selectedGroupId && mainGroups.length > 0) {
      setSelectedGroupId(mainGroups[0].id);
    }
  }, [mainGroups, selectedGroupId]);

  useEffect(() => {
    if (!selectedGroupId) {
      setGroupCourseMap(null);
      setGroupAssignedCourseIds([]);
      setSelectedCourseId(null);
      setGroupLoading(false);
      return;
    }

    let active = true;
    const loadGroupPlan = async () => {
      setGroupLoading(true);
      try {
        const [mapRes, assignedRes] = await Promise.allSettled([
          groupsAPI.getCourseMap(selectedGroupId),
          groupsAPI.getAssignedCourses(selectedGroupId),
        ]);
        if (!active) return;
        if (mapRes.status === 'fulfilled') {
          setGroupCourseMap(mapRes.value);
        } else {
          setGroupCourseMap(null);
        }

        if (assignedRes.status === 'fulfilled') {
          setGroupAssignedCourseIds(toList<any>(assignedRes.value).map((course) => course.id));
        } else if (mapRes.status === 'fulfilled') {
          setGroupAssignedCourseIds(toList<number>(mapRes.value?.selected_course_ids ?? []));
        } else {
          setGroupAssignedCourseIds([]);
        }
      } catch {
        if (!active) return;
        setGroupCourseMap(null);
        setGroupAssignedCourseIds([]);
      } finally {
        if (active) setGroupLoading(false);
      }
    };

    void loadGroupPlan();
    return () => {
      active = false;
    };
  }, [selectedGroupId]);

  const selectedGroup = useMemo(
    () => mainGroups.find((group) => group.id === selectedGroupId) || null,
    [mainGroups, selectedGroupId],
  );

  const selectedGroupSubgroups = useMemo(
    () => labSubgroups.filter((group) => group.parent_group_id === selectedGroupId),
    [labSubgroups, selectedGroupId],
  );

  const departmentRooms = useMemo(
    () => rooms.filter((room) => departmentRoomIds.includes(room.id)),
    [rooms, departmentRoomIds],
  );

  const selectedGroupCourseIds = useMemo(
    () => new Set<number>(groupAssignedCourseIds.length > 0 ? groupAssignedCourseIds : (groupCourseMap?.selected_course_ids ?? [])),
    [groupAssignedCourseIds, groupCourseMap],
  );

  const selectedGroupLabCourses = useMemo(
    () => labCourses.filter((course) => selectedGroupCourseIds.has(course.id)),
    [labCourses, selectedGroupCourseIds],
  );

  const currentGroupSessions = useMemo(
    () => sessions.filter((session) => session.group_id === selectedGroupId),
    [sessions, selectedGroupId],
  );

  const selectedCourseSessions = useMemo(
    () => currentGroupSessions.filter((session) => session.course_id === selectedCourseId),
    [currentGroupSessions, selectedCourseId],
  );

  const scheduledCourseIds = useMemo(
    () => new Set<number>(currentGroupSessions.map((session) => session.course_id)),
    [currentGroupSessions],
  );

  const completedCourseCount = selectedGroupLabCourses.filter((course) => scheduledCourseIds.has(course.id)).length;
  const nextUnscheduledCourse = selectedGroupLabCourses.find((course) => !scheduledCourseIds.has(course.id)) || null;

  useEffect(() => {
    if (!selectedGroupLabCourses.length) {
      setSelectedCourseId(null);
      return;
    }

    if (!selectedCourseId || !selectedGroupLabCourses.some((course) => course.id === selectedCourseId)) {
      setSelectedCourseId((nextUnscheduledCourse || selectedGroupLabCourses[0]).id);
    }
  }, [selectedGroupLabCourses, selectedCourseId, nextUnscheduledCourse]);

  const handleSmartSchedule = async () => {
    if (!selectedGroupId || !selectedCourseId || smartForm.room_ids.length === 0) {
      setError('Please select a group, course, and at least one room.');
      return;
    }

    if (selectedGroupSubgroups.length === 0) {
      setError('This group has no lab subgroups yet. Create them first.');
      return;
    }

    setSmartGenerating(true);
    setError('');
    
    try {
      const res = await labCoordinatorAPI.smartSchedule({
        course_id: Number(selectedCourseId),
        parent_group_id: Number(selectedGroupId),
        group_ids: selectedGroupSubgroups.map((group) => group.id),
        room_ids: smartForm.room_ids,
        duration_minutes: smartForm.duration_minutes,
        frequency_weeks: smartForm.frequency_weeks,
        subgroups_per_session: smartForm.subgroups_per_session,
        session_type: smartForm.session_type,
        preferred_days: smartForm.preferred_days,
        start_hour: smartForm.start_hour,
        end_hour: smartForm.end_hour,
      });

      setSuccess(`${res.scheduled} draft lab session(s) are ready to review. They will not reach students until you publish them.`);
      setSmartOpen(false);
      await fetchDashboard();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to run smart scheduler');
    } finally {
      setSmartGenerating(false);
    }
  };

  const handleDeleteSession = async (id: number) => {
    if (!window.confirm('Delete this lab session?')) return;
    try {
      await labCoordinatorAPI.deleteSession(id);
      setSuccess('Session deleted.');
      fetchDashboard();
    } catch (e) {
      setError('Failed to delete session.');
    }
  };

  const handlePublishSession = async (id: number) => {
    setPublicationActionId(id);
    setError('');
    try {
      await labCoordinatorAPI.publishSession(id);
      setSuccess('Lab session published. It is now available in the student timetable.');
      await fetchDashboard();
    } catch (e: any) {
      const detail = e.response?.data?.detail;
      setError(typeof detail === 'object' ? (detail.message || 'Resolve the listed conflicts before publishing.') : (detail || 'Could not publish this lab session.'));
    } finally {
      setPublicationActionId(null);
    }
  };

  const handleUnpublishSession = async (id: number) => {
    if (!window.confirm('Withdraw this lab session from student timetables? It will remain available as a draft for editing.')) return;
    setPublicationActionId(id);
    setError('');
    try {
      await labCoordinatorAPI.unpublishSession(id);
      setSuccess('Lab session withdrawn from publication and returned to drafts.');
      await fetchDashboard();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Could not withdraw this lab session.');
    } finally {
      setPublicationActionId(null);
    }
  };

  const moveToNextGroup = () => {
    if (mainGroups.length === 0) return;
    const index = mainGroups.findIndex((group) => group.id === selectedGroupId);
    const next = mainGroups[(index + 1) % mainGroups.length];
    setSelectedGroupId(next?.id ?? null);
  };

  return (
    <Container maxWidth={false} sx={{ mt: 3, mb: 4 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Box>
          <Typography variant="h4" fontWeight="600" color="primary.main">
            Lab Scheduling Studio
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Build lab sessions safely as drafts, test them against lectures, then publish only the sessions that are ready for students.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          {activeTab === 1 && (
            <Button
              variant="contained"
              color="success"
              startIcon={<AutoAwesomeIcon />}
              onClick={() => setSmartOpen(true)}
              disabled={!selectedGroupId || !selectedCourseId || selectedGroupSubgroups.length === 0}
              sx={{ textTransform: 'none' }}
            >
              Schedule Selected Course
            </Button>
          )}
        </Box>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>{success}</Alert>}

      <Paper sx={{ mb: 3, borderRadius: 2 }}>
        <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)} variant="fullWidth">
          <Tab icon={<GroupIcon />} label="1. Subgroups & Cohorts" />
          <Tab icon={<EventIcon />} label="2. Lab Schedule" />
          <Tab icon={<ScienceIcon />} label="3. Lab Venues" />
        </Tabs>
      </Paper>

      {activeTab === 0 && <LabGroupsPage isEmbedded />}

      {activeTab === 1 && (
        <Box>
          <Grid container spacing={3} sx={{ mb: 4 }}>
            <Grid item xs={12} sm={3}>
              <Card elevation={2}>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="body2" color="text.secondary" gutterBottom>Total Sessions</Typography>
                      <Typography variant="h4" fontWeight="600">{summary.total_sessions}</Typography>
                    </Box>
                    <EventIcon sx={{ fontSize: 40, color: 'primary.main', opacity: 0.6 }} />
                  </Box>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Card elevation={2}>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="body2" color="text.secondary" gutterBottom>Conflicted Sessions</Typography>
                      <Typography variant="h4" fontWeight="600" color={summary.conflicted_sessions > 0 ? 'error.main' : 'success.main'}>
                        {summary.conflicted_sessions}
                      </Typography>
                    </Box>
                    <WarningIcon sx={{ fontSize: 40, color: summary.conflicted_sessions > 0 ? 'error.main' : 'success.main', opacity: 0.6 }} />
                  </Box>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Card elevation={2}>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="body2" color="text.secondary" gutterBottom>Lab Venues</Typography>
                      <Typography variant="h4" fontWeight="600">{summary.lab_rooms}</Typography>
                    </Box>
                    <ScienceIcon sx={{ fontSize: 40, color: 'secondary.main', opacity: 0.6 }} />
                  </Box>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Card elevation={2}>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="body2" color="text.secondary" gutterBottom>Active Subgroups</Typography>
                      <Typography variant="h4" fontWeight="600">{summary.lab_groups}</Typography>
                    </Box>
                    <GroupIcon sx={{ fontSize: 40, color: 'warning.main', opacity: 0.6 }} />
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
              <CircularProgress />
            </Box>
          ) : (
            <Grid container spacing={3}>
              <Grid item xs={12} lg={4}>
                <Card elevation={2} sx={{ mb: 3 }}>
                  <CardContent>
                    <Stack spacing={2}>
                      <Box>
                        <Typography variant="h6" fontWeight={700}>
                          Select a main group
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          We keep the work focused on one group until every lab course in that group is slotted.
                        </Typography>
                      </Box>

                      <FormControl fullWidth>
                        <InputLabel>Main Group</InputLabel>
                        <Select
                          value={selectedGroupId ?? ''}
                          label="Main Group"
                          onChange={(e) => setSelectedGroupId(Number(e.target.value))}
                        >
                          {mainGroups.map((group) => (
                            <MenuItem key={group.id} value={group.id}>
                              {group.name}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>

                      {selectedGroup && (
                        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
                          <Chip size="small" label={`Level ${selectedGroup.level}`} variant="outlined" />
                          <Chip size="small" label={selectedGroup.department_name || selectedGroup.department_id || 'Department'} variant="outlined" />
                          <Chip size="small" label={`${completedCourseCount}/${selectedGroupLabCourses.length} lab courses scheduled`} color="primary" />
                        </Stack>
                      )}

                      {groupLoading ? (
                        <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                          <CircularProgress size={24} />
                        </Box>
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          {groupCourseMap?.note || 'Lab courses for the selected group will appear here.'}
                        </Typography>
                      )}

                      <Stack direction="row" spacing={1}>
                        <Button
                          variant="contained"
                          onClick={() => {
                            if (nextUnscheduledCourse) {
                              setSelectedCourseId(nextUnscheduledCourse.id);
                            }
                            setSmartOpen(true);
                          }}
                          disabled={!selectedGroupId || !selectedCourseId || selectedGroupSubgroups.length === 0}
                          sx={{ textTransform: 'none' }}
                        >
                          Schedule next course
                        </Button>
                        <Button
                          variant="outlined"
                          onClick={moveToNextGroup}
                          disabled={mainGroups.length < 2}
                          sx={{ textTransform: 'none' }}
                        >
                          Next group
                        </Button>
                      </Stack>
                    </Stack>
                  </CardContent>
                </Card>

                <Card elevation={1}>
                  <CardContent>
                    <Typography variant="subtitle1" fontWeight={700} gutterBottom>
                      Rotating subgroups
                    </Typography>
                    {selectedGroupSubgroups.length === 0 ? (
                      <Alert severity="info" sx={{ borderRadius: 2 }}>
                        This group has no lab subgroups yet. Create them first, then the rotation slot can be reused across them.
                      </Alert>
                    ) : (
                      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
                        {selectedGroupSubgroups.map((group) => (
                          <Chip key={group.id} label={group.name} variant="outlined" />
                        ))}
                      </Stack>
                    )}
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} lg={8}>
                <Card elevation={2} sx={{ mb: 3 }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                      <Box>
                        <Typography variant="h6" fontWeight={700}>
                          Course queue
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Only courses marked as lab-bearing appear here.
                        </Typography>
                      </Box>
                      <Chip label={`${selectedGroupLabCourses.length} lab courses`} color="primary" variant="outlined" />
                    </Box>

                    {!selectedGroupId ? (
                      <Alert severity="info">Choose a main group to start scheduling.</Alert>
                    ) : selectedGroupLabCourses.length === 0 ? (
                      <Alert severity="info">
                        This group has no lab-bearing courses assigned yet.
                      </Alert>
                    ) : (
                      <Grid container spacing={2}>
                        {selectedGroupLabCourses.map((course) => {
                          const scheduled = scheduledCourseIds.has(course.id);
                          const sessionCount = sessions.filter(
                            (session) => session.group_id === selectedGroupId && session.course_id === course.id,
                          ).length;
                          const active = selectedCourseId === course.id;
                          return (
                            <Grid item xs={12} md={6} key={course.id}>
                              <Card
                                variant="outlined"
                                sx={{
                                  borderColor: active ? 'primary.main' : scheduled ? 'success.main' : 'divider',
                                  bgcolor: active ? 'rgba(25,118,210,0.04)' : 'background.paper',
                                }}
                              >
                                <CardContent>
                                  <Stack spacing={1.5}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
                                      <Box>
                                        <Typography variant="subtitle1" fontWeight={700}>
                                          {course.code}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                          {course.name}
                                        </Typography>
                                      </Box>
                                      <Chip
                                        size="small"
                                        label={scheduled ? 'Scheduled' : 'Pending'}
                                        color={scheduled ? 'success' : 'warning'}
                                        variant="outlined"
                                      />
                                    </Box>

                                    <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
                                      <Chip size="small" label={`${sessionCount} session${sessionCount === 1 ? '' : 's'}`} variant="outlined" />
                                      <Chip size="small" label={`P: ${course.practical_hours ?? 0}`} variant="outlined" />
                                    </Stack>

                                    <Stack direction="row" spacing={1}>
                                      <Button
                                        size="small"
                                        variant="contained"
                                        onClick={() => {
                                          setSelectedCourseId(course.id);
                                          setSmartOpen(true);
                                        }}
                                        sx={{ textTransform: 'none' }}
                                      >
                                        {scheduled ? 'Review slot' : 'Schedule slot'}
                                      </Button>
                                      <Button
                                        size="small"
                                        variant="text"
                                        onClick={() => setSelectedCourseId(course.id)}
                                        sx={{ textTransform: 'none' }}
                                      >
                                        Focus
                                      </Button>
                                    </Stack>
                                  </Stack>
                                </CardContent>
                              </Card>
                            </Grid>
                          );
                        })}
                      </Grid>
                    )}
                  </CardContent>
                </Card>

                <Card elevation={2}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                      <Box>
                        <Typography variant="h6" fontWeight={700}>
                          Review & publish lab sessions
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Drafts are private. Publishing is blocked until the session is conflict-free.
                        </Typography>
                      </Box>
                      <Chip label={`${currentGroupSessions.length} sessions`} variant="outlined" />
                    </Box>

                    {currentGroupSessions.length === 0 ? (
                      <Alert severity="info">
                        No lab sessions have been created for this group yet.
                      </Alert>
                    ) : (
                      <Grid container spacing={2}>
                        {currentGroupSessions.map((session) => {
                          const rotConfig = session.rotation_configuration;
                          const cycleLen = session.rotation_cycle_length || 1;
                          const isPublished = ['published', 'scheduled'].includes(String(session.status || '').toLowerCase());
                          const isBusy = publicationActionId === session.id;
                          return (
                            <Grid item xs={12} md={6} key={session.id}>
                              <Card
                                variant="outlined"
                                sx={{
                                  borderRadius: 3,
                                  borderColor: session.has_conflict ? '#f87171' : 'rgba(0,0,0,0.1)',
                                  borderLeft: `4px solid ${session.has_conflict ? '#ef4444' : '#10b981'}`,
                                  height: '100%',
                                }}
                              >
                                <CardContent>
                                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                                    <Typography variant="subtitle1" fontWeight="bold" color="primary">
                                      {session.course_code}
                                    </Typography>
                                    <Stack direction="row" spacing={0.75}>
                                      <Chip size="small" label={isPublished ? 'Published' : 'Draft'} color={isPublished ? 'success' : 'default'} sx={{ fontWeight: 700 }} />
                                      <Chip size="small" label={`${session.day_name} ${session.start_time}-${session.end_time}`} sx={{ fontWeight: 'bold' }} />
                                    </Stack>
                                  </Box>
                                  <Typography variant="body2" sx={{ mb: 0.5 }}>
                                    <strong>Master Slot:</strong> {session.group_name} ({session.group_size} students)
                                  </Typography>
                                  <Typography variant="body2" sx={{ mb: 1.5 }}>
                                    <strong>Venue:</strong> {session.room_name} ({session.room_building})
                                  </Typography>

                                  <Box sx={{ display: 'flex', gap: 1, mb: 1, flexWrap: 'wrap' }}>
                                    <Chip size="small" label={`${session.duration_minutes}m`} variant="outlined" />
                                    <Chip size="small" label={`Cycle: ${cycleLen} wks`} color="info" variant="outlined" />
                                    <Chip size="small" label={session.session_type} color="secondary" variant="outlined" />
                                  </Box>

                                  {rotConfig && Object.keys(rotConfig).length > 0 && (
                                    <Box sx={{ mt: 1.5, p: 1.5, bgcolor: 'rgba(99,102,241,0.06)', borderRadius: 2, border: '1px solid rgba(99,102,241,0.15)' }}>
                                      <Typography variant="caption" fontWeight="bold" color="primary" sx={{ mb: 0.5, display: 'block' }}>
                                        Rotation schedule
                                      </Typography>
                                      {Object.entries(rotConfig).map(([weekPos, subgroupIds]: [string, any]) => {
                                        const subNames = (subgroupIds as number[]).map((sgId) => {
                                          const sg = labSubgroups.find((group) => group.id === sgId);
                                          return sg ? sg.name : `#${sgId}`;
                                        });
                                        return (
                                          <Typography key={weekPos} variant="caption" display="block" color="text.secondary" sx={{ pl: 1 }}>
                                            Week {weekPos}: {subNames.join(', ')}
                                          </Typography>
                                        );
                                      })}
                                    </Box>
                                  )}

                                  {session.has_conflict && (
                                    <Box sx={{ mt: 2, p: 1.5, bgcolor: '#fef2f2', borderRadius: 2, border: '1px solid #fecaca' }}>
                                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                        <WarningIcon color="error" fontSize="small" />
                                        <Typography variant="caption" color="error" fontWeight="bold">Schedule Conflict Detected</Typography>
                                      </Box>
                                      {session.conflict_detail?.map((c: any, i: number) => (
                                        <Typography key={i} variant="caption" display="block" color="text.secondary">
                                          • {c.description}
                                        </Typography>
                                      ))}
                                    </Box>
                                  )}

                                  <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                                    {isPublished ? (
                                      <Button
                                        size="small"
                                        variant="outlined"
                                        color="warning"
                                        startIcon={isBusy ? <CircularProgress size={14} /> : <UnpublishedIcon />}
                                        onClick={() => void handleUnpublishSession(session.id)}
                                        disabled={isBusy}
                                        sx={{ textTransform: 'none' }}
                                      >
                                        Withdraw
                                      </Button>
                                    ) : (
                                      <Button
                                        size="small"
                                        variant="contained"
                                        color="success"
                                        startIcon={isBusy ? <CircularProgress size={14} color="inherit" /> : <PublishIcon />}
                                        onClick={() => void handlePublishSession(session.id)}
                                        disabled={isBusy || session.has_conflict}
                                        sx={{ textTransform: 'none' }}
                                      >
                                        Publish
                                      </Button>
                                    )}
                                    <Tooltip title={isPublished ? 'Withdraw before permanently deleting' : 'Delete draft'}>
                                      <span>
                                        <IconButton color="error" size="small" onClick={() => handleDeleteSession(session.id)} disabled={isPublished || isBusy}>
                                          <DeleteIcon fontSize="small" />
                                        </IconButton>
                                      </span>
                                    </Tooltip>
                                  </Box>
                                </CardContent>
                              </Card>
                            </Grid>
                          );
                        })}
                      </Grid>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          )}
        </Box>
      )}

      {activeTab === 2 && (
        <Box>
          <Grid container spacing={4}>
            <Grid item xs={12} md={4}>
              <Card elevation={2}>
                <CardContent>
                  <Typography variant="h6" gutterBottom color="primary.main">
                    Add New Lab Venue
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    Venues created here are owned by your department but can be scheduled for cross-department cohorts if needed.
                  </Typography>
                  <TextField
                    fullWidth
                    label="Venue Name"
                    placeholder="e.g. Computer Lab 1"
                    value={venueForm.name}
                    onChange={(e) => setVenueForm((p) => ({ ...p, name: e.target.value }))}
                    sx={{ mb: 2 }}
                  />
                  <TextField
                    fullWidth
                    label="Building (Optional)"
                    placeholder="e.g. Engineering Block A"
                    value={venueForm.building}
                    onChange={(e) => setVenueForm((p) => ({ ...p, building: e.target.value }))}
                    sx={{ mb: 2 }}
                  />
                  <TextField
                    fullWidth
                    label="Capacity"
                    type="number"
                    value={venueForm.capacity}
                    onChange={(e) => setVenueForm((p) => ({ ...p, capacity: Number(e.target.value) }))}
                    inputProps={{ min: 1 }}
                    sx={{ mb: 2 }}
                  />
                  <Button
                    variant="contained"
                    color="primary"
                    fullWidth
                    onClick={handleCreateVenue}
                    disabled={creatingVenue || !venueForm.name}
                    startIcon={creatingVenue ? <CircularProgress size={16} /> : <AddIcon />}
                  >
                    {creatingVenue ? 'Creating...' : 'Create Venue'}
                  </Button>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={8}>
              <Card elevation={2} sx={{ mb: 3, border: '1px solid', borderColor: 'primary.light' }}>
                <CardContent>
                  <Typography variant="h6" color="primary.main" gutterBottom>
                    Department Lab-Room Pool
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Choose the rooms your department plans to use. This is not an all-day reservation: every proposed slot is still checked against all university room bookings before it is saved.
                  </Typography>
                  <FormControl fullWidth sx={{ mb: 2 }}>
                    <InputLabel>Rooms available to this department</InputLabel>
                    <Select
                      multiple
                      value={departmentRoomIds}
                      label="Rooms available to this department"
                      onChange={(e) => setDepartmentRoomIds(e.target.value as number[])}
                      renderValue={(selected) => (
                        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                          {selected.map((roomId) => {
                            const room = rooms.find((entry) => entry.id === roomId);
                            return <Chip key={roomId} size="small" label={room?.name || roomId} />;
                          })}
                        </Box>
                      )}
                    >
                      {rooms.map((room) => (
                        <MenuItem key={room.id} value={room.id}>
                          {room.name} — {room.building || 'Building not set'} (capacity {room.capacity})
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <Button
                    variant="contained"
                    onClick={saveDepartmentRoomPool}
                    disabled={savingRoomPool}
                    sx={{ textTransform: 'none' }}
                  >
                    {savingRoomPool ? 'Saving room pool…' : 'Save department room pool'}
                  </Button>
                </CardContent>
              </Card>
              <Typography variant="h6" gutterBottom color="text.primary">
                Available Lab Venues ({rooms.length})
              </Typography>
              <Grid container spacing={2}>
                {rooms.map((room) => (
                  <Grid item xs={12} sm={6} key={room.id}>
                    <Card elevation={1} sx={{ '&:hover': { elevation: 3 } }}>
                      <CardContent>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <Box>
                            <Typography variant="h6">{room.name}</Typography>
                            {room.building && <Typography variant="body2" color="text.secondary">{room.building}</Typography>}
                            <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
                              <Chip size="small" label={`Cap: ${room.capacity}`} color="primary" variant="outlined" />
                              <Chip size="small" label={room.room_type} variant="outlined" />
                              {departmentRoomIds.includes(room.id) && <Chip size="small" label="In your pool" color="success" />}
                            </Box>
                          </Box>
                          {room.owned_by_department && (
                            <IconButton color="error" size="small" onClick={() => handleDeleteVenue(room.id)}>
                              <DeleteIcon />
                            </IconButton>
                          )}
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </Grid>
          </Grid>
        </Box>
      )}

      <Dialog open={smartOpen} onClose={() => setSmartOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AutoAwesomeIcon color="success" />
          Smart Lab Scheduler
        </DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            This schedules the currently selected course for the selected group, then reuses that slot as the group&apos;s subgroups rotate through it.
          </Typography>

          <Card variant="outlined" sx={{ mb: 2 }}>
            <CardContent>
              <Typography variant="subtitle2" fontWeight={700} gutterBottom>
                Selected work item
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Group: {selectedGroup?.name || 'No group selected'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Course: {selectedGroupLabCourses.find((course) => course.id === selectedCourseId)?.code || 'No course selected'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Subgroups: {selectedGroupSubgroups.length || 0}
              </Typography>
            </CardContent>
          </Card>

          {selectedCourseSessions.length > 0 && (
            <Alert severity="info" sx={{ mb: 2 }}>
              This course already has {selectedCourseSessions.length} scheduled session(s) for the selected group.
            </Alert>
          )}

          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Lab Venues (Select multiple)</InputLabel>
            <Select
              multiple
              value={smartForm.room_ids}
              label="Lab Venues (Select multiple)"
              onChange={(e) => setSmartForm((p) => ({ ...p, room_ids: e.target.value as number[] }))}
              renderValue={(selected) => (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {selected.map((value) => {
                    const room = departmentRooms.find((entry) => entry.id === value);
                    return <Chip key={value} label={room?.name || value} size="small" />;
                  })}
                </Box>
              )}
            >
              {departmentRooms.map((room) => (
                <MenuItem key={room.id} value={room.id}>
                  {room.name} (Cap: {room.capacity})
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {departmentRooms.length === 0 && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Select and save at least one room in “Lab Venues” before scheduling.
            </Alert>
          )}

          <Grid container spacing={2}>
            <Grid item xs={4}>
              <FormControl fullWidth>
                <InputLabel>Duration (Minutes)</InputLabel>
                <Select
                  value={smartForm.duration_minutes}
                  label="Duration (Minutes)"
                  onChange={(e) => setSmartForm((p) => ({ ...p, duration_minutes: Number(e.target.value) }))}
                >
                  <MenuItem value={60}>60 (1 hour)</MenuItem>
                  <MenuItem value={120}>120 (2 hours)</MenuItem>
                  <MenuItem value={180}>180 (3 hours)</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={4}>
              <FormControl fullWidth>
                <InputLabel>Subgroups / Session</InputLabel>
                <Select
                  value={smartForm.subgroups_per_session}
                  label="Subgroups / Session"
                  onChange={(e) => setSmartForm((p) => ({ ...p, subgroups_per_session: Number(e.target.value) }))}
                >
                  <MenuItem value={1}>1 Subgroup (Rotate one at a time)</MenuItem>
                  <MenuItem value={2}>2 Subgroups</MenuItem>
                  <MenuItem value={3}>3 Subgroups</MenuItem>
                  <MenuItem value={4}>4 Subgroups</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={4}>
              <FormControl fullWidth>
                <InputLabel>Session Type</InputLabel>
                <Select
                  value={smartForm.session_type}
                  label="Session Type"
                  onChange={(e) => setSmartForm((p) => ({ ...p, session_type: e.target.value as string }))}
                >
                  <MenuItem value="lab">Lab Group</MenuItem>
                  <MenuItem value="tutorial">Tutorial</MenuItem>
                  <MenuItem value="drawing">Drawing</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>

          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Preferred days</InputLabel>
                <Select
                  multiple
                  value={smartForm.preferred_days}
                  label="Preferred days"
                  onChange={(e) => setSmartForm((p) => ({ ...p, preferred_days: e.target.value as number[] }))}
                  renderValue={(selected) => ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                    .filter((_, index) => selected.includes(index)).join(', ')}
                >
                  {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].map((day, index) => (
                    <MenuItem key={day} value={index}>{day}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6} md={3}>
              <FormControl fullWidth>
                <InputLabel>Earliest start</InputLabel>
                <Select
                  value={smartForm.start_hour}
                  label="Earliest start"
                  onChange={(e) => setSmartForm((p) => ({ ...p, start_hour: Number(e.target.value) }))}
                >
                  {[7, 8, 9, 10, 11, 12].map((hour) => <MenuItem key={hour} value={hour}>{String(hour).padStart(2, '0')}:00</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6} md={3}>
              <FormControl fullWidth>
                <InputLabel>Latest end</InputLabel>
                <Select
                  value={smartForm.end_hour}
                  label="Latest end"
                  onChange={(e) => setSmartForm((p) => ({ ...p, end_hour: Number(e.target.value) }))}
                >
                  {[13, 14, 15, 16, 17, 18, 19].map((hour) => <MenuItem key={hour} value={hour}>{String(hour).padStart(2, '0')}:00</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
          </Grid>
          {smartForm.end_hour <= smartForm.start_hour && (
            <Alert severity="error" sx={{ mt: 2 }}>Latest end must be after earliest start.</Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSmartOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            color="success"
            onClick={handleSmartSchedule}
            disabled={smartGenerating || departmentRooms.length === 0 || smartForm.preferred_days.length === 0 || smartForm.end_hour <= smartForm.start_hour}
            startIcon={smartGenerating ? <CircularProgress size={16} /> : <AutoAwesomeIcon />}
          >
            {smartGenerating ? 'Scheduling...' : 'Save Slot'}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default LabSchedulingPage;
