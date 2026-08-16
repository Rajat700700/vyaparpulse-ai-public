import { useState } from 'react';
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Logo } from './Logo';
import GuidedTour from './GuidedTour';
import { SHELL } from '../constants/testIds';
import {
    LayoutDashboard, Upload, Radar, ClipboardList, Store, ScrollText, Sparkles,
    Settings, LogOut, Menu, X, ShieldCheck
} from 'lucide-react';

const NAV = [
    { to: '/app/command-centre', label: 'Command Centre', icon: LayoutDashboard, key: 'command' },
    { to: '/app/import', label: 'Data Ingestion', icon: Upload, key: 'import' },
    { to: '/app/recovery-radar', label: 'Recovery Radar', icon: Radar, key: 'radar' },
    { to: '/app/actions', label: 'Action Board', icon: ClipboardList, key: 'actions' },
    { to: '/app/outlets', label: 'Outlet 360', icon: Store, key: 'outlets' },
    { to: '/app/impact-ledger', label: 'Impact Ledger', icon: ScrollText, key: 'ledger' },
    { to: '/app/brief', label: 'Daily Brief', icon: Sparkles, key: 'brief' },
    // /app/settings route intentionally retained (placeholder) but hidden from
    // contest-MVP sidebar to avoid a "features arriving post-contest" surface.
];

export default function AppShell() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const [mobileOpen, setMobileOpen] = useState(false);
    const isDemo = !!user?.is_demo;

    // Route-aware phase label. All Phase 1-4 modules are shipped for the
    // contest MVP; header now reflects the module you are on.
    const path = location.pathname;
    let phaseLabel = 'Contest MVP · Revenue Recovery';
    if (path.includes('/recovery-radar')) phaseLabel = 'Deterministic Recovery Radar';
    else if (path.includes('/import')) phaseLabel = 'Data Ingestion';
    else if (path.includes('/command-centre')) phaseLabel = 'Enterprise Command';
    else if (path.includes('/actions')) phaseLabel = 'Salesperson Action Board';
    else if (path.includes('/impact-ledger')) phaseLabel = 'Verified Impact Ledger';
    else if (path.includes('/outlets')) phaseLabel = 'Outlet 360';
    else if (path.includes('/brief')) phaseLabel = 'AI Daily Recovery Brief';

    const handleLogout = async () => { await logout(); navigate('/'); };

    return (
        <div className="min-h-screen bg-vp-canvas text-vp-navy flex" data-testid={SHELL.root}>
            {/* Sidebar */}
            <aside
                className={`fixed z-40 lg:static inset-y-0 left-0 w-64 bg-white border-r border-vp-border flex-col ${mobileOpen ? 'flex' : 'hidden'} lg:flex`}
                data-testid={SHELL.sidebar}
            >
                <div className="h-16 flex items-center px-5 border-b border-vp-border">
                    <Logo />
                </div>
                <nav className="flex-1 px-3 py-5 space-y-0.5">
                    {NAV.map(({ to, label, icon: Icon, key, phase }) => (
                        <NavLink
                            key={key}
                            to={to}
                            data-testid={SHELL.nav(key)}
                            onClick={() => setMobileOpen(false)}
                            className={({ isActive }) =>
                                `flex items-center justify-between gap-3 px-3 py-2.5 rounded-md text-[13px] font-medium transition-colors ${
                                    isActive
                                        ? 'bg-vp-navy text-white'
                                        : 'text-slate-700 hover:bg-slate-100'
                                }`
                            }
                        >
                            <span className="flex items-center gap-3">
                                <Icon strokeWidth={1.75} className="h-4 w-4" />
                                <span>{label}</span>
                            </span>
                            {phase && (
                                <span className="text-[10px] uppercase tracking-wider text-vp-muted opacity-70">
                                    P{phase}
                                </span>
                            )}
                        </NavLink>
                    ))}
                </nav>
                <div className="p-3 border-t border-vp-border">
                    <div className="flex items-center gap-3 px-3 py-2">
                        <div className="h-8 w-8 rounded-sm bg-vp-navy text-white flex items-center justify-center font-heading text-xs">
                            {(user?.display_name || user?.email || 'U').slice(0, 1).toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="text-[13px] font-medium truncate">{user?.display_name || user?.email}</div>
                            <div className="text-[11px] text-vp-muted truncate">{user?.enterprise_name}</div>
                        </div>
                    </div>
                    <button
                        onClick={handleLogout}
                        data-testid={SHELL.logout}
                        className="mt-2 w-full flex items-center justify-center gap-2 px-3 py-2 rounded-md border border-vp-border text-[13px] text-vp-navy hover:bg-slate-50 transition-colors"
                    >
                        <LogOut strokeWidth={1.75} className="h-3.5 w-3.5" /> Sign out
                    </button>
                </div>
            </aside>

            {/* Main */}
            <div className="flex-1 flex flex-col min-w-0">
                {isDemo && (
                    <div
                        data-testid={SHELL.demoRibbon}
                        className="bg-vp-amberbg border-b border-vp-amber/40 text-vp-navy text-[12px] px-5 py-2 flex items-center gap-2"
                    >
                        <ShieldCheck strokeWidth={1.75} className="h-3.5 w-3.5 text-vp-amber" />
                        <span>
                            <b>Interactive Sandbox.</b> You can browse and map data temporarily.
                            Committing imports and writing production data are disabled — sign in with an
                            Enterprise Admin account to run a real import.
                        </span>
                    </div>
                )}
                <header
                    className="h-16 bg-white border-b border-vp-border flex items-center justify-between px-4 lg:px-8"
                    data-testid={SHELL.header}
                >
                    <button
                        className="lg:hidden p-2 -ml-2"
                        onClick={() => setMobileOpen((v) => !v)}
                        aria-label="Toggle navigation"
                    >
                        {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
                    </button>
                    <div className="hidden lg:block text-[12px] text-vp-muted tracking-[0.18em] uppercase">
                        {user?.enterprise_name} · {user?.role.replace('_', ' ')}
                    </div>
                    <div className="text-[12px] text-vp-muted" data-testid="app-shell-phase-label">
                        <span className="hidden sm:inline">{phaseLabel}</span>
                    </div>
                </header>
                <main className="flex-1 p-4 lg:p-8">
                    <Outlet />
                </main>
                <GuidedTour />
            </div>
        </div>
    );
}
