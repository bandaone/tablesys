import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Tabs,
  Tab,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  TextField,
  Grid,
  Card,
  CardContent,
  Button,
  Link,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  IconButton,
  Chip,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Help as HelpIcon,
  MenuBook as MenuBookIcon,
  VideoLibrary as VideoLibraryIcon,
  ContactSupport as ContactSupportIcon,
  Download as DownloadIcon,
  Search as SearchIcon,
  CheckCircle as CheckCircleIcon,
  ArrowForward as ArrowForwardIcon,
  Email as EmailIcon,
  Phone as PhoneIcon,
  School as SchoolIcon,
} from '@mui/icons-material';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
  return (
    <div role="tabpanel" hidden={value !== index}>
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
};

interface FAQItem {
  question: string;
  answer: string;
  category: string;
}

const faqData: FAQItem[] = [
  {
    question: "How do I create a new timetable?",
    answer: "Navigate to the Timetables page and click the 'Create Timetable' button. Fill in the required fields including name, academic year, semester, and department. You can then add courses and generate the schedule automatically.",
    category: "Timetables"
  },
  {
    question: "What does the timetable generation optimize for?",
    answer: "The system optimizes for multiple factors including: no scheduling conflicts for lecturers or students, room capacity matching, lecturer availability preferences, and balanced workload distribution. It finds the best possible schedule given your institution's constraints.",
    category: "Timetables"
  },
  {
    question: "How do I add a new course?",
    answer: "Go to the Courses page and click 'Add Course'. Enter the course code, name, credit hours, department, year level, and semester. You can also assign lecturers and set teaching requirements.",
    category: "Courses"
  },
  {
    question: "Can I edit a timetable after it's been generated?",
    answer: "Yes! You can manually edit any timetable slot by clicking on it. You can change the time, room, or lecturer. The system will validate your changes to ensure no conflicts are created.",
    category: "Timetables"
  },
  {
    question: "How do I export timetables?",
    answer: "Click the 'Export' button on the Timetables page. You can export to Excel, PDF, or JSON format. Choose whether to export by department, lecturer, or student group.",
    category: "Export"
  },
  {
    question: "What are student groups and how do I manage them?",
    answer: "Student groups represent cohorts of students that take classes together. Navigate to the Student Groups page to create and manage groups. Assign students to groups based on their program and year level.",
    category: "Groups"
  },
  {
    question: "How do I assign rooms to courses?",
    answer: "Rooms can be assigned during timetable generation (automatic) or manually when editing a timetable slot. The system considers room capacity and availability when making assignments.",
    category: "Rooms"
  },
  {
    question: "What user roles are available?",
    answer: "The system has four roles: Admin (full access), Coordinator (manage all timetables), HOD (manage department timetables), and Lecturer (view only). Admins can create and manage users from the Users page.",
    category: "Users"
  },
  {
    question: "How do I view reports?",
    answer: "Navigate to the Reports page (Coordinator/Admin only). You can generate lecturer workload reports, room utilization reports, and department comparison reports. Export options are available for all reports.",
    category: "Reports"
  },
  {
    question: "What should I do if timetable generation fails?",
    answer: "Generation may fail if requirements are too tight (not enough rooms, overlapping lecturer assignments, etc.). Review the error message, check for conflicts in course requirements, and ensure adequate resources are available.",
    category: "Troubleshooting"
  },
  {
    question: "How do students access their timetables?",
    answer: "Students can log in to the Student Portal at /student using their student number and password. They'll see their personal timetable based on their assigned group.",
    category: "Student Portal"
  },
  {
    question: "Can I print timetables?",
    answer: "Yes! Use the Print view from the Timetables page. You can customize the print layout to show timetables by day, week, lecturer, or student group.",
    category: "Export"
  },
  {
    question: "How do I update my password?",
    answer: "Click on your profile icon in the top right corner and select 'Change Password'. Enter your current password and choose a new one. Students can update their password from the Student Portal.",
    category: "Account"
  },
  {
    question: "What does the Admin Dashboard show?",
    answer: "The Admin Dashboard provides system-wide analytics including total users, courses, timetables, activity trends, user role distribution, and recent system activity logs.",
    category: "Admin"
  },
  {
    question: "How are audit logs used?",
    answer: "Audit logs track all system actions (create, update, delete) by users. Administrators and Coordinators can view logs from the Audit Logs page to monitor system activity and troubleshoot issues.",
    category: "Audit"
  }
];

