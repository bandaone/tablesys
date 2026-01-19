import { createTheme } from '@mui/material/styles';

// University of Zambia Official Colors
// Primary: UNZA Green (#006837)
// Secondary: UNZA Gold/Yellow (#FDB913)
// Accent: Black (#000000)

export const theme = createTheme({
  palette: {
    primary: {
      main: '#006837', // UNZA Green
      light: '#33865f',
      dark: '#004826',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#FDB913', // UNZA Gold
      light: '#fdc642',
      dark: '#b1810d',
      contrastText: '#000000',
    },
    info: {
      main: '#4A90E2',
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
      default: '#f4f6f4', // Slight green tint
      paper: '#ffffff',
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontWeight: 600,
      color: '#006837',
    },
    h2: {
      fontWeight: 600,
      color: '#006837',
    },
    h3: {
      fontWeight: 600,
      color: '#006837',
    },
    h4: {
      fontWeight: 600,
      color: '#006837',
    },
    h5: {
      fontWeight: 600,
      color: '#006837',
    },
    h6: {
      fontWeight: 600,
      color: '#006837',
    },
  },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#006837',
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
