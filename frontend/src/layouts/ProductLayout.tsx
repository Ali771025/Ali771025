import { useMemo, type ReactNode } from 'react';
import {
  AppBar,
  Box,
  Chip,
  CssBaseline,
  Divider,
  Drawer,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  Toolbar,
  Typography
} from '@mui/material';
import { environments, pageRegistry } from '../routes/pageRegistry';
import type { EnvironmentKey } from '../shared/contracts/pageBlueprint';

const drawerWidth = 330;

export function ProductLayout({ currentPath, onNavigate, children }: { currentPath: string; onNavigate: (path: string) => void; children: ReactNode }) {
  const grouped = useMemo(() => {
    return environments.map((environment) => ({
      ...environment,
      pages: pageRegistry.filter((page) => page.environment === environment.key)
    }));
  }, []);

  const activePage = pageRegistry.find((page) => page.path === currentPath) ?? pageRegistry[0];

  return (
    <Box dir="rtl" sx={{ display: 'flex', minHeight: '100vh', bgcolor: '#f5f7fb' }}>
      <CssBaseline />
      <AppBar color="inherit" elevation={0} position="fixed" sx={{ borderBottom: '1px solid #e5e7eb', width: { md: `calc(100% - ${drawerWidth}px)` }, mr: { md: `${drawerWidth}px` } }}>
        <Toolbar>
          <Stack direction="row" spacing={1} sx={{ flexGrow: 1 }}>
            <Typography sx={{ fontWeight: 800 }}>سامانه هوشمند گزارش‌ساز و NL2SQL</Typography>
            <Chip color="primary" label="۴ محیط کاربری" size="small" />
            <Chip label={`${pageRegistry.length} صفحه عملیاتی`} size="small" />
          </Stack>
          <Stack direction="row" spacing={1}>
            <Chip label={`صفحه فعال: ${activePage.title}`} variant="outlined" />
            <Chip color="success" label="No raw customer data leaves network" />
          </Stack>
        </Toolbar>
      </AppBar>
      <Drawer
        anchor="right"
        open
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': { width: drawerWidth, boxSizing: 'border-box', borderLeft: '1px solid #e5e7eb' }
        }}
      >
        <Toolbar>
          <Box>
            <Typography sx={{ fontWeight: 900 }}>NL2SQL Ops Console</Typography>
            <Typography color="text.secondary" variant="caption">Clean Frontend navigation map</Typography>
          </Box>
        </Toolbar>
        <Divider />
        <Box sx={{ overflow: 'auto', pb: 4 }}>
          {grouped.map((group) => (
            <Box key={group.key} sx={{ mt: 1 }}>
              <Typography color="text.secondary" sx={{ fontWeight: 800, px: 2, py: 1 }} variant="caption">
                {group.label} ({group.pages.length})
              </Typography>
              <List dense disablePadding>
                {group.pages.map((page) => (
                  <ListItemButton
                    key={page.id}
                    selected={page.path === currentPath}
                    onClick={() => onNavigate(page.path)}
                    sx={{ mx: 1, borderRadius: 2 }}
                  >
                    <ListItemText
                      primary={<Typography sx={{ fontSize: 14, fontWeight: page.path === currentPath ? 800 : 600 }}>{page.title}</Typography>}
                      secondary={<Typography color="text.secondary" sx={{ fontSize: 11 }}>{page.priority} • {page.module}</Typography>}
                    />
                  </ListItemButton>
                ))}
              </List>
            </Box>
          ))}
        </Box>
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, p: 3, width: { md: `calc(100% - ${drawerWidth}px)` } }}>
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
}

export function environmentHome(environment: EnvironmentKey) {
  return pageRegistry.find((page) => page.environment === environment)?.path ?? '/owner/dashboard';
}
