import React, { createContext, useContext, useState, useEffect } from 'react';
import { authAPI, User } from '../api';
import axios from 'axios';

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (username: string) => Promise<void>;
  logout: () => void;
  isCoordinator: boolean;
  isHOD: boolean;
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

  useEffect(() => {
    // Check for existing token on mount
    const savedToken = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');
    
    if (savedToken && savedUser) {
      setToken(savedToken);
      setUser(JSON.parse(savedUser));
    }
  }, []);

  const login = async (username: string) => {
    try {
      const response = await authAPI.login({ username });
      const { access_token } = response;
      
      // Store token temporarily for the next request
      localStorage.setItem('token', access_token);
      
      // Fetch user details
      const userResponse = await axios.get('/api/auth/me', {
        headers: {
          Authorization: `Bearer ${access_token}`,
        },
      });
      
      const userData = userResponse.data;
      
      localStorage.setItem('token', access_token);
      localStorage.setItem('user', JSON.stringify(userData));
      
      setToken(access_token);
      setUser(userData);
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
  };

  const isCoordinator = user?.role === 'coordinator';
  const isHOD = user?.role === 'hod' || user?.role === 'coordinator';

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isCoordinator, isHOD }}>
      {children}
    </AuthContext.Provider>
  );
};
