import { Construction } from 'lucide-react';

export default function AppPlaceholder({ title, phase = 2, description }) {
    return (
        <div className="max-w-2xl mx-auto mt-10">
            <div className="bg-white border border-vp-border rounded-md p-8 text-center">
                <div className="mx-auto h-11 w-11 rounded-sm bg-slate-100 text-vp-navy flex items-center justify-center mb-4">
                    <Construction strokeWidth={1.75} className="h-5 w-5" />
                </div>
                <div className="text-[11px] tracking-[0.22em] uppercase text-vp-muted font-semibold">Phase {phase}</div>
                <h2 className="mt-2 font-heading font-bold text-2xl text-vp-navy">{title}</h2>
                <p className="mt-3 text-[13px] text-vp-muted leading-relaxed">{description}</p>
            </div>
        </div>
    );
}
