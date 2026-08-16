import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children }) {
    const { user, loading } = useAuth();
    const location = useLocation();
    if (loading || user === null) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-vp-canvas">
                <div className="text-vp-muted text-sm tracking-wide uppercase">Loading workspace…</div>
            </div>
        );
    }
    if (user === false) {
        return <Navigate to="/login" state={{ from: location }} replace />;
    }
    return children;
}
