import React from 'react';
import {
  alpha,
  useTheme,
} from '@mui/material/styles';
import {
  Box,
  Button,
  Chip,
  FormControl,
  Paper,
  Select,
  Stack,
  Typography,
} from '@mui/material';

type Tone = 'default' | 'success' | 'warning' | 'danger' | 'info';
type GlassVariant = 'dark' | 'light' | 'solid';

const toneMap: Record<Tone, { color: string; soft: string }> = {
  default: { color: '#8b5cf6', soft: 'rgba(139, 92, 246, 0.16)' },
  success: { color: '#22c55e', soft: 'rgba(34, 197, 94, 0.16)' },
  warning: { color: '#f59e0b', soft: 'rgba(245, 158, 11, 0.18)' },
  danger: { color: '#ef4444', soft: 'rgba(239, 68, 68, 0.18)' },
  info: { color: '#38bdf8', soft: 'rgba(56, 189, 248, 0.18)' },
};

export const tenantGlass = (primaryColor: string, secondaryColor = '#9c27b0') => ({
  gradient: `linear-gradient(135deg, ${primaryColor} 0%, #1976d2 52%, ${secondaryColor} 100%)`,
  shellBg: `radial-gradient(circle at top right, ${alpha(secondaryColor, 0.18)} 0%, transparent 22%), linear-gradient(180deg, ${alpha(primaryColor, 0.08)} 0%, #f6f8fc 34%, #edf2fb 100%)`,
  darkGlassBg: 'linear-gradient(135deg, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0.08) 100%)',
  darkGlassBorder: '1px solid rgba(255,255,255,0.18)',
  darkGlassShadow: `0 24px 48px ${alpha('#0f172a', 0.14)}`,
  lightGlassBg: 'linear-gradient(180deg, rgba(255,255,255,0.78) 0%, rgba(247,250,255,0.72) 100%)',
  lightGlassBorder: `1px solid ${alpha('#ffffff', 0.44)}`,
  lightGlassShadow: `0 18px 38px ${alpha('#0f172a', 0.08)}`,
  solidBorder: `1px solid ${alpha('#0f172a', 0.08)}`,
  solidShadow: `0 18px 40px ${alpha('#0f172a', 0.06)}`,
});

export const StatusBadge: React.FC<{ label: string; tone?: Tone; subtle?: boolean }> = ({
  label,
  tone = 'default',
  subtle = false,
}) => {
  const palette = toneMap[tone];

  return (
    <Chip
      label={label}
      size="small"
      sx={{
        height: 24,
        fontSize: '0.7rem',
        fontWeight: 800,
        letterSpacing: 0.5,
        color: subtle ? palette.color : '#fff',
        bgcolor: subtle ? palette.soft : palette.color,
        border: subtle ? `1px solid ${alpha(palette.color, 0.26)}` : 'none',
      }}
    />
  );
};

export const GlassPanel: React.FC<{
  children: React.ReactNode;
  primaryColor?: string;
  secondaryColor?: string;
  variant?: GlassVariant;
  padding?: number;
  sx?: Record<string, any>;
}> = ({
  children,
  primaryColor = '#1976d2',
  secondaryColor = '#9c27b0',
  variant = 'light',
  padding = 3,
  sx = {},
}) => {
  const styles = tenantGlass(primaryColor, secondaryColor);
  const isDark = variant === 'dark';
  const isSolid = variant === 'solid';
  const isLight = variant === 'light';

  return (
    <Paper
      elevation={0}
      sx={{
        p: padding,
        borderRadius: 4,
        overflow: 'hidden',
        position: 'relative',
        bgcolor: isSolid ? 'rgba(255,255,255,0.9)' : 'transparent',
        background: isDark
          ? styles.darkGlassBg
          : isLight
            ? styles.lightGlassBg
            : 'linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(247,250,255,0.96) 100%)',
        backdropFilter: isDark ? 'blur(22px) saturate(140%)' : 'blur(14px) saturate(135%)',
        WebkitBackdropFilter: isDark ? 'blur(22px) saturate(140%)' : 'blur(14px) saturate(135%)',
        border: isDark ? styles.darkGlassBorder : isLight ? styles.lightGlassBorder : styles.solidBorder,
        boxShadow: isDark ? styles.darkGlassShadow : isLight ? styles.lightGlassShadow : styles.solidShadow,
        color: isDark ? '#fff' : '#0f172a',
        ...sx,
      }}
    >
      {children}
    </Paper>
  );
};

export const GlassFilterBar: React.FC<{
  children: React.ReactNode;
  primaryColor?: string;
  secondaryColor?: string;
  variant?: GlassVariant;
  sx?: Record<string, any>;
}> = ({ children, primaryColor, secondaryColor, variant = 'light', sx }) => (
  <GlassPanel
    primaryColor={primaryColor}
    secondaryColor={secondaryColor}
    variant={variant}
    padding={2}
    sx={{
      mb: 3,
      ...sx,
    }}
  >
    <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} useFlexGap flexWrap="wrap" alignItems={{ md: 'center' }}>
      {children}
    </Stack>
  </GlassPanel>
);

