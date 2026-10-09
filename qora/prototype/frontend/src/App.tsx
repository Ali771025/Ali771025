import { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import { useAuth } from "./context/AuthContext";
import Home from "./pages/Home";
import Services from "./pages/Services";
import ServiceDetail from "./pages/ServiceDetail";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Assistant from "./pages/Assistant";
import Dashboard from "./pages/Dashboard";
import Provider from "./pages/Provider";
import Admin from "./pages/Admin";
import WalletPage from "./pages/WalletPage";
import { Spinner } from "./components/ui";

function Protected({ children, roles }: { children: ReactNode; roles?: string[] }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <Spinner label="Checking your session…" />;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/services" element={<Services />} />
          <Route path="/services/:id" element={<ServiceDetail />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/assistant" element={<Assistant />} />
          <Route
            path="/dashboard"
            element={
              <Protected roles={["consumer", "provider", "admin"]}>
                <Dashboard />
              </Protected>
            }
          />
          <Route
            path="/wallet"
            element={
              <Protected>
                <WalletPage />
              </Protected>
            }
          />
          <Route
            path="/provider"
            element={
              <Protected roles={["provider", "admin"]}>
                <Provider />
              </Protected>
            }
          />
          <Route
            path="/admin"
            element={
              <Protected roles={["admin"]}>
                <Admin />
              </Protected>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}
