import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from "react";
import { get, post, tokens, User } from "./api";

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (d: { email: string; password: string; display_name: string; roles_wanted: string[] }) => Promise<User>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      if (tokens.access) {
        try { setUser(await get<User>("/me")); } catch { setUser(null); }
      }
      setLoading(false);
    })();
  }, []);

  const login = async (email: string, password: string) => {
    const t = await post<{ access_token: string; refresh_token: string }>("/auth/login", { email, password });
    tokens.access = t.access_token;
    tokens.refresh = t.refresh_token;
    const me = await get<User>("/me");
    setUser(me);
    return me;
  };

  const register = async (d: { email: string; password: string; display_name: string; roles_wanted: string[] }) => {
    const t = await post<{ access_token: string; refresh_token: string }>("/auth/register", d);
    tokens.access = t.access_token;
    tokens.refresh = t.refresh_token;
    const me = await get<User>("/me");
    setUser(me);
    return me;
  };

  const logout = () => {
    tokens.access = null;
    tokens.refresh = null;
    setUser(null);
  };

  return <Ctx.Provider value={{ user, loading, login, register, logout }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
