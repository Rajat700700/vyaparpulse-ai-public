import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Logo } from '../components/Logo';
import { LOGIN } from '../constants/testIds';
import { formatApiErrorDetail } from '../lib/api';
import { AlertCircle, ArrowRight } from 'lucide-react';

export default function LoginPage() {
    const { login, startSandbox } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const from = location.state?.from?.pathname || '/app/command-centre';

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [submitting, setSubmitting] = useState(false);

    const onSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSubmitting(true);
        try {
            await login(email, password);
            navigate(from, { replace: true });
        } catch (err) {
            setError(formatApiErrorDetail(err.response?.data?.detail) || 'Sign-in failed.');
        } finally {
            setSubmitting(false);
        }
    };

    const onSandbox = async () => {
        setError('');
        setSubmitting(true);
        try {
            await startSandbox();
            navigate('/app/command-centre', { replace: true });
        } catch (err) {
            setError(formatApiErrorDetail(err.response?.data?.detail) || 'Sandbox unavailable.');
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="min-h-screen grid grid-cols-1 lg:grid-cols-5 bg-vp-canvas">
            {/* Left brand pane */}
            <div className="hidden lg:flex lg:col-span-2 bg-vp-navy text-white relative overflow-hidden">
                <div className="absolute inset-0 opacity-15" style={{
                    backgroundImage: 'radial-gradient(circle at 20% 20%, #10B981 0px, transparent 40%), radial-gradient(circle at 80% 70%, #F59E0B 0px, transparent 40%)'
                }} />
                <div className="relative p-12 flex flex-col justify-between w-full">
                    <Logo />
                    <div>
                        <div className="text-[11px] tracking-[0.22em] uppercase text-white/60 mb-4">Revenue Recovery Copilot</div>
                        <h2 className="font-heading font-bold text-3xl leading-tight max-w-md">
                            Every rupee is calculated, explained and verified against a real invoice.
                        </h2>
                        <p className="mt-4 text-white/70 text-[13px] max-w-md leading-relaxed">
                            Sign in with your Enterprise Admin account, or open the interactive sandbox for a
                            no-login walkthrough of the contest demo story.
                        </p>
                    </div>
                    <div className="text-[11px] text-white/50 tracking-wide">Contest MVP · Verified Recovery Copilot</div>
                </div>
            </div>

            {/* Form pane */}
            <div className="lg:col-span-3 flex items-center justify-center p-6 sm:p-10">
                <div className="w-full max-w-md">
                    <div className="lg:hidden mb-8"><Logo /></div>
                    <h1 className="font-heading font-bold text-3xl text-vp-navy">Sign in</h1>
                    <p className="mt-2 text-[14px] text-vp-muted">Enterprise Admin access. Users are provisioned by your Platform team — public self-service signup is intentionally disabled.</p>

                    <form
                        onSubmit={onSubmit}
                        data-testid={LOGIN.form}
                        className="mt-8 space-y-4"
                    >
                        {error && (
                            <div
                                data-testid={LOGIN.error}
                                className="flex items-start gap-2 bg-vp-redbg border border-vp-red/30 text-vp-red text-[13px] rounded-md px-3 py-2.5"
                            >
                                <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                                <span>{error}</span>
                            </div>
                        )}
                        <div>
                            <label className="text-[12px] font-medium text-vp-navy tracking-wide uppercase" htmlFor="email">Email</label>
                            <input
                                id="email"
                                type="email"
                                required
                                autoComplete="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                data-testid={LOGIN.email}
                                className="mt-1.5 block w-full rounded-md border border-vp-border bg-white px-3 py-2.5 text-[14px] text-vp-navy focus:outline-none focus:ring-2 focus:ring-vp-navy/20 focus:border-vp-navy transition"
                                placeholder="you@enterprise.com"
                            />
                        </div>
                        <div>
                            <label className="text-[12px] font-medium text-vp-navy tracking-wide uppercase" htmlFor="password">Password</label>
                            <input
                                id="password"
                                type="password"
                                required
                                autoComplete="current-password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                data-testid={LOGIN.password}
                                className="mt-1.5 block w-full rounded-md border border-vp-border bg-white px-3 py-2.5 text-[14px] text-vp-navy focus:outline-none focus:ring-2 focus:ring-vp-navy/20 focus:border-vp-navy transition"
                                placeholder="••••••••"
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={submitting}
                            data-testid={LOGIN.submit}
                            className="w-full inline-flex items-center justify-center gap-2 bg-vp-navy hover:bg-vp-navyhover text-white text-[14px] font-medium px-4 py-3 rounded-md transition-colors disabled:opacity-60"
                        >
                            {submitting ? 'Signing in…' : (<>Sign in <ArrowRight strokeWidth={1.75} className="h-4 w-4" /></>)}
                        </button>
                    </form>

                    <div className="mt-6 flex items-center gap-3">
                        <span className="flex-1 h-px bg-vp-border" />
                        <span className="text-[11px] tracking-widest uppercase text-vp-muted">or</span>
                        <span className="flex-1 h-px bg-vp-border" />
                    </div>

                    <button
                        type="button"
                        onClick={onSandbox}
                        disabled={submitting}
                        data-testid={LOGIN.demoLink}
                        className="mt-6 w-full inline-flex items-center justify-center gap-2 bg-white border border-vp-navy text-vp-navy hover:bg-slate-50 text-[14px] font-medium px-4 py-3 rounded-md transition-colors disabled:opacity-60"
                    >
                        Open interactive sandbox (no login)
                    </button>

                    <div className="mt-8 text-[12px] text-vp-muted">
                        <Link to="/" className="hover:text-vp-navy underline underline-offset-4">← Back to landing</Link>
                    </div>
                </div>
            </div>
        </div>
    );
}
