import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { COMMAND } from '../constants/testIds';
import { paiseToCompact, formatFreshness } from '../lib/format';
import { CalendarClock, TrendingUp, TriangleAlert, Target, CheckCircle2, Filter } from 'lucide-react';

const KPI = ({ label, value, sub, tone = 'navy', testid, icon: Icon }) => {
    const toneStyles = {
        navy: 'text-vp-navy',
        emerald: 'text-vp-emerald',
        amber: 'text-vp-amber',
        red: 'text-vp-red',
    }[tone];
    return (
        <div
            data-testid={testid}
            className="bg-white border border-vp-border rounded-md p-5 hover:-translate-y-0.5 hover:shadow-md transition-all duration-300"
        >
            <div className="flex items-center justify-between">
                <div className="text-[11px] tracking-[0.2em] uppercase text-vp-muted font-semibold">{label}</div>
                <Icon strokeWidth={1.75} className={`h-4 w-4 ${toneStyles} opacity-80`} />
            </div>
            <div className={`mt-4 font-heading font-bold text-[28px] leading-none ${toneStyles}`}>{value}</div>
            <div className="mt-2 text-[12px] text-vp-muted">{sub}</div>
        </div>
    );
};

const FILTERS = ['Period', 'Region', 'Distributor', 'Salesperson', 'Beat', 'Outlet', 'Brand', 'Category', 'SKU'];

export default function CommandCentre() {
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        api.get('/tenant/command-centre')
            .then((r) => setData(r.data))
            .catch((e) => setError(e?.response?.data?.detail || 'Failed to load'));
    }, []);

    if (error) {
        return (
            <div className="max-w-4xl mx-auto bg-vp-redbg border border-vp-red/30 rounded-md p-5 text-vp-red text-[13px]">
                {String(error)}
            </div>
        );
    }
    if (!data) {
        return (
            <div className="animate-pulse space-y-6">
                <div className="h-8 w-64 bg-slate-200 rounded" />
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                    {[0,1,2,3].map((i) => <div key={i} className="h-28 bg-white border border-vp-border rounded-md" />)}
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-8" data-testid={COMMAND.page}>
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
                <div>
                    <div className="text-[11px] tracking-[0.22em] uppercase text-vp-muted font-semibold">Enterprise Command Centre</div>
                    <h1 className="mt-1 font-heading font-bold text-3xl sm:text-4xl text-vp-navy">{data.enterprise.name}</h1>
                </div>
                <div
                    data-testid={COMMAND.freshness}
                    className="inline-flex items-center gap-2 bg-white border border-vp-border rounded-md px-3 py-2 text-[12px] text-vp-navy"
                >
                    <CalendarClock strokeWidth={1.75} className="h-3.5 w-3.5 text-vp-muted" />
                    <span>{formatFreshness(data.data_through)}</span>
                </div>
            </div>

            {/* Filters (disabled shell) */}
            <div
                data-testid={COMMAND.filterBar}
                className="bg-white border border-vp-border rounded-md p-4 flex flex-wrap items-center gap-2"
            >
                <div className="inline-flex items-center gap-2 text-[11px] tracking-[0.2em] uppercase text-vp-muted font-semibold mr-2">
                    <Filter strokeWidth={1.75} className="h-3.5 w-3.5" /> Filters
                </div>
                {FILTERS.map((f) => (
                    <button
                        key={f}
                        disabled
                        className="text-[12px] px-3 py-1.5 rounded-sm border border-dashed border-vp-border text-vp-muted bg-slate-50 cursor-not-allowed"
                        title="Enabled in Phase 2 (after data ingestion)"
                    >
                        {f}
                    </button>
                ))}
            </div>

            {/* KPIs */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                <KPI
                    label="Revenue · MTD"
                    value={paiseToCompact(data.kpis.revenue_mtd_paise)}
                    sub="Populated after first import"
                    tone="navy"
                    icon={TrendingUp}
                    testid={COMMAND.kpiRevenue}
                />
                <KPI
                    label="Outlets at Risk"
                    value={data.kpis.outlets_at_risk}
                    sub="Lapsed + Declining outlets"
                    tone="red"
                    icon={TriangleAlert}
                    testid={COMMAND.kpiOutletsAtRisk}
                />
                <KPI
                    label="Estimated Opportunity"
                    value={paiseToCompact(data.kpis.estimated_opportunity_paise)}
                    sub="Deduped per outlet · matches Impact Ledger"
                    tone="amber"
                    icon={Target}
                    testid={COMMAND.kpiOpportunity}
                />
                <KPI
                    label="Verified Recovery"
                    value={paiseToCompact(data.kpis.verified_recovery_paise)}
                    sub="Invoice-attributed only"
                    tone="emerald"
                    icon={CheckCircle2}
                    testid={COMMAND.kpiVerified}
                />
            </div>

            {/* Empty or Live state */}
            {data.is_empty ? (
                <div
                    data-testid={COMMAND.emptyState}
                    className="bg-white border border-vp-border rounded-md p-10 text-center"
                >
                    <div className="mx-auto h-11 w-11 rounded-sm bg-vp-navy text-white flex items-center justify-center mb-4">
                        <Target strokeWidth={1.75} className="h-5 w-5" />
                    </div>
                    <div className="font-heading font-semibold text-vp-navy text-xl">Command Centre is ready</div>
                    <p className="mt-2 text-[13px] text-vp-muted max-w-xl mx-auto leading-relaxed">
                        {data.empty_reason}
                    </p>
                    <a href="/app/import" className="mt-6 inline-flex items-center gap-2 bg-vp-navy text-white text-[13px] font-medium px-4 py-2 rounded-md">
                        Import sales data
                    </a>
                </div>
            ) : (
                <div className="bg-white border border-vp-border rounded-md p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div>
                        <div className="text-[11px] tracking-[0.22em] uppercase text-vp-muted font-semibold">Live data</div>
                        <div className="mt-1 font-heading font-semibold text-vp-navy text-lg">Recovery Radar is populated</div>
                        <p className="text-[13px] text-vp-muted mt-1">Deterministic Lapsed / Declining / Missed Cycle / Whitespace opportunities are ready to review.</p>
                    </div>
                    <a href="/app/recovery-radar" className="inline-flex items-center gap-2 bg-vp-navy hover:bg-vp-navyhover text-white text-[13px] font-medium px-5 py-2.5 rounded-md">
                        Open Recovery Radar
                    </a>
                </div>
            )}
        </div>
    );
}
