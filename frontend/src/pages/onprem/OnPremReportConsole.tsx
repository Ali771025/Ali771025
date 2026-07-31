import { useState } from 'react';
import { Card, MetricCard } from '../../shared/ui/Card';
import { DataTable } from '../../shared/ui/DataTable';
import { clientUuid } from '../../shared/api/httpClient';
import { reportApi } from '../../features/reporting/api/reportApi';
import type { ReportResponse } from '../../features/reporting/model/types';


type Row = Record<string, unknown>;

export function OnPremReportConsole() {
  const [question, setQuestion] = useState('آخرین پرونده‌های ماده ۱۰۰ را نشان بده');
  const [outputType, setOutputType] = useState('table');
  const [limit, setLimit] = useState(20);
  const [region, setRegion] = useState('1,2');
  const [response, setResponse] = useState<ReportResponse>();
  const [localRows, setLocalRows] = useState<Row[]>([]);
  const [message, setMessage] = useState('');

  async function submitReport(extra = '') {
    const payload = {
      request_id: clientUuid(),
      software_id: 'behsaz',
      software_version: '12.4.0',
      user_id: 'user-1025',
      question: `${question} ${extra}`.trim(),
      access_context: {
        organization: 'municipality-01',
        region: region.split(',').map((item) => item.trim()).filter(Boolean),
        roles: ['report-user'],
        scopes: ['commission100.read']
      },
      locale: 'fa-IR',
      timezone: 'Asia/Tehran'
    };
    setMessage('در حال تولید SQL پارامتری...');
    const result = await reportApi.generate(payload);
    setResponse(result);
    setLocalRows([]);
    setMessage(result.status === 'success' ? 'SQL تولید شد. اجرای واقعی باید داخل شبکه مشتری و توسط Connector انجام شود.' : 'نیازمند اقدام کاربر.');
  }

  async function simulateLocalExecution() {
    if (!response || response.status !== 'success') return;
    const rows = [
      { CaseNo: '100-1405-0001', RegionCode: '1', CreatedAt: '1405/05/10', Status: 'در حال رسیدگی' },
      { CaseNo: '100-1405-0002', RegionCode: '2', CreatedAt: '1405/05/09', Status: 'صدور رأی' }
    ].slice(0, limit);
    setLocalRows(rows);
    await reportApi.sendExecutionMetadata({ audit_id: response.audit_id, execution_time_ms: 32, row_count: rows.length, display_type: outputType });
    setMessage('نتیجه محلی نمایش داده شد؛ داده خام به سرویس مرکزی ارسال نشد.');
  }

  async function sendFeedback(verdict: 'correct' | 'incorrect' | 'partially_correct') {
    if (!response) return;
    await reportApi.sendFeedback({ audit_id: response.audit_id, verdict, rating: verdict === 'correct' ? 5 : 2, description: 'بازخورد کاربر داخل بهساز', problem_type: verdict === 'correct' ? null : 'wrong_filter', manager_review_requested: verdict !== 'correct' });
    setMessage('Feedback ID ثبت شد و در صورت نیاز به صف بازبینی مدیر ارسال گردید.');
  }

  return (
    <div className="stack">
      <Card title="فرم درخواست گزارش داخل بهساز" subtitle="کاربر فقط شرح فارسی، نوع خروجی و پارامترهای مجاز را می‌بیند؛ request_id، software_id، JWT/API Key مخفی هستند.">
        <div className="form-grid">
          <label>شرح فارسی گزارش<textarea value={question} onChange={(e) => setQuestion(e.target.value)} /></label>
          <label>نوع خروجی ترجیحی<select value={outputType} onChange={(e) => setOutputType(e.target.value)}><option value="auto">خودکار</option><option value="table">جدول</option><option value="text">متن</option></select></label>
          <label>حداکثر رکورد<input type="number" value={limit} onChange={(e) => setLimit(Number(e.target.value))} /></label>
          <label>منطقه/واحد<input value={region} onChange={(e) => setRegion(e.target.value)} /></label>
          <button className="primary" onClick={() => void submitReport()}>ارسال درخواست</button>
        </div>
      </Card>

      {response?.status === 'needs_clarification' && (
        <Card title="فرم تکمیل ابهام" subtitle={response.question}>
          <div className="choice-list">
            {response.options.map((option) => <button key={option} onClick={() => void submitReport(option)}>{option}</button>)}
          </div>
        </Card>
      )}

      {response?.status === 'rejected' && (
        <Card title="درخواست رد شد">
          <div className="rejected"><strong>{response.reason_code}</strong><p>{response.message}</p><small>Audit ID: {response.audit_id}</small></div>
        </Card>
      )}

      {response?.status === 'success' && (
        <Card title="SQL و Policy برگشتی" actions={<button className="primary" onClick={simulateLocalExecution}>شبیه‌سازی اجرای محلی</button>}>
          <div className="metrics-grid">
            <MetricCard label="Confidence" value={`${Math.round(response.confidence.score * 100)}٪ ${response.confidence.level}`} />
            <MetricCard label="Max Rows" value={String(response.policy.max_rows)} />
            <MetricCard label="Timeout" value={`${String(response.policy.timeout_seconds)}s`} />
            <MetricCard label="Audit ID" value={response.audit_id} />
          </div>
          <pre className="code-block">{response.sql}</pre>
          <pre className="code-block">{JSON.stringify(response.parameters, null, 2)}</pre>
        </Card>
      )}

      {localRows.length > 0 && (
        <Card title={response?.status === 'success' ? response.display.title : 'نتیجه گزارش'} subtitle="داده خام فقط داخل شبکه مشتری نمایش داده می‌شود.">
          <DataTable rows={localRows} columns={[{ key: 'CaseNo', title: 'شماره پرونده' }, { key: 'RegionCode', title: 'منطقه' }, { key: 'CreatedAt', title: 'تاریخ' }, { key: 'Status', title: 'وضعیت' }]} />
          <div className="choice-list">
            <button onClick={() => void sendFeedback('correct')}>صحیح</button>
            <button onClick={() => void sendFeedback('partially_correct')}>نسبتاً صحیح</button>
            <button onClick={() => void sendFeedback('incorrect')}>نادرست و ارسال به مدیر</button>
          </div>
        </Card>
      )}

      {message && <p className="message sticky">{message}</p>}
    </div>
  );
}
