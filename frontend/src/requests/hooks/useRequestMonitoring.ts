import { useQuery } from '@tanstack/react-query';
import { softwareAdminApi } from '../../features/software-admin/api/softwareAdminApi';
import { useSessionStore } from '../../auth/store/useSessionStore';

export function useRequestMonitoring(softwareId?: string) {
  const token = useSessionStore((state) => state.session?.token ?? 'demo-token');
  return useQuery({
    queryKey: ['requests', softwareId],
    enabled: Boolean(softwareId),
    queryFn: () => softwareAdminApi.listRequests(token, softwareId!, 50),
    refetchInterval: 15_000
  });
}
