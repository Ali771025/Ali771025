import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { softwareAdminApi } from '../../features/software-admin/api/softwareAdminApi';
import { useSessionStore } from '../../auth/store/useSessionStore';

export function useKnowledgeWorkflow(softwareId?: string, versionId?: string) {
  const token = useSessionStore((state) => state.session?.token ?? 'demo-token');
  const queryClient = useQueryClient();
  const documents = useQuery({
    queryKey: ['knowledge', softwareId, versionId],
    enabled: Boolean(softwareId),
    queryFn: () => softwareAdminApi.listKnowledge(token, softwareId!, versionId)
  });
  const upload = useMutation({
    mutationFn: (payload: Record<string, unknown>) => softwareAdminApi.uploadKnowledge(token, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['knowledge'] })
  });
  const standardize = useMutation({
    mutationFn: (payload: Record<string, unknown>) => softwareAdminApi.standardizeKnowledge(token, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['knowledge'] })
  });
  return { documents, upload, standardize };
}
