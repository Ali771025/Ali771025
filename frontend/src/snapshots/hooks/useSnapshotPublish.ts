import { useMutation, useQueryClient } from '@tanstack/react-query';
import { softwareAdminApi } from '../../features/software-admin/api/softwareAdminApi';
import { useSessionStore } from '../../auth/store/useSessionStore';

export function useSnapshotPublish() {
  const token = useSessionStore((state) => state.session?.token ?? 'demo-token');
  const queryClient = useQueryClient();
  const publish = useMutation({
    mutationFn: (payload: Record<string, unknown>) => softwareAdminApi.publishSnapshot(token, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge'] });
      queryClient.invalidateQueries({ queryKey: ['software-dashboard'] });
    }
  });
  return { publish };
}
