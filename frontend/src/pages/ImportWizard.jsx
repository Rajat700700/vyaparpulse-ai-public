import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { paiseToCompact } from '../lib/format';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { Upload, FileSpreadsheet, CheckCircle2, AlertCircle, ArrowRight, ArrowLeft, ShieldAlert, Sparkles } from 'lucide-react';

const REQUIRED_LABELS = {
    distributor_code: 'Distributor code', salesperson_code: 'Salesperson code',
    beat_or_route: 'Beat / Route', outlet_code: 'Outlet code',
    outlet_name: 'Outlet name', order_date: 'Order date', invoice_no: 'Invoice no',
    sku_code: 'SKU code', sku_name: 'SKU name', quantity: 'Quantity', net_sales: 'Net sales',
};
const OPTIONAL = ['enterprise','region','category','brand','pack','gross_sales','discount','return_value'];

export default function ImportWizardPage() {
    const [step, setStep] = useState(1);
    const [file, setFile] = useState(null);
    const [preview, setPreview] = useState(null);
    const [mapping, setMapping] = useState({});
    const [validation, setValidation] = useState(null);
    const [importing, setImporting] = useState(false);
    const [busy, setBusy] = useState(false);
    const navigate = useNavigate();
    const { user } = useAuth();
    const isDemo = !!user?.is_demo;

    const onFile = async (e) => {
        const f = e.target.files?.[0];
        if (!f) return;
        setFile(f); setBusy(true);
        try {
            const fd = new FormData(); fd.append('file', f);
            const { data } = await api.post('/imports/preview', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
            setPreview(data);
            // Auto-select ALL suggestions with confidence >= 0.5 — this includes
            // AI suggestions (visibly badged) that the user must confirm before
            // Validate. Rules ≥ 0.85 win; AI fills the rest.
            const auto = {};
            const used = new Set();
            const entries = Object.entries(data.mapping_suggestion || {})
                .sort((a, b) => (b[1].confidence || 0) - (a[1].confidence || 0));
            for (const [src, info] of entries) {
                if ((info.confidence || 0) < 0.5) continue;
                if (used.has(info.target)) continue;   // don't dupe target
                auto[src] = info.target;
                used.add(info.target);
            }
            setMapping(auto);
            setStep(2);
        } catch (err) {
            toast.error(err?.response?.data?.detail || 'Could not read file');
        } finally { setBusy(false); }
    };

    const setMap = (src, target) => setMapping((m) => ({ ...m, [src]: target || undefined }));

    const requiredCovered = Object.keys(REQUIRED_LABELS).every((t) => Object.values(mapping).includes(t));

    const onValidate = async () => {
        setBusy(true);
        try {
            const fd = new FormData(); fd.append('file', file); fd.append('mapping', JSON.stringify(mapping));
            const { data } = await api.post('/imports/validate', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
            setValidation(data); setStep(3);
        } catch (err) {
            toast.error(err?.response?.data?.detail || 'Validation failed');
        } finally { setBusy(false); }
    };

    const onCommit = async () => {
        setImporting(true);
        try {
            const fd = new FormData(); fd.append('file', file); fd.append('mapping', JSON.stringify(mapping));
            const { data } = await api.post('/imports/commit', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
            toast.success(`Imported ${data.inserted} rows. Recovery Radar refreshed.`);
            navigate('/app/recovery-radar');
        } catch (err) {
            const d = err?.response?.data?.detail;
            toast.error(typeof d === 'string' ? d : 'Import failed');
        } finally { setImporting(false); }
    };

    const StepBadge = ({ n, label, active }) => (
        <div className={`flex items-center gap-2 ${active ? 'text-vp-navy' : 'text-vp-muted'}`}>
            <span className={`h-6 w-6 rounded-sm flex items-center justify-center text-[11px] font-semibold ${active ? 'bg-vp-navy text-white' : 'bg-slate-100'}`}>{n}</span>
            <span className="text-[12px] font-medium tracking-wide">{label}</span>
        </div>
    );

    return (
        <div className="max-w-5xl mx-auto space-y-6">
            <div>
                <div className="text-[11px] tracking-[0.22em] uppercase text-vp-muted font-semibold">Data Ingestion</div>
                <h1 className="mt-1 font-heading font-bold text-3xl text-vp-navy">Import sales data</h1>
                <p className="mt-2 text-[13px] text-vp-muted max-w-2xl">Bring in CSV or XLSX order lines. Rules match your headers first; only uncertain fields need review.</p>
            </div>

            {isDemo && (
                <div data-testid="import-demo-notice" className="bg-vp-amberbg border border-vp-amber/40 rounded-md p-4 flex items-start gap-3">
                    <ShieldAlert strokeWidth={1.75} className="h-4 w-4 text-vp-amber mt-0.5 shrink-0" />
                    <div className="text-[12px] text-vp-navy leading-relaxed">
                        <b>Sandbox mode.</b> You can upload a file, map columns and preview validation to see how ingestion works.
                        The final <b>Commit import</b> step is disabled — sandbox sessions never persist data to production tenants.
                        <a href="/login" className="ml-1 underline underline-offset-2 font-semibold">Sign in with an Enterprise Admin account</a> to run a real import.
                    </div>
                </div>
            )}

            <div className="flex items-center gap-6 bg-white border border-vp-border rounded-md p-4">
                <StepBadge n={1} label="Upload" active={step >= 1} />
                <span className="h-px w-8 bg-vp-border" />
                <StepBadge n={2} label="Map columns" active={step >= 2} />
                <span className="h-px w-8 bg-vp-border" />
                <StepBadge n={3} label="Validate" active={step >= 3} />
                <span className="h-px w-8 bg-vp-border" />
                <StepBadge n={4} label="Import" active={step >= 4} />
            </div>

            {/* STEP 1 */}
            {step === 1 && (
                <div className="bg-white border border-vp-border rounded-md p-10 text-center">
                    <div className="mx-auto h-12 w-12 rounded-sm bg-vp-navy text-white flex items-center justify-center mb-4">
                        <FileSpreadsheet strokeWidth={1.5} className="h-5 w-5" />
                    </div>
                    <div className="font-heading font-semibold text-vp-navy text-xl">Choose a CSV or XLSX file</div>
                    <p className="mt-2 text-[13px] text-vp-muted max-w-lg mx-auto">Files stay private to your enterprise. Duplicate imports are prevented by a stable row hash.</p>
                    <label className="mt-6 inline-flex items-center gap-2 bg-vp-navy hover:bg-vp-navyhover text-white text-sm font-medium px-5 py-3 rounded-md cursor-pointer transition-colors">
                        <Upload strokeWidth={1.75} className="h-4 w-4" />
                        {busy ? 'Reading…' : 'Select file'}
                        <input data-testid="import-file-input" type="file" accept=".csv,.xls,.xlsx" className="hidden" onChange={onFile} disabled={busy} />
                    </label>
                </div>
            )}

            {/* STEP 2 */}
            {step === 2 && preview && (
                <div className="space-y-4">
                    {preview.ai_status === 'ok' && (
                        <div className="bg-vp-emeraldbg border border-vp-emerald/40 rounded-md p-3 text-[12px] text-vp-navy flex items-start gap-2">
                            <Sparkles strokeWidth={1.75} className="h-3.5 w-3.5 text-vp-emerald mt-0.5" />
                            <div><b>AI suggestions applied.</b> Unfamiliar headers were mapped by GPT-5.2 based only on their names. Confirm each row before continuing.</div>
                        </div>
                    )}
                    {preview.ai_status === 'unavailable' && (
                        <div className="bg-vp-amberbg border border-vp-amber/40 rounded-md p-3 text-[12px] text-vp-navy flex items-start gap-2" data-testid="ai-unavailable-banner">
                            <AlertCircle strokeWidth={1.75} className="h-3.5 w-3.5 text-vp-amber mt-0.5" />
                            <div><b>AI unavailable — review manually.</b> Only deterministic rules were applied. Please map any remaining columns yourself.</div>
                        </div>
                    )}
                    <div className="bg-white border border-vp-border rounded-md p-5">
                        <div className="text-[12px] text-vp-muted mb-3">
                            <b>{preview.headers.length}</b> columns detected · <b>{preview.sample.length}</b>-row preview · file <code className="text-[11px]">{file?.name}</code>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {preview.headers.map((h) => {
                                const suggest = preview.mapping_suggestion?.[h];
                                const val = mapping[h] || '';
                                const src = suggest?.source;
                                const conf = suggest?.confidence || 0;
                                let badgeClass = 'bg-slate-100 text-vp-muted';
                                let badgeLabel = '—';
                                if (src === 'rules' && conf >= 0.85) {
                                    badgeClass = 'bg-vp-emeraldbg text-vp-emerald';
                                    badgeLabel = `Rules · ${Math.round(conf * 100)}%`;
                                } else if (src === 'ai') {
                                    badgeClass = 'bg-[#E0E7FF] text-[#4338CA]';
                                    badgeLabel = `AI · ${Math.round(conf * 100)}%`;
                                } else if (suggest) {
                                    badgeClass = 'bg-vp-amberbg text-vp-amber';
                                    badgeLabel = `Uncertain · ${Math.round(conf * 100)}%`;
                                }
                                return (
                                    <div key={h} className="flex items-center gap-3">
                                        <div className="flex-1 min-w-0">
                                            <div className="text-[13px] font-medium text-vp-navy truncate">{h}</div>
                                            <div className="text-[11px] text-vp-muted truncate" title={suggest?.reason || ''}>
                                                {suggest?.reason ? `AI: ${suggest.reason}` : `e.g. ${String(preview.sample[0]?.[h] ?? '—').slice(0, 40)}`}
                                            </div>
                                        </div>
                                        <select
                                            data-testid={`map-${h}`}
                                            value={val}
                                            onChange={(e) => setMap(h, e.target.value)}
                                            className="w-56 border border-vp-border rounded-md bg-white px-2 py-1.5 text-[12px] text-vp-navy focus:outline-none focus:border-vp-navy"
                                        >
                                            <option value="">— ignore —</option>
                                            <optgroup label="Required">
                                                {Object.entries(REQUIRED_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                                            </optgroup>
                                            <optgroup label="Optional">
                                                {OPTIONAL.map((k) => <option key={k} value={k}>{k}</option>)}
                                            </optgroup>
                                        </select>
                                        <span className={`text-[10px] px-1.5 py-0.5 rounded-sm whitespace-nowrap ${badgeClass}`} data-testid={`badge-${h}`}>
                                            {badgeLabel}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                    {!requiredCovered && (
                        <div className="bg-vp-amberbg border border-vp-amber/40 rounded-md p-3 text-[12px] text-vp-navy">
                            Map all required fields before continuing.
                        </div>
                    )}
                    <div className="flex justify-between">
                        <button className="text-[13px] text-vp-muted flex items-center gap-1" onClick={() => setStep(1)}><ArrowLeft className="h-3.5 w-3.5" /> Choose different file</button>
                        <button
                            data-testid="import-validate-btn"
                            onClick={onValidate} disabled={!requiredCovered || busy}
                            className="inline-flex items-center gap-2 bg-vp-navy hover:bg-vp-navyhover text-white text-sm font-medium px-5 py-2.5 rounded-md disabled:opacity-60"
                        >
                            {busy ? 'Validating…' : 'Validate'} <ArrowRight className="h-4 w-4" />
                        </button>
                    </div>
                </div>
            )}

            {/* STEP 3 */}
            {step === 3 && validation && (
                <div className="space-y-4">
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                        {[
                            ['Rows total', validation.stats.rows_total],
                            ['Rows ok', validation.stats.rows_ok],
                            ['Rejected', validation.stats.rows_rejected],
                            ['Distributors', validation.stats.distributors],
                            ['Outlets', validation.stats.outlets],
                        ].map(([l, v]) => (
                            <div key={l} className="bg-white border border-vp-border rounded-md p-4">
                                <div className="text-[10px] tracking-[0.18em] uppercase text-vp-muted font-semibold">{l}</div>
                                <div className="mt-2 font-heading font-bold text-2xl text-vp-navy">{v}</div>
                            </div>
                        ))}
                    </div>
                    <div className="text-[12px] text-vp-muted">Date range: <b className="text-vp-navy">{validation.stats.min_date?.slice(0,10)} → {validation.stats.max_date?.slice(0,10)}</b></div>
                    {validation.blocking?.length > 0 && (
                        <div className="bg-vp-redbg border border-vp-red/30 rounded-md p-3">
                            <div className="text-[12px] font-semibold text-vp-red mb-1 flex items-center gap-1"><AlertCircle className="h-3.5 w-3.5" /> Blocking</div>
                            {validation.blocking.map((b, i) => <div key={i} className="text-[12px] text-vp-red">• {b}</div>)}
                        </div>
                    )}
                    {validation.warnings?.length > 0 && (
                        <div className="bg-vp-amberbg border border-vp-amber/40 rounded-md p-3">
                            <div className="text-[12px] font-semibold text-vp-amber mb-1">Warnings</div>
                            {validation.warnings.slice(0, 8).map((w, i) => <div key={i} className="text-[12px] text-vp-navy">• {w}</div>)}
                        </div>
                    )}
                    {validation.rejected_preview?.length > 0 && (
                        <details className="bg-white border border-vp-border rounded-md p-3 text-[12px]">
                            <summary className="cursor-pointer font-semibold text-vp-navy">Rejected rows ({validation.stats.rows_rejected})</summary>
                            <div className="mt-2 space-y-1 max-h-40 overflow-auto">
                                {validation.rejected_preview.map((r, i) => (
                                    <div key={i} className="text-vp-muted">Row {r.row}: {r.errors.join(', ')}</div>
                                ))}
                            </div>
                        </details>
                    )}
                    <div className="flex justify-between items-center">
                        <button className="text-[13px] text-vp-muted flex items-center gap-1" onClick={() => setStep(2)}><ArrowLeft className="h-3.5 w-3.5" /> Back</button>
                        <button
                            data-testid="import-commit-btn"
                            onClick={onCommit}
                            disabled={!validation.ok || importing || isDemo}
                            title={isDemo ? 'Sandbox sessions cannot commit — sign in with Enterprise Admin.' : ''}
                            className="inline-flex items-center gap-2 bg-vp-emerald hover:brightness-95 text-white text-sm font-medium px-5 py-2.5 rounded-md disabled:opacity-60 disabled:cursor-not-allowed"
                        >
                            {isDemo ? 'Commit disabled in sandbox' : (importing ? 'Importing…' : (<>Confirm import <CheckCircle2 className="h-4 w-4" /></>))}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
