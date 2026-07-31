import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ownerApi } from '../../features/owner/api/ownerApi';
import { useSessionStore } from '../../auth/store/useSessionStore';

export function useTenantManagement() {
  const token = useSessionStore((state) => state.session?.token ?? 'demo-token');
  const queryClient = useQueryClient();
  const tenants = useQuery({ queryKey: ['owner', 'tenants'], queryFn: () => ownerApi.tenants(token) });
  const createTenant = useMutation({
    mutationFn: (payload: Record<string, unknown>) => ownerApi.createTenant(token, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['owner', 'tenants'] })
  });
  const suspendTenant = useMutation({
    mutationFn: ({ tenantId, reason }: { tenantId: string; reason: string }) => ownerApi.suspendTenant(token, tenantId, reason),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['owner', 'tenants'] })
  });
  const updatePolicies = useMutation({
    mutationFn: ({ tenantId, policies }: { tenantId: string; policies: Record<string, unknown> }) => ownerApi.updateTenantPolicies(token, tenantId, policies),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['owner', 'tenants'] })
  });
  return { tenants, createTenant, suspendTenant, updatePolicies };
}
