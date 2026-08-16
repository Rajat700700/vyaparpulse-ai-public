import { Link } from 'react-router-dom';

export function Logo({ compact = false }) {
    return (
        <Link to="/" className="flex items-center gap-2.5 group">
            <span className="relative flex h-8 w-8 items-center justify-center rounded-sm bg-vp-navy text-white overflow-hidden">
                <span className="absolute inset-0 opacity-70" style={{
                    background: 'radial-gradient(circle at 30% 30%, rgba(16,185,129,0.35), transparent 60%)',
                }} />
                <span className="relative font-heading font-black text-[15px] leading-none">V</span>
                <span className="absolute right-0 bottom-0 h-1.5 w-1.5 bg-vp-emerald rounded-sm" />
            </span>
            {!compact && (
                <span className="font-heading font-bold text-vp-navy text-[17px] tracking-tight leading-none">
                    VyaparPulse<span className="text-vp-emerald">·</span>AI
                </span>
            )}
        </Link>
    );
}
