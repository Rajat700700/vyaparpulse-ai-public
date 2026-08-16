import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { paiseToCompact } from '../lib/format';
import { toast } from 'sonner';
import { CheckCircle2, XCircle, Play, Clock, AlertTriangle, Globe } from 'lucide-react';

const L = {
    en: {
        title: 'Action Board', overdue: 'Overdue', today: 'Today', upcoming: 'Upcoming', done: 'Done',
        start: 'Start', complete: 'Complete', skip: 'Skip',
        invoice: 'Invoice number', claimed: 'Claimed ₹', reason: 'Skip reason', due: 'Due',
        completed: 'Marked completed', skipped: 'Marked skipped',
        empty: 'Nothing here yet — actions will appear when opportunities are assigned to you.',
        actions: {
            LAPSED: 'Visit outlet within 3 days; confirm reason for stoppage and re-activate with current top SKUs.',
            DECLINING: 'Call salesperson; audit last two orders and prevent further slide with a targeted assortment refresh.',
            MISSED: 'Trigger next-order reminder; schedule visit before overdue cycle doubles.',
            WHITESPACE: 'Introduce the recommended SKU adopted by peers on the next visit.',
        },
    },
    hi: {
        title: 'कार्य सूची', overdue: 'देर से', today: 'आज', upcoming: 'आने वाले', done: 'पूरे',
        start: 'शुरू करें', complete: 'पूरा करें', skip: 'छोड़ें',
        invoice: 'इनवॉइस नंबर', claimed: 'दावा ₹', reason: 'छोड़ने का कारण', due: 'अंतिम तारीख',
        completed: 'पूरा कर दिया', skipped: 'छोड़ दिया',
        empty: 'अभी कोई कार्य नहीं। जब आपको कोई अवसर सौंपा जाएगा, यह यहाँ दिखाई देगा।',
        actions: {
            LAPSED: '3 दिन के अंदर आउटलेट पर जाएँ; ऑर्डर रुकने का कारण जानें और मौजूदा टॉप SKU के साथ फिर से ऐक्टिवेट करें।',
            DECLINING: 'सेल्समैन को कॉल करें; पिछले दो ऑर्डर की जांच करें और सही SKU मिक्स से गिरावट रोकें।',
            MISSED: 'अगले ऑर्डर का रिमाइंडर भेजें; साइकल दोगुनी होने से पहले विज़िट प्लान करें।',
            WHITESPACE: 'अगली विज़िट में पड़ोसी आउटलेट में चल रहा नया SKU आउटलेट को दिखाएँ और ट्रायल ऑर्डर लें।',
        },
    },
};

