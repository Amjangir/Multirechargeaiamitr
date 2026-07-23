import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/app/ProtectedRoute";
import AppShell from "@/components/app/AppShell";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
import AuthCallback from "@/pages/AuthCallback";
import Dashboard from "@/pages/Dashboard";
import Recharge from "@/pages/Recharge";
import WalletPage from "@/pages/Wallet";
import Transactions from "@/pages/Transactions";
import UsersPage from "@/pages/Users";
import Commissions from "@/pages/Commissions";
import Reports from "@/pages/Reports";
import Settings from "@/pages/Settings";
import { Toaster } from "sonner";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route
            element={
              <ProtectedRoute>
                <AppShell />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/recharge" element={<Recharge />} />
            <Route path="/wallet" element={<WalletPage />} />
            <Route path="/transactions" element={<Transactions />} />
            <Route
              path="/users"
              element={
                <ProtectedRoute roles={["admin", "master_distributor", "distributor"]}>
                  <UsersPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/commissions"
              element={
                <ProtectedRoute roles={["admin"]}>
                  <Commissions />
                </ProtectedRoute>
              }
            />
            <Route path="/reports" element={<Reports />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors theme="dark" />
    </AuthProvider>
  );
}

export default App;
