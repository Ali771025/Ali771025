import { useEffect, useState } from 'react';
import { Card, MetricCard } from '../../components/Card';
import { DataTable } from '../../components/DataTable';
import { StatusPill } from '../../components/StatusPill';
import { api } from '../../lib/api';

type Row = Record<string, unknown>;

type Connector = {
  id: string;
  software_id: string;
  version_id?: string | null;
  registration_status: string;
  policy_hash: string;
  central_connection_status: Record<string, unknown>;
  database_connection_status: Record<string, unknown>;
  last_heartbeat_at?: string | null;
};

export function ConnectorConsole({ token }: { token?: string }) {
  const [software, setSoftware] = useState<Row[]>([]);
  const [connector, setConnector] = useState<Connector>();
  const [message, setMessage] = useState('');
  const [form, setForm] = useState({ connector_id: 'connector-behsaz-01', software_id: '', central_api_url: 'http://backend:8000/api/v1', encrypted_connection_string: 'vault://customer/behsaz/readonly', readonly_account: 'behsaz_readonly', policy_version: 'pilot-1', max_rows: 20 });
  const [sql, setSql] = useState('SELECT TOP (@limit) CaseNo, RegionCode, CreatedAt, Status FROM dbo.Commission100Cases ORDER BY CreatedAt DESC');
  const [result, setResult] = useState<Row[]>([]);

  async function loadSoftware() {
    if (!token) return;
    const sw = await api<Row[]>('/software-admin/software', {}, token);
    setSoftware(sw);
    setForm((old) => ({ ...old, software_id: old.software_id || String(sw[0]?.id ?? '') }));
  }

  useEffect(() => { void loadSoftware(); }, [token]);

  async function register() {
    if (!token) return;
    const registered = await api<Connector>('/connectors/register', {
      method: 'POST',
      body: JSON.stringify({ ...form, database_dialect: 'T-SQL', timeout_seconds: 10, allowed_views: ['dbo.Commission100Cases'] })
    }, token);
    setConnector(registered);
    setMessage('Connector ثبت و Policy Hash صادر شد.');
  }

  async function heartbeat() {
    if (!token || !connector) return;
    const health = await api<Connector>(`/connectors/${connector.id}/health`, {}, token);
    setConnector(health);
    setMessage('Heartbeat و تست ارتباط ثبت شد.');
  }

  async function execute() {
    if (!token || !connector) return;
    const response = await api<Row>(`/connectors/${connector.id}/execute`, {
      method: 'POST',
      body: JSON.stringify({ sql, parameters: { limit: 20 }, ttl: 60, signature: 'signed-by-central-api', policy_hash: connector.policy_hash, audit_id: `audit-${Date.now()}` })
    }, token);
    setResult([response]);
    setMessage('اعتبارسنجی/اجرای محلی انجام شد؛ متادیتا بدون داده واقعی آماده ارسال است.');
  }

  return (
    <div className="stack">
      <Card title="ثبت و پیکربندی Connector" subtitle="گواهی TLS/mTLS، Credential امن، Connection String رمزگذاری‌شده، حساب Read-only و Policy Hash">
        <div className="form-grid">
          <label>Connector ID<input value={form.connector_id} onChange={(e) => setForm({ ...form, connector_id: e.target.value })} /></label>
          <label>نرم‌افزار<select value={form.software_id} onChange={(e) => setForm({ ...form, software_id: e.target.value })}>{software.map((item) => <option key={String(item.id)} value={String(item.id)}>{String(item.name)}</option>)}</select></label>
          <label>API مرکزی<input value={form.central_api_url} onChange={(e) => setForm({ ...form, central_api_url: e.target.value })} /></label>
          <label>Connection String رمزگذاری‌شده<input value={form.encrypted_connection_string} onChange={(e) => setForm({ ...form, encrypted_connection_string: e.target.value })} /></label>
          <label>Read-only Account<input value={form.readonly_account} onChange={(e) => setForm({ ...form, readonly_account: e.target.value })} /></label>
          <label>Policy Version<input value={form.policy_version} onChange={(e) => setForm({ ...form, policy_version: e.target.value })} /></label>
          <button className="primary" onClick={register}>ثبت Connector</button>
        </div>
      </Card>

      {connector && (
        <Card title="سلامت و همگام‌سازی" actions={<button onClick={heartbeat}>Heartbeat</button>}>
          <div className="metrics-grid">
            <MetricCard label="وضعیت ثبت" value={connector.registration_status} />
            <MetricCard label="Policy Hash" value={connector.policy_hash.slice(0, 12)} />
            <MetricCard label="مرکزی" value={String(connector.central_connection_status.status ?? 'unknown')} />
            <MetricCard label="دیتابیس" value={String(connector.database_connection_status.status ?? 'unknown')} />
          </div>
        </Card>
      )}

      {connector && (
        <Card title="اعتبارسنجی و اجرای محلی" subtitle="Connector SQL پارامتری، Signature و Policy Hash را بررسی می‌کند و فقط متادیتای اجرا را ارسال می‌کند." actions={<button className="primary" onClick={execute}>Validate / Execute</button>}>
          <textarea value={sql} onChange={(e) => setSql(e.target.value)} />
          <DataTable rows={result} columns={[{ key: 'validation_result', title: 'نتیجه' }, { key: 'accepted', title: 'قبول شد' }, { key: 'rejection_reason', title: 'علت رد' }, { key: 'execution_metadata', title: 'متادیتا', render: (row) => <code>{JSON.stringify(row.execution_metadata)}</code> }]} />
        </Card>
      )}

      <Card title="چک‌لیست عملیاتی Connector">
        <ul className="check-list">
          <li><StatusPill status="required" /> حساب دیتابیس فقط Read-only باشد.</li>
          <li><StatusPill status="required" /> داده خام گزارش به سرویس مرکزی ارسال یا ذخیره نشود.</li>
          <li><StatusPill status="recommended" /> mTLS و Rotation گواهی برای production فعال شود.</li>
          <li><StatusPill status="required" /> Policy Hash و Signature قبل از اجرا کنترل شود.</li>
        </ul>
      </Card>
      {message && <p className="message sticky">{message}</p>}
    </div>
  );
}
