import { useEffect, useMemo, useState } from 'react';
import { Card, MetricCard } from '../../shared/ui/Card';
import { DataTable } from '../../shared/ui/DataTable';
import { StatusPill } from '../../shared/ui/StatusPill';
import { softwareAdminApi } from '../../features/software-admin/api/softwareAdminApi';
import type { Row, SoftwareDashboard as Dashboard } from '../../features/software-admin/model/types';

export function SoftwareAdminDashboard({ token }: { token?: string }) {
  const [dashboard, setDashboard] = useState<Dashboard>();
  const [software, setSoftware] = useState<Row[]>([]);
  const [versions, setVersions] = useState<Row[]>([]);
  const [documents, setDocuments] = useState<Row[]>([]);
  const [requests, setRequests] = useState<Row[]>([]);
  const [apiKeys, setApiKeys] = useState<Row[]>([]);
  const [goldTests, setGoldTests] = useState<Row[]>([]);
  const [selectedSoftwareId, setSelectedSoftwareId] = useState('');
  const [selectedVersionId, setSelectedVersionId] = useState('');
  const [message, setMessage] = useState('');
  const selectedSoftware = useMemo(() => software.find((item) => item.id === selectedSoftwareId), [software, selectedSoftwareId]);
  const selectedVersion = useMemo(() => versions.find((item) => item.id === selectedVersionId), [versions, selectedVersionId]);

  const [softwareForm, setSoftwareForm] = useState({ code: 'my-app', name: 'نرم‌افزار من', database_dialect: 'T-SQL', default_schema: 'dbo' });
  const [versionForm, setVersionForm] = useState({ version_number: '1.0.0', title: 'نسخه اولیه', build_number: 'build-001' });
  const [knowledgeForm, setKnowledgeForm] = useState({ document_type: 'ddl', title: 'DDL پرونده ماده ۱۰۰', content: 'CREATE TABLE dbo.Commission100Cases (CaseNo NVARCHAR(50), RegionCode NVARCHAR(10), CreatedAt DATETIME, Status NVARCHAR(50));' });
  const [userForm, setUserForm] = useState({ external_user_id: 'external-1', username: 'new-report-user', email: 'user@example.local', scopes: 'commission100.read' });
  const [goldQuestion, setGoldQuestion] = useState('آخرین پرونده‌های ماده ۱۰۰ را نشان بده');

  async function load() {
    if (!token) return;
    try {
      const dash = await softwareAdminApi.dashboard(token);
      const sw = await softwareAdminApi.listSoftware(token);
      setDashboard(dash);
      setSoftware(sw);
      const firstSoftware = selectedSoftwareId || String(sw[0]?.id ?? '');
      setSelectedSoftwareId(firstSoftware);
      if (firstSoftware) {
        const versionsResult = await softwareAdminApi.listVersions(token, firstSoftware);
        setVersions(versionsResult);
        const firstVersion = selectedVersionId || String(versionsResult[0]?.id ?? '');
        setSelectedVersionId(firstVersion);
        const docs = await softwareAdminApi.listKnowledge(token, firstSoftware, firstVersion);
        setDocuments(docs);
        const req = await softwareAdminApi.listRequests(token, firstSoftware, 20);
        setRequests(req);
        if (firstVersion) {
          const gold = await softwareAdminApi.listGoldTests(token, firstSoftware, firstVersion);
          setGoldTests(gold);
        }
      }
      const keys = await softwareAdminApi.listApiKeys(token);
      setApiKeys(keys);
      setMessage('داشبورد مدیر نرم‌افزار به‌روزرسانی شد.');
    } catch (error) {
      setMessage(`برای مشاهده این پنل با owner یا software-admin وارد شوید. ${JSON.stringify(error)}`);
    }
  }

  useEffect(() => { void load(); }, [token]);

  async function createSoftware() {
    if (!token) return;
    await softwareAdminApi.createSoftware(token, { ...softwareForm, product_type: 'standalone', access_policy: { max_rows: 20, timeout_seconds: 10 } });
    await load();
  }

  async function createVersion() {
    if (!token || !selectedSoftwareId) return;
    await softwareAdminApi.createVersion(token, { ...versionForm, software_id: selectedSoftwareId, database_dialect: 'T-SQL', status: 'draft' });
    await load();
  }

  async function uploadKnowledge() {
    if (!token || !selectedSoftwareId || !selectedVersionId) return;
    await softwareAdminApi.uploadKnowledge(token, { ...knowledgeForm, software_id: selectedSoftwareId, version_id: selectedVersionId, tags: ['pilot'], sensitivity_level: 'internal' });
    await load();
  }

  async function standardizeKnowledge() {
    if (!token || !selectedSoftwareId || !selectedVersionId || documents.length === 0) return;
    await softwareAdminApi.standardizeKnowledge(token, { document_ids: documents.map((doc) => doc.id), software_id: selectedSoftwareId, version_id: selectedVersionId, standardization_type: 'full', use_llm: false });
    await load();
  }

  async function publishSnapshot() {
    if (!token || !selectedSoftwareId || !selectedVersionId || documents.length === 0) return;
    await softwareAdminApi.publishSnapshot(token, { software_id: selectedSoftwareId, version_id: selectedVersionId, document_ids: documents.map((doc) => doc.id), name: `snapshot-${Date.now()}`, release_note: 'انتشار پایلوت', approvers: ['software-admin'], mandatory_test_result: { passed: true } });
    await load();
  }

  async function createUser() {
    if (!token) return;
    await softwareAdminApi.createUser(token, { ...userForm, scopes: userForm.scopes.split(',').map((item) => item.trim()), roles: ['report_user'], region: ['1', '2'], temporary_password: 'UserChangeMe!12345' });
    setMessage('کاربر نرم‌افزار ایجاد شد.');
  }

  async function issueApiKey() {
    if (!token || !selectedSoftwareId) return;
    const issued = await softwareAdminApi.issueApiKey(token, { name: 'کلید پایلوت', software_id: selectedSoftwareId, version_id: selectedVersionId || null, scopes: ['report.request', 'commission100.read'], environment: 'development', rate_limit: { requests_per_minute: 60 } });
    setMessage(`Secret فقط یک‌بار نمایش داده می‌شود: ${issued.secret} | Prefix: ${issued.prefix}`);
    await load();
  }

  async function createGoldTest() {
    if (!token || !selectedSoftwareId || !selectedVersionId) return;
    await softwareAdminApi.createGoldTest(token, { question: goldQuestion, software_id: selectedSoftwareId, version_id: selectedVersionId, expected_tables: ['Commission100Cases'], expected_intent: 'commission100_cases', test_user_context: { organization: 'municipality-01', region: ['1'], roles: ['report-user'], scopes: ['commission100.read'] } });
    await load();
  }

  return (
    <div className="stack">
      <Card title="داشبورد مدیر نرم‌افزار" subtitle="نسخه فعال، Snapshot، کیفیت دانش، کاربران، کلیدها، مصرف و Connector" actions={<button onClick={load}>به‌روزرسانی</button>}>
        <div className="metrics-grid">
          {(dashboard?.metrics ?? []).map((metric) => <MetricCard key={metric.label} label={metric.label} value={metric.value} />)}
        </div>
      </Card>

      <div className="selector-bar">
        <label>نرم‌افزار<select value={selectedSoftwareId} onChange={(e) => { setSelectedSoftwareId(e.target.value); setSelectedVersionId(''); }}>
          {software.map((item) => <option key={String(item.id)} value={String(item.id)}>{String(item.name)} ({String(item.code)})</option>)}
        </select></label>
        <label>نسخه<select value={selectedVersionId} onChange={(e) => setSelectedVersionId(e.target.value)}>
          {versions.map((item) => <option key={String(item.id)} value={String(item.id)}>{String(item.version_number)}</option>)}
        </select></label>
        <span>{selectedSoftware ? `Dialect: ${String(selectedSoftware.database_dialect)}` : ''} {selectedVersion ? ` | وضعیت نسخه: ${String(selectedVersion.status)}` : ''}</span>
      </div>

      <div className="page-grid two">
        <Card title="تعریف نرم‌افزار" subtitle="کد یکتا، Dialect، Schema، سیاست دسترسی و مصرف">
          <div className="form-grid compact">
            <input value={softwareForm.code} onChange={(e) => setSoftwareForm({ ...softwareForm, code: e.target.value })} />
            <input value={softwareForm.name} onChange={(e) => setSoftwareForm({ ...softwareForm, name: e.target.value })} />
            <input value={softwareForm.database_dialect} onChange={(e) => setSoftwareForm({ ...softwareForm, database_dialect: e.target.value })} />
            <button className="primary" onClick={createSoftware}>ثبت نرم‌افزار</button>
          </div>
        </Card>
        <Card title="مدیریت نسخه‌های نرم‌افزار" subtitle="draft / review / approved / active / obsolete">
          <div className="form-grid compact">
            <input value={versionForm.version_number} onChange={(e) => setVersionForm({ ...versionForm, version_number: e.target.value })} />
            <input value={versionForm.title} onChange={(e) => setVersionForm({ ...versionForm, title: e.target.value })} />
            <input value={versionForm.build_number} onChange={(e) => setVersionForm({ ...versionForm, build_number: e.target.value })} />
            <button className="primary" onClick={createVersion}>ثبت نسخه</button>
          </div>
        </Card>
      </div>

      <Card title="مخزن دانش نسخه‌ای" subtitle="DDL، روابط Join، فرهنگ اصطلاحات، قواعد کسب‌وکار، Query تأییدشده و تست طلایی" actions={<><button onClick={standardizeKnowledge}>استانداردسازی</button><button className="primary" onClick={publishSnapshot}>انتشار Snapshot</button></>}>
        <div className="form-grid">
          <input value={knowledgeForm.title} onChange={(e) => setKnowledgeForm({ ...knowledgeForm, title: e.target.value })} />
          <select value={knowledgeForm.document_type} onChange={(e) => setKnowledgeForm({ ...knowledgeForm, document_type: e.target.value })}>
            <option value="ddl">DDL</option><option value="business_rule">قاعده کسب‌وکار</option><option value="approved_query">Query تأییدشده</option><option value="gold_test">تست طلایی</option>
          </select>
          <textarea value={knowledgeForm.content} onChange={(e) => setKnowledgeForm({ ...knowledgeForm, content: e.target.value })} />
          <button className="primary" onClick={uploadKnowledge}>بارگذاری/ثبت دانش</button>
        </div>
        <DataTable rows={documents} columns={[{ key: 'title', title: 'عنوان' }, { key: 'document_type', title: 'نوع' }, { key: 'quality_score', title: 'کیفیت' }, { key: 'approval_status', title: 'وضعیت', render: (row) => <StatusPill status={String(row.approval_status)} /> }]} />
      </Card>

      <div className="page-grid two">
        <Card title="مدیریت کاربران نرم‌افزار و نقش‌ها">
          <div className="form-grid compact">
            <input value={userForm.external_user_id} onChange={(e) => setUserForm({ ...userForm, external_user_id: e.target.value })} />
            <input value={userForm.username} onChange={(e) => setUserForm({ ...userForm, username: e.target.value })} />
            <input value={userForm.email} onChange={(e) => setUserForm({ ...userForm, email: e.target.value })} />
            <input value={userForm.scopes} onChange={(e) => setUserForm({ ...userForm, scopes: e.target.value })} />
            <button className="primary" onClick={createUser}>ایجاد کاربر</button>
          </div>
        </Card>
        <Card title="مدیریت API Key" subtitle="Secret فقط یک‌بار نمایش داده می‌شود؛ Rotation و ابطال پشتیبانی شده است." actions={<button className="primary" onClick={issueApiKey}>صدور کلید</button>}>
          <DataTable rows={apiKeys} columns={[{ key: 'name', title: 'نام' }, { key: 'prefix', title: 'Prefix' }, { key: 'environment', title: 'محیط' }, { key: 'status', title: 'وضعیت', render: (row) => <StatusPill status={String(row.status)} /> }]} />
        </Card>
      </div>

      <Card title="مانیتورینگ درخواست‌ها و جزئیات" subtitle="SQL تولیدشده، Validator Result، Confidence، Token، هزینه و Cache؛ Chain-of-Thought نمایش داده نمی‌شود.">
        <DataTable rows={requests} columns={[{ key: 'created_at', title: 'زمان' }, { key: 'user_id', title: 'کاربر' }, { key: 'status', title: 'وضعیت', render: (row) => <StatusPill status={String(row.status)} /> }, { key: 'confidence_level', title: 'Confidence' }, { key: 'cache_hit', title: 'Cache' }]} />
      </Card>

      <Card title="تست طلایی و محیط آزمایش" subtitle="حداقل ۲۰ سؤال طلایی کارفرما در این قسمت تعریف می‌شود.">
        <div className="form-grid compact">
          <input value={goldQuestion} onChange={(e) => setGoldQuestion(e.target.value)} />
          <button className="primary" onClick={createGoldTest}>افزودن تست طلایی</button>
        </div>
        <DataTable rows={goldTests} columns={[{ key: 'question', title: 'سؤال' }, { key: 'expected_intent', title: 'Intent' }, { key: 'last_run_result', title: 'آخرین اجرا', render: (row) => <code>{JSON.stringify(row.last_run_result)}</code> }]} />
      </Card>

      {message && <p className="message sticky">{message}</p>}
    </div>
  );
}
