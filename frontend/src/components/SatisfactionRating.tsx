import { useState } from "react";
import { ThumbsUp, ThumbsDown, Send, CheckCircle } from "lucide-react";
import { useColorMode } from "../contexts/ColorModeContext";
import { submitFeedback } from "../api/client";

interface Props {
  taskId: string;
  expression?: string;
}

export default function SatisfactionRating({ taskId, expression }: Props) {
  const { isDark } = useColorMode();
  const [rating, setRating] = useState<"up" | "down" | null>(null);
  const [feedbackText, setFeedbackText] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [hidden, setHidden] = useState(false);

  if (hidden) return null;

  const handleThumbsUp = () => {
    setRating("up");
    submitFeedback({
      description: `[满意] 回测结果满意${expression ? ` | 表达式: ${expression}` : ""}`,
      task_id: taskId,
      page_url: window.location.href,
    }).catch(() => {});
    setTimeout(() => setHidden(true), 2000);
  };

  const handleThumbsDown = () => {
    setRating("down");
  };

  const handleSubmitFeedback = async () => {
    if (!feedbackText.trim()) return;
    setSubmitting(true);
    try {
      await submitFeedback({
        description: `[不满意] ${feedbackText.trim()}${expression ? ` | 表达式: ${expression}` : ""}`,
        task_id: taskId,
        page_url: window.location.href,
      });
      setSubmitted(true);
      setTimeout(() => setHidden(true), 2000);
    } catch {
      setSubmitting(false);
    }
  };

  return (
    <div className={`rounded-xl border ${isDark ? "border-gray-700" : "border-gray-200"} ${isDark ? "bg-gray-900" : "bg-white"} px-4 py-3 animate-fade-in`}>
      {rating === null && (
        <div className="flex items-center justify-between">
          <span className={`text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>这次回测结果如何？</span>
          <div className="flex items-center gap-2">
            <button
              onClick={handleThumbsUp}
              className={`flex items-center gap-1 px-3 py-1.5 text-sm ${isDark ? "text-gray-400" : "text-gray-500"} ${isDark ? "hover:text-emerald-400 hover:bg-emerald-500/10" : "hover:text-emerald-600 hover:bg-emerald-50"} rounded-lg transition-colors`}
            >
              <ThumbsUp className="h-4 w-4" /> 满意
            </button>
            <button
              onClick={handleThumbsDown}
              className={`flex items-center gap-1 px-3 py-1.5 text-sm ${isDark ? "text-gray-400" : "text-gray-500"} ${isDark ? "hover:text-red-400 hover:bg-red-500/10" : "hover:text-red-600 hover:bg-red-50"} rounded-lg transition-colors`}
            >
              <ThumbsDown className="h-4 w-4" /> 不满意
            </button>
          </div>
        </div>
      )}

      {rating === "up" && (
        <div className={`flex items-center gap-2 text-sm ${isDark ? "text-emerald-400" : "text-emerald-600"}`}>
          <CheckCircle className="h-4 w-4" /> 感谢反馈！
        </div>
      )}

      {rating === "down" && !submitted && (
        <div className="space-y-2">
          <p className={`text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>哪里可以改进？</p>
          <textarea
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            placeholder="告诉我们你的想法..."
            rows={2}
            maxLength={500}
            className={`w-full rounded-lg border ${isDark ? "border-gray-700" : "border-gray-200"} px-3 py-2 text-sm ${isDark ? "bg-gray-800 text-gray-200" : ""} focus:outline-none focus:ring-2 ${isDark ? "focus:ring-amber-500" : "focus:ring-blue-500"} focus:border-transparent resize-none`}
            autoFocus
          />
          <div className="flex justify-end">
            <button
              onClick={handleSubmitFeedback}
              disabled={!feedbackText.trim() || submitting}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white ${isDark ? "bg-amber-500 hover:bg-amber-600" : "bg-blue-600 hover:bg-blue-700"} rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors`}
            >
              <Send className="h-3.5 w-3.5" />
              {submitting ? "提交中..." : "提交"}
            </button>
          </div>
        </div>
      )}

      {rating === "down" && submitted && (
        <div className={`flex items-center gap-2 text-sm ${isDark ? "text-emerald-400" : "text-emerald-600"}`}>
          <CheckCircle className="h-4 w-4" /> 已收到，感谢反馈！
        </div>
      )}
    </div>
  );
}
