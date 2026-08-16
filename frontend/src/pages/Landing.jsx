import { Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Logo } from '../components/Logo';
import { LANDING, DEMO } from '../constants/testIds';
import { ArrowRight, TrendingDown, Radar, Store, ScrollText, ShieldCheck, Sparkles } from 'lucide-react';
import { toast } from 'sonner';

const OUTCOMES = [
    { k: 'lapsed', title: 'Lapsed outlets', desc: 'Outlets with no order in 30 days but ≥ 2 invoices in the prior 90.', icon: Store },
    { k: 'declining', title: 'Declining outlets', desc: 'Latest 30-day net sales down ≥ 25% versus the prior 30 days.', icon: TrendingDown },
    { k: 'missed', title: 'Missed order cycle', desc: 'Days since last order exceed 1.5× the outlet\u2019s historical median.', icon: Radar },
    { k: 'whitespace', title: 'SKU whitespace', desc: 'Relevant SKUs bought by comparable peers but absent for this outlet.', icon: Sparkles },
];

export default function LandingPage() {
    const { startSandbox } = useAuth();
    const [busy, setBusy] = useState(false);
    const navigate = useNavigate();

    const handleDemo = async () => {
        setBusy(true);
        try {
            await startSandbox();
            toast.success('Sandbox ready. Redirecting to the Command Centre.');
            navigate('/app/command-centre');
        } catch (e) {
            toast.error('Could not start the sandbox. Please try again.');
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="min-h-screen bg-vp-canvas text-vp-navy">
            {/* Nav */}
            <div className="border-b border-vp-border bg-white/95 backdrop-blur sticky top-0 z-30">
                <div className="max-w-7xl mx-auto px-6 lg:px-10 h-16 flex items-center justify-between">
                    <Logo />
                    <div className="flex items-center gap-3">
                        <Link
                            to="/login"
                            data-testid={LANDING.ctaLogin}
                            className="text-[13px] font-medium text-vp-navy hover:text-vp-navyhover px-3 py-2"
                        >
                            Sign in
                        </Link>
                        <button
                            onClick={handleDemo}
                            data-testid={DEMO.startButton}
                            disabled={busy}
                            className="inline-flex items-center gap-2 bg-vp-navy hover:bg-vp-navyhover text-white text-[13px] font-medium px-4 py-2 rounded-md transition-colors disabled:opacity-60"
                        >
                            {busy ? 'Starting…' : 'Try Live Demo'}
                            <ArrowRight strokeWidth={1.75} className="h-3.5 w-3.5" />
                        </button>
                    </div>
                </div>
            </div>

            {/* Hero */}
            <section className="relative overflow-hidden">
                <div className="absolute inset-0 vp-grid-bg opacity-40 pointer-events-none" />
                <div className="max-w-7xl mx-auto px-6 lg:px-10 pt-20 pb-24 relative">
                    <div className="max-w-3xl">
                        <div className="inline-flex items-center gap-2 text-[11px] tracking-[0.22em] uppercase text-vp-emerald bg-vp-emeraldbg border border-vp-emerald/20 px-3 py-1 rounded-sm mb-6">
                            <span className="h-1.5 w-1.5 rounded-full bg-vp-emerald" />
                            B2B2B Revenue Recovery Copilot
                        </div>
                        <h1
                            data-testid={LANDING.heroTitle}
                            className="font-heading font-black text-4xl sm:text-5xl lg:text-6xl leading-[1.05] tracking-tight text-vp-navy"
                        >
                            Turn dormant sales data into<br />
                            <span className="text-vp-emerald">verified ₹ recovery</span> — outlet by outlet.
                        </h1>
                        <p className="mt-6 text-[17px] leading-relaxed text-vp-muted max-w-2xl">
                            VyaparPulse AI converts ERP and distributor Excel into region-, salesperson-, beat- and
                            SKU-level recovery actions for Indian FMCG enterprises. Every rupee is calculated,
                            explained and verified against a real invoice — not summarised by an LLM.
                        </p>
                        <div className="mt-8 flex flex-wrap items-center gap-3">
                            <button
                                onClick={handleDemo}
                                data-testid={LANDING.ctaDemo}
                                disabled={busy}
                                className="inline-flex items-center gap-2 bg-vp-navy hover:bg-vp-navyhover text-white text-sm font-medium px-5 py-3 rounded-md transition-colors disabled:opacity-60"
                            >
                                {busy ? 'Preparing sandbox…' : 'Open Interactive Sandbox'}
                                <ArrowRight strokeWidth={1.75} className="h-4 w-4" />
                            </button>
                            <Link
                                to="/login"
                                className="inline-flex items-center gap-2 bg-white border border-vp-navy text-vp-navy hover:bg-slate-50 text-sm font-medium px-5 py-3 rounded-md transition-colors"
                            >
                                Enterprise sign in
                            </Link>
                            <div className="flex items-center gap-2 text-[12px] text-vp-muted ml-2">
                                <ShieldCheck strokeWidth={1.75} className="h-3.5 w-3.5 text-vp-emerald" />
                                Safe interactive sandbox — changes reset automatically.
                            </div>
                        </div>
                    </div>

                    {/* Outcome grid */}
                    <div className="mt-20 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {OUTCOMES.map(({ k, title, desc, icon: Icon }, i) => (
                            <div
                                key={k}
                                data-testid={LANDING.featureCard(k)}
                                className="bg-white border border-vp-border rounded-md p-5 hover:-translate-y-1 hover:shadow-md transition-all duration-300 animate-fade-in-up"
                                style={{ animationDelay: `${i * 70}ms` }}
                            >
                                <div className="h-9 w-9 rounded-sm bg-vp-navy text-white flex items-center justify-center mb-4">
                                    <Icon strokeWidth={1.75} className="h-4 w-4" />
                                </div>
                                <div className="font-heading font-semibold text-[15px] text-vp-navy">{title}</div>
                                <div className="mt-1.5 text-[13px] leading-relaxed text-vp-muted">{desc}</div>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Trust strip */}
            <section className="border-t border-vp-border bg-white">
                <div className="max-w-7xl mx-auto px-6 lg:px-10 py-14 grid grid-cols-1 md:grid-cols-3 gap-8">
                    <div>
                        <div className="text-[11px] tracking-[0.22em] uppercase text-vp-muted mb-2">Deterministic core</div>
                        <div className="font-heading font-semibold text-vp-navy text-lg">Every rupee is calculated code, never guessed by an LLM.</div>
                        <p className="mt-2 text-[13px] text-vp-muted">Formulas, thresholds and inputs are stored with every opportunity so a judge can audit each ₹ in one click.</p>
                    </div>
                    <div>
                        <div className="text-[11px] tracking-[0.22em] uppercase text-vp-muted mb-2">Impact Ledger</div>
                        <div className="font-heading font-semibold text-vp-navy text-lg">From estimated opportunity to verified invoice.</div>
                        <p className="mt-2 text-[13px] text-vp-muted">Actions are attributed to matching invoices dated between assignment and completion + 14 days. No back-dated claims.</p>
                    </div>
                    <div>
                        <div className="text-[11px] tracking-[0.22em] uppercase text-vp-muted mb-2">Built for the field</div>
                        <div className="font-heading font-semibold text-vp-navy text-lg">Mobile Action Board in English &amp; हिंदी.</div>
                        <p className="mt-2 text-[13px] text-vp-muted">Salesperson-first UI with next-best actions, due dates and swipe-to-complete on the beat.</p>
                    </div>
                </div>
            </section>

            <footer className="border-t border-vp-border py-8">
                <div className="max-w-7xl mx-auto px-6 lg:px-10 flex flex-col md:flex-row items-center justify-between gap-3 text-[12px] text-vp-muted">
                    <div>© {new Date().getFullYear()} VyaparPulse AI · Contest MVP</div>
                    <div>Deterministic Recovery Engine · AI Brief · Verified Impact Ledger</div>
                </div>
            </footer>
        </div>
    );
}
