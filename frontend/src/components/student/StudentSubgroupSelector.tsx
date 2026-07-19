import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Card,
  CardContent,
  Checkbox,
  CircularProgress,
  Divider,
  FormControlLabel,
  Stack,
  TextField,
  Typography,
  Chip,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import { studentPortalApi } from '../../studentPortalApi';

interface LabSubgroupOption {
  id: number;
  name: string;
  display_code?: string | null;
  group_type?: string | null;
  parent_group_id?: number | null;
  course_codes?: string[];
  course_names?: string[];
  rotation_weeks?: string[];
  active_this_week?: boolean;
}

interface StudentSubgroupSelectorProps {
  groupId: number | null;
  value: number[];
  onChange: (next: number[]) => void;
  academicWeek: number;
  onAcademicWeekChange: (week: number) => void;
}

const StudentSubgroupSelector: React.FC<StudentSubgroupSelectorProps> = ({
  groupId,
  value,
  onChange,
  academicWeek,
  onAcademicWeekChange,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [options, setOptions] = useState<LabSubgroupOption[]>([]);

  useEffect(() => {
    let active = true;
    const load = async () => {
      if (!groupId) {
        setOptions([]);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const response = await studentPortalApi.getLabSubgroups(academicWeek);
        if (!active) return;
        setOptions(response.lab_subgroups || []);
      } catch {
        if (active) {
          setError('Unable to load lab subgroup options right now.');
          setOptions([]);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [groupId, academicWeek]);

  const toggle = (id: number) => {
    if (value.includes(id)) {
      onChange(value.filter((entry) => entry !== id));
      return;
    }
    onChange([...value, id]);
  };

  return (
    <Card sx={{ borderRadius: 5 }}>
      <CardContent sx={{ p: 2.5 }}>
        <Stack spacing={1.8}>
          <Box>
            <Typography variant="h6" fontWeight={800}>
              Lab and tutorial groups
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Your stream is already selected. Choose only the lab or tutorial groups you attend; the timetable will add those sessions to your normal stream timetable.
            </Typography>
          </Box>

          <TextField
            type="number"
            label="Current Academic Week"
            value={academicWeek}
            onChange={(event) => onAcademicWeekChange(Math.max(1, Number(event.target.value) || 1))}
            inputProps={{ min: 1, step: 1 }}
            fullWidth
          />

          {error && <Alert severity="warning">{error}</Alert>}

          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
              <CircularProgress size={24} />
            </Box>
          ) : options.length === 0 ? (
            <Alert severity="info" sx={{ borderRadius: 3 }}>
              No rotating lab subgroups are available for this timetable yet.
            </Alert>
          ) : (
            <Stack spacing={1.2}>
              {options.map((option, index) => {
                const checked = value.includes(option.id);
                return (
                  <Box
                    key={option.id}
                    sx={{
                      p: 1.5,
                      borderRadius: 3,
                      border: '1px solid',
                      borderColor: checked ? 'primary.main' : 'divider',
                      bgcolor: checked ? alpha('#1976d2', 0.06) : 'background.paper',
                    }}
                  >
                    <Stack spacing={1}>
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={checked}
                            onChange={() => toggle(option.id)}
                            color="primary"
                          />
                        }
                        label={
                          <Box>
                            <Typography variant="body2" fontWeight={800}>
                              {option.name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary" display="block">
                              {option.display_code ? `${option.display_code} · ` : ''}
                              {option.course_codes?.length ? option.course_codes.join(', ') : 'Lab rotation option'}
                            </Typography>
                          </Box>
                        }
                      />
                      <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
                        {option.active_this_week && <Chip label="Active this week" color="success" size="small" />}
                        {option.group_type && <Chip label={option.group_type.replace('_', ' ')} size="small" variant="outlined" />}
                      </Stack>
                    </Stack>
                    {index < options.length - 1 && <Divider sx={{ mt: 1.5 }} />}
                  </Box>
                );
              })}
            </Stack>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};

export default StudentSubgroupSelector;
