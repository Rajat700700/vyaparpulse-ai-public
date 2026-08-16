import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { paiseToCompact } from '../lib/format';
import { Sparkles, Globe, RefreshCw, ShieldCheck, TrendingDown, ClipboardList, AlertTriangle, Loader2, AlertCircle } from 'lucide-react';

export default function DailyBrief() {
    const [data, setData] = useState(null);
    const [lang, setLang] = useState('en');
    const [busy, setBusy] = useState(false);
    const [err, setErr] = useState(null);

    const load = () => {
        setBusy(true);
        setErr(null);
        api.get('/brief/daily')
            .then((r) => setData(r.data))
            .catch((e) => setErr(e?.response?.data?.detail || 'Failed to load brief'))
            .finally(() => setBusy(false));
    };
    useEffect(load, []);

    // --- Cold-load skeleton (no data yet, no error) --------------------
    // Mirrors the final layout so the shift is minimal; role=status +
    // aria-live keep it accessible; never renders stale or zero values.
    if (!data && !err) {
        return (
            <div className="space-y-6" data-testid="brief-page" aria-busy="true">
                <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
                    <div>
                        <div className="text-[11px] tracking-[0.22em] uppercase text-vp-muted font-semibold flex items-center gap-1.5">
                            <Sparkles className="h-3 w-3 text-vp-amber" /> AI Daily Recovery Brief
                        </div>
                        <div className="mt-1 h-9 w-72 bg-slate-200/80 rounded animate-pulse" aria-hidden="true" />
                        <div
                            role="status"
                            aria-live="polite"
                            data-testid="brief-loading-status"
                            className="mt-2 inline-flex items-center gap-2 text-[12px] text-vp-navy bg-vp-amberbg/60 border border-vp-amber/30 rounded-md px-2.5 py-1.5"
                        >
                            <Loader2 className="h-3.5 w-3.5 animate-spin text-vp-amber" />
                            <span>Generating grounded recovery brief… this can take a few seconds while GPT-5.2 explains today&apos;s deterministic metrics.</span>
                        </div>
                    </div>
                    <div className="h-8 w-36 bg-slate-200/70 rounded-md animate-pulse" aria-hidden="true" />
                </div>

                {/* Skeleton summary card */}
                <div className="bg-white border border-vp-border rounded-md p-5 space-y-2" data-testid="brief-loading" aria-hidden="true">
                    <div className="text-[10px] tracking-[0.22em] uppercase text-vp-muted font-semibold">Management summary</div>
                    <div className="h-3.5 w-full bg-slate-100 rounded animate-pulse" />
                    <div className="h-3.5 w-11/12 bg-slate-100 rounded animate-pulse" />
                    <div className="h-3.5 w-9/12 bg-slate-100 rounded animate-pulse" />
                </div>

                {/* Skeleton KPI strip */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3" aria-hidden="true">
                    {[0, 1, 2, 3].map((i) => (
                        <div key={i} className="bg-white border border-vp-border rounded-md p-4">
                            <div className="h-2.5 w-20 bg-slate-100 rounded animate-pulse" />
                            <div className="mt-3 h-6 w-16 bg-slate-200/70 rounded animate-pulse" />
                        </div>
                    ))}
                </div>

                {/* Skeleton priorities */}
                <div className="bg-white border border-vp-border rounded-md p-5 space-y-2.5" aria-hidden="true">
                    <div className="text-[10px] tracking-[0.22em] uppercase text-vp-muted font-semibold mb-1">Top recovery priorities</div>
                    {[0, 1, 2, 3, 4].map((i) => (
                        <div key={i} className="border-l-2 border-vp-amber/40 pl-3">
                            <div className="h-3.5 w-full max-w-2xl bg-slate-100 rounded animate-pulse" />
                        </div>
                    ))}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4" aria-hidden="true">
                    <div className="bg-white border border-vp-border rounded-md p-5 space-y-2">
                        <div className="h-2.5 w-24 bg-slate-100 rounded animate-pulse" />
                        {[0, 1, 2, 3].map((i) => <div key={i} className="h-3 w-4/5 bg-slate-100 rounded animate-pulse" />)}
                    </div>
                    <div className="bg-white border border-vp-border rounded-md p-5 space-y-2">
                        <div className="h-2.5 w-24 bg-slate-100 rounded animate-pulse" />
                        <div className="h-3 w-full bg-slate-100 rounded animate-pulse" />
                        <div className="h-3 w-10/12 bg-slate-100 rounded animate-pulse" />
                    </div>
                </div>
            </div>
        );
    }

    // --- Error state with retry ---------------------------------------
    if (err) {
        return (
            <div className="max-w-3xl space-y-4" data-testid="brief-error" role="alert">
                <div className="bg-vp-redbg border border-vp-red/30 rounded-md p-5 flex items-start gap-3">
                    <AlertCircle className="h-5 w-5 text-vp-red mt-0.5 shrink-0" />
                    <div className="flex-1">
                        <div className="font-heading font-semibold text-vp-navy">Could not generate the brief</div>
                        <p className="mt-1 text-[13px] text-vp-navy leading-relaxed">{String(err)}</p>
                        <p className="mt-2 text-[12px] text-vp-muted">
                            All deterministic ₹ values remain calculated in the backend — the brief endpoint is
                            what failed to respond. Nothing was mutated. Retry or open the Impact Ledger directly.
                        </p>
                        <div className="mt-3 flex items-center gap-2">
                            <button
                                data-testid="brief-retry"
                                onClick={load}
                                disabled={busy}
                                className="inline-flex items-center gap-1.5 text-[12px] bg-vp-navy hover:bg-vp-navyhover text-white rounded-md px-3 py-1.5 disabled:opacity-60"
                            >
                                <RefreshCw className={`h-3.5 w-3.5 ${busy ? 'animate-spin' : ''}`} /> {busy ? 'Retrying…' : 'Retry'}
                            </button>
                            <a
                                href="/app/impact-ledger"
                                className="text-[12px] text-vp-navy underline underline-offset-4"
                            >
                                Open Impact Ledger
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    const view = data[lang];
    const facts = data.facts;
    const src = data.narrative_source;

    return (
        <div className="space-y-6" data-testid="brief-page" aria-busy={busy ? "true" : "false"}>
            <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
                <div>
                    <div className="text-[11px] tracking-[0.22em] uppercase text-vp-muted font-semibold flex items-center gap-1.5">
                        <Sparkles className="h-3 w-3 text-vp-amber" /> AI Daily Recovery Brief
                    </div>
                    <h1 className="mt-1 font-heading font-bold text-3xl text-vp-navy">{view.date_line}</h1>
                    <div className="mt-1.5 text-[11px] text-vp-muted">
                        Narrative source: <b>{src}</b> · every ₹ echoes deterministic backend calculation.
                        {src && src.startsWith('deterministic_fallback') && (
                            <span className="ml-1 text-vp-amber">LLM output failed grounding — using deterministic template.</span>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {busy && (
                        <div
                            role="status"
                            aria-live="polite"
                            data-testid="brief-regenerating-status"
                            className="inline-flex items-center gap-1.5 text-[11px] text-vp-navy bg-vp-amberbg/60 border border-vp-amber/30 rounded-md px-2 py-1.5"
                        >
                            <Loader2 className="h-3 w-3 animate-spin text-vp-amber" />
                            <span>Regenerating brief…</span>
                        </div>
                    )}
                    <button data-testid="brief-lang-toggle"
                        onClick={() => setLang(lang === 'en' ? 'hi' : 'en')}
                        className="inline-flex items-center gap-1.5 text-[12px] bg-white border border-vp-border rounded-md px-3 py-1.5 text-vp-navy">
                        <Globe className="h-3.5 w-3.5" /> {lang === 'en' ? 'हिंदी / Hinglish' : 'English'}
                    </button>
                    <button data-testid="brief-refresh"
                        onClick={load} disabled={busy}
                        className="inline-flex items-center gap-1.5 text-[12px] bg-vp-navy hover:bg-vp-navyhover text-white rounded-md px-3 py-1.5 disabled:opacity-60">
                        <RefreshCw className={`h-3.5 w-3.5 ${busy ? 'animate-spin' : ''}`} /> Regenerate
                    </button>
                </div>
            </div>

            {/* Management summary */}
            <div className="bg-white border border-vp-border rounded-md p-5" data-testid="brief-summary">
                <div className="text-[10px] tracking-[0.22em] uppercase text-vp-muted font-semibold mb-2">
                    Management summary
                </div>
                <p className="text-[15px] leading-relaxed text-vp-navy">{view.management_summary}</p>
            </div>

            {/* Fact-based KPI strip (deterministic, always) */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <FactCard label={lang === 'en' ? 'Open opportunities' : 'खुले अवसर'}
                    value={facts.summary_counts.total_opportunities} icon={TrendingDown} tone="text-vp-amber" testid="brief-kpi-opps" />
                <FactCard label={lang === 'en' ? 'Est. recovery (deduped)' : 'अनुमानित रिकवरी (deduped)'}
                    value={paiseToCompact(facts.summary_counts.estimated_recovery_deduped_paise)} icon={ClipboardList} tone="text-vp-navy" testid="brief-kpi-est" />
                <FactCard label={lang === 'en' ? 'Verified ₹' : 'Verified ₹'}
                    value={paiseToCompact(facts.summary_counts.verified_recovery_paise)} icon={ShieldCheck} tone="text-vp-emerald" testid="brief-kpi-verified" />
                <FactCard label={lang === 'en' ? 'Overdue actions' : 'देर से actions'}
                    value={facts.summary_counts.overdue_actions} icon={AlertTriangle} tone="text-vp-red" testid="brief-kpi-overdue" />
            </div>

            {/* Top priorities */}
            <div className="bg-white border border-vp-border rounded-md p-5" data-testid="brief-priorities">
                <div className="text-[10px] tracking-[0.22em] uppercase text-vp-muted font-semibold mb-3">
                    {lang === 'en' ? 'Top recovery priorities' : 'शीर्ष रिकवरी priorities'}
                </div>
                <ul className="space-y-2 list-none">
                    {view.top_priorities.map((line, i) => (
                        <li key={i} className="text-[13px] text-vp-navy leading-relaxed border-l-2 border-vp-amber/60 pl-3">
                            {line}
                        </li>
                    ))}
                    {view.top_priorities.length === 0 && (
                        <li className="text-[12px] text-vp-muted">
                            {lang === 'en' ? 'No open priorities.' : 'कोई priority नहीं।'}
                        </li>
                    )}
                </ul>
            </div>

            {/* Salesperson workload + Risks */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white border border-vp-border rounded-md p-5" data-testid="brief-sp">
                    <div className="text-[10px] tracking-[0.22em] uppercase text-vp-muted font-semibold mb-3">
                        {lang === 'en' ? 'Salesperson workload' : 'Salesperson workload'}
                    </div>
                    <ul className="space-y-1.5 list-none">
                        {view.salesperson_workload.map((line, i) => (
                            <li key={i} className="text-[13px] text-vp-navy">{line}</li>
                        ))}
                    </ul>
                </div>
                <div className="bg-white border border-vp-border rounded-md p-5" data-testid="brief-risks">
                    <div className="text-[10px] tracking-[0.22em] uppercase text-vp-muted font-semibold mb-3">
                        {lang === 'en' ? 'Risks by type' : 'Risk (प्रकार अनुसार)'}
                    </div>
                    <p className="text-[13px] text-vp-navy leading-relaxed">{view.risks}</p>
                </div>
            </div>

            <div className="text-[10px] text-vp-muted">
                Brief version {data.brief_version} · generated {new Date(data.generated_at).toLocaleString('en-IN')}
            </div>
        </div>
    );
}

function FactCard({ label, value, icon: Icon, tone, testid }) {
    return (
        <div className="bg-white border border-vp-border rounded-md p-4" data-testid={testid}>
            <div className="flex items-center justify-between">
                <div className="text-[10px] tracking-[0.22em] uppercase text-vp-muted font-semibold">{label}</div>
                <Icon className={`h-4 w-4 opacity-80 ${tone}`} />
            </div>
            <div className={`mt-2 font-heading font-bold text-[22px] leading-none ${tone}`}>{value}</div>
        </div>
    );
}