export const TenantPageHero: React.FC<{
  title: string;
  description: string;
  eyebrow?: string;
  primaryColor: string;
  secondaryColor?: string;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  meta?: React.ReactNode;
  children?: React.ReactNode;
}> = ({
  title,
  description,
  eyebrow = 'Tenant Admin',
  primaryColor,
  secondaryColor = '#9c27b0',
  icon,
  actions,
  meta,
  children,
}) => {
  const styles = tenantGlass(primaryColor, secondaryColor);

  return (
    <Box
      sx={{
        position: 'relative',
        overflow: 'hidden',
        borderRadius: 5,
        background: styles.gradient,
        boxShadow: `0 30px 80px ${alpha(primaryColor, 0.3)}`,
        px: { xs: 3, md: 4 },
        py: { xs: 3, md: 4 },
        mb: 3.5,
      }}
    >
      <Box sx={{ position: 'absolute', inset: 0, background: 'radial-gradient(circle at top right, rgba(255,255,255,0.16), transparent 34%)' }} />
      <Box sx={{ position: 'absolute', top: -100, right: -80, width: 280, height: 280, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.08)' }} />
      <Box sx={{ position: 'absolute', bottom: -110, left: -60, width: 240, height: 240, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.06)' }} />

      <Box sx={{ position: 'relative', zIndex: 1 }}>
        <Stack direction={{ xs: 'column', lg: 'row' }} spacing={3} justifyContent="space-between" alignItems={{ lg: 'flex-start' }}>
          <Box sx={{ maxWidth: 760 }}>
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 1.5 }}>
              {icon && (
                <Box
                  sx={{
                    width: 46,
                    height: 46,
                    borderRadius: 3,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    bgcolor: 'rgba(255,255,255,0.14)',
                    border: '1px solid rgba(255,255,255,0.18)',
                    color: '#fff',
                  }}
                >
                  {icon}
                </Box>
              )}
              <StatusBadge label={eyebrow} subtle />
            </Stack>
            <Typography variant="h3" sx={{ color: '#fff', fontWeight: 900, lineHeight: 1.08, letterSpacing: '-0.03em', mb: 1 }}>
              {title}
            </Typography>
            <Typography variant="body1" sx={{ color: 'rgba(255,255,255,0.84)', maxWidth: 720, lineHeight: 1.7 }}>
              {description}
            </Typography>
            {meta && (
              <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mt: 2.25 }}>
                {meta}
              </Stack>
            )}
          </Box>

          {actions && (
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} useFlexGap alignItems={{ lg: 'flex-end' }}>
              {actions}
            </Stack>
          )}
        </Stack>

        {children && <Box sx={{ mt: 3 }}>{children}</Box>}
      </Box>
    </Box>
  );
};

export const MetricCard: React.FC<{
  label: string;
  value: React.ReactNode;
  icon?: React.ReactNode;
  tone?: Tone;
  helper?: React.ReactNode;
  primaryColor?: string;
  secondaryColor?: string;
}> = ({
  label,
  value,
  icon,
  tone = 'default',
  helper,
  primaryColor,
  secondaryColor,
}) => {
  const palette = toneMap[tone];

  return (
    <GlassPanel primaryColor={primaryColor} secondaryColor={secondaryColor} variant="dark" sx={{ height: '100%' }}>
      <Stack spacing={1.5}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
          <Typography variant="overline" sx={{ color: 'rgba(255,255,255,0.82)', fontWeight: 800, letterSpacing: 1.2 }}>
            {label}
          </Typography>
          {icon && (
            <Box sx={{ color: '#fff', bgcolor: alpha(palette.color, 0.22), border: `1px solid ${alpha('#fff', 0.16)}`, borderRadius: 2.5, p: 1 }}>
              {icon}
            </Box>
          )}
        </Stack>
        <Typography variant="h4" sx={{ color: '#fff', fontWeight: 900, lineHeight: 1.05 }}>
          {value}
        </Typography>
        {helper && (
          <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.72)', lineHeight: 1.5 }}>
            {helper}
          </Typography>
        )}
      </Stack>
    </GlassPanel>
  );
};

