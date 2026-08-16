import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { paiseToCompact, formatFreshness } from '../lib/format';
import { Store, Search, Filter } from 'lucide-react';

export default function OutletsPage() {
    const [outlets, setOutlets] = useState([]);
    const [q, setQ] = useState('');
    const [distributor, setDistributor] = useState('');
    const [region, setRegion] = useState('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        const params = { limit: 500 };
        if (q) params.q = q;
        if (distributor) params.distributor = distributor;
        if (region) params.region = region;
        api.get('/outlets', { params })
            .then((r) => setOutlets(r.data.outlets))
            .finally(() => setLoading(false));
    }, [q, distributor, region]);

    const dists = Array.from(new Set(outlets.map((o) => o.distributor_code))).sort();
    const regions = Array.from(new Set(outlets.map((o) => o.region).filter(Boolean))).sort();

    return (
        <div className="space-y-6">
            <div>
                <div className="text-[11px] tracking-[0.22em] uppercase text-vp-muted font-semibold">Outlet 360</div>
                <h1 className="mt-1 font-heading font-bold text-3xl text-vp-navy">Outlets</h1>
            </div>

            <div className="bg-white border border-vp-border rounded-md p-3 flex flex-wrap items-center gap-2">
                <Filter className="h-3.5 w-3.5 text-vp-muted mr-1" />
                <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-vp-muted" />
                    <input data-testid="outlet-search" placeholder="Search outlet name…" value={q}
                        onChange={(e) => setQ(e.target.value)}
                        className="pl-8 pr-3 py-1.5 border border-vp-border rounded-md text-[12px] w-56" />
                </div>
                <select value={distributor} onChange={(e) => setDistributor(e.target.value)} className="text-[12px] border border-vp-border rounded-md px-2 py-1.5">
                    <option value="">All distributors</option>
                    {dists.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
                <select value={region} onChange={(e) => setRegion(e.target.value)} className="text-[12px] border border-vp-border rounded-md px-2 py-1.5">
                    <option value="">All regions</option>
                    {regions.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
                <span className="text-[11px] text-vp-muted ml-auto">{outlets.length} outlets</span>
            </div>

            <div className="bg-white border border-vp-border rounded-md overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="min-w-full text-[12px]">
                        <thead className="bg-slate-50 text-vp-muted uppercase tracking-wider text-[10px]">
                            <tr>
                                <th className="text-left px-4 py-3">Outlet</th>
                                <th className="text-left px-4 py-3 hidden md:table-cell">Distributor / Beat</th>
                                <th className="text-left px-4 py-3 hidden lg:table-cell">Salesperson</th>
                                <th className="text-right px-4 py-3">Net sales · Jan–Jun 2026</th>
                                <th className="text-right px-4 py-3">Last order</th>
                            </tr>
                        </thead>
                        <tbody data-testid="outlets-table">
                            {outlets.map((o) => (
                                <tr key={`${o.distributor_code}-${o.outlet_code || o._id}`} className="border-t border-vp-border hover:bg-slate-50">
                                    <td className="px-4 py-3">
                                        <Link to={`/app/outlets/${encodeURIComponent(o.outlet_code || '')}?distributor=${o.distributor_code}`}
                                            className="font-medium text-vp-navy hover:underline"
                                            data-testid={`outlet-link-${o.outlet_code}`}>
                                            {o.outlet_name || o.outlet_code}
                                        </Link>
                                        <div className="text-[11px] text-vp-muted">{o.outlet_code}</div>
                                    </td>
                                    <td className="px-4 py-3 hidden md:table-cell text-vp-navy">{o.distributor_code} · {o.beat_or_route}</td>
                                    <td className="px-4 py-3 hidden lg:table-cell text-vp-navy">{o.salesperson_name}</td>
                                    <td className="px-4 py-3 text-right font-heading font-semibold text-vp-navy">{paiseToCompact(o.net_180d_paise)}</td>
                                    <td className="px-4 py-3 text-right text-vp-muted">{o.last_order_date ? formatFreshness(o.last_order_date).replace('Data through ', '') : '—'}</td>
                                </tr>
                            ))}
                            {!loading && outlets.length === 0 && (
                                <tr><td colSpan={5} className="text-center text-vp-muted py-8">No outlets match the filters.</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
