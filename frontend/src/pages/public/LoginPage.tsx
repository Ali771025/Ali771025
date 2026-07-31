import { useState } from 'react';
import { Card, MetricCard } from '../../shared/ui/Card';
import { authApi } from '../../features/auth/api/authApi';
import type { LoginResponse } from '../../features/auth/model/types';


export function LoginPage({ token, setToken }: { token?: string; setToken: (token?: string) => void }) {
  const [form, setForm] = useState({ username_or_email: 'owner', password: 'OwnerChangeMe!12345', tenant_code: 'municipality-01', remember_me: true });
  const [mfaCode, setMfaCode] = useState('123456');
  const [challengeId, setChallengeId] = useState<string>();
  const [user, setUser] = useState<LoginResponse['user']>();
  const [message, setMessage] = useState<string>('');

  async function login() {
    setMessage('در حال ورود...');
    try {
      const result = await authApi.login(form);
      setUser(result.user);
      setChallengeId(result.challenge_id ?? undefined);
      if (result.tokens?.access_token) setToken(result.tokens.access_token);
      setMessage(result.requires_mfa ? 'کد MFA را وارد کنید. کد نمونه توسعه: 123456' : 'ورود موفق بود.');
    } catch (error) {
      setMessage(`خطا در ورود: ${JSON.stringify(error)}`);
    }
  }

  async function verifyMfa() {
    setMessage('در حال بررسی MFA...');
    const result = await authApi.verifyMfa({ challenge_id: challengeId, otp_code: mfaCode });
    if (result.tokens?.access_token) setToken(result.tokens.access_token);
    setMessage(result.verified ? 'MFA تأیید شد.' : 'MFA رد شد.');
  }

  return (
    <div className="page-grid two">
      <Card title="ورود به سامانه" subtitle="ورود به پنل متناسب با نقش، صدور Access Token و ثبت Audit Log">
        <div className="form-grid">
          <label>نام کاربری یا ایمیل<input value={form.username_or_email} onChange={(e) => setForm({ ...form, username_or_email: e.target.value })} /></label>
          <label>رمز عبور<input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
          <label>کد سازمان / Tenant<input value={form.tenant_code} onChange={(e) => setForm({ ...form, tenant_code: e.target.value })} /></label>
          <label className="checkbox"><input type="checkbox" checked={form.remember_me} onChange={(e) => setForm({ ...form, remember_me: e.target.checked })} /> مرا به خاطر بسپار</label>
          <button className="primary" onClick={login}>ورود</button>
        </div>
        {challengeId && (
          <div className="mfa-box">
            <label>کد OTP / Authenticator<input value={mfaCode} onChange={(e) => setMfaCode(e.target.value)} /></label>
            <button onClick={verifyMfa}>تأیید MFA</button>
          </div>
        )}
        {message && <p className="message">{message}</p>}
      </Card>

      <Card title="پروفایل و امنیت حساب" subtitle="MFA، نشست‌ها، آخرین ورود و ابطال نشست‌های دیگر">
        <div className="metrics-grid">
          <MetricCard label="وضعیت Token" value={token ? 'فعال' : 'ندارد'} />
          <MetricCard label="CAPTCHA" value="پس از ۳ ورود ناموفق" />
          <MetricCard label="Audit Log" value="فعال" />
        </div>
        {user && (
          <div className="profile-panel">
            <strong>{user.full_name ?? user.username}</strong>
            <span>نقش‌ها: {user.roles.join('، ')}</span>
            <span>مجوزها: {user.permissions.slice(0, 6).join('، ')}{user.permissions.length > 6 ? ' ...' : ''}</span>
          </div>
        )}
      </Card>
    </div>
  );
}
