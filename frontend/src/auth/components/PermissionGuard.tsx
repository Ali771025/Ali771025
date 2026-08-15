import type { ReactNode } from 'react';
import { Alert, Button, Card, CardContent, Stack, Typography } from '@mui/material';
import { effectivePermissionSummary, hasPermission } from '../model/accessControl';
import { useSessionStore } from '../store/useSessionStore';

export function PermissionGuard({ required, children }: { required: string[]; children: ReactNode }) {
  const session = useSessionStore((state) => state.session);
  const setSession = useSessionStore((state) => state.setSession);
  const allowed = hasPermission(session, required);
  if (allowed) return <>{children}</>;
  return (
    <Card variant="outlined">
      <CardContent>
        <Stack spacing={2}>
          <Alert severity="error">Forbidden — سطح دسترسی لازم وجود ندارد. Request ID: ui-forbidden-{Date.now()}</Alert>
          <Typography>مجوزهای لازم: {required.join('، ')}</Typography>
          <Typography color="text.secondary">مجوز مؤثر فعلی: {effectivePermissionSummary(session)}</Typography>
          <Button onClick={() => setSession({ userId: 'owner', tenantId: 'municipality-01', roles: ['system_owner'], permissions: ['*'], scopes: ['*'] })} variant="contained">
            فعال‌سازی نشست Demo مالک سامانه
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}
