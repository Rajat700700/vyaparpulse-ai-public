import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { paiseToCompact, paiseToInr } from '../lib/format';
import { toast } from 'sonner';
import { Target, ClipboardList, CheckCircle2, ShieldCheck, X, FileText, Share2, Copy, Trash2 } from 'lucide-react';

const Stage = ({ label, count, paise, sub, tone, icon: Icon, testid }) => (
    <div className={`bg-white border rounded-md p-5 ${tone}`} data-testid={testid}>
        <div className="flex items-center justify-between">
            <div className="text-[10px] tracking-[0.22em] uppercase text-vp-muted font-semibold">{label}</div>
            <Icon className="h-4 w-4 opacity-70" />
        </div>
        <div className="mt-3 font-heading font-bold text-vp-navy text-[24px] leading-none">{count}</div>
        {paise != null && <div className="mt-1 text-[12px] text-vp-navy">{paiseToCompact(paise)}</div>}
        {sub && <div className="mt-2 text-[10px] text-vp-muted leading-snug">{sub}</div>}
    </div>
);

export default function ImpactLedger() {
    const [data, setData] = useState(null);
    const [selected, setSelected] = useState(null);
    const [share, setShare] = useState(null); // {url, jti, expires_at}
    const [sharing, setSharing] = useState(false);
    useEffect(() => { api.get('/impact-ledger').then((r) => setData(r.data)); }, []);
    if (!data) return <div className="animate-pulse text-vp-muted">Loading ledger…</div>;

    const s = data.stages;

    const attributionWindow = (r) => {
        if (!r.invoice_order_date) return '—';
        return `Assignment window through +14 days · order dated ${String(r.invoice_order_date).slice(0, 10)}`;
    };
    const explain = (r) =>
        `verified_paise = min(claimed ${paiseToInr(r.claimed_paise)}, invoice ${paiseToInr(r.invoice_net_paise)}) = ${paiseToInr(r.verified_paise)}. Unique per (enterprise, distributor, outlet, invoice_no).`;

    const issueShare = async () => {
        if (!selected) return;
        setSharing(true);
        try {
            const r = await api.post(`/impact-ledger/${selected.id}/share`, {});
            const publicUrl = `${window.location.origin}/proof/${r.data.token}`;
            setShare({ url: publicUrl, jti: r.data.jti, expires_at: r.data.expires_at });
            try { await navigator.clipboard.writeText(publicUrl); toast.success('Share link copied to clipboard'); }
            catch { toast.success('Share link created'); }
        } catch (e) {
            toast.error('Could not create share link');
        } finally {
            setSharing(false);
        }
    };

    const revokeShare = async () => {
        if (!selected || !share) return;
        try {
            await api.post(`/impact-ledger/${selected.id}/share/revoke`, { jti: share.jti });
            toast.success('Share link revoked');
            setShare(null);
        } catch {
            toast.error('Could not revoke');
        }
    };

    return (
        <div className="space-y-6">
            <div>
                <div className="text-[11px] tracking-[0.22em] uppercase text-vp-muted font-semibold">Impact Ledger</div>
                <h1 className="mt-1 font-heading font-bold text-3xl text-vp-navy">From estimated to verified ₹</h1>
                <p className="text-[13px] text-vp-muted mt-1">
                    Attribution window inclusive: <b>assigned_at through completed_at + 14 calendar days</b>. Every ₹ shown is deterministic
                    code — verified only against real invoices, never claimed alone.
                </p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 items-stretch">
                <Stage label="Estimated" count={s.estimated.count} paise={s.estimated.paise}
                    sub={`Deduped per outlet by precedence LAPSED > DECLINING > MISSED > WHITESPACE (matches Command Centre). Gross undeduped sum: ${paiseToCompact(s.estimated.gross_paise ?? 0)}.`}
                    tone="border-vp-amber/40" icon={Target} testid="stage-estimated" />
                <Stage label="Assigned" count={s.assigned.count}
                    sub="Actions currently ASSIGNED or IN_PROGRESS with a salesperson."
                    tone="border-vp-navy/30" icon={ClipboardList} testid="stage-assigned" />
                <Stage label="Completed" count={s.completed.count}
                    sub="Actions transitioned to COMPLETED (with or without invoice attribution)."
                    tone="border-vp-amber/40" icon={CheckCircle2} testid="stage-completed" />
                <Stage label="Verified" count={s.verified.count} paise={s.verified.paise}
                    sub="Invoice-attributed only, capped at invoice value. Never double-counted."
                    tone="border-vp-emerald/40" icon={ShieldCheck} testid="stage-verified" />
            </div>

            <div className="bg-white border border-vp-border rounded-md overflow-hidden">
                <div className="p-4 border-b border-vp-border flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4 text-vp-emerald" />
                    <div className="text-[12px] text-vp-navy font-semibold">Verified against real invoices</div>
                    <div className="text-[11px] text-vp-muted">Click any row to see the full audit trail.</div>
                </div>
                <div className="overflow-x-auto">
                    <table className="min-w-full text-[12px]">
                        <thead className="bg-slate-50 text-vp-muted uppercase tracking-wider text-[10px]">
                            <tr>
                                <th className="text-left px-4 py-3">Outlet</th>
                                <th className="text-left px-4 py-3 hidden md:table-cell">Invoice</th>
                                <th className="text-left px-4 py-3 hidden md:table-cell">Order date</th>
                                <th className="text-right px-4 py-3">Claimed</th>
                                <th className="text-right px-4 py-3">Verified</th>
                                <th className="text-right px-4 py-3"></th>
                            </tr>
                        </thead>
                        <tbody data-testid="ledger-entries">
                            {data.entries.map((r) => (
                                <tr key={r.id} className="border-t border-vp-border hover:bg-slate-50 cursor-pointer" onClick={() => setSelected(r)}
                                    data-testid={`ledger-row-${r.id}`}>
                                    <td className="px-4 py-3 text-vp-navy">
                                        <div className="font-medium">{r.outlet_name || r.outlet_code}</div>
                                        <div className="text-[10px] text-vp-muted">{r.distributor_code}</div>
                                    </td>
                                    <td className="px-4 py-3 hidden md:table-cell text-vp-navy">{r.invoice_no}</td>
                                    <td className="px-4 py-3 hidden md:table-cell text-vp-muted">{String(r.invoice_order_date).slice(0, 10)}</td>
                                    <td className="px-4 py-3 text-right text-vp-muted">{paiseToCompact(r.claimed_paise)}</td>
                                    <td className="px-4 py-3 text-right font-heading font-bold text-vp-emerald">{paiseToCompact(r.verified_paise)}</td>
                                    <td className="px-4 py-3 text-right text-vp-navy underline text-[11px]">Audit</td>
                                </tr>
                            ))}
                            {data.entries.length === 0 && (
                                <tr><td colSpan={6} className="text-center text-vp-muted py-8">No verified recoveries yet.</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {selected && (
                <div className="fixed inset-0 z-50 flex" onClick={() => { setSelected(null); setShare(null); }}>
                    <div className="flex-1 bg-black/30" />
                    <div className="w-full max-w-md bg-white border-l border-vp-border overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="ledger-audit-drawer">
                        <div className="p-5 border-b border-vp-border flex items-start justify-between gap-3">
                            <div>
                                <div className="text-[10px] tracking-[0.2em] uppercase text-vp-emerald font-semibold flex items-center gap-1"><ShieldCheck className="h-3 w-3" /> Verified recovery audit</div>
                                <div className="font-heading font-bold text-vp-navy text-xl mt-1">{selected.outlet_name || selected.outlet_code}</div>
                                <div className="text-[12px] text-vp-muted">{selected.distributor_code} · Outlet {selected.outlet_code}</div>
                            </div>
                            <button onClick={() => { setSelected(null); setShare(null); }}><X className="h-5 w-5 text-vp-muted" /></button>
                        </div>
                        <div className="p-5 space-y-4 text-[13px]">
                            <AuditField label="Action ID" value={selected.action_id || '—'} />
                            <AuditField label="Opportunity type" value={selected.opportunity_type || '—'} />
                            <AuditField label="Salesperson" value={
                                selected.salesperson_code && selected.salesperson_name
                                    ? `${selected.salesperson_code} · ${selected.salesperson_name}`
                                    : (selected.salesperson_code || selected.salesperson_name || '—')
                            } />
                            <AuditField label="Invoice no" value={selected.invoice_no} icon={<FileText className="h-3 w-3" />} />
                            <AuditField label="Order date" value={String(selected.invoice_order_date).slice(0, 10)} />
                            <AuditField label="Claimed" value={paiseToInr(selected.claimed_paise)} />
                            <AuditField label="Invoice net" value={paiseToInr(selected.invoice_net_paise)} />
                            <AuditField label="Verified" value={paiseToInr(selected.verified_paise)} highlight />
                            <AuditField label="Attribution window" value={attributionWindow(selected)} />
                            <div>
                                <div className="text-[10px] uppercase tracking-widest text-vp-muted mb-1">Calculation explanation</div>
                                <div className="bg-slate-50 border border-vp-border rounded-md p-3 text-[11px] text-vp-navy leading-relaxed" data-testid="audit-calc-explanation">
                                    {explain(selected)}
                                </div>
                            </div>

                            {/* Prove-it share link */}
                            <div className="pt-3 border-t border-vp-border">
                                <div className="text-[10px] uppercase tracking-widest text-vp-muted mb-2">Public "Prove it" share link</div>
                                {!share ? (
                                    <button data-testid="proof-share-button" onClick={issueShare} disabled={sharing}
                                        className="inline-flex items-center gap-1.5 text-[12px] bg-vp-navy text-white rounded-md px-3 py-1.5 disabled:opacity-60">
                                        <Share2 className="h-3.5 w-3.5" /> {sharing ? 'Creating…' : 'Create share link'}
                                    </button>
                                ) : (
                                    <div data-testid="proof-share-result" className="space-y-2">
                                        <div className="bg-slate-50 border border-vp-border rounded-md p-3 text-[11px] text-vp-navy break-all">
                                            {share.url}
                                        </div>
                                        <div className="text-[10px] text-vp-muted">Expires {String(share.expires_at).slice(0, 10)} · signed, revocable, no login required.</div>
                                        <div className="flex items-center gap-2">
                                            <button onClick={() => { navigator.clipboard.writeText(share.url); toast.success('Copied'); }}
                                                className="inline-flex items-center gap-1 text-[11px] border border-vp-border rounded-md px-2 py-1 text-vp-navy">
                                                <Copy className="h-3 w-3" /> Copy
                                            </button>
                                            <button data-testid="proof-revoke-button" onClick={revokeShare}
                                                className="inline-flex items-center gap-1 text-[11px] border border-vp-red/40 text-vp-red rounded-md px-2 py-1">
                                                <Trash2 className="h-3 w-3" /> Revoke
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

function AuditField({ label, value, highlight, icon }) {
    return (
        <div>
            <div className="text-[10px] uppercase tracking-widest text-vp-muted flex items-center gap-1">{icon}{label}</div>
            <div className={`mt-0.5 ${highlight ? 'text-vp-emerald font-heading font-bold text-lg' : 'text-vp-navy'}`}>{value}</div>
        </div>
    );
}
