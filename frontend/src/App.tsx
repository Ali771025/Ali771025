import { useState } from 'react';
import { Shell, type Workspace } from './layouts/Shell';
import { LoginPage } from './pages/public/LoginPage';
import { OwnerDashboard } from './pages/owner/OwnerDashboard';
import { SoftwareAdminDashboard } from './pages/software/SoftwareAdminDashboard';
import { OnPremReportConsole } from './pages/onprem/OnPremReportConsole';
import { ConnectorConsole } from './pages/connector/ConnectorConsole';

function App() {
  const [workspace, setWorkspace] = useState<Workspace>('public');
  const [token, setToken] = useState<string | undefined>(() => localStorage.getItem('access_token') ?? undefined);

  function persistToken(next?: string) {
    setToken(next);
    if (next) localStorage.setItem('access_token', next);
    else localStorage.removeItem('access_token');
  }

  return (
    <Shell workspace={workspace} onWorkspaceChange={setWorkspace} token={token}>
      <header className="hero">
        <div>
          <span className="eyebrow">RFP سامانه هوشمند گزارش‌ساز و NL2SQL</span>
          <h1>چهار محیط کاربری محصول</h1>
          <p>پنل مالک سامانه، پنل مدیر نرم‌افزار، رابط کاربر On-Premise مانند بهساز و کنسول فنی Connector؛ مستقل از RFP Learning Center.</p>
        </div>
        <div className="hero-actions">
          <button onClick={() => persistToken(undefined)}>خروج / حذف Token</button>
          <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">OpenAPI</a>
        </div>
      </header>
      {workspace === 'public' && <LoginPage token={token} setToken={persistToken} />}
      {workspace === 'owner' && <OwnerDashboard token={token} />}
      {workspace === 'software' && <SoftwareAdminDashboard token={token} />}
      {workspace === 'onprem' && <OnPremReportConsole />}
      {workspace === 'connector' && <ConnectorConsole token={token} />}
    </Shell>
  );
}

export default App;
