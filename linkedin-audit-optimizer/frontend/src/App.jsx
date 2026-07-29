import { useState } from 'react';
import ProfileAudit from './pages/ProfileAudit.jsx';

const NAV_ITEMS = [
  { key: 'profile-audit', label: 'Profile Audit', enabled: true },
  { key: 'content-optimizer', label: 'Content Optimizer', enabled: false },
  { key: 'redesign', label: 'Redesign & Restructure', enabled: false },
];

export default function App() {
  const [activeSection, setActiveSection] = useState('profile-audit');

  return (
    <div className="min-h-screen flex">
      <aside className="w-64 shrink-0 border-r border-slate-200 bg-white p-4 hidden sm:block">
        <div className="text-lg font-semibold text-slate-900 mb-6 px-2">
          LinkedIn Audit Optimizer
        </div>
        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              disabled={!item.enabled}
              onClick={() => setActiveSection(item.key)}
              className={[
                'w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                item.enabled
                  ? activeSection === item.key
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-700 hover:bg-slate-100'
                  : 'text-slate-400 cursor-not-allowed',
              ].join(' ')}
              title={item.enabled ? undefined : 'Coming soon'}
            >
              {item.label}
              {!item.enabled && (
                <span className="ml-2 text-xs font-normal text-slate-400">soon</span>
              )}
            </button>
          ))}
        </nav>
      </aside>

      <main className="flex-1 min-w-0">
        {activeSection === 'profile-audit' && <ProfileAudit />}
      </main>
    </div>
  );
}
