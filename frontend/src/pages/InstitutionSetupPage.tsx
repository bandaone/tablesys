import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from '@mui/material';
import {
  AutoAwesome as AutoAwesomeIcon,
  SettingsSuggest as SettingsSuggestIcon,
} from '@mui/icons-material';
import { Link as RouterLink } from 'react-router-dom';
import { institutionSetupAPI } from '../api';
import {
  GlassPanel,
  HeroButton,
  HeroGhostButton,
  TenantPageHero,
} from '../components/tenant/TenantAdminUI';
import { useBranding } from '../contexts/BrandingContext';

const steps = ['Calendar', 'Policy', 'Template', 'Activities', 'Room Tags', 'Schools'];

const InstitutionSetupPage: React.FC = () => {
  const { branding } = useBranding();
  const primaryColor = branding.primary_color || '#1976d2';
  const secondaryColor = branding.secondary_color || '#9c27b0';

  const [activeStep, setActiveStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [templates, setTemplates] = useState<any[]>([]);
  const [form, setForm] = useState<any>({
    template_key: 'engineering',
    calendar_name: 'Institution Calendar',
    days_of_week: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
    start_time: '07:00',
    end_time: '18:00',
    slot_duration_minutes: 60,
    lunch_start: '13:00',
    lunch_end: '14:00',
    scheduling_policy: {
      default_lecture_frequency: 2,
      default_tutorial_frequency: 1,
      default_practical_frequency: 1,
      daily_max_teaching_hours: 8,
      enforce_lunch_break: true,
    },
    room_tags: [],
    activity_types: [],
  });

  useEffect(() => {
    const load = async () => {
      try {
        const [templateRes, currentRes] = await Promise.all([
          institutionSetupAPI.getTemplates(),
          institutionSetupAPI.getCurrent(),
        ]);
        setTemplates(templateRes.templates || []);
        setForm((prev: any) => ({
          ...prev,
          ...currentRes,
          calendar_name: currentRes.calendar?.name || prev.calendar_name,
          days_of_week: currentRes.calendar?.days_of_week || prev.days_of_week,
          start_time: currentRes.calendar?.start_time || prev.start_time,
          end_time: currentRes.calendar?.end_time || prev.end_time,
          slot_duration_minutes: currentRes.calendar?.slot_duration_minutes || prev.slot_duration_minutes,
          lunch_start: currentRes.scheduling_policy?.lunch_start || prev.lunch_start,
          lunch_end: currentRes.scheduling_policy?.lunch_end || prev.lunch_end,
        }));
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load institution setup.');
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const selectedTemplate = useMemo(
    () => templates.find((item) => item.key === form.template_key),
    [templates, form.template_key],
  );

  const applyTemplate = (templateKey: string) => {
    const template = templates.find((item) => item.key === templateKey);
    setForm((prev: any) => ({
      ...prev,
      template_key: templateKey,
      room_tags: template?.room_tags || [],
      activity_types: template?.activity_types || [],
      scheduling_policy: {
        ...prev.scheduling_policy,
        institution_template_key: templateKey,
      },
    }));
  };

  const updateField = (field: string, value: any) => {
    setForm((prev: any) => ({ ...prev, [field]: value }));
  };

  const updatePolicy = (field: string, value: any) => {
    setForm((prev: any) => ({
      ...prev,
      scheduling_policy: {
        ...prev.scheduling_policy,
        [field]: value,
      },
    }));
  };

  const updateActivity = (index: number, field: string, value: any) => {
    setForm((prev: any) => ({
      ...prev,
      activity_types: prev.activity_types.map((item: any, idx: number) => (
        idx === index ? { ...item, [field]: value } : item
      )),
    }));
  };

  const addActivity = () => {
    setForm((prev: any) => ({
      ...prev,
      activity_types: [
        ...prev.activity_types,
        {
          key: '',
          display_name: '',
          color: '#3B82F6',
          default_duration_periods: 1,
          default_frequency_per_week: 1,
          requires_subgroups: false,
          resource_tags_required: [],
          counts_toward_contact_hours: true,
          is_active: true,
        },
      ],
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      await institutionSetupAPI.save({
        ...form,
        room_tags: form.room_tags,
        activity_types: form.activity_types.map((item: any) => ({
          ...item,
          key: String(item.key || '').trim().toLowerCase(),
          resource_tags_required: Array.isArray(item.resource_tags_required)
            ? item.resource_tags_required
            : String(item.resource_tags_required || '')
              .split(',')
              .map((tag) => tag.trim())
              .filter(Boolean),
        })),
      });
      setSuccess('Institution setup saved. The universal scheduling model is now configured for this tenant.');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save institution setup.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ minHeight: '50vh', display: 'grid', placeItems: 'center' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <TenantPageHero
        title="Institution Setup"
        description="Configure the scheduling model once, then let every school, coordinator, and timetable inherit a more predictable institutional foundation."
        eyebrow="Configuration"
        icon={<SettingsSuggestIcon />}
        primaryColor={primaryColor}
        secondaryColor={secondaryColor}
        meta={<Typography variant="body2" sx={{ color: '#fff' }}>{steps[activeStep]} step active</Typography>}
      />

      {error && <Alert severity="error" sx={{ mb: 2.5 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2.5 }}>{success}</Alert>}

      <GlassPanel primaryColor={primaryColor} secondaryColor={secondaryColor} variant="dark" padding={2.5} sx={{ mb: 3 }}>
        <Stepper activeStep={activeStep} alternativeLabel sx={{ '& .MuiStepLabel-label': { color: '#fff !important' } }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>
      </GlassPanel>

      <GlassPanel primaryColor={primaryColor} secondaryColor={secondaryColor} variant="solid" sx={{ mb: 3 }}>
        <Stack spacing={2.5}>
          {activeStep === 0 && (
            <>
              <Typography variant="h6" fontWeight={800}>Academic calendar frame</Typography>
              <TextField label="Calendar Name" value={form.calendar_name} onChange={(e) => updateField('calendar_name', e.target.value)} />
              <TextField
                label="Teaching Days"
                value={form.days_of_week.join(', ')}
                onChange={(e) => updateField('days_of_week', e.target.value.split(',').map((value: string) => value.trim()).filter(Boolean))}
                helperText="Comma-separated day names"
              />
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
                <TextField label="Start Time" value={form.start_time} onChange={(e) => updateField('start_time', e.target.value)} fullWidth />
                <TextField label="End Time" value={form.end_time} onChange={(e) => updateField('end_time', e.target.value)} fullWidth />
                <TextField label="Slot Minutes" type="number" value={form.slot_duration_minutes} onChange={(e) => updateField('slot_duration_minutes', Number(e.target.value))} fullWidth />
              </Stack>
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
                <TextField label="Lunch Start" value={form.lunch_start} onChange={(e) => updateField('lunch_start', e.target.value)} fullWidth />
                <TextField label="Lunch End" value={form.lunch_end} onChange={(e) => updateField('lunch_end', e.target.value)} fullWidth />
              </Stack>
            </>
          )}

          {activeStep === 1 && (
            <>
              <Typography variant="h6" fontWeight={800}>Scheduling defaults</Typography>
              <TextField label="Default Lecture Frequency" type="number" value={form.scheduling_policy.default_lecture_frequency} onChange={(e) => updatePolicy('default_lecture_frequency', Number(e.target.value))} />
              <TextField label="Default Tutorial Frequency" type="number" value={form.scheduling_policy.default_tutorial_frequency} onChange={(e) => updatePolicy('default_tutorial_frequency', Number(e.target.value))} />
              <TextField label="Default Practical Frequency" type="number" value={form.scheduling_policy.default_practical_frequency} onChange={(e) => updatePolicy('default_practical_frequency', Number(e.target.value))} />
              <TextField label="Daily Max Teaching Hours" type="number" value={form.scheduling_policy.daily_max_teaching_hours} onChange={(e) => updatePolicy('daily_max_teaching_hours', Number(e.target.value))} />
            </>
          )}

          {activeStep === 2 && (
            <>
              <Typography variant="h6" fontWeight={800}>Template baseline</Typography>
              <FormControl fullWidth>
                <InputLabel>Institution Template</InputLabel>
                <Select value={form.template_key} label="Institution Template" onChange={(e) => applyTemplate(String(e.target.value))}>
                  {templates.map((template) => (
                    <MenuItem key={template.key} value={template.key}>{template.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Alert severity="info">
                {selectedTemplate
                  ? `This template seeds ${selectedTemplate.activity_types.length} activity types and ${selectedTemplate.room_tags.length} room tags.`
                  : 'Select a template to load a starting point.'}
              </Alert>
            </>
          )}

          {activeStep === 3 && (
            <>
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} justifyContent="space-between" alignItems={{ md: 'center' }}>
                <Typography variant="h6" fontWeight={800}>Activity vocabulary</Typography>
                <Button variant="outlined" startIcon={<AutoAwesomeIcon />} onClick={addActivity}>Add Activity Type</Button>
              </Stack>
              <Stack spacing={2}>
                {form.activity_types.map((activity: any, index: number) => (
                  <Card key={`${activity.key || 'new'}-${index}`} variant="outlined">
                    <CardContent>
                      <Stack spacing={2}>
                        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
                          <TextField label="Key" value={activity.key} onChange={(e) => updateActivity(index, 'key', e.target.value)} fullWidth />
                          <TextField label="Display Name" value={activity.display_name} onChange={(e) => updateActivity(index, 'display_name', e.target.value)} fullWidth />
                        </Stack>
                        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
                          <TextField label="Duration (periods)" type="number" value={activity.default_duration_periods} onChange={(e) => updateActivity(index, 'default_duration_periods', Number(e.target.value))} fullWidth />
                          <TextField label="Frequency / Week" type="number" value={activity.default_frequency_per_week} onChange={(e) => updateActivity(index, 'default_frequency_per_week', Number(e.target.value))} fullWidth />
                          <TextField
                            label="Required Room Tags"
                            value={(activity.resource_tags_required || []).join(', ')}
                            onChange={(e) => updateActivity(index, 'resource_tags_required', e.target.value.split(',').map((tag) => tag.trim()).filter(Boolean))}
                            fullWidth
                          />
                        </Stack>
                      </Stack>
                    </CardContent>
                  </Card>
                ))}
              </Stack>
            </>
          )}

          {activeStep === 4 && (
            <>
              <Typography variant="h6" fontWeight={800}>Room capability tags</Typography>
              <TextField
                label="Room Tag Catalog"
                value={form.room_tags.join(', ')}
                onChange={(e) => updateField('room_tags', e.target.value.split(',').map((tag) => tag.trim()).filter(Boolean))}
                helperText="Comma-separated tags like skill_lab, projector, ward, workshop"
                fullWidth
              />
            </>
          )}

          {activeStep === 5 && (
            <>
              <Typography variant="h6" fontWeight={800}>School hierarchy handoff</Typography>
              <Typography color="text.secondary">
                Institution-wide scheduling setup is saved. Next, create your schools, add any shared university rooms, and invite school coordinators so timetable generation can be scoped correctly.
              </Typography>
              <Button component={RouterLink} to="/schools" variant="contained" sx={{ alignSelf: 'flex-start', borderRadius: 999, textTransform: 'none', fontWeight: 800 }}>
                Continue To School Management
              </Button>
            </>
          )}
        </Stack>
      </GlassPanel>

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} justifyContent="space-between">
        <HeroGhostButton disabled={activeStep === 0} onClick={() => setActiveStep((prev) => prev - 1)}>
          Back
        </HeroGhostButton>
        {activeStep < steps.length - 1 ? (
          <HeroButton onClick={() => setActiveStep((prev) => prev + 1)}>Next Step</HeroButton>
        ) : (
          <HeroButton onClick={handleSave} disabled={saving}>{saving ? 'Saving...' : 'Save Setup'}</HeroButton>
        )}
      </Stack>
    </Box>
  );
};

export default InstitutionSetupPage;
