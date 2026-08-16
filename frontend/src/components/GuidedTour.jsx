import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { X, ArrowRight, ArrowLeft, RotateCcw, PlayCircle } from 'lucide-react';

/*  90-second guided judge demo tour.

    Steps: Command Centre → Recovery Radar → Outlet 360 → Action Board →
    Impact Ledger → verified invoice proof card.

    - Controls: Next / Back / Skip / Restart.
    - localStorage flag `vp_tour_completed` prevents auto-open on return.
    - Also exposes an imperative start via window.dispatchEvent('vp:tour:start').
    - Sandbox reset is preserved by design — tour is purely navigational.
*/

const STEPS = [
    {
        route: '/app/command-centre',
        title: 'Enterprise Command Centre',
        body: 'One glance. Revenue MTD, outlets at risk, deduped estimated opportunity, and verified ₹ — all deterministic. This number reconciles exactly with the Impact Ledger.',
        seconds: 12,
    },
    {
        route: '/app/recovery-radar',
        title: 'Recovery Radar',
        body: 'Every ₹ opportunity is calculated by four deterministic formulas — Lapsed, Declining, Missed Cycle, SKU Whitespace. Filter by distributor, salesperson or type; open any row to see the exact inputs & thresholds.',
        seconds: 15,
    },
    {
        route: '/app/outlets',
        title: 'Outlet 360',
        body: 'Drill into any outlet: 6-month bar trend, SKU mix (last 90 days), cadence, and all opportunities & actions attached. This is the atomic unit of recovery.',
        seconds: 15,
    },
    {
        route: '/app/actions',
        title: 'Salesperson Action Board',
        body: 'Field-first mobile UI. Overdue / Today / Upcoming / Done. Toggle हिंदी. Start an action, then complete it against a real invoice — that is what turns opportunity into recovery.',
        seconds: 15,
    },
    {
        route: '/app/impact-ledger',
        title: 'Impact Ledger — verified ₹',
        body: 'Estimated → Assigned → Completed → Verified. Every verified rupee is invoice-attributed inside [assigned_at, completed_at + 14d] and capped at the invoice value. ₹624.45 locked on the seed.',
        seconds: 18,
    },
    {
        route: '/app/impact-ledger?share=1',
        title: '"Prove it" share card',
        body: 'Click Audit on any row, then Share Proof. That produces a signed, expiring, revocable public link — no login required — so a judge can independently verify one ₹ recovery in isolation.',
        seconds: 15,
    },
];

export default function GuidedTour() {
    const navigate = useNavigate();
    const location = useLocation();
    const [open, setOpen] = useState(false);
    const [step, setStep] = useState(0);

    // Global start listener
    useEffect(() => {
        const start = () => { setStep(0); setOpen(true); };
        window.addEventListener('vp:tour:start', start);
        return () => window.removeEventListener('vp:tour:start', start);
    }, []);

    // Auto-open once per browser for demo/sandbox users
    useEffect(() => {
        if (localStorage.getItem('vp_tour_completed') === '1') return;
        // Only auto-open when we're inside /app/*
        if (location.pathname.startsWith('/app')) {
            const t = setTimeout(() => setOpen(true), 900);
            return () => clearTimeout(t);
        }
    }, [location.pathname]);

    // Navigate to route for current step when it changes.
    useEffect(() => {
        if (!open) return;
        const target = STEPS[step].route;
        if (location.pathname + location.search !== target) {
            navigate(target);
        }
    }, [open, step]); // eslint-disable-line

    if (!open) return (
        <button data-testid="tour-start-button"
            onClick={() => { setStep(0); setOpen(true); }}
            className="fixed bottom-4 right-4 z-40 inline-flex items-center gap-1.5 bg-vp-navy hover:bg-vp-navyhover text-white text-[12px] font-medium rounded-full px-4 py-2 shadow-lg">
            <PlayCircle className="h-4 w-4" /> Start 90-second tour
        </button>
    );

    const s = STEPS[step];
    const finish = (completed) => {
        setOpen(false);
        if (completed) localStorage.setItem('vp_tour_completed', '1');
    };
    const restart = () => { setStep(0); };

    return (
        <>
            <div className="fixed inset-0 z-50 pointer-events-none" data-testid="tour-overlay">
                {/* dim canvas at top only, so users still see the app */}
                <div className="absolute inset-x-0 top-0 h-16 bg-vp-navy/5 pointer-events-none" />
            </div>
            <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 w-[min(560px,92vw)]" data-testid="tour-dialog">
                <div className="bg-white border border-vp-navy/30 rounded-lg shadow-2xl overflow-hidden">
                    <div className="p-4 border-b border-vp-border flex items-center gap-3 bg-vp-navy text-white">
                        <div className="text-[10px] uppercase tracking-[0.22em] opacity-70">Judge demo · 90 seconds</div>
                        <div className="ml-auto text-[10px] tabular-nums opacity-80">Step {step + 1} / {STEPS.length}</div>
                        <button data-testid="tour-close" onClick={() => finish(false)} className="text-white/70 hover:text-white"><X className="h-4 w-4" /></button>
                    </div>
                    <div className="p-5">
                        <div className="font-heading font-bold text-vp-navy text-lg">{s.title}</div>
                        <p className="mt-1.5 text-[13px] text-vp-navy leading-relaxed">{s.body}</p>
                    </div>
                    <div className="px-5 pb-4 flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                            <button data-testid="tour-back" onClick={() => setStep(Math.max(0, step - 1))}
                                disabled={step === 0}
                                className="inline-flex items-center gap-1 text-[12px] px-3 py-1.5 rounded-md border border-vp-border text-vp-navy disabled:opacity-40">
                                <ArrowLeft className="h-3.5 w-3.5" /> Back
                            </button>
                            <button data-testid="tour-restart" onClick={restart}
                                className="inline-flex items-center gap-1 text-[12px] px-3 py-1.5 rounded-md border border-vp-border text-vp-muted">
                                <RotateCcw className="h-3.5 w-3.5" /> Restart
                            </button>
                        </div>
                        <div className="flex items-center gap-2">
                            <button data-testid="tour-skip" onClick={() => finish(true)}
                                className="text-[12px] px-3 py-1.5 text-vp-muted hover:text-vp-navy">
                                Skip
                            </button>
                            {step < STEPS.length - 1 ? (
                                <button data-testid="tour-next" onClick={() => setStep(step + 1)}
                                    className="inline-flex items-center gap-1 text-[12px] px-4 py-1.5 rounded-md bg-vp-navy text-white hover:bg-vp-navyhover">
                                    Next <ArrowRight className="h-3.5 w-3.5" />
                                </button>
                            ) : (
                                <button data-testid="tour-finish" onClick={() => finish(true)}
                                    className="inline-flex items-center gap-1 text-[12px] px-4 py-1.5 rounded-md bg-vp-emerald text-white">
                                    Finish
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}
