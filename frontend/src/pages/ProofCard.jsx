import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { paiseToInr } from '../lib/format';
import { ShieldCheck, FileText, AlertCircle, ArrowUpRightFromSquare } from 'lucide-react';

const BASE = process.env.REACT_APP_BACKEND_URL;

/*  Public "Prove it" audit view. Reached via a signed, expiring, revocable
    share token. NO authentication required. Server returns ONLY the audit
    fields for one recovery. This route is intentionally OUTSIDE /app/*.
*/
export default function ProofCard() {
    const { token } = useParams();
    const [data, setData] = useState(null);
    const [err, setErr] = useState(null);

    useEffect(() => {
        axios.get(`${BASE}/api/public/proof/${token}`)
            .then((r) => setData(r.data))
            .catch((e) => {
                const detail = e?.response?.data?.detail;
                setErr(detail || 'This share link is not valid.');
            });
    }, [token]);

    if (err) {
        return (
            <div className="min-h-screen bg-vp-canvas flex items-center justify-center p-4">
                <div className="max-w-md bg-white border border-vp-red/40 rounded-md p-6 text-center" data-testid="proof-error">
                    <AlertCircle className="h-8 w-8 text-vp-red mx-auto" />
                    <div className="mt-3 font-heading font-bold text-vp-navy">Share link unavailable</div>
                    <p className="mt-1.5 text-[13px] text-vp-muted">{String(err)}</p>
                </div>
            </div>
        );
    }
    if (!data) {
        return (
            <div className="min-h-screen bg-vp-canvas flex items-center justify-center">
                <div className="animate-pulse text-vp-muted text-[13px]" data-testid="proof-loading">Loading verified recovery…</div>
            </div>
        );
    }

    const attribution = data.attribution_window || {};
    const ent = data.enterprise || {};
    return (
        <div className="min-h-screen bg-vp-canvas py-10 px-4" data-testid="proof-page">
            <div className="max-w-2xl mx-auto">
                <div className="text-center mb-8">
                    <div className="inline-flex items-center gap-1.5 bg-vp-emeraldbg border border-vp-emerald/30 text-vp-emerald text-[11px] tracking-[0.22em] uppercase px-3 py-1 rounded-sm">
                        <ShieldCheck className="h-3 w-3" /> Verified recovery · public audit
                    </div>
                    <h1 className="mt-4 font-heading font-bold text-3xl text-vp-navy">{paiseToInr(data.verified_paise)}</h1>
                    <div className="mt-1.5 text-[13px] text-vp-muted">
                        {ent.name} {ent.is_demo && <span className="text-vp-amber">(sandbox demo)</span>}
                    </div>
                </div>

                <div className="bg-white border border-vp-border rounded-md overflow-hidden">
                    <Row label="Outlet" value={<><b>{data.outlet_name}</b><div className="text-[11px] text-vp-muted">Outlet {data.outlet_code}</div></>} testid="proof-outlet" />
                    <Row label="Distributor" value={data.distributor_code} testid="proof-distributor" />
                    <Row label="Salesperson" value={
                        data.salesperson_code && data.salesperson_name
                            ? `${data.salesperson_code} · ${data.salesperson_name}`
                            : (data.salesperson_code || data.salesperson_name || '—')
                    } testid="proof-salesperson" />
                    <Row label="Opportunity type" value={data.opportunity_type} testid="proof-opp-type" />
                    <Row label="Action ID" value={data.action_id || '—'} testid="proof-action-id" />
                    <Row label="Invoice number" value={<><FileText className="h-3 w-3 inline-block mr-1 text-vp-muted" />{data.invoice_no}</>} testid="proof-invoice" />
                    <Row label="Invoice date" value={(data.invoice_order_date || '').slice(0, 10)} testid="proof-invoice-date" />
                    <Row label="Claimed" value={paiseToInr(data.claimed_paise)} testid="proof-claimed" />
                    <Row label="Invoice net" value={paiseToInr(data.invoice_net_paise)} testid="proof-invoice-net" />
                    <Row label="Verified" value={<span className="font-heading font-bold text-vp-emerald text-lg">{paiseToInr(data.verified_paise)}</span>} testid="proof-verified" />
                    <Row label="Assigned at" value={(attribution.assigned_at || '—').slice(0, 19).replace('T', ' ')} testid="proof-assigned-at" />
                    <Row label="Completed at" value={(attribution.completed_at || '—').slice(0, 19).replace('T', ' ')} testid="proof-completed-at" />
                    <Row label="Attribution window" value={attribution.window_end_note} testid="proof-window" />
                    <Row label="Calculation" value={<div className="text-[12px] leading-relaxed">{data.calculation_explanation}</div>} testid="proof-calc" />
                </div>

                <div className="mt-6 text-[11px] text-vp-muted text-center leading-relaxed">
                    Token <code className="bg-slate-100 px-1.5 py-0.5 rounded-sm">{data.token?.jti?.slice(0, 12)}…</code>
                    · issued {(data.token?.issued_at || '').slice(0, 19).replace('T', ' ')}
                    · expires {(data.token?.expires_at || '').slice(0, 19).replace('T', ' ')}
                </div>
                <div className="mt-6 text-center">
                    <a href="/" className="inline-flex items-center gap-1 text-[12px] text-vp-navy underline underline-offset-4" data-testid="proof-home-link">
                        VyaparPulse AI <ArrowUpRightFromSquare className="h-3 w-3" />
                    </a>
                </div>
            </div>
        </div>
    );
}

function Row({ label, value, testid }) {
    return (
        <div className="grid grid-cols-3 gap-4 px-5 py-3 border-b border-vp-border last:border-0" data-testid={testid}>
            <div className="text-[10px] uppercase tracking-widest text-vp-muted">{label}</div>
            <div className="col-span-2 text-[13px] text-vp-navy">{value}</div>
        </div>
    );
}
