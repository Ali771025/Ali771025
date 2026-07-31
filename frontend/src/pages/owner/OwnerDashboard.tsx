import { useEffect, useState } from 'react';
import { Card, MetricCard } from '../../components/Card';
import { DataTable } from '../../components/DataTable';
import { StatusPill } from '../../components/StatusPill';
import { api } from '../../lib/api';

type Dashboard = { metrics: { label: string; value: string | number }[]; charts: Record<string, unknown>; alerts: { severity: string; message: string }[] };
type Row = Record<string, unknown>;

export function OwnerDashboard({ token }: { token?: string }) {
  const [dashboard, setDashboard] = useState<Dashboard>();
  const [tenants, setTenants] = useState<Row[]>([]);
  const [models, setModels] = useState<Row[]>([]);
  const [audit, setAudit] = useState<Row[]>([]);
  const [message, setMessage] = useState('');
  const [manager, setManager] = useState({ username: 'new-manager', email: 'manager@example.local', tenant_id: '', first_name: 'مدیر', last_name: 'جدید' });
  const [tenant, setTenant] = useState({ code: 'municipality-new', name: 'شهرداری جدید' });

  async function load() {
    if (!token) return;
    setMessage('در حال دریافت اطلاعات مالک...');
    try {
      const [dash, tenantsResult, modelsResult, auditResult] = await Promise.all([
        api<Dashboard>('/owner/dashboard', {}, token),
        api<Row[]>('/owner/tenants', {}, token),
        api<Row[]>('/owner/models', {}, token),
        api<Row[]>('/owner/audit-logs?limit=20', {}, token)
      ]);
      setDashboard(dash);
      setTenants(tenantsResult);
      setModels(modelsResult);
      setAudit(auditResult);
      setMessage('به‌روز شد.');
    } catch (error) {
      setMessage(`برای مشاهده پنل مالک با کاربر owner وارد شوید. ${JSON.stringify(error)}`);
    }
  }

  useEffect(() => { void load(); }, [token]);

  async function createManager() {
    if (!token) return;
    const payload = { ...manager, roles: ['software_admin'], scopes: ['commission100.read'], temporary_password: 'AdminChangeMe!12345', mfa_required: true };
    await api('/owner/managers', { method: 'POST', body: JSON.stringify(payload) }, token);
    setMessage('مدیر نرم‌افزار ایجاد شد.');
  }

  async function createTenant() {
    if (!token) return;
    await api('/owner/tenants', { method: 'POST', body: JSON.stringify({ ...tenant, cloud_model_policy: 'restricted', log_retention_days: 365 }) }, token);
    setMessage('Tenant ایجاد شد.');
    await load();
  }

  async function testFirstModel() {
    if (!token || !models[0]) return;
    await api(`/owner/models/${models[0].id}/test`, { method: 'POST', body: JSON.stringify({}) }, token);
    setMessage('تست سلامت مدل انجام شد.');
    await load();
  }

  return (
    <div className="stack">
      <Card title="داشبورد مدیریتی مالک" subtitle="درخواست، مصرف Token، هزینه، Cache، Latency، رخدادهای امنیتی و سلامت مدل‌ها" actions={<button onClick={load}>به‌روزرسانی</button>}>
        <div className="metrics-grid">
          {(dashboard?.metrics ?? []).map((metric) => <MetricCard key={metric.label} label={metric.label} value={metric.value} />)}
        </div>
        {dashboard?.alerts.map((alert) => <p key={alert.message} className="message">{alert.message}</p>)}
      </Card>

      <div className="page-grid two">
        <Card title="مدیریت مدیران نرم‌افزار" subtitle="ایجاد/ویرایش، الزام MFA، سقف مصرف، ابطال نشست‌ها و مشاهده فعالیت">
          <div className="form-grid compact">
            <input placeholder="نام کاربری" value={manager.username} onChange={(e) => setManager({ ...manager, username: e.target.value })} />
            <input placeholder="ایمیل" value={manager.email} onChange={(e) => setManager({ ...manager, email: e.target.value })} />
            <input placeholder="Tenant ID" value={manager.tenant_id} onChange={(e) => setManager({ ...manager, tenant_id: e.target.value })} />
            <button className="primary" onClick={createManager}>ایجاد مدیر</button>
          </div>
        </Card>
        <Card title="مدیریت سازمان‌ها و Tenantها" subtitle="سیاست Cloud، Retention، سقف مصرف و وضعیت امنیتی">
          <div className="form-grid compact">
            <input placeholder="کد یکتا" value={tenant.code} onChange={(e) => setTenant({ ...tenant, code: e.target.value })} />
            <input placeholder="نام سازمان" value={tenant.name} onChange={(e) => setTenant({ ...tenant, name: e.target.value })} />
            <button className="primary" onClick={createTenant}>ایجاد Tenant</button>
          </div>
        </Card>
      </div>

      <Card title="Tenantها">
        <DataTable rows={tenants} columns={[{ key: 'code', title: 'کد' }, { key: 'name', title: 'نام' }, { key: 'cloud_model_policy', title: 'سیاست Cloud' }, { key: 'status', title: 'وضعیت', render: (row) => <StatusPill status={String(row.status)} /> }]} />
      </Card>

      <Card title="مدل‌های هوش مصنوعی و Model Router" actions={<button onClick={testFirstModel}>تست مدل اول</button>}>
        <DataTable rows={models} columns={[{ key: 'provider', title: 'Provider' }, { key: 'name', title: 'نام مدل' }, { key: 'hosting_type', title: 'محلی/ابری' }, { key: 'status', title: 'وضعیت', render: (row) => <StatusPill status={String(row.status)} /> }]} />
      </Card>

      <Card title="Audit Log و رخدادهای امنیتی" subtitle="Token و API Key کامل Redact می‌شوند.">
        <DataTable rows={audit} columns={[{ key: 'created_at', title: 'زمان' }, { key: 'actor_id', title: 'Actor' }, { key: 'action', title: 'Action' }, { key: 'severity', title: 'شدت', render: (row) => <StatusPill status={String(row.severity)} /> }]} />
      </Card>
      {message && <p className="message sticky">{message}</p>}
    </div>
  );
}
