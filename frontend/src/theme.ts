import { createTheme } from '@mui/material/styles';

// University of Zambia Official Colors
// Primary: Dark Blue (#003366)
// Secondary: Orange/Gold (#FF8C00)
// Accent: Light Blue (#4A90E2)

export const theme = createTheme({
  palette: {
    primary: {
      main: '#003366', // UNZA Dark Blue
      light: '#1a4d7a',
      dark: '#002244',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#FF8C00', // UNZA Orange/Gold
      light: '#ffa033',
      dark: '#cc7000',
      contrastText: '#ffffff',
    },
    info: {
      main: '#4A90E2', // Light Blue accent
      light: '#6ba3e8',
      dark: '#3a73b5',
    },
    success: {
      main: '#2e7d32',
    },
    error: {
      main: '#d32f2f',
    },
    warning: {
      main: '#ed6c02',
    },
    background: {
      default: '#f5f5f5',
      paper: '#ffffff',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontWeight: 600,
      color: '#003366',
    },
    h2: {
      fontWeight: 600,
      color: '#003366',
    },
    h3: {
      fontWeight: 600,
      color: '#003366',
    },
    h4: {
      fontWeight: 600,
      color: '#003366',
    },
    h5: {
      fontWeight: 600,
      color: '#003366',
    },
    h6: {
      fontWeight: 600,
      color: '#003366',
    },
  },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#003366',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
        },
        contained: {
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          borderRadius: 8,
        },
      },
    },
  },
});
