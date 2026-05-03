import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  InputAdornment,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Stack,
  TextField,
  Typography,
  CircularProgress,
} from '@mui/material';
import { Search as SearchIcon, PlaylistAddCheck as PlaylistAddCheckIcon } from '@mui/icons-material';
import { groupsAPI } from '../api';

interface CourseOption {
  id: number;
  code: string;
  name: string;
  level: number;
  department_id: number;
  department_name?: string | null;
  department_code?: string | null;
  course_type: string;
  source_kind: 'own' | 'general' | 'shared';
  owner_department_id: number;
  owner_department_name?: string | null;
  owner_department_code?: string | null;
  editable: boolean;
  control_scope: 'owner' | 'read_only';
  read_only_reason?: string | null;
  inherited_from_parent: boolean;
  selected: boolean;
  recommended: boolean;
}

interface GroupCourseMap {
  group_id: number;
  group_name: string;
  group_level: number;
  group_department_id: number;
  group_department_name?: string | null;
  selected_course_ids: number[];
  recommended_course_ids: number[];
  available_courses: CourseOption[];
  note: string;
}

interface GroupCourseManagerProps {
  open: boolean;
  onClose: () => void;
  groupId: number;
  groupName: string;
  groupCode?: string;
  groupType?: string;
  parentGroupName?: string;
  groupLevel: number;
  groupDepartmentId: number;
}

