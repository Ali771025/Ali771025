import type { ReactNode } from 'react';
import { Activity, Database, KeyRound, LayoutDashboard, Lock, Network, ServerCog, ShieldCheck } from 'lucide-react';

export type Workspace = 'public' | 'owner' | 'software' | 'onprem' | 'connector';

const nav: { id: Workspace; label: string; icon: ReactNode; description: string }[] = [
  { id: 'public', label: 'عمومی و امنیت', icon: <Lock size={18} />, description: 'ورود، MFA، پروفایل' },
  { id: 'owner', label: 'پنل مالک سامانه', icon: <ShieldCheck size={18} />, description: 'Tenant، RBAC، مدل، مالی' },
  { id: 'software', label: 'پنل مدیر نرم‌افزار', icon: <LayoutDashboard size={18} />, description: 'دانش، Snapshot، کاربران' },
  { id: 'onprem', label: 'رابط داخل بهساز', icon: <Database size={18} />, description: 'درخواست گزارش و بازخورد' },
  { id: 'connector', label: 'کنسول Connector', icon: <ServerCog size={18} />, description: 'سلامت و اجرای محلی' }
];

export function Shell({ workspace, onWorkspaceChange, children, token }: { workspace: Workspace; onWorkspaceChange: (workspace: Workspace) => void; children: ReactNode; token?: string }) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Network size={28} />
          <div>
            <strong>NL2SQL Report Builder</strong>
            <span>سامانه هوشمند گزارش‌ساز</span>
          </div>
        </div>
        <nav>
          {nav.map((item) => (
            <button key={item.id} className={workspace === item.id ? 'active' : ''} onClick={() => onWorkspaceChange(item.id)}>
              {item.icon}
              <span>{item.label}<small>{item.description}</small></span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <Activity size={16} />
          <span>{token ? 'JWT فعال است' : 'ابتدا وارد شوید یا از API عمومی پایلوت استفاده کنید'}</span>
        </div>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  );
}
