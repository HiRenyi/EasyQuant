import { useState, useCallback, useEffect, useRef } from "react";
import { BarChart3, Mail, Lock, ArrowLeft, Loader2, Eye, EyeOff, FlaskConical, Terminal, Sparkles, ShieldCheck } from "lucide-react";
import { sendCode, verifyCode, loginWithPassword, resetPassword } from "../api/auth";
import { useAuth } from "../contexts/AuthContext";
import { useNavigate } from "react-router-dom";

type Mode = "password" | "code-email" | "code-verify" | "register-email" | "register-verify" | "forgot-email" | "forgot-verify";

export default function LoginPage() {
  const { login, isAuthenticated, enterGuestMode } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [successMsg, setSuccessMsg] = useState("");
  const codeInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isAuthenticated) navigate("/", { replace: true });
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    if (countdown <= 0) return;
    const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
    return () => clearTimeout(timer);
  }, [countdown]);

  useEffect(() => {
    if (mode === "code-verify" || mode === "register-verify" || mode === "forgot-verify")
      codeInputRef.current?.focus();
  }, [mode]);

  const resetState = () => {
    setCode("");
    setPassword("");
    setNewPwd("");
    setError("");
    setSuccessMsg("");
  };

  // --- Password login ---
  const handlePasswordLogin = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const res = await loginWithPassword(email, password);
      login(res.access_token, res.refresh_token, res.user);
    } catch (e) {
      setError(e instanceof Error ? e.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }, [email, password, login]);

  // --- Send code (shared) ---
  const handleSendCode = useCallback(async (nextMode: Mode) => {
    setError("");
    setLoading(true);
    try {
      await sendCode(email);
      setMode(nextMode);
      setCountdown(60);
    } catch (e) {
      setError(e instanceof Error ? e.message : "发送失败");
    } finally {
      setLoading(false);
    }
  }, [email]);

  // --- Verify code (login/register) ---
  const handleVerify = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const res = await verifyCode(email, code);
      login(res.access_token, res.refresh_token, res.user);
    } catch (e) {
      setError(e instanceof Error ? e.message : "验证失败");
    } finally {
      setLoading(false);
    }
  }, [email, code, login]);

  // --- Reset password ---
  const handleResetPassword = useCallback(async () => {
    setError("");
    if (newPwd.length < 6) {
      setError("密码至少 6 个字符");
      return;
    }
    setLoading(true);
    try {
      await resetPassword(email, code, newPwd);
      setSuccessMsg("密码重置成功，请使用新密码登录");
      setTimeout(() => {
        setMode("password");
        resetState();
      }, 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "重置失败");
    } finally {
      setLoading(false);
    }
  }, [email, code, newPwd]);

  // --- Resend ---
  const handleResend = useCallback(async () => {
    if (countdown > 0) return;
    setError("");
    try {
      await sendCode(email);
      setCountdown(60);
    } catch (e) {
      setError(e instanceof Error ? e.message : "发送失败");
    }
  }, [email, countdown]);

  const title: Record<Mode, string> = {
    password: "登录",
    "code-email": "验证码登录",
    "code-verify": "输入验证码",
    "register-email": "注册新账号",
    "register-verify": "输入验证码",
    "forgot-email": "忘记密码",
    "forgot-verify": "重置密码",
  };

  const subtitle: Record<Mode, string> = {
    password: "使用邮箱和密码登录",
    "code-email": "向邮箱发送 6 位验证码",
    "code-verify": `验证码已发送至 ${email}`,
    "register-email": "首次使用？验证邮箱即可注册",
    "register-verify": `验证码已发送至 ${email}`,
    "forgot-email": "通过邮箱验证码重置密码",
    "forgot-verify": `验证码已发送至 ${email}`,
  };

  return (
    <div className="min-h-screen bg-[#f9fafb] flex items-center justify-center px-4">
      <div className="w-full max-w-4xl flex gap-12 items-center">
        {/* Left: Hero positioning (hidden on small screens) */}
        <div className="hidden lg:block flex-1">
          <div className="flex items-center gap-2 mb-8">
            <BarChart3 className="h-8 w-8 text-blue-600" />
            <span className="text-2xl font-bold text-gray-900">QuantGPT</span>
          </div>

          <h2 className="text-2xl font-bold text-gray-900 tracking-tight leading-tight">
            Agent-Native<br />
            Quant Research<br />
            Infrastructure
          </h2>
          <p className="mt-3 text-base font-semibold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
            AI 时代量化研究新范式
          </p>
          <p className="mt-2 text-sm text-gray-500 leading-relaxed">
            Agent 自治因子挖矿 · 批量回测 · WQ BRAIN 自动提交。<br />从假设到可提交因子，全程 Agent 驱动。
          </p>

          <div className="mt-8 grid grid-cols-2 gap-3">
            {[
              { icon: Terminal, color: "text-orange-500", bg: "bg-orange-50", title: "Agent 自治研究", desc: "LLM Agent 通过 MCP 工具自主挖矿、评估、迭代因子" },
              { icon: FlaskConical, color: "text-emerald-500", bg: "bg-emerald-50", title: "因子研究引擎", desc: "50+ 算子，IC/IR/Sharpe 等 20+ 指标，行业/市值中性化" },
              { icon: Sparkles, color: "text-blue-500", bg: "bg-blue-50", title: "WQ BRAIN 对齐", desc: "算子标准对齐 BRAIN，一键模拟 + IS 检测 + 正式提交" },
              { icon: ShieldCheck, color: "text-purple-500", bg: "bg-purple-50", title: "抗过拟合验证", desc: "IC 稳定性、子样本压力、安慰剂检验、Walk-Forward" },
            ].map((f, i) => (
              <div key={i} className="rounded-xl border border-gray-100 bg-white/60 p-3">
                <div className={`${f.bg} rounded-lg p-1.5 w-fit mb-2`}>
                  <f.icon className={`h-3.5 w-3.5 ${f.color}`} />
                </div>
                <p className="text-xs font-semibold text-gray-900 mb-0.5">{f.title}</p>
                <p className="text-[11px] text-gray-500 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>

          <div className="mt-6 flex items-center gap-2 text-[11px] text-gray-400">
            <span>30+ 算子</span>
            <span>·</span>
            <span>4 大股票池</span>
            <span>·</span>
            <span>2015-2025 全量数据</span>
            <span>·</span>
            <span>开源免费</span>
          </div>
        </div>

        {/* Right: Login form */}
        <div className="w-full max-w-sm shrink-0">
          {/* Logo (mobile only) */}
          <div className="flex items-center justify-center gap-2 mb-8 lg:hidden">
            <BarChart3 className="h-7 w-7 text-blue-600" />
            <span className="text-xl font-semibold text-gray-900">QuantGPT</span>
          </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">{title[mode]}</h2>
          <p className="text-sm text-gray-500 mb-5">{subtitle[mode]}</p>

          {error && (
            <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}
          {successMsg && (
            <div className="mb-4 rounded-lg bg-green-50 border border-green-200 px-3 py-2 text-sm text-green-700">
              {successMsg}
            </div>
          )}

          {/* ===== Password Login ===== */}
          {mode === "password" && (
            <form onSubmit={(e) => { e.preventDefault(); handlePasswordLogin(); }}>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">邮箱地址</label>
              <div className="relative mb-3">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  required
                  autoFocus
                  className="w-full pl-10 pr-3 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <label className="block text-sm font-medium text-gray-700 mb-1.5">密码</label>
              <div className="relative mb-4">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type={showPwd ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="输入密码"
                  required
                  className="w-full pl-10 pr-10 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(!showPwd)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>

              <button
                type="submit"
                disabled={loading || !email || !password}
                className="w-full py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                登录
              </button>

              <div className="mt-4 flex items-center justify-between text-sm">
                <button
                  type="button"
                  onClick={() => { resetState(); setMode("forgot-email"); }}
                  className="text-gray-500 hover:text-blue-600"
                >
                  忘记密码
                </button>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => { resetState(); setMode("code-email"); }}
                    className="text-blue-600 hover:text-blue-700"
                  >
                    验证码登录
                  </button>
                  <button
                    type="button"
                    onClick={() => { resetState(); setMode("register-email"); }}
                    className="text-blue-600 hover:text-blue-700 font-medium"
                  >
                    注册
                  </button>
                </div>
              </div>
            </form>
          )}

          {/* ===== Email step (code login / register / forgot) ===== */}
          {(mode === "code-email" || mode === "register-email" || mode === "forgot-email") && (
            <form onSubmit={(e) => {
              e.preventDefault();
              const nextMode = mode === "code-email" ? "code-verify"
                : mode === "register-email" ? "register-verify"
                : "forgot-verify";
              handleSendCode(nextMode as Mode);
            }}>
              <button
                type="button"
                onClick={() => { setMode("password"); resetState(); }}
                className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                返回密码登录
              </button>

              <label className="block text-sm font-medium text-gray-700 mb-1.5">邮箱地址</label>
              <div className="relative mb-4">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  required
                  autoFocus
                  className="w-full pl-10 pr-3 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <button
                type="submit"
                disabled={loading || !email}
                className="w-full py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                发送验证码
              </button>
            </form>
          )}

          {/* ===== Code verify step (code login / register) ===== */}
          {(mode === "code-verify" || mode === "register-verify") && (
            <form onSubmit={(e) => { e.preventDefault(); handleVerify(); }}>
              <button
                type="button"
                onClick={() => {
                  setMode(mode === "code-verify" ? "code-email" : "register-email");
                  setCode("");
                  setError("");
                }}
                className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                换个邮箱
              </button>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">6 位验证码</label>
              <input
                ref={codeInputRef}
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="000000"
                required
                className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-900 text-center tracking-[0.3em] font-mono placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 mb-4"
              />
              <button
                type="submit"
                disabled={loading || code.length !== 6}
                className="w-full py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mb-3"
              >
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                验证并登录
              </button>
              <button
                type="button"
                onClick={handleResend}
                disabled={countdown > 0}
                className="w-full text-sm text-gray-500 hover:text-gray-700 disabled:cursor-not-allowed"
              >
                {countdown > 0 ? `${countdown} 秒后可重新发送` : "重新发送验证码"}
              </button>
            </form>
          )}

          {/* ===== Forgot password verify step ===== */}
          {mode === "forgot-verify" && (
            <form onSubmit={(e) => { e.preventDefault(); handleResetPassword(); }}>
              <button
                type="button"
                onClick={() => { setMode("forgot-email"); setCode(""); setNewPwd(""); setError(""); }}
                className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                换个邮箱
              </button>

              <label className="block text-sm font-medium text-gray-700 mb-1.5">6 位验证码</label>
              <input
                ref={codeInputRef}
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="000000"
                required
                className="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-900 text-center tracking-[0.3em] font-mono placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 mb-3"
              />

              <label className="block text-sm font-medium text-gray-700 mb-1.5">新密码</label>
              <div className="relative mb-4">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type={showPwd ? "text" : "password"}
                  value={newPwd}
                  onChange={(e) => setNewPwd(e.target.value)}
                  placeholder="至少 6 个字符"
                  required
                  className="w-full pl-10 pr-10 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(!showPwd)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>

              <button
                type="submit"
                disabled={loading || code.length !== 6 || !newPwd}
                className="w-full py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mb-3"
              >
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                重置密码
              </button>
              <button
                type="button"
                onClick={handleResend}
                disabled={countdown > 0}
                className="w-full text-sm text-gray-500 hover:text-gray-700 disabled:cursor-not-allowed"
              >
                {countdown > 0 ? `${countdown} 秒后可重新发送` : "重新发送验证码"}
              </button>
            </form>
          )}
        </div>

        {/* Guest mode */}
        <button
          onClick={() => { enterGuestMode(); navigate("/", { replace: true }); }}
          className="mt-4 w-full py-2.5 rounded-lg border border-gray-200 bg-white text-sm text-gray-600 hover:bg-gray-50 hover:text-gray-900 transition-colors"
        >
          免登录体验
          <span className="text-xs text-gray-400 ml-1.5">(仅限小样本股票池)</span>
        </button>
        </div>
      </div>
    </div>
  );
}
