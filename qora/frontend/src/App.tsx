import { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth";
import { Navbar, Spinner } from "./ui";
import Chat from "./pages/Chat";
import Explore from "./pages/Explore";
import MyQora from "./pages/MyQora";
import Creator from "./pages/Creator";
import Orchestrate from "./pages/Orchestrate";
import Auth from "./pages/Auth";

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <Spinner label="Starting QORA…" />;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="flex-1">
        <Routes>
          <Route path="/login" element={<Auth mode="login" />} />
          <Route path="/register" element={<Auth mode="register" />} />
          <Route path="/" element={<Protected><Chat /></Protected>} />
          <Route path="/explore" element={<Protected><Explore /></Protected>} />
          <Route path="/my-qora" element={<Protected><MyQora /></Protected>} />
          <Route path="/creator" element={<Protected><Creator /></Protected>} />
          <Route path="/orchestrate" element={<Protected><Orchestrate /></Protected>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
