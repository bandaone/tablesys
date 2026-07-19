import React, { createContext, useContext, useState, useEffect } from 'react';
import { authAPI, User } from '../api';
import axios from 'axios';

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (username: string, password: string) => Promise<User>;
  /** Used by the SSO callback page to bootstrap a session from a JWT. */
  loginWithToken: (token: string) => Promise<User>;
  logout: () => void;
  loading: boolean;
  isCoordinator: boolean;
  isTenantAdmin: boolean;
  isSchoolCoordinator: boolean;
  isSchoolOperator: boolean;
  isHOD: boolean;
  isSuperadmin: boolean;
  isLabCoordinator: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Check for existing token on mount
    const savedToken = sessionStorage.getItem('token');
    const savedUser = sessionStorage.getItem('user');

    if (savedToken && savedUser) {
      setToken(savedToken);
      setUser(JSON.parse(savedUser));
    }
  }, []);

  const login = async (username: string, password: string) => {
    try {
      setLoading(true);
      
      const currentUniId = localStorage.getItem('university_id');
      const university_id = currentUniId ? parseInt(currentUniId, 10) : undefined;

      // 1. Clear existing session data first (Prevent Overwrapping)
      sessionStorage.removeItem('token');
      sessionStorage.removeItem('user');
      sessionStorage.removeItem('superadmin_impersonator');
      // Do NOT clear university_id yet - if login fails we still need it for branding
      setToken(null);
      setUser(null);

      const response = await authAPI.login({ username, password, university_id });
      const { access_token } = response;

      // 2. Fetch user details with NEW token
      const userResponse = await axios.get('/api/v1/auth/me', {
        headers: {
          Authorization: `Bearer ${access_token}`,
        },
      });

      const userData = userResponse.data;

      // 3. Persist new session
      sessionStorage.setItem('token', access_token);
      sessionStorage.setItem('user', JSON.stringify(userData));
      localStorage.setItem('university_id', String(userData.university_id));

      setToken(access_token);
      setUser(userData);

      return userData;
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  /**
   * SSO login — given a raw JWT (from the SSOCallback page query string),
   * fetch /me to get user details and store the session exactly like a
   * normal password login.
   */
  const loginWithToken = async (accessToken: string): Promise<User> => {
    try {
      setLoading(true);
      sessionStorage.removeItem('token');
      sessionStorage.removeItem('user');
      sessionStorage.removeItem('superadmin_impersonator');
      // Do NOT clear university_id
      setToken(null);
      setUser(null);

      const userResponse = await axios.get('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      const userData = userResponse.data;

      sessionStorage.setItem('token', accessToken);
      sessionStorage.setItem('user', JSON.stringify(userData));
      localStorage.setItem('university_id', String(userData.university_id));
      setToken(accessToken);
      setUser(userData);
      return userData;
    } catch (error) {
      console.error('SSO loginWithToken error:', error);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    sessionStorage.removeItem('token');
    sessionStorage.removeItem('user');
    sessionStorage.removeItem('superadmin_impersonator');
    localStorage.removeItem('university_id');
    setToken(null);
    setUser(null);
  };

  const safeRole = user?.role?.toUpperCase() || '';
  const isTenantAdmin = safeRole === 'TENANT_ADMIN';
  const isSchoolCoordinator = safeRole === 'SCHOOL_COORDINATOR';
  const isCoordinator = safeRole === 'COORDINATOR' || isSchoolCoordinator;
  const isSchoolOperator = isCoordinator;
  const isHOD = safeRole === 'HOD' || isSchoolOperator;
  const isSuperadmin = safeRole === 'SUPERADMIN';
  const isLabCoordinator = safeRole === 'LAB_COORDINATOR' || (isCoordinator && !isSchoolCoordinator) || (isHOD && !isSchoolCoordinator);

  return (
    <AuthContext.Provider value={{ user, token, login, loginWithToken, logout, loading, isCoordinator, isTenantAdmin, isSchoolCoordinator, isSchoolOperator, isHOD, isSuperadmin, isLabCoordinator }}>
      {children}
    </AuthContext.Provider>
  );
};
