import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { connectorApi } from '../../features/connector/api/connectorApi';
import { useSessionStore } from '../../auth/store/useSessionStore';

export function useConnectorHealth(connectorId?: string) {
  const token = useSessionStore((state) => state.session?.token ?? 'demo-token');
  const queryClient = useQueryClient();
  const health = useQuery({
    queryKey: ['connector-health', connectorId],
    enabled: Boolean(connectorId),
    queryFn: () => connectorApi.health(token, connectorId!),
    refetchInterval: 20_000
  });
  const executeValidation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => connectorApi.execute(token, connectorId!, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['connector-health', connectorId] })
  });
  return { health, executeValidation };
}
