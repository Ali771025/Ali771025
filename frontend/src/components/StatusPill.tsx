export function StatusPill({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const tone = normalized.includes('success') || normalized.includes('active') || normalized.includes('approved') || normalized.includes('published')
    ? 'success'
    : normalized.includes('fail') || normalized.includes('reject') || normalized.includes('revoked') || normalized.includes('conflict')
      ? 'danger'
      : normalized.includes('review') || normalized.includes('pending') || normalized.includes('queued')
        ? 'warning'
        : 'neutral';
  return <span className={`status-pill ${tone}`}>{status}</span>;
}
