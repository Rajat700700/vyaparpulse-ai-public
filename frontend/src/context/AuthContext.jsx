import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { api } from '../lib/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);      // null=checking, false=anon, object=authed
    const [loading, setLoading] = useState(true);

    const refresh = useCallback(async () => {
        try {
            const { data } = await api.get('/auth/me');
            setUser(data);
        } catch (e) {
            setUser(false);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { refresh(); }, [refresh]);

    const login = async (email, password) => {
        const { data } = await api.post('/auth/login', { email, password });
        setUser(data);
        return data;
    };

    const startSandbox = async () => {
        const { data } = await api.post('/demo/session');
        setUser(data);
        return data;
    };

    const logout = async () => {
        try { await api.post('/auth/logout'); } catch (_) { /* ignore */ }
        setUser(false);
    };

    return (
        <AuthContext.Provider value={{ user, loading, login, startSandbox, logout, refresh }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within AuthProvider');
    return ctx;
}
