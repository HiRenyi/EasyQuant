import { useState } from "react";
import { X, Lock, Eye, EyeOff } from "lucide-react";
import { setPassword } from "../api/auth";
import { useAuth } from "../contexts/AuthContext";

export default function SetPasswordModal() {
  const { accessToken, showSetPassword, setShowSetPassword, updateUser } = useAuth();
  const [password, setPasswordVal] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (!showSetPassword) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password.length < 6) {
      setError("密码至少 6 个字符");
      return;
    }
    if (password !== confirm) {
      setError("两次密码不一致");
      return;
    }
    if (!accessToken) return;

    setLoading(true);
    try {
      await setPassword(accessToken, password);
      updateUser({ has_password: true });
      setShowSetPassword(false);
    } catch (err: any) {
      setError(err.message || "设置失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 flex items-start justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
              <Lock className="h-5 w-5 text-blue-600" />
              设置登录密码
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              设置密码后，下次可直接用邮箱 + 密码登录，无需验证码
            </p>
          </div>
          <button
            onClick={() => setShowSetPassword(false)}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 pb-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              新密码
            </label>
            <div className="relative">
              <input
                type={showPwd ? "text" : "password"}
                value={password}
                onChange={(e) => setPasswordVal(e.target.value)}
                placeholder="至少 6 个字符"
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all pr-10"
                autoFocus
              />
              <button
                type="button"
                onClick={() => setShowPwd(!showPwd)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              确认密码
            </label>
            <input
              type={showPwd ? "text" : "password"}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="再次输入密码"
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={() => setShowSetPassword(false)}
              className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors text-sm font-medium"
            >
              稍后设置
            </button>
            <button
              type="submit"
              disabled={loading || !password || !confirm}
              className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
            >
              {loading ? "设置中..." : "确认设置"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
