"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, ApiError } from "@/lib/api";
import type { LoginPayload, SignUpPayload, UserProfile } from "@/lib/auth/types";

interface AuthContextValue {
  user: UserProfile | null;
  loading: boolean;
  signUp: (payload: SignUpPayload) => Promise<void>;
  signIn: (payload: LoginPayload) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
  setUser: (user: UserProfile) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    try {
      const me = await api.get<UserProfile>("/auth/me");
      setUser(me);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    api
      .get<UserProfile>("/auth/me")
      .then((me) => {
        if (active) setUser(me);
      })
      .catch((err) => {
        if (active && err instanceof ApiError && err.status === 401) setUser(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const signUp = useCallback(async (payload: SignUpPayload) => {
    const created = await api.post<UserProfile>("/auth/signup", payload);
    setUser(created);
  }, []);

  const signIn = useCallback(async (payload: LoginPayload) => {
    const loggedIn = await api.post<UserProfile>("/auth/login", payload);
    setUser(loggedIn);
  }, []);

  const signOut = useCallback(async () => {
    await api.post("/auth/logout");
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, loading, signUp, signIn, signOut, refreshUser: loadUser, setUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