const userGuideSteps = [
  {
    title: "Getting Started",
    steps: [
      "Log in with your username and password provided by the administrator",
      "Navigate to the Dashboard to see an overview of your timetables",
      "Use the sidebar menu to access different sections (Courses, Lecturers, Rooms, etc.)",
      "Click on your profile icon (top right) to access account settings"
    ]
  },
  {
    title: "Managing Courses",
    steps: [
      "Go to the Courses page from the sidebar",
      "Click 'Add Course' to create a new course",
      "Fill in course details: code, name, credit hours, department, year, semester",
      "Assign lecturers and set teaching requirements",
      "Use the search bar to find specific courses",
      "Click on a course card to edit or delete it"
    ]
  },
  {
    title: "Creating Timetables",
    steps: [
      "Navigate to the Timetables page",
      "Click 'Create Timetable' button",
      "Enter name, academic year, semester, and select department",
      "Add courses to the timetable",
      "Click 'Generate' to auto-generate the schedule",
      "Review and manually adjust any slots if needed",
      "Publish the timetable when satisfied"
    ]
  },
  {
    title: "Managing Student Groups",
    steps: [
      "Go to the Student Groups page (Coordinator only)",
      "Click 'Add Group' to create a new student group",
      "Enter group name, program, year level, and expected size",
      "Assign students to groups (if Students module is configured)",
      "Groups are used during timetable generation to avoid student conflicts"
    ]
  },
  {
    title: "Generating Reports",
    steps: [
      "Navigate to the Reports page (Coordinator/Admin only)",
      "Choose a report type: Lecturer Workload, Room Utilization, or Department Comparison",
      "Apply filters (department, date range, etc.) as needed",
      "Click 'Generate Report' to view results",
      "Download the report in JSON format for further analysis"
    ]
  },
  {
    title: "Exporting Data",
    steps: [
      "From the Timetables page, click 'Export'",
      "Choose format: Excel, PDF, or JSON",
      "Select export view: by Department, Lecturer, or Student Group",
      "Select specific timetables to export",
      "Click 'Export' to download the file"
    ]
  }
];

const tutorials = [
  {
    title: "System Overview",
    description: "Introduction to the Timetable Management System",
    duration: "5 min",
    topics: ["Dashboard navigation", "User roles", "Key features"]
  },
  {
    title: "Creating Your First Timetable",
    description: "Step-by-step guide to timetable creation",
    duration: "10 min",
    topics: ["Course setup", "Room configuration", "Auto-generation", "Manual adjustments"]
  },
  {
    title: "Advanced Timetable Optimization",
    description: "Best practices for complex schedules",
    duration: "15 min",
    topics: ["Schedule optimization", "Resource allocation", "Conflict resolution"]
  },
  {
    title: "Reporting and Analytics",
    description: "Using the Reports module effectively",
    duration: "8 min",
    topics: ["Workload analysis", "Utilization reports", "Data export"]
  }
];

