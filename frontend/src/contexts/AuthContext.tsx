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
  isHOD: boolean;
  isAdmin: boolean;
  isSuperadmin: boolean;
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
      // 1. Clear existing session data first (Prevent Overwrapping)
      sessionStorage.removeItem('token');
      sessionStorage.removeItem('user');
      setToken(null);
      setUser(null);

      const response = await authAPI.login({ username, password });
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
      setToken(null);
      setUser(null);

      const userResponse = await axios.get('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      const userData = userResponse.data;

      sessionStorage.setItem('token', accessToken);
      sessionStorage.setItem('user', JSON.stringify(userData));
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
    setToken(null);
    setUser(null);
  };

  const safeRole = user?.role?.toUpperCase() || '';
  const isCoordinator = safeRole === 'COORDINATOR';
  const isHOD = safeRole === 'HOD' || safeRole === 'COORDINATOR';
  const isAdmin = safeRole === 'ADMIN';
  const isSuperadmin = safeRole === 'SUPERADMIN';

  return (
    <AuthContext.Provider value={{ user, token, login, loginWithToken, logout, loading, isCoordinator, isHOD, isAdmin, isSuperadmin }}>
      {children}
    </AuthContext.Provider>
  );
};
