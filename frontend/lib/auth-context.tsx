"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiClient, clearTokens, getAccessToken, setTokens } from "@/lib/api-client";
import type { ApiSuccess, User } from "@/types/api";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasRole: (...roles: string[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const loadUser = useCallback(async () => {
    if (!getAccessToken()) {
      setIsLoading(false);
      return;
    }
    try {
      const res = await apiClient.get<ApiSuccess<User>>("/auth/me");
      setUser(res.data);
    } catch {
      clearTokens();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await apiClient.post<
        ApiSuccess<{ access_token: string; refresh_token: string }>
      >("/auth/login", { email, password }, { skipAuth: true });
      setTokens(res.data.access_token, res.data.refresh_token);
      await loadUser();
      router.push("/dashboard");
    },
    [loadUser, router]
  );

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    router.push("/login");
  }, [router]);

  const hasRole = useCallback((...roles: string[]) => !!user && roles.some((r) => user.roles.includes(r)), [user]);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, hasRole }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
