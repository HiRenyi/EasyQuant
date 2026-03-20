import { useState, useRef, useEffect } from "react";
import { Plus, Trash2, MessageSquare } from "lucide-react";
import type { Session, Task } from "../types/backtest";
import TaskHistoryItem from "./TaskHistoryItem";

interface Props {
  sessions: Session[];
  activeSessionId: string | null;
  tasks: Task[];
  activeTaskId?: string;
  onCreateSession: () => void;
  onSwitchSession: (id: string) => void;
  onRenameSession: (id: string, name: string) => void;
  onDeleteSession: (id: string) => void;
  onSelectTask: (task: Task) => void;
}

export default function SessionSidebar({
  sessions,
  activeSessionId,
  tasks,
  activeTaskId,
  onCreateSession,
  onSwitchSession,
  onRenameSession,
  onDeleteSession,
  onSelectTask,
}: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingId]);

  const startEdit = (session: Session) => {
    setEditingId(session.id);
    setEditValue(session.name ?? "");
  };

  const commitEdit = () => {
    if (editingId && editValue.trim()) {
      onRenameSession(editingId, editValue.trim());
    }
    setEditingId(null);
  };

  return (
    <div className="space-y-2">
      <button
        onClick={onCreateSession}
        className="w-full flex items-center gap-2 rounded-lg border border-dashed border-gray-300 px-3 py-2 text-sm text-gray-500 hover:border-blue-400 hover:text-blue-600 transition-colors"
      >
        <Plus className="h-4 w-4" />
        新建会话
      </button>

      <div className="space-y-1">
        {sessions.map((session) => {
          const isActive = session.id === activeSessionId;
          const isEditing = session.id === editingId;

          return (
            <div key={session.id}>
              {/* Session header */}
              <div
                className={`group flex items-center gap-2 rounded-lg px-3 py-2 cursor-pointer transition-colors ${
                  isActive
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
                onClick={() => onSwitchSession(session.id)}
                onDoubleClick={(e) => {
                  e.stopPropagation();
                  startEdit(session);
                }}
              >
                <MessageSquare className="h-4 w-4 shrink-0" />
                <div className="flex-1 min-w-0">
                  {isEditing ? (
                    <input
                      ref={inputRef}
                      className="w-full bg-white border border-blue-300 rounded px-1 py-0.5 text-sm text-gray-800 outline-none"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onBlur={commitEdit}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitEdit();
                        if (e.key === "Escape") setEditingId(null);
                      }}
                      onClick={(e) => e.stopPropagation()}
                    />
                  ) : (
                    <p className="text-sm truncate">
                      {session.name || "新会话"}
                    </p>
                  )}
                </div>
                {!isEditing && (
                  <button
                    className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-100 transition-opacity"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteSession(session.id);
                    }}
                    title="删除会话"
                  >
                    <Trash2 className="h-3.5 w-3.5 text-red-400 hover:text-red-600" />
                  </button>
                )}
              </div>

              {/* Tasks under active session */}
              {isActive && tasks.length > 0 && (
                <div className="ml-4 mt-1 space-y-1">
                  {tasks.map((task) => (
                    <TaskHistoryItem
                      key={task.task_id}
                      task={task}
                      isActive={task.task_id === activeTaskId}
                      onClick={() => onSelectTask(task)}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {sessions.length === 0 && (
        <div className="text-center py-8 text-sm text-gray-400">
          暂无会话
        </div>
      )}
    </div>
  );
}