export const GroupCourseManager: React.FC<GroupCourseManagerProps> = ({
  open,
  onClose,
  groupId,
  groupName,
  groupType,
  parentGroupName,
}) => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [mapping, setMapping] = useState<GroupCourseMap | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      void fetchInitData();
    }
  }, [open, groupId]);

  const fetchInitData = async () => {
    setLoading(true);
    setError('');
    try {
      const data: GroupCourseMap = await groupsAPI.getCourseMap(groupId);
      setMapping(data);
      setSelectedIds(data.selected_course_ids);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load group course mapping.');
    } finally {
      setLoading(false);
    }
  };

  const toggleCourse = (courseId: number) => {
    const target = availableCourses.find((course) => course.id === courseId);
    if (!target || !target.editable) {
      return;
    }
    setSelectedIds((prev) => (
      prev.includes(courseId)
        ? prev.filter((id) => id !== courseId)
        : [...prev, courseId]
    ));
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      await groupsAPI.assignCourses(groupId, selectedIds);
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update course assignments.');
      setSaving(false);
    }
  };

  const availableCourses = mapping?.available_courses ?? [];
  const selectedLookup = useMemo(() => new Set(selectedIds), [selectedIds]);
  const recommendedLookup = useMemo(() => new Set(mapping?.recommended_course_ids ?? []), [mapping]);
  const normalizedSearch = searchQuery.trim().toLowerCase();

  const filteredCourses = useMemo(
    () => availableCourses.filter((course) => (
      !normalizedSearch
      || course.code.toLowerCase().includes(normalizedSearch)
      || course.name.toLowerCase().includes(normalizedSearch)
      || (course.department_code || '').toLowerCase().includes(normalizedSearch)
    )),
    [availableCourses, normalizedSearch],
  );

  const groupedCourses = useMemo(() => {
    const local = filteredCourses.filter((course) => course.editable);
    const pulled = filteredCourses.filter((course) => !course.editable);
    return { local, pulled };
  }, [filteredCourses, recommendedLookup]);

  const renderCourseList = (courses: CourseOption[], emptyLabel: string) => {
    if (courses.length === 0) {
      return (
        <Typography variant="body2" color="text.secondary" sx={{ px: 2, py: 1.5 }}>
          {emptyLabel}
        </Typography>
      );
    }

    return (
      <List disablePadding>
        {courses.map((course) => {
          const isSelected = selectedLookup.has(course.id) || course.inherited_from_parent;
          return (
            <ListItem
              key={course.id}
              dense
              onClick={() => toggleCourse(course.id)}
              sx={{
                borderBottom: '1px solid rgba(0,0,0,0.05)',
                bgcolor: isSelected ? 'rgba(25, 118, 210, 0.05)' : 'transparent',
                cursor: 'pointer',
              }}
            >
              <ListItemIcon sx={{ minWidth: 40 }}>
                <Checkbox
                  edge="start"
                  checked={isSelected}
                  disabled={!course.editable}
                  tabIndex={-1}
                  disableRipple
                  color="primary"
                />
              </ListItemIcon>
              <ListItemText
                primary={(
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                    <Typography variant="body2" fontWeight={700}>
                      {course.code}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {course.name}
                    </Typography>
                    {course.recommended && (
                      <Chip size="small" color="success" variant="outlined" label="Auto" />
                    )}
                    {course.control_scope === 'read_only' && (
                      <Chip size="small" color="secondary" variant="outlined" label="Pulled In" />
                    )}
                    {course.inherited_from_parent && (
                      <Chip size="small" color="primary" variant="outlined" label="Inherited" />
                    )}
                  </Stack>
                )}
                secondary={(
                  <Stack direction="row" spacing={1} sx={{ mt: 0.5 }} flexWrap="wrap">
                    <Chip
                      size="small"
                      variant="outlined"
                      label={course.department_code || course.department_name || 'Dept'}
                      sx={{ height: 20, fontSize: '0.65rem' }}
                    />
                    <Chip
                      size="small"
                      variant="outlined"
                      label={course.course_type.replace(/_/g, ' ')}
                      sx={{ height: 20, fontSize: '0.65rem' }}
                    />
                    {course.control_scope === 'read_only' && (
                      <Chip
                        size="small"
                        variant="outlined"
                        color="secondary"
                        label={`Owner ${course.owner_department_code || course.owner_department_name || 'Dept'}`}
                        sx={{ height: 20, fontSize: '0.65rem' }}
                      />
                    )}
                  </Stack>
                )}
              />
              {!course.editable && course.read_only_reason && (
                <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                  {course.read_only_reason}
                </Typography>
              )}
            </ListItem>
          );
        })}
      </List>
    );
  };

  return (
    <Dialog open={open} onClose={!saving ? onClose : undefined} maxWidth="md" fullWidth>
      <DialogTitle sx={{ pb: 1 }}>
        <Typography variant="h6" fontWeight="bold">
          {groupType === 'stream' ? 'Manage Stream Courses' : 'Manage Group Courses'}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {groupType === 'stream'
            ? `This stream starts from ${parentGroupName || 'its parent cohort'} and can then refine course choices.`
            : `Auto-mapped same-level courses are preselected for ${groupName}. You can keep them or refine them here.`}
        </Typography>
      </DialogTitle>

      <DialogContent sx={{ minHeight: '460px', display: 'flex', flexDirection: 'column' }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {groupType === 'stream' ? (
          <Alert severity="info" sx={{ mb: 2 }}>
            Streams inherit baseline courses from {parentGroupName || 'the parent cohort'}.
            Keep a course selected on multiple sibling streams to keep it common; remove it on one stream to make it stream-specific.
          </Alert>
        ) : (
          <Alert severity="info" sx={{ mb: 2 }}>
            {mapping?.note || 'Courses are suggested automatically by level and department sharing rules.'}
            <Box component="span" sx={{ display: 'block', mt: 0.5 }}>
              Courses owned by other departments are visible here, but they are read only on the group side.
            </Box>
          </Alert>
        )}

        <Box sx={{ display: 'flex', gap: 2, mb: 2, alignItems: 'center' }}>
          <TextField
            fullWidth
            size="small"
            placeholder="Search visible same-level courses..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
          <Button
            variant="outlined"
            color="secondary"
            startIcon={<PlaylistAddCheckIcon />}
            onClick={() => {
              const readOnlySelected = availableCourses
                .filter((course) => !course.editable && selectedLookup.has(course.id))
                .map((course) => course.id);
              const recommendedEditable = availableCourses
                .filter((course) => course.editable && recommendedLookup.has(course.id))
                .map((course) => course.id);
              setSelectedIds([...readOnlySelected, ...recommendedEditable]);
            }}
            disabled={loading}
            sx={{ flexShrink: 0 }}
          >
            Reset To Auto
          </Button>
        </Box>

        <Divider />

        <Box sx={{ flexGrow: 1, overflowY: 'auto', bgcolor: '#fafafa', borderRadius: 1, mt: 1, p: 1.5 }}>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            <Stack spacing={2}>
              <Box>
                <Typography variant="subtitle2" fontWeight={700} sx={{ px: 1, pb: 0.5 }}>
                  Department-Controlled Courses
                </Typography>
                {renderCourseList(groupedCourses.local, 'No department-controlled courses matched this group yet.')}
              </Box>
              <Box>
                <Typography variant="subtitle2" fontWeight={700} sx={{ px: 1, pb: 0.5 }}>
                  Shared In From Other Departments
                </Typography>
                {renderCourseList(groupedCourses.pulled, 'No outside-owned same-level courses are enrolled or shared into this group.')}
              </Box>
            </Stack>
          )}
        </Box>
      </DialogContent>

      <DialogActions sx={{ p: 2, pt: 0, justifyContent: 'space-between' }}>
        <Typography variant="body2" color="text.secondary">
          Selected: {selectedIds.length} course(s)
        </Typography>
        <Box>
          <Button onClick={onClose} disabled={saving} sx={{ mr: 1 }}>
            Cancel
          </Button>
          <Button onClick={() => { void handleSave(); }} variant="contained" disabled={saving || loading}>
            {saving ? 'Saving...' : 'Save Courses'}
          </Button>
        </Box>
      </DialogActions>
    </Dialog>
  );
};

export default GroupCourseManager;
