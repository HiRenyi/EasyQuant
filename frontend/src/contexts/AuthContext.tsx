import { createContext, useContext, useState, useEffect, useCallback } from "react";
import type { ReactNode } from "react";
import type { User } from "../types/auth";
import { getMe, refreshToken } from "../api/auth";

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isGuest: boolean;
  isLoading: boolean;
  accessToken: string | null;
  showSetPassword: boolean;
  setShowSetPassword: (v: boolean) => void;
  login: (accessToken: string, refreshToken: string, user: User) => void;
  logout: () => void;
  enterGuestMode: () => void;
  updateUser: (u: Partial<User>) => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

const TOKEN_KEY = "quantgpt_access_token";
const REFRESH_KEY = "quantgpt_refresh_token";
const GUEST_FLAG_KEY = "quantgpt_is_guest";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGuest, setIsGuest] = useState(false);
  const [showSetPassword, setShowSetPassword] = useState(false);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(GUEST_FLAG_KEY);
    setAccessToken(null);
    setUser(null);
    setIsGuest(false);
    setShowSetPassword(false);
  }, []);

  const login = useCallback((access: string, refresh: string, u: User) => {
    localStorage.setItem(TOKEN_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
    localStorage.removeItem(GUEST_FLAG_KEY);
    setAccessToken(access);
    setUser(u);
    setIsGuest(false);
    if (!u.has_password) {
      setShowSetPassword(true);
    }
  }, []);

  const enterGuestMode = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/auth/guest-token", { method: "POST" });
      if (!res.ok) throw new Error("Failed to get guest token");
      const { access_token } = await res.json();
      localStorage.setItem(TOKEN_KEY, access_token);
      localStorage.removeItem(REFRESH_KEY);
      localStorage.setItem(GUEST_FLAG_KEY, "1");
      setAccessToken(access_token);
      setUser(null);
      setIsGuest(true);
    } catch {
      localStorage.removeItem(TOKEN_KEY);
    }
  }, []);

  const updateUser = useCallback((partial: Partial<User>) => {
    setUser((prev) => (prev ? { ...prev, ...partial } : prev));
  }, []);

  // On mount: check stored token
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    const storedRefresh = localStorage.getItem(REFRESH_KEY);
    if (!stored) {
      setIsLoading(false);
      return;
    }

    // Restore guest mode
    if (localStorage.getItem(GUEST_FLAG_KEY) === "1") {
      setAccessToken(stored);
      setIsGuest(true);
      setIsLoading(false);
      return;
    }

    getMe(stored)
      .then((u) => {
        setAccessToken(stored);
        setUser(u);
      })
      .catch(async () => {
        // Try refresh
        if (storedRefresh) {
          try {
            const { access_token } = await refreshToken(storedRefresh);
            localStorage.setItem(TOKEN_KEY, access_token);
            const u = await getMe(access_token);
            setAccessToken(access_token);
            setUser(u);
          } catch {
            logout();
          }
        } else {
          logout();
        }
      })
      .finally(() => setIsLoading(false));
  }, [logout]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user || isGuest,
        isGuest,
        isLoading,
        accessToken,
        showSetPassword,
        setShowSetPassword,
        login,
        logout,
        enterGuestMode,
        updateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