export default function ActionBoard() {
    const [lang, setLang] = useState('en');
    const [buckets, setBuckets] = useState({ overdue: [], today: [], upcoming: [], done: [] });
    const [loading, setLoading] = useState(true);
    const [dialog, setDialog] = useState(null); // {action, event}
    const t = L[lang];

    const load = () => {
        setLoading(true);
        api.get('/actions').then((r) => setBuckets(r.data.buckets)).finally(() => setLoading(false));
    };
    useEffect(load, []);

    const doTransition = async (action, event, payload = {}) => {
        try {
            const r = await api.post(`/actions/${action.id}/transition`, { event, ...payload });
            if (event === 'complete') {
                const rec = r.data.recovery;
                toast.success(rec ? `${t.completed} · ${paiseToCompact(rec.verified_paise)} verified` : t.completed);
            } else if (event === 'skip') {
                toast.success(t.skipped);
            } else {
                toast.success('OK');
            }
            setDialog(null);
            load();
        } catch (e) {
            const detail = e?.response?.data?.detail;
            toast.error(typeof detail === 'string' ? detail : 'Transition failed');
        }
    };

    const ActionCard = ({ a, tone }) => (
        <div className={`bg-white border rounded-md p-3 ${tone}`} data-testid={`action-${a.id}`}>
            <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                    <div className="text-[11px] text-vp-muted uppercase tracking-widest">{a.opportunity_type} · Score {a.priority_score_snapshot}</div>
                    <div className="font-heading font-semibold text-vp-navy text-[14px] truncate">{a.outlet_name}</div>
                    <div className="text-[11px] text-vp-muted truncate">{a.distributor_code} · {a.salesperson_code}</div>
                </div>
                <div className="text-right shrink-0">
                    <div className="font-heading font-bold text-vp-navy">{paiseToCompact(a.est_recovery_paise_snapshot)}</div>
                    <div className="text-[10px] text-vp-muted">{t.due} {String(a.due_date).slice(0, 10)}</div>
                </div>
            </div>
            <div className="text-[11px] text-vp-navy mt-1 line-clamp-2" data-testid={`action-instruction-${a.id}`}>
                {t.actions[a.opportunity_type] || a.recommended_action}
            </div>
            {a.status !== 'COMPLETED' && a.status !== 'SKIPPED' && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                    {a.status === 'ASSIGNED' && (
                        <button data-testid={`start-${a.id}`} onClick={() => doTransition(a, 'start')} className="text-[11px] px-2.5 py-1 rounded-sm bg-vp-navy text-white flex items-center gap-1"><Play className="h-3 w-3" /> {t.start}</button>
                    )}
                    {a.status === 'IN_PROGRESS' && (
                        <button data-testid={`complete-${a.id}`} onClick={() => setDialog({ action: a, event: 'complete' })} className="text-[11px] px-2.5 py-1 rounded-sm bg-vp-emerald text-white flex items-center gap-1"><CheckCircle2 className="h-3 w-3" /> {t.complete}</button>
                    )}
                    <button data-testid={`skip-${a.id}`} onClick={() => setDialog({ action: a, event: 'skip' })} className="text-[11px] px-2.5 py-1 rounded-sm bg-slate-200 text-vp-navy flex items-center gap-1"><XCircle className="h-3 w-3" /> {t.skip}</button>
                </div>
            )}
            {(a.status === 'COMPLETED' || a.status === 'SKIPPED') && (
                <div className="mt-2 text-[10px] uppercase tracking-widest">
                    <span className={`px-1.5 py-0.5 rounded-sm ${a.status === 'COMPLETED' ? 'bg-vp-emeraldbg text-vp-emerald' : 'bg-slate-100 text-vp-muted'}`}>{a.status}</span>
                    {a.verified_paise != null && (
                        <span className="ml-2 text-vp-emerald">Verified {paiseToCompact(a.verified_paise)}</span>
                    )}
                </div>
            )}
        </div>
    );

    const Column = ({ title, items, tone, testid, icon }) => (
        <div>
            <div className="text-[10px] tracking-[0.22em] uppercase text-vp-muted font-semibold mb-2 flex items-center gap-1">{icon}{title} <span className="text-vp-navy">({items.length})</span></div>
            <div className="space-y-2" data-testid={testid}>
                {items.map((a) => <ActionCard key={a.id} a={a} tone={tone} />)}
                {items.length === 0 && <div className="text-[11px] text-vp-muted">—</div>}
            </div>
        </div>
    );

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
                <div>
                    <div className="text-[11px] tracking-[0.22em] uppercase text-vp-muted font-semibold">{t.title}</div>
                    <h1 className="mt-1 font-heading font-bold text-3xl text-vp-navy">{lang === 'en' ? 'Your recovery actions' : 'आपके रिकवरी कार्य'}</h1>
                </div>
                <button data-testid="lang-toggle" onClick={() => setLang(lang === 'en' ? 'hi' : 'en')}
                    className="inline-flex items-center gap-1.5 text-[12px] bg-white border border-vp-border rounded-md px-3 py-1.5 text-vp-navy">
                    <Globe className="h-3.5 w-3.5" /> {lang === 'en' ? 'हिंदी' : 'English'}
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <Column title={t.overdue} items={buckets.overdue} tone="border-vp-red/40" testid="col-overdue" icon={<AlertTriangle className="h-3 w-3 text-vp-red" />} />
                <Column title={t.today} items={buckets.today} tone="border-vp-amber/40" testid="col-today" icon={<Clock className="h-3 w-3 text-vp-amber" />} />
                <Column title={t.upcoming} items={buckets.upcoming} tone="border-vp-border" testid="col-upcoming" icon={<Play className="h-3 w-3 text-vp-navy" />} />
                <Column title={t.done} items={buckets.done} tone="border-vp-emerald/40" testid="col-done" icon={<CheckCircle2 className="h-3 w-3 text-vp-emerald" />} />
            </div>

            {/* Dialog */}
            {dialog && (
                <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setDialog(null)}>
                    <div className="bg-white rounded-md w-full max-w-md p-5" onClick={(e) => e.stopPropagation()} data-testid="action-dialog">
                        <div className="font-heading font-bold text-vp-navy">{dialog.event === 'complete' ? t.complete : t.skip} · {dialog.action.outlet_name}</div>
                        {dialog.event === 'complete' ? (
                            <CompleteForm onSubmit={(payload) => doTransition(dialog.action, 'complete', payload)} t={t} action={dialog.action} />
                        ) : (
                            <SkipForm onSubmit={(payload) => doTransition(dialog.action, 'skip', payload)} t={t} />
                        )}
                        <button onClick={() => setDialog(null)} className="mt-3 text-[12px] text-vp-muted">Cancel</button>
                    </div>
                </div>
            )}
        </div>
    );
}

