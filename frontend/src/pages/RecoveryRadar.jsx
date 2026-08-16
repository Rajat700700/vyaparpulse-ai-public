import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import { paiseToCompact, formatFreshness } from '../lib/format';
import { Radar, Search, X, TrendingDown, Store, Sparkles, Filter, Info } from 'lucide-react';

const TYPE_META = {
    LAPSED: { label: 'Lapsed', tone: 'bg-vp-redbg text-vp-red', icon: Store },
    DECLINING: { label: 'Declining', tone: 'bg-vp-amberbg text-vp-amber', icon: TrendingDown },
    MISSED: { label: 'Missed cycle', tone: 'bg-vp-amberbg text-vp-amber', icon: Radar },
    WHITESPACE: { label: 'Whitespace', tone: 'bg-vp-emeraldbg text-vp-emerald', icon: Sparkles },
};

const KPI = ({ label, value, tone = 'text-vp-navy' }) => (
    <div className="bg-white border border-vp-border rounded-md p-4">
        <div className="text-[10px] tracking-[0.18em] uppercase text-vp-muted font-semibold">{label}</div>
        <div className={`mt-2 font-heading font-bold text-[22px] leading-none ${tone}`}>{value}</div>
    </div>
);

export default function RecoveryRadar() {
    const [summary, setSummary] = useState(null);
    const [opps, setOpps] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selected, setSelected] = useState(null);
    const [q, setQ] = useState('');
    const [type, setType] = useState('');
    const [distributor, setDistributor] = useState('');
    const [salesperson, setSalesperson] = useState('');
    const [minScore, setMinScore] = useState(0);

    useEffect(() => {
        (async () => {
            try {
                const s = await api.get('/radar/summary');
                setSummary(s.data);
            } catch (_) {}
        })();
    }, []);

    useEffect(() => {
        setLoading(true);
        const params = { limit: 200, min_score: minScore };
        if (q) params.q = q;
        if (type) params.type = type;
        if (distributor) params.distributor = distributor;
        if (salesperson) params.salesperson = salesperson;
        api.get('/radar/opportunities', { params })
            .then((r) => setOpps(r.data.opportunities))
            .finally(() => setLoading(false));
    }, [q, type, distributor, salesperson, minScore]);

    const hasData = summary && (summary.counts.LAPSED + summary.counts.DECLINING + summary.counts.MISSED + summary.counts.WHITESPACE) > 0;

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
                <div>
                    <div className="text-[11px] tracking-[0.22em] uppercase text-vp-muted font-semibold">Recovery Radar</div>
                    <h1 className="mt-1 font-heading font-bold text-3xl sm:text-4xl text-vp-navy">Where the money is hiding</h1>
                </div>
                <div className="text-[12px] bg-white border border-vp-border rounded-md px-3 py-2 text-vp-navy">
                    {formatFreshness(summary?.analysis_as_of)}
                </div>
            </div>

            {!hasData && !loading && (
                <div className="bg-white border border-vp-border rounded-md p-10 text-center">
                    <div className="mx-auto h-11 w-11 rounded-sm bg-vp-navy text-white flex items-center justify-center mb-4">
                        <Radar strokeWidth={1.5} className="h-5 w-5" />
                    </div>
                    <div className="font-heading font-semibold text-vp-navy text-xl">No opportunities yet</div>
                    <p className="mt-2 text-[13px] text-vp-muted max-w-lg mx-auto">Import a sales file to compute deterministic Lapsed / Declining / Missed Cycle / Whitespace opportunities.</p>
                    <a href="/app/import" className="mt-6 inline-flex items-center gap-2 bg-vp-navy text-white text-[13px] font-medium px-4 py-2 rounded-md">Import data</a>
                </div>
            )}

            {hasData && (
                <>
                    <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
                        <KPI label="Recoverable ₹" value={paiseToCompact(summary.recoverable_paise)} tone="text-vp-emerald" />
                        <KPI label="Priority outlets" value={summary.priority_outlets} tone="text-vp-navy" />
                        <KPI label="Lapsed" value={summary.counts.LAPSED} tone="text-vp-red" />
                        <KPI label="Declining" value={summary.counts.DECLINING} tone="text-vp-amber" />
                        <KPI label="Missed cycle" value={summary.counts.MISSED} tone="text-vp-amber" />
                        <KPI label="Whitespace" value={summary.counts.WHITESPACE} tone="text-vp-emerald" />
                    </div>

                    <div className="bg-white border border-vp-border rounded-md p-3 flex flex-wrap items-center gap-2">
                        <div className="inline-flex items-center gap-2 text-[11px] tracking-[0.2em] uppercase text-vp-muted font-semibold mr-1">
                            <Filter className="h-3.5 w-3.5" /> Filters
                        </div>
                        <div className="relative">
                            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-vp-muted" />
                            <input data-testid="radar-search" placeholder="Search outlet…" value={q} onChange={(e) => setQ(e.target.value)}
                                className="pl-8 pr-3 py-1.5 border border-vp-border rounded-md text-[12px] w-52" />
                        </div>
                        <select data-testid="radar-type" value={type} onChange={(e) => setType(e.target.value)} className="text-[12px] border border-vp-border rounded-md px-2 py-1.5">
                            <option value="">All types</option>
                            {Object.entries(TYPE_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
                        </select>
                        <select value={distributor} onChange={(e) => setDistributor(e.target.value)} className="text-[12px] border border-vp-border rounded-md px-2 py-1.5">
                            <option value="">All distributors</option>
                            {summary.filters.distributors.map((d) => <option key={d} value={d}>{d}</option>)}
                        </select>
                        <select value={salesperson} onChange={(e) => setSalesperson(e.target.value)} className="text-[12px] border border-vp-border rounded-md px-2 py-1.5">
                            <option value="">All salespeople</option>
                            {summary.filters.salespeople.map((d) => <option key={d} value={d}>{d}</option>)}
                        </select>
                        <label className="text-[12px] text-vp-muted flex items-center gap-2">
                            Min score
                            <input type="range" min={0} max={100} step={5} value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} />
                            <span className="text-vp-navy font-medium w-6 text-right">{minScore}</span>
                        </label>
                    </div>

                    <div className="bg-white border border-vp-border rounded-md overflow-hidden">
                        <div className="overflow-x-auto">
                            <table className="min-w-full text-[12px]">
                                <thead className="bg-slate-50 text-vp-muted uppercase tracking-wider text-[10px]">
                                    <tr>
                                        <th className="text-left px-4 py-3">Type</th>
                                        <th className="text-left px-4 py-3">Outlet</th>
                                        <th className="text-left px-4 py-3 hidden md:table-cell">Dist / Beat</th>
                                        <th className="text-left px-4 py-3 hidden lg:table-cell">Salesperson</th>
                                        <th className="text-right px-4 py-3">Est. ₹</th>
                                        <th className="text-right px-4 py-3">Score</th>
                                        <th className="text-right px-4 py-3"></th>
                                    </tr>
                                </thead>
                                <tbody data-testid="radar-table-body">
                                    {opps.map((o) => {
                                        const T = TYPE_META[o.type];
                                        const Icon = T.icon;
                                        return (
                                            <tr key={o.id} className="border-t border-vp-border hover:bg-slate-50">
                                                <td className="px-4 py-3">
                                                    <span className={`inline-flex items-center gap-1 rounded-sm px-2 py-0.5 ${T.tone} text-[10px] uppercase tracking-wider font-semibold`}>
                                                        <Icon className="h-3 w-3" /> {T.label}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-3">
                                                    <div className="font-medium text-vp-navy">{o.outlet_name || o.outlet_code}</div>
                                                    <div className="text-[11px] text-vp-muted">{o.outlet_code}</div>
                                                </td>
                                                <td className="px-4 py-3 hidden md:table-cell text-vp-navy">{o.distributor_code} · {o.beat_or_route}</td>
                                                <td className="px-4 py-3 hidden lg:table-cell text-vp-navy">{o.salesperson_code}</td>
                                                <td className="px-4 py-3 text-right font-heading font-semibold text-vp-navy">{paiseToCompact(o.est_recovery_paise)}</td>
                                                <td className="px-4 py-3 text-right font-heading font-bold text-vp-navy">{o.priority_score}</td>
                                                <td className="px-4 py-3 text-right">
                                                    <button data-testid={`radar-open-${o.id}`} onClick={() => setSelected(o)} className="text-vp-navy underline underline-offset-2 text-[11px]">Details</button>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                    {opps.length === 0 && !loading && (
                                        <tr><td colSpan={7} className="text-center text-vp-muted py-8">No opportunities match the current filters.</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}

            {/* Drawer */}
            {selected && (
                <div className="fixed inset-0 z-50 flex" onClick={() => setSelected(null)}>
                    <div className="flex-1 bg-black/30" />
                    <div className="w-full max-w-md bg-white border-l border-vp-border overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="radar-drawer">
                        <div className="p-5 border-b border-vp-border flex items-start justify-between gap-3">
                            <div>
                                <div className="text-[10px] tracking-[0.2em] uppercase text-vp-muted font-semibold">{TYPE_META[selected.type].label}</div>
                                <div className="font-heading font-bold text-vp-navy text-xl">{selected.outlet_name || selected.outlet_code}</div>
                                <div className="text-[12px] text-vp-muted">{selected.distributor_code} · {selected.beat_or_route} · {selected.salesperson_code}</div>
                            </div>
                            <button onClick={() => setSelected(null)} className="text-vp-muted"><X className="h-5 w-5" /></button>
                        </div>
                        <div className="p-5 space-y-4 text-[13px]">
                            <div>
                                <div className="text-[10px] uppercase tracking-widest text-vp-muted">Estimated recovery</div>
                                <div className="font-heading font-bold text-vp-emerald text-3xl">{paiseToCompact(selected.est_recovery_paise)}</div>
                                <div className="text-[11px] text-vp-muted">Confidence {Math.round(selected.confidence * 100)}%</div>
                            </div>
                            <div>
                                <div className="text-[10px] uppercase tracking-widest text-vp-muted mb-1">Why flagged</div>
                                <p className="text-vp-navy leading-relaxed">{selected.reason}</p>
                            </div>
                            <div>
                                <div className="text-[10px] uppercase tracking-widest text-vp-muted mb-2">Priority score {selected.priority_score}/100</div>
                                <div className="grid grid-cols-4 gap-2 text-center text-[11px]">
                                    {['value', 'confidence', 'urgency', 'strategic'].map((k) => (
                                        <div key={k} className="bg-slate-50 border border-vp-border rounded-md p-2">
                                            <div className="font-heading font-bold text-vp-navy">{selected.score_components[k]}</div>
                                            <div className="text-vp-muted uppercase tracking-wider text-[9px]">{k}</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <div>
                                <div className="text-[10px] uppercase tracking-widest text-vp-muted mb-1">Inputs used</div>
                                <pre className="bg-slate-50 border border-vp-border rounded-md p-3 text-[11px] overflow-x-auto text-vp-navy">{JSON.stringify(selected.inputs_snapshot, null, 2)}</pre>
                            </div>
                            <div>
                                <div className="text-[10px] uppercase tracking-widest text-vp-muted mb-1">Thresholds applied</div>
                                <pre className="bg-slate-50 border border-vp-border rounded-md p-3 text-[11px] overflow-x-auto text-vp-navy">{JSON.stringify(selected.thresholds_snapshot, null, 2)}</pre>
                                <div className="text-[10px] text-vp-muted mt-1">calc_version {selected.calc_version} · analysis {String(selected.analysis_as_of).slice(0, 10)}</div>
                            </div>
                            <div>
                                <div className="text-[10px] uppercase tracking-widest text-vp-muted mb-1">Recommended next action</div>
                                <p className="text-vp-navy leading-relaxed">{selected.recommended_action}</p>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
