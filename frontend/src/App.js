import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AuthProvider } from '@/context/AuthContext';
import ProtectedRoute from '@/components/ProtectedRoute';
import AppShell from '@/components/AppShell';
import LandingPage from '@/pages/Landing';
import LoginPage from '@/pages/Login';
import CommandCentre from '@/pages/CommandCentre';
import ImportWizardPage from '@/pages/ImportWizard';
import RecoveryRadar from '@/pages/RecoveryRadar';
import OutletsPage from '@/pages/Outlets';
import OutletDetail from '@/pages/OutletDetail';
import ActionBoard from '@/pages/ActionBoard';
import ImpactLedger from '@/pages/ImpactLedger';
import DailyBrief from '@/pages/DailyBrief';
import ProofCard from '@/pages/ProofCard';
import AppPlaceholder from '@/pages/AppPlaceholder';

function App() {
    return (
        <AuthProvider>
            <BrowserRouter>
                <Toaster richColors closeButton position="top-right" />
                <Routes>
                    <Route path="/" element={<LandingPage />} />
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="/proof/:token" element={<ProofCard />} />
                    <Route
                        path="/app"
                        element={
                            <ProtectedRoute>
                                <AppShell />
                            </ProtectedRoute>
                        }
                    >
                        <Route index element={<Navigate to="command-centre" replace />} />
                        <Route path="command-centre" element={<CommandCentre />} />
                        <Route path="import" element={<ImportWizardPage />} />
                        <Route path="recovery-radar" element={<RecoveryRadar />} />
                        <Route path="actions" element={<ActionBoard />} />
                        <Route path="outlets" element={<OutletsPage />} />
                        <Route path="outlets/:outletCode" element={<OutletDetail />} />
                        <Route path="impact-ledger" element={<ImpactLedger />} />
                        <Route path="brief" element={<DailyBrief />} />
                        <Route path="settings" element={<AppPlaceholder title="Settings" phase={4} description="Threshold tuning, user provisioning and mapping templates — arriving post-contest." />} />
                    </Route>
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </BrowserRouter>
        </AuthProvider>
    );
}

export default App;
