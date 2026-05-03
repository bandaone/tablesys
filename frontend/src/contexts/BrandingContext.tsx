import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { publicAPI } from '../api';

export interface Branding {
  university_id: number;
  name: string;
  short_name?: string;
  domain: string;
  logo_url?: string;
  primary_color: string;
  secondary_color: string;
  tagline?: string;
  plan_tier: string;
  max_users: number;
}

const defaultBranding: Branding = {
  university_id: 0,
  name: "TableSys",
  domain: "tablesys.com",
  primary_color: "#1976d2",
  secondary_color: "#9c27b0",
  plan_tier: "free",
  max_users: 50,
};

interface BrandingContextType {
  branding: Branding;
  loading: boolean;
  refreshBranding: () => Promise<void>;
  tenantError: boolean;
}

const BrandingContext = createContext<BrandingContextType>({
  branding: defaultBranding,
  loading: false,
  refreshBranding: async () => {},
  tenantError: false,
});

export const useBranding = () => useContext(BrandingContext);

export const BrandingProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [branding, setBranding] = useState<Branding>(defaultBranding);
  const [loading, setLoading] = useState<boolean>(true);
  const [tenantError, setTenantError] = useState<boolean>(false);

  const refreshBranding = async () => {
    try {
      setLoading(true);
      setTenantError(false);
      const hostname = window.location.hostname;
      
      // Admin and global domains bypass tenant check
      const globalDomains = ['localhost', '127.0.0.1', 'tablesys.com', 'www.tablesys.com'];
      const isIpAddress = /^(\d{1,3}\.){3}\d{1,3}$/.test(hostname);
      if (hostname.startsWith('admin.') || globalDomains.includes(hostname) || isIpAddress) {
        setBranding(defaultBranding);
        localStorage.removeItem('university_id');
        document.title = hostname.startsWith('admin.') ? 'TableSys Superadmin' : 'TableSys';
        setLoading(false);
        return;
      }

      // Fetch tenant branding publicly
      const data = await publicAPI.getUniversityBranding(hostname);
      const tenantBranding: Branding = {
        ...data,
        university_id: data.id,
        plan_tier: data.plan_tier || 'pro',
        max_users: data.max_users || 1000
      };
      
      setBranding(tenantBranding);
      localStorage.setItem('university_id', data.id.toString());
      document.title = data.short_name || data.name || 'TableSys';
    } catch (err: any) {
      console.error("Failed to load branding:", err);
      // If 404, we set tenant error flag to hard-block the UI later
      if (err.response && err.response.status === 404) {
         setTenantError(true);
      }
      setBranding(defaultBranding);
      localStorage.removeItem('university_id');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshBranding();
  }, []);

  return (
    <BrandingContext.Provider value={{ branding, loading, refreshBranding, tenantError }}>
      {children}
    </BrandingContext.Provider>
  );
};