const HelpPage: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedAccordion, setExpandedAccordion] = useState<string | false>(false);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleAccordionChange = (panel: string) => (event: React.SyntheticEvent, isExpanded: boolean) => {
    setExpandedAccordion(isExpanded ? panel : false);
  };

  const filteredFAQs = faqData.filter(faq =>
    faq.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
    faq.answer.toLowerCase().includes(searchQuery.toLowerCase()) ||
    faq.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const faqsByCategory = filteredFAQs.reduce((acc, faq) => {
    if (!acc[faq.category]) {
      acc[faq.category] = [];
    }
    acc[faq.category].push(faq);
    return acc;
  }, {} as Record<string, FAQItem[]>);

  return (
    <Box>
      <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', gap: 1 }}>
        <HelpIcon sx={{ fontSize: 32, color: 'primary.main' }} />
        <Typography variant="h4">Help & Documentation</Typography>
      </Box>

      <Paper sx={{ mb: 3 }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab icon={<HelpIcon />} label="FAQ" />
          <Tab icon={<MenuBookIcon />} label="User Guide" />
          <Tab icon={<VideoLibraryIcon />} label="Tutorials" />
          <Tab icon={<ContactSupportIcon />} label="Support" />
        </Tabs>

        {/* FAQ Tab */}
        <TabPanel value={tabValue} index={0}>
          <Box sx={{ p: 3 }}>
            <TextField
              fullWidth
              placeholder="Search FAQ..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              InputProps={{
                startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />
              }}
              sx={{ mb: 3 }}
            />

            {Object.entries(faqsByCategory).map(([category, faqs]) => (
              <Box key={category} sx={{ mb: 3 }}>
                <Typography variant="h6" sx={{ mb: 2, color: 'primary.main' }}>
                  {category}
                </Typography>
                {faqs.map((faq, index) => (
                  <Accordion
                    key={`${category}-${index}`}
                    expanded={expandedAccordion === `${category}-${index}`}
                    onChange={handleAccordionChange(`${category}-${index}`)}
                    sx={{ mb: 1 }}
                  >
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography fontWeight={500}>{faq.question}</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Typography color="text.secondary">{faq.answer}</Typography>
                    </AccordionDetails>
                  </Accordion>
                ))}
              </Box>
            ))}
          </Box>
        </TabPanel>

        {/* User Guide Tab */}
        <TabPanel value={tabValue} index={1}>
          <Box sx={{ p: 3 }}>
            <Grid container spacing={3}>
              {userGuideSteps.map((guide, index) => (
                <Grid item xs={12} md={6} key={index}>
                  <Card>
                    <CardContent>
                      <Typography variant="h6" gutterBottom color="primary">
                        {guide.title}
                      </Typography>
                      <List dense>
                        {guide.steps.map((step, stepIndex) => (
                          <ListItem key={stepIndex}>
                            <ListItemIcon>
                              <CheckCircleIcon color="success" fontSize="small" />
                            </ListItemIcon>
                            <ListItemText primary={step} />
                          </ListItem>
                        ))}
                      </List>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>

            <Box sx={{ mt: 4, p: 3, bgcolor: 'primary.light', borderRadius: 2 }}>
              <Typography variant="h6" gutterBottom>
                Quick Reference Guide
              </Typography>
              <Typography variant="body2" sx={{ mb: 2 }}>
                Download our comprehensive PDF user manual for offline reference.
              </Typography>
              <Button
                variant="contained"
                startIcon={<DownloadIcon />}
                disabled
              >
                Download User Manual (Coming Soon)
              </Button>
            </Box>
          </Box>
        </TabPanel>

        {/* Tutorials Tab */}
        <TabPanel value={tabValue} index={2}>
          <Box sx={{ p: 3 }}>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
              Learn how to use the system effectively with our video tutorials.
            </Typography>

            <Grid container spacing={3}>
              {tutorials.map((tutorial, index) => (
                <Grid item xs={12} md={6} key={index}>
                  <Card sx={{ height: '100%' }}>
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                        <VideoLibraryIcon color="primary" sx={{ mr: 1 }} />
                        <Typography variant="h6">{tutorial.title}</Typography>
                      </Box>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        {tutorial.description}
                      </Typography>
                      <Chip label={tutorial.duration} size="small" sx={{ mb: 2 }} />
                      <Divider sx={{ my: 2 }} />
                      <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
                        Topics covered:
                      </Typography>
                      {tutorial.topics.map((topic, topicIndex) => (
                        <Chip
                          key={topicIndex}
                          label={topic}
                          size="small"
                          variant="outlined"
                          sx={{ mr: 0.5, mb: 0.5 }}
                        />
                      ))}
                      <Box sx={{ mt: 2 }}>
                        <Button
                          variant="outlined"
                          endIcon={<ArrowForwardIcon />}
                          fullWidth
                          disabled
                        >
                          Watch Tutorial (Coming Soon)
                        </Button>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Box>
        </TabPanel>

        {/* Support Tab */}
        <TabPanel value={tabValue} index={3}>
          <Box sx={{ p: 3 }}>
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <EmailIcon color="primary" sx={{ mr: 1 }} />
                      <Typography variant="h6">Email Support</Typography>
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      For technical issues or questions, contact our support team:
                    </Typography>
                    <Link href="mailto:support@tablesys.com" underline="hover">
                      support@tablesys.com
                    </Link>
                    <Typography variant="caption" display="block" sx={{ mt: 2, color: 'text.secondary' }}>
                      Response time: Within 24 hours during business days
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <PhoneIcon color="primary" sx={{ mr: 1 }} />
                      <Typography variant="h6">Phone Support</Typography>
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      Call our support hotline for urgent issues:
                    </Typography>
                    <Typography variant="h6" color="primary">
                      +260 XXX XXX XXX
                    </Typography>
                    <Typography variant="caption" display="block" sx={{ mt: 2, color: 'text.secondary' }}>
                      Available: Monday - Friday, 9:00 AM - 5:00 PM
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12}>
                <Card>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <SchoolIcon color="primary" sx={{ mr: 1 }} />
                      <Typography variant="h6">University IT Department</Typography>
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      For system administration and access requests, contact your University IT Department:
                    </Typography>
                    <List dense>
                      <ListItem>
                        <ListItemText
                          primary="Support Portal"
                          secondary="Contact your university administrator for system access"
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemText primary="Office Hours" secondary="Monday - Friday, 8:00 AM - 5:00 PM" />
                      </ListItem>
                    </List>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12}>
                <Paper sx={{ p: 3, bgcolor: 'info.light' }}>
                  <Typography variant="h6" gutterBottom>
                    System Information
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2">
                        <strong>Platform:</strong> TABLESYS
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2">
                        <strong>Last Updated:</strong> {new Date().getFullYear()}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2">
                        <strong>Status:</strong> Production
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2">
                        <strong>Browser Support:</strong> Chrome, Firefox, Edge (latest versions)
                      </Typography>
                    </Grid>
                  </Grid>
                </Paper>
              </Grid>
            </Grid>
          </Box>
        </TabPanel>
      </Paper>
    </Box>
  );
};

export default HelpPage;
