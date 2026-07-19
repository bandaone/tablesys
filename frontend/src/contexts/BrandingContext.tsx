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
  refreshBranding: async () => { },
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
      let hostname = window.location.hostname;

      const urlParams = new URLSearchParams(window.location.search);
      const tenantParam = urlParams.get('tenant');
      
      if (tenantParam) {
          localStorage.setItem('tenantOverride', tenantParam);
      }
      const override = localStorage.getItem('tenantOverride');

      const globalDomains = ['localhost', '127.0.0.1', 'tablesys.com', 'www.tablesys.com'];
      // nip.io / sslip.io: wildcard DNS — e.g. unza.192.168.0.103.nip.io → IP 192.168.0.103
      // These carry the tenant slug as the FIRST subdomain, so treat them like real subdomains.
      const isNipIo = /\.(\d{1,3}\.){3}\d{1,3}\.(nip\.io|sslip\.io)$/.test(hostname);
      const isIpAddress = /^(\d{1,3}\.){3}\d{1,3}$/.test(hostname);
      
      // Only apply override if we are on a plain IP or global domain (not nip.io — those have real subdomains)
      if ((isIpAddress || globalDomains.includes(hostname)) && !isNipIo) {
          if (override) {
              hostname = override;
          }
      } else if (!isNipIo) {
          localStorage.removeItem('tenantOverride');
      }

      // Re-evaluate if it's STILL an IP address or global domain after potential override
      const isStillBypass = (/^(\d{1,3}\.){3}\d{1,3}$/.test(hostname) || globalDomains.includes(hostname)) && !isNipIo;

      if (hostname.startsWith('admin.') || isStillBypass) {
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