function CompleteForm({ onSubmit, t, action }) {
    const [invoice, setInvoice] = useState('');
    const [claimed, setClaimed] = useState(String(Math.round((action.est_recovery_paise_snapshot || 0) / 100)));
    return (
        <div className="mt-4 space-y-3">
            <div>
                <label className="text-[11px] uppercase tracking-widest text-vp-muted">{t.invoice}</label>
                <input data-testid="invoice-input" value={invoice} onChange={(e) => setInvoice(e.target.value)}
                    className="mt-1 w-full border border-vp-border rounded-md px-3 py-2 text-[13px]" placeholder="INV-XXX" />
            </div>
            <div>
                <label className="text-[11px] uppercase tracking-widest text-vp-muted">{t.claimed}</label>
                <input data-testid="claimed-input" value={claimed} onChange={(e) => setClaimed(e.target.value.replace(/[^0-9]/g, ''))}
                    className="mt-1 w-full border border-vp-border rounded-md px-3 py-2 text-[13px]" />
            </div>
            <button data-testid="complete-submit" onClick={() => onSubmit({ invoice_ref: invoice, claimed_paise: Number(claimed) * 100 })}
                disabled={!invoice || !claimed}
                className="w-full bg-vp-emerald text-white text-[13px] font-medium py-2 rounded-md disabled:opacity-50">
                {t.complete}
            </button>
        </div>
    );
}

function SkipForm({ onSubmit, t }) {
    const [reason, setReason] = useState('');
    return (
        <div className="mt-4 space-y-3">
            <div>
                <label className="text-[11px] uppercase tracking-widest text-vp-muted">{t.reason}</label>
                <textarea data-testid="skip-reason" value={reason} onChange={(e) => setReason(e.target.value)}
                    className="mt-1 w-full border border-vp-border rounded-md px-3 py-2 text-[13px] h-20" placeholder="Outlet closed…" />
            </div>
            <button data-testid="skip-submit" onClick={() => onSubmit({ skip_reason: reason })} disabled={!reason}
                className="w-full bg-slate-800 text-white text-[13px] font-medium py-2 rounded-md disabled:opacity-50">
                {t.skip}
            </button>
        </div>
    );
}
