import { useState, useCallback, useEffect } from "react";
import type { Session } from "../types/backtest";
import {
  fetchSessions,
  createSession as apiCreateSession,
  renameSession as apiRenameSession,
  deleteSession as apiDeleteSession,
} from "../api/client";

export function useSession() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  useEffect(() => {
    fetchSessions()
      .then(({ sessions: loaded }) => {
        if (loaded.length > 0) {
          setSessions(loaded);
          setActiveSessionId(loaded[0].id);
        } else {
          apiCreateSession().then((s) => {
            setSessions([s]);
            setActiveSessionId(s.id);
          });
        }
      })
      .catch(() => {
        setSessions([]);
        setActiveSessionId(null);
      });
  }, []);

  const createSession = useCallback(async () => {
    const s = await apiCreateSession();
    setSessions((prev) => [s, ...prev]);
    setActiveSessionId(s.id);
    return s;
  }, []);

  const switchSession = useCallback((id: string) => {
    setActiveSessionId(id);
  }, []);

  const renameSession = useCallback(async (id: string, name: string) => {
    const updated = await apiRenameSession(id, name);
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, name: updated.name, updated_at: updated.updated_at } : s))
    );
  }, []);

  const deleteSessionById = useCallback(
    async (id: string) => {
      await apiDeleteSession(id);
      setSessions((prev) => {
        const next = prev.filter((s) => s.id !== id);
        if (activeSessionId === id) {
          if (next.length > 0) {
            setActiveSessionId(next[0].id);
          } else {
            apiCreateSession().then((s) => {
              setSessions([s]);
              setActiveSessionId(s.id);
            });
          }
        }
        return next;
      });
    },
    [activeSessionId]
  );

  const refreshSessions = useCallback(() => {
    fetchSessions()
      .then(({ sessions: loaded }) => {
        setSessions(loaded);
      })
      .catch(() => {});
  }, []);

  return {
    sessions,
    activeSessionId,
    createSession,
    switchSession,
    renameSession,
    deleteSession: deleteSessionById,
    refreshSessions,
  };
}
