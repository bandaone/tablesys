import React, { useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Button,
  Chip,
  Grid,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import {
  ArrowForward as ArrowForwardIcon,
  CheckCircle as CheckCircleIcon,
  ContactSupport as ContactSupportIcon,
  Download as DownloadIcon,
  Email as EmailIcon,
  ExpandMore as ExpandMoreIcon,
  Help as HelpIcon,
  MenuBook as MenuBookIcon,
  Phone as PhoneIcon,
  School as SchoolIcon,
  Search as SearchIcon,
  VideoLibrary as VideoLibraryIcon,
} from '@mui/icons-material';
import {
  GlassPanel,
  HeroGhostButton,
  InsightCard,
  TenantPageHero,
} from '../components/tenant/TenantAdminUI';
import { useBranding } from '../contexts/BrandingContext';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => (
  <div role="tabpanel" hidden={value !== index}>
    {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
  </div>
);

interface FAQItem {
  question: string;
  answer: string;
  category: string;
}

const faqData: FAQItem[] = [
  { question: 'How do I create a new timetable?', answer: "Navigate to the Timetables page and click the 'Create Timetable' button. Fill in the required fields including name, academic year, semester, and department. You can then add courses and generate the schedule automatically.", category: 'Timetables' },
  { question: 'What does the timetable generation optimize for?', answer: "The system optimizes for multiple factors including: no scheduling conflicts for lecturers or students, room capacity matching, lecturer availability preferences, and balanced workload distribution. It finds the best possible schedule given your institution's constraints.", category: 'Timetables' },
  { question: 'How do I add a new course?', answer: "Go to the Courses page and click 'Add Course'. Enter the course code, name, credit hours, department, year level, and semester. You can also assign lecturers and set teaching requirements.", category: 'Courses' },
  { question: "Can I edit a timetable after it's been generated?", answer: 'Yes. You can manually edit a timetable slot, change the time, room, or lecturer, and the system validates the change against known conflicts.', category: 'Timetables' },
  { question: 'How do I export timetables?', answer: 'Click the Export button on the Timetables page. You can export to Excel, PDF, or JSON format by department, lecturer, or student group.', category: 'Export' },
  { question: 'What user roles are available?', answer: 'Tenant admins manage institution-wide setup, school coordinators manage school-scoped operations, HODs manage department ownership, and lecturers view assigned schedules.', category: 'Users' },
  { question: 'How do I view reports?', answer: 'Navigate to the Reports page if your role allows it. You can generate lecturer workload, room utilization, and comparison reports with export options.', category: 'Reports' },
  { question: 'How are audit logs used?', answer: 'Audit logs track create, update, delete, login, and generation events so tenant admins can investigate operational history and user actions.', category: 'Audit' },
];

const userGuideSteps = [
  { title: 'Getting Started', steps: ['Log in with your provided credentials', 'Use the dashboard to review activity and system health', 'Navigate via the left workspace rail', 'Use the profile menu for account tasks'] },
  { title: 'Managing Courses', steps: ['Open Courses from the navigation', 'Create or edit course records', 'Assign lecturers and teaching requirements', 'Use filters or search to find specific offerings'] },
  { title: 'Creating Timetables', steps: ['Open Timetables', 'Create a timetable shell with year and semester details', 'Add courses to scope the generation', 'Generate, review, adjust, and publish'] },
  { title: 'Generating Reports', steps: ['Open Reports', 'Choose a report type', 'Apply relevant filters', 'Generate and export the result set'] },
];

const tutorials = [
  { title: 'System Overview', description: 'Introduction to the Timetable Management System', duration: '5 min', topics: ['Dashboard navigation', 'User roles', 'Key features'] },
  { title: 'Creating Your First Timetable', description: 'Step-by-step guide to timetable creation', duration: '10 min', topics: ['Course setup', 'Room configuration', 'Auto-generation', 'Manual adjustments'] },
  { title: 'Advanced Timetable Optimization', description: 'Best practices for complex schedules', duration: '15 min', topics: ['Schedule optimization', 'Resource allocation', 'Conflict resolution'] },
];

const HelpPage: React.FC = () => {
  const { branding } = useBranding();
  const primaryColor = branding.primary_color || '#1976d2';
  const secondaryColor = branding.secondary_color || '#9c27b0';
  const [tabValue, setTabValue] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedAccordion, setExpandedAccordion] = useState<string | false>(false);

  const filteredFAQs = faqData.filter((faq) => (
    faq.question.toLowerCase().includes(searchQuery.toLowerCase())
    || faq.answer.toLowerCase().includes(searchQuery.toLowerCase())
    || faq.category.toLowerCase().includes(searchQuery.toLowerCase())
  ));

  const faqsByCategory = filteredFAQs.reduce((acc, faq) => {
    if (!acc[faq.category]) acc[faq.category] = [];
    acc[faq.category].push(faq);
    return acc;
  }, {} as Record<string, FAQItem[]>);

  return (
    <Box>
      <TenantPageHero
        title="Help & Documentation"
        description="Support content now lives inside the same branded tenant-admin system, with cleaner task groupings and calmer reading surfaces."
        eyebrow="Support"
        icon={<HelpIcon />}
        primaryColor={primaryColor}
        secondaryColor={secondaryColor}
        actions={(
          <HeroGhostButton startIcon={<EmailIcon />} onClick={() => { window.location.href = 'mailto:support@tablesys.com'; }}>
            Contact Support
          </HeroGhostButton>
        )}
      />

      <GlassPanel primaryColor={primaryColor} secondaryColor={secondaryColor} variant="light" padding={0}>
        <Tabs
          value={tabValue}
          onChange={(_, value) => setTabValue(value)}
          sx={{
            px: 2.5,
            pt: 1.5,
            borderBottom: '1px solid rgba(15,23,42,0.08)',
            '& .MuiTab-root': { color: '#475569', textTransform: 'none', fontWeight: 700 },
            '& .Mui-selected': { color: primaryColor },
          }}
        >
          <Tab icon={<HelpIcon />} label="FAQ" />
          <Tab icon={<MenuBookIcon />} label="User Guide" />
          <Tab icon={<VideoLibraryIcon />} label="Tutorials" />
          <Tab icon={<ContactSupportIcon />} label="Support" />
        </Tabs>

        <TabPanel value={tabValue} index={0}>
          <Box sx={{ p: 3 }}>
            <TextField
              fullWidth
              placeholder="Search the knowledge base"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              InputProps={{ startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} /> }}
              sx={{ mb: 3 }}
            />

            {Object.entries(faqsByCategory).map(([category, faqs]) => (
              <Box key={category} sx={{ mb: 3 }}>
                <Chip label={category} sx={{ mb: 1.5, fontWeight: 800 }} />
                {faqs.map((faq, index) => {
                  const key = `${category}-${index}`;
                  return (
                    <Accordion
                      key={key}
                      expanded={expandedAccordion === key}
                      onChange={(_, isExpanded) => setExpandedAccordion(isExpanded ? key : false)}
                      sx={{ mb: 1, borderRadius: '16px !important', overflow: 'hidden' }}
                    >
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography fontWeight={700}>{faq.question}</Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <Typography color="text.secondary">{faq.answer}</Typography>
                      </AccordionDetails>
                    </Accordion>
                  );
                })}
              </Box>
            ))}
          </Box>
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <Box sx={{ p: 3 }}>
            <Grid container spacing={3}>
              {userGuideSteps.map((guide) => (
                <Grid item xs={12} md={6} key={guide.title}>
                  <InsightCard title={guide.title} icon={<MenuBookIcon />} primaryColor={primaryColor} secondaryColor={secondaryColor}>
                    <List dense>
                      {guide.steps.map((step) => (
                        <ListItem key={step} sx={{ px: 0 }}>
                          <ListItemIcon sx={{ minWidth: 32 }}>
                            <CheckCircleIcon color="success" fontSize="small" />
                          </ListItemIcon>
                          <ListItemText primary={step} />
                        </ListItem>
                      ))}
                    </List>
                  </InsightCard>
                </Grid>
              ))}
            </Grid>

            <GlassPanel primaryColor={primaryColor} secondaryColor={secondaryColor} variant="solid" sx={{ mt: 3 }}>
              <Typography variant="h6" fontWeight={800} gutterBottom>Quick Reference Guide</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Download our comprehensive PDF manual for offline reference.
              </Typography>
              <Button variant="contained" startIcon={<DownloadIcon />} disabled>
                Download User Manual
              </Button>
            </GlassPanel>
          </Box>
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          <Box sx={{ p: 3 }}>
            <Grid container spacing={3}>
              {tutorials.map((tutorial) => (
                <Grid item xs={12} md={6} key={tutorial.title}>
                  <InsightCard title={tutorial.title} description={tutorial.description} icon={<VideoLibraryIcon />} primaryColor={primaryColor} secondaryColor={secondaryColor}>
                    <Chip label={tutorial.duration} size="small" sx={{ alignSelf: 'flex-start' }} />
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                      {tutorial.topics.map((topic) => (
                        <Chip key={topic} label={topic} size="small" variant="outlined" />
                      ))}
                    </Box>
                    <Button variant="outlined" endIcon={<ArrowForwardIcon />} disabled>
                      Watch Tutorial
                    </Button>
                  </InsightCard>
                </Grid>
              ))}
            </Grid>
          </Box>
        </TabPanel>

        <TabPanel value={tabValue} index={3}>
          <Box sx={{ p: 3 }}>
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <InsightCard title="Email Support" icon={<EmailIcon />} primaryColor={primaryColor} secondaryColor={secondaryColor}>
                  <Typography variant="body2" color="text.secondary">For technical issues or product questions, contact:</Typography>
                  <Typography variant="subtitle1" fontWeight={800}>support@tablesys.com</Typography>
                  <Typography variant="caption" color="text.secondary">Response time: within 24 hours during business days</Typography>
                </InsightCard>
              </Grid>
              <Grid item xs={12} md={6}>
                <InsightCard title="Phone Support" icon={<PhoneIcon />} primaryColor={primaryColor} secondaryColor={secondaryColor}>
                  <Typography variant="body2" color="text.secondary">Call our support line for urgent operational issues.</Typography>
                  <Typography variant="subtitle1" fontWeight={800}>+260 XXX XXX XXX</Typography>
                  <Typography variant="caption" color="text.secondary">Monday to Friday, 9:00 AM to 5:00 PM</Typography>
                </InsightCard>
              </Grid>
              <Grid item xs={12}>
                <InsightCard title="Tenant Administration Support" icon={<SchoolIcon />} primaryColor={primaryColor} secondaryColor={secondaryColor}>
                  <Typography variant="body2" color="text.secondary">
                    Contact your tenant admin or institutional IT support team for account setup, access changes, and school assignments.
                  </Typography>
                </InsightCard>
              </Grid>
            </Grid>
          </Box>
        </TabPanel>
      </GlassPanel>
    </Box>
  );
};

export default HelpPage;
