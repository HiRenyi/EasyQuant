import { useState, useRef, useCallback, useEffect } from "react";
import { MessageSquarePlus, X, Image, Send, CheckCircle } from "lucide-react";
import { submitFeedback } from "../api/client";
import { useColorMode } from "../contexts/ColorModeContext";

type Status = "idle" | "submitting" | "success" | "error";

const SEEN_KEY = "quantgpt_feedback_seen";

export default function FeedbackButton() {
  const { isDark } = useColorMode();
  const [open, setOpen] = useState(false);
  const [description, setDescription] = useState("");
  const [screenshot, setScreenshot] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [showTooltip, setShowTooltip] = useState(false);
  const [pulse, setPulse] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // First-visit pulse animation
  useEffect(() => {
    if (!localStorage.getItem(SEEN_KEY)) {
      setPulse(true);
      setShowTooltip(true);
      const timer = setTimeout(() => setShowTooltip(false), 4000);
      return () => clearTimeout(timer);
    }
  }, []);

  // Listen for external open-feedback events (from failure UI, etc.)
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail || {};
      if (detail.prefill) setDescription(detail.prefill);
      if (detail.task_id) setTaskId(detail.task_id);
      setOpen(true);
    };
    window.addEventListener("open-feedback", handler);
    return () => window.removeEventListener("open-feedback", handler);
  }, []);

  // Focus textarea when modal opens
  useEffect(() => {
    if (open) setTimeout(() => textareaRef.current?.focus(), 100);
  }, [open]);

  // Handle paste anywhere in the modal
  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith("image/")) {
        e.preventDefault();
        const file = item.getAsFile();
        if (file) readFileAsBase64(file);
        return;
      }
    }
  }, []);

  const readFileAsBase64 = (file: File) => {
    if (file.size > 5 * 1024 * 1024) {
      setErrorMsg("截图文件过大（最大5MB）");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setScreenshot(reader.result as string);
    reader.readAsDataURL(file);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) readFileAsBase64(file);
  };

  const handleSubmit = async () => {
    if (!description.trim()) return;
    setStatus("submitting");
    setErrorMsg("");
    try {
      await submitFeedback({
        description: description.trim(),
        screenshot,
        task_id: taskId,
        page_url: window.location.href,
        user_agent: navigator.userAgent,
      });
      setStatus("success");
      setTimeout(() => {
        setOpen(false);
        setDescription("");
        setScreenshot(null);
        setTaskId(null);
        setStatus("idle");
      }, 1500);
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "提交失败");
    }
  };

  const handleClose = () => {
    if (status === "submitting") return;
    setOpen(false);
    setStatus("idle");
    setErrorMsg("");
  };

  const handleButtonClick = () => {
    setPulse(false);
    setShowTooltip(false);
    localStorage.setItem(SEEN_KEY, "1");
    setOpen(true);
  };

  return (
    <>
      {/* Floating button with optional pulse */}
      <div className="fixed bottom-6 right-6 z-50">
        {showTooltip && (
          <div className="absolute bottom-full right-0 mb-2 px-3 py-1.5 bg-gray-800 text-white text-xs rounded-lg whitespace-nowrap shadow-lg animate-fade-in">
            遇到问题？点我反馈
            <div className="absolute top-full right-4 border-4 border-transparent border-t-gray-800" />
          </div>
        )}
        <button
          onClick={handleButtonClick}
          className={`flex items-center gap-2 px-4 py-2.5 bg-gray-800 text-white rounded-full shadow-lg hover:bg-gray-700 transition-colors text-sm font-medium ${pulse ? "animate-pulse" : ""}`}
        >
          <MessageSquarePlus className="h-4 w-4" />
          反馈
        </button>
      </div>

      {/* Modal overlay */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={handleClose}>
          <div
            className={`${isDark ? "bg-gray-900" : "bg-white"} rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden`}
            onClick={(e) => e.stopPropagation()}
            onPaste={handlePaste}
          >
            {/* Header */}
            <div className={`flex items-center justify-between px-5 py-4 border-b ${isDark ? "border-gray-700" : "border-gray-100"}`}>
              <h3 className={`text-base font-semibold ${isDark ? "text-gray-100" : "text-gray-900"}`}>问题反馈</h3>
              <button onClick={handleClose} className={`text-gray-400 ${isDark ? "hover:text-gray-200" : "hover:text-gray-600"} transition-colors`}>
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Body */}
            <div className="px-5 py-4 space-y-4">
              <div>
                <label className={`block text-sm font-medium ${isDark ? "text-gray-300" : "text-gray-700"} mb-1.5`}>问题描述</label>
                <textarea
                  ref={textareaRef}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="描述你遇到的问题..."
                  rows={4}
                  maxLength={2000}
                  className={`w-full rounded-lg border ${isDark ? "border-gray-700 bg-gray-800 text-gray-100 placeholder-gray-500 focus:ring-amber-500" : "border-gray-200 bg-white text-gray-900 focus:ring-blue-500"} px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:border-transparent resize-none`}
                />
                <p className="mt-1 text-xs text-gray-400 text-right">{description.length}/2000</p>
              </div>

              <div>
                <label className={`block text-sm font-medium ${isDark ? "text-gray-300" : "text-gray-700"} mb-1.5`}>截图（可选）</label>
                {screenshot ? (
                  <div className="relative group">
                    <img src={screenshot} alt="截图预览" className={`w-full max-h-48 object-contain rounded-lg border ${isDark ? "border-gray-700 bg-gray-800" : "border-gray-200 bg-gray-50"}`} />
                    <button
                      onClick={() => setScreenshot(null)}
                      className="absolute top-2 right-2 p-1 bg-black/60 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ) : (
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className={`flex flex-col items-center justify-center gap-2 py-6 rounded-lg border-2 border-dashed ${isDark ? "border-gray-700 cursor-pointer hover:border-amber-500/50 hover:bg-amber-500/5" : "border-gray-200 cursor-pointer hover:border-blue-300 hover:bg-blue-50/30"} transition-colors`}
                  >
                    <Image className={`h-6 w-6 ${isDark ? "text-gray-600" : "text-gray-300"}`} />
                    <p className="text-xs text-gray-400">粘贴截图 <span className={isDark ? "text-gray-600" : "text-gray-300"}>(Ctrl+V)</span> 或点击上传</p>
                  </div>
                )}
                <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileSelect} className="hidden" />
              </div>

              {errorMsg && <p className={`text-sm ${isDark ? "text-red-400" : "text-red-600"}`}>{errorMsg}</p>}
            </div>

            {/* Footer */}
            <div className={`px-5 py-3 border-t ${isDark ? "border-gray-700" : "border-gray-100"} flex justify-end gap-2`}>
              <button onClick={handleClose} disabled={status === "submitting"} className={`px-4 py-2 text-sm ${isDark ? "text-gray-400 hover:text-gray-200" : "text-gray-600 hover:text-gray-800"} transition-colors`}>
                取消
              </button>
              <button
                onClick={handleSubmit}
                disabled={!description.trim() || status === "submitting" || status === "success"}
                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {status === "submitting" ? (
                  <>
                    <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    提交中...
                  </>
                ) : status === "success" ? (
                  <>
                    <CheckCircle className="h-4 w-4" />
                    已收到
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4" />
                    提交反馈
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