export const InsightCard: React.FC<{
  title: string;
  description?: React.ReactNode;
  icon?: React.ReactNode;
  badge?: React.ReactNode;
  primaryColor?: string;
  secondaryColor?: string;
  solid?: boolean;
  dark?: boolean;
  children?: React.ReactNode;
}> = ({
  title,
  description,
  icon,
  badge,
  primaryColor = '#1976d2',
  secondaryColor = '#9c27b0',
  solid = true,
  dark = false,
  children,
}) => {
  const variant = dark ? 'dark' : solid ? 'solid' : 'light';
  const titleColor = dark ? 'rgba(255,255,255,0.95)' : '#0f172a';
  const descColor = dark ? 'rgba(255,255,255,0.6)' : '#475569';
  const iconBg = dark
    ? `linear-gradient(135deg, ${alpha(primaryColor, 0.38)}, ${alpha(secondaryColor, 0.28)})`
    : 'rgba(255,255,255,0.64)';
  const iconBorder = dark ? `1px solid ${alpha('#fff', 0.14)}` : `1px solid ${alpha('#64748b', 0.12)}`;
  const iconColor = dark ? '#fff' : 'primary.main';

  return (
    <GlassPanel primaryColor={primaryColor} secondaryColor={secondaryColor} variant={variant} sx={{ height: '100%' }}>
      <Stack spacing={2}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
          <Stack direction="row" spacing={1.25} alignItems="center">
            {icon && (
              <Box
                sx={{
                  width: 40,
                  height: 40,
                  borderRadius: 2.5,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: iconBg,
                  border: iconBorder,
                  color: iconColor,
                }}
              >
                {icon}
              </Box>
            )}
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 800, color: titleColor }}>
                {title}
              </Typography>
              {description && (
                <Typography variant="body2" sx={{ color: descColor, mt: 0.4, lineHeight: 1.6 }}>
                  {description}
                </Typography>
              )}
            </Box>
          </Stack>
          {badge}
        </Stack>
        {children}
      </Stack>
    </GlassPanel>
  );
};

export const DataTableShell: React.FC<{
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  primaryColor?: string;
  secondaryColor?: string;
  children: React.ReactNode;
}> = ({
  title,
  description,
  actions,
  primaryColor,
  secondaryColor,
  children,
}) => (
  <GlassPanel primaryColor={primaryColor} secondaryColor={secondaryColor} variant="solid" sx={{ p: 0 }}>
    <Box sx={{ px: 3, py: 2.5, borderBottom: `1px solid ${alpha('#0f172a', 0.08)}` }}>
      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} justifyContent="space-between" alignItems={{ md: 'center' }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 800, color: '#0f172a' }}>
            {title}
          </Typography>
          {description && (
            <Typography variant="body2" sx={{ color: '#64748b', mt: 0.5 }}>
              {description}
            </Typography>
          )}
        </Box>
        {actions}
      </Stack>
    </Box>
    {children}
  </GlassPanel>
);

export const BrandedEmptyState: React.FC<{
  title: string;
  description: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  primaryColor?: string;
  secondaryColor?: string;
}> = ({
  title,
  description,
  icon,
  action,
  primaryColor,
  secondaryColor,
}) => (
  <GlassPanel primaryColor={primaryColor} secondaryColor={secondaryColor} variant="solid" sx={{ textAlign: 'center' }}>
    <Stack spacing={1.5} alignItems="center" sx={{ py: 2 }}>
      {icon && (
        <Box
          sx={{
            width: 56,
            height: 56,
            borderRadius: 3,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, rgba(25,118,210,0.14), rgba(156,39,176,0.18))',
            color: 'primary.main',
          }}
        >
          {icon}
        </Box>
      )}
      <Typography variant="h6" sx={{ fontWeight: 800, color: '#0f172a' }}>
        {title}
      </Typography>
      <Typography variant="body2" sx={{ color: '#64748b', maxWidth: 480, lineHeight: 1.7 }}>
        {description}
      </Typography>
      {action}
    </Stack>
  </GlassPanel>
);

export const HeroButton: React.FC<React.ComponentProps<typeof Button>> = (props) => {
  const theme = useTheme();

  return (
    <Button
      variant="contained"
      {...props}
      sx={{
        borderRadius: 999,
        px: 2.5,
        py: 1.1,
        fontWeight: 800,
        textTransform: 'none',
        bgcolor: 'rgba(255,255,255,0.96)',
        color: theme.palette.primary.main,
        boxShadow: '0 14px 30px rgba(15, 23, 42, 0.18)',
        '&:hover': {
          bgcolor: '#fff',
        },
        ...props.sx,
      }}
    />
  );
};

export const HeroGhostButton: React.FC<React.ComponentProps<typeof Button>> = (props) => (
  <Button
    variant="outlined"
    {...props}
    sx={{
      borderRadius: 999,
      px: 2.5,
      py: 1.1,
      fontWeight: 800,
      textTransform: 'none',
      color: '#fff',
      borderColor: 'rgba(255,255,255,0.28)',
      bgcolor: 'rgba(255,255,255,0.08)',
      '&:hover': {
        borderColor: 'rgba(255,255,255,0.42)',
        bgcolor: 'rgba(255,255,255,0.14)',
      },
      ...props.sx,
    }}
  />
);

export const lightGlassFieldSx = {
  minWidth: { xs: '100%', md: 180 },
  '& .MuiInputLabel-root': { color: '#475569' },
  '& .MuiInputBase-root': {
    color: '#0f172a',
    bgcolor: 'rgba(255,255,255,0.46)',
  },
  '& .MuiSvgIcon-root': {
    color: '#64748b',
  },
};

export const lightGlassSelectMenuProps = {
  PaperProps: {
    sx: {
      borderRadius: 2.5,
    },
  },
};
