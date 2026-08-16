import { useEffect, useState } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { api } from '../lib/api';
import { paiseToCompact } from '../lib/format';
import { ArrowLeft, TrendingUp, Store, Calendar, Package, Target } from 'lucide-react';

const TYPE_COLOR = {
    LAPSED: 'text-vp-red bg-vp-redbg',
    DECLINING: 'text-vp-amber bg-vp-amberbg',
    MISSED: 'text-vp-amber bg-vp-amberbg',
    WHITESPACE: 'text-vp-emerald bg-vp-emeraldbg',
};

export default function OutletDetail() {
    const { outletCode } = useParams();
    const [params] = useSearchParams();
    const distributor = params.get('distributor') || '';
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        api.get(`/outlets/${encodeURIComponent(outletCode)}`, { params: { distributor } })
            .then((r) => setData(r.data))
            .catch((e) => setError(e?.response?.data?.detail || 'Not found'));
    }, [outletCode, distributor]);

    if (error) return <div className="text-vp-red">{String(error)}</div>;
    if (!data) return <div className="animate-pulse text-vp-muted">Loading outlet…</div>;

    const trendMax = Math.max(1, ...data.trend_6m.map((t) => t.net_paise));
    const totalOpp = data.opportunities.reduce((s, o) => s + (o.est_recovery_paise || 0), 0);
    const totalVerified = data.recoveries.reduce((s, r) => s + (r.verified_paise || 0), 0);

    return (
        <div className="space-y-6" data-testid="outlet-360-page">
            <div>
                <Link to="/app/outlets" className="text-[12px] text-vp-muted inline-flex items-center gap-1"><ArrowLeft className="h-3.5 w-3.5" /> All outlets</Link>
                <div className="mt-2 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
                    <div>
                        <div className="text-[11px] tracking-[0.22em] uppercase text-vp-muted font-semibold">Outlet 360</div>
                        <h1 className="mt-1 font-heading font-bold text-3xl text-vp-navy">{data.meta.outlet_name}</h1>
                        <div className="text-[12px] text-vp-muted mt-1">
                            {data.meta.outlet_code} · {data.meta.distributor_code} · {data.meta.beat_or_route} · {data.meta.salesperson_name} · {data.meta.region}
                        </div>
                    </div>
                    <div className="grid grid-cols-3 gap-2 min-w-[300px]">
                        <div className="bg-white border border-vp-border rounded-md p-3">
                            <div className="text-[9px] uppercase tracking-widest text-vp-muted">Est. opportunity</div>
                            <div className="mt-1 font-heading font-bold text-vp-amber text-lg" data-testid="outlet-est-total">{paiseToCompact(totalOpp)}</div>
                        </div>
                        <div className="bg-white border border-vp-border rounded-md p-3">
                            <div className="text-[9px] uppercase tracking-widest text-vp-muted">Verified ₹</div>
                            <div className="mt-1 font-heading font-bold text-vp-emerald text-lg" data-testid="outlet-verified-total">{paiseToCompact(totalVerified)}</div>
                        </div>
                        <div className="bg-white border border-vp-border rounded-md p-3">
                            <div className="text-[9px] uppercase tracking-widest text-vp-muted">Median cadence</div>
                            <div className="mt-1 font-heading font-bold text-vp-navy text-lg">{data.cadence.median_interval_days ?? '—'}d</div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Trend */}
            <div className="bg-white border border-vp-border rounded-md p-5">
                <div className="text-[10px] uppercase tracking-widest text-vp-muted mb-3 flex items-center gap-1"><TrendingUp className="h-3.5 w-3.5" /> 6-month sales trend</div>
                <div className="flex items-end gap-2 h-32">
                    {data.trend_6m.map((t, i) => (
                        <div key={i} className="flex-1 flex flex-col items-center gap-1">
                            <div className="w-full bg-vp-navy rounded-sm" style={{ height: `${Math.max(4, (t.net_paise / trendMax) * 110)}px` }} title={paiseToCompact(t.net_paise)} />
                            <div className="text-[9px] text-vp-muted">{t.month_end}</div>
                        </div>
                    ))}
                </div>
            </div>

            {/* SKU mix + opportunities */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="bg-white border border-vp-border rounded-md p-5">
                    <div className="text-[10px] uppercase tracking-widest text-vp-muted mb-3 flex items-center gap-1"><Package className="h-3.5 w-3.5" /> SKU mix (last 90d)</div>
                    <div className="space-y-1.5 text-[12px]">
                        {data.sku_mix.map((s) => (
                            <div key={s.sku_code} className="flex items-center justify-between border-b border-vp-border/50 pb-1">
                                <div>
                                    <div className="text-vp-navy font-medium">{s.sku_name}</div>
                                    <div className="text-[10px] text-vp-muted">{s.category}</div>
                                </div>
                                <div className="text-vp-navy font-heading font-semibold">{paiseToCompact(s.net_paise)}</div>
                            </div>
                        ))}
                        {data.sku_mix.length === 0 && <div className="text-vp-muted">No recent purchases.</div>}
                    </div>
                </div>
                <div className="bg-white border border-vp-border rounded-md p-5">
                    <div className="text-[10px] uppercase tracking-widest text-vp-muted mb-3 flex items-center gap-1"><Target className="h-3.5 w-3.5" /> Active opportunities</div>
                    <div className="space-y-2 text-[12px]">
                        {data.opportunities.map((o) => (
                            <div key={o.id} className="flex items-center justify-between border border-vp-border rounded-md p-2">
                                <div>
                                    <span className={`inline-block text-[9px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded-sm ${TYPE_COLOR[o.type]}`}>{o.type}</span>
                                    <div className="text-vp-navy mt-1">{o.reason}</div>
                                </div>
                                <div className="text-right">
                                    <div className="font-heading font-bold text-vp-navy">{paiseToCompact(o.est_recovery_paise)}</div>
                                    <div className="text-[10px] text-vp-muted">Score {o.priority_score}</div>
                                </div>
                            </div>
                        ))}
                        {data.opportunities.length === 0 && <div className="text-vp-muted">No open opportunities.</div>}
                    </div>
                </div>
            </div>

            {/* Actions + recoveries */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="bg-white border border-vp-border rounded-md p-5">
                    <div className="text-[10px] uppercase tracking-widest text-vp-muted mb-3">Action history</div>
                    <div className="space-y-2 text-[12px]" data-testid="outlet-actions">
                        {data.actions.map((a) => (
                            <div key={a.id} className="border border-vp-border rounded-md p-2 flex items-center justify-between">
                                <div>
                                    <div className="text-vp-navy font-medium">{a.opportunity_type} — {a.salesperson_code}</div>
                                    <div className="text-[10px] text-vp-muted">Assigned {String(a.assigned_at).slice(0,10)} · Due {String(a.due_date).slice(0,10)}</div>
                                </div>
                                <span className={`text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-sm ${a.status === 'COMPLETED' ? 'bg-vp-emeraldbg text-vp-emerald' : a.status === 'SKIPPED' ? 'bg-slate-100 text-vp-muted' : 'bg-vp-amberbg text-vp-amber'}`}>{a.status}</span>
                            </div>
                        ))}
                        {data.actions.length === 0 && <div className="text-vp-muted">No actions yet.</div>}
                    </div>
                </div>
                <div className="bg-white border border-vp-border rounded-md p-5">
                    <div className="text-[10px] uppercase tracking-widest text-vp-muted mb-3">Verified recoveries</div>
                    <div className="space-y-2 text-[12px]" data-testid="outlet-recoveries">
                        {data.recoveries.map((r) => (
                            <div key={r.id} className="border border-vp-border rounded-md p-2 flex items-center justify-between">
                                <div>
                                    <div className="text-vp-navy font-medium">Invoice {r.invoice_no}</div>
                                    <div className="text-[10px] text-vp-muted">Order {String(r.invoice_order_date).slice(0,10)}</div>
                                </div>
                                <div className="font-heading font-bold text-vp-emerald">{paiseToCompact(r.verified_paise)}</div>
                            </div>
                        ))}
                        {data.recoveries.length === 0 && <div className="text-vp-muted">No verified recoveries yet.</div>}
                    </div>
                </div>
            </div>
        </div>
    );
}
