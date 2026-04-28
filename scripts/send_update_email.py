"""Send v2.5.0 update email."""
import os, sys, asyncio
from pathlib import Path

# Load .env
env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.is_file():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from quantgpt.email_service import _send_email, _email_wrapper

TO = sys.argv[1] if len(sys.argv) > 1 else "835777924@qq.com"
SUBJECT = "QuantGPT v2.5.0 — 说一句话，回测一个交易策略"

html = _email_wrapper("""
<h2 style="margin:0 0 8px;font-size:20px;color:#1e293b;">说一句话，回测一个交易策略</h2>
<p style="color:#94a3b8;font-size:12px;margin:0 0 20px;">QuantGPT v2.5.0 已上线 &middot; 2026-03-27</p>

<p style="color:#475569;font-size:14px;line-height:1.8;margin:0 0 20px;">
  Hi，<br><br>
  过去 QuantGPT 只能做因子回测 —— 验证"某个选股因子有没有效"。<br>
  很多用户告诉我们：<strong>"我有一个完整的策略想法，能不能直接帮我跑一下？"</strong><br><br>
  今天，可以了。
</p>

<!-- Hero Feature -->
<div style="background:linear-gradient(135deg,#fff7ed,#ffedd5);border:1px solid #fed7aa;border-radius:12px;padding:20px 22px;margin:0 0 24px;">
  <p style="margin:0 0 10px;font-size:16px;font-weight:700;color:#c2410c;">策略一键回测</p>
  <p style="margin:0 0 14px;color:#9a3412;font-size:13px;line-height:1.7;">
    用自然语言描述你的交易策略，AI 自动生成完整代码，在真实回测环境中执行，返回专业级分析报告。<strong>全程零代码。</strong>
  </p>

  <p style="margin:0 0 8px;color:#78350f;font-size:12px;font-weight:600;">试试这样说：</p>
  <div style="background:#fff;border-radius:8px;padding:12px 16px;margin:0 0 14px;">
    <p style="margin:0 0 6px;color:#ea580c;font-size:13px;font-family:monospace;">"帮我写一个双均线策略，5日上穿20日买入，下穿卖出"</p>
    <p style="margin:0 0 6px;color:#ea580c;font-size:13px;font-family:monospace;">"做一个布林带均值回归策略，突破上轨减仓，触及下轨加仓"</p>
    <p style="margin:0;color:#ea580c;font-size:13px;font-family:monospace;">"帮我构建一个海龟交易法则策略，20日突破入场"</p>
  </div>

  <p style="margin:0 0 6px;color:#78350f;font-size:12px;font-weight:600;">回测报告包含：</p>
  <table style="width:100%;font-size:12px;color:#9a3412;line-height:1.6;">
    <tr>
      <td style="padding:2px 0;">&#10003; 净值曲线 &amp; 基准对比</td>
      <td style="padding:2px 0;">&#10003; 年化收益 / 最大回撤</td>
    </tr>
    <tr>
      <td style="padding:2px 0;">&#10003; 夏普 / 索提诺 / Alpha / Beta</td>
      <td style="padding:2px 0;">&#10003; 每笔交易明细</td>
    </tr>
    <tr>
      <td style="padding:2px 0;">&#10003; 每日持仓快照</td>
      <td style="padding:2px 0;">&#10003; 胜率 / 盈亏比</td>
    </tr>
  </table>
</div>

<!-- Factor vs Strategy -->
<div style="background:#f8fafc;border-radius:12px;padding:18px 20px;margin:0 0 24px;">
  <p style="margin:0 0 12px;font-size:14px;font-weight:600;color:#334155;">现在 QuantGPT 能做什么？</p>
  <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <tr style="border-bottom:1px solid #e2e8f0;">
      <td style="padding:10px 8px;color:#64748b;font-weight:600;width:30%"></td>
      <td style="padding:10px 8px;color:#2563eb;font-weight:600;text-align:center;">因子回测</td>
      <td style="padding:10px 8px;color:#ea580c;font-weight:600;text-align:center;">策略回测 <span style="background:#fff7ed;color:#ea580c;font-size:10px;padding:1px 6px;border-radius:4px;font-weight:700;">NEW</span></td>
    </tr>
    <tr style="border-bottom:1px solid #f1f5f9;">
      <td style="padding:8px;color:#64748b;">输入</td>
      <td style="padding:8px;color:#475569;text-align:center;">因子描述 / 表达式</td>
      <td style="padding:8px;color:#475569;text-align:center;">交易策略描述</td>
    </tr>
    <tr style="border-bottom:1px solid #f1f5f9;">
      <td style="padding:8px;color:#64748b;">验证</td>
      <td style="padding:8px;color:#475569;text-align:center;">选股因子有效性</td>
      <td style="padding:8px;color:#475569;text-align:center;">完整交易策略收益</td>
    </tr>
    <tr style="border-bottom:1px solid #f1f5f9;">
      <td style="padding:8px;color:#64748b;">输出</td>
      <td style="padding:8px;color:#475569;text-align:center;">IC / IR / 分组收益</td>
      <td style="padding:8px;color:#475569;text-align:center;">净值 / 交易 / 持仓</td>
    </tr>
    <tr>
      <td style="padding:8px;color:#64748b;">适合</td>
      <td style="padding:8px;color:#475569;text-align:center;">量化研究</td>
      <td style="padding:8px;color:#475569;text-align:center;">策略验证</td>
    </tr>
  </table>
</div>

<!-- Evolution Engine -->
<div style="background:#f5f3ff;border-left:3px solid #8b5cf6;padding:14px 18px;border-radius:0 8px 8px 0;margin:0 0 24px;">
  <p style="margin:0 0 6px;color:#5b21b6;font-size:14px;font-weight:600;">因子进化引擎</p>
  <p style="margin:0;color:#6d28d9;font-size:13px;line-height:1.7;">
    灵感来自遗传算法 —— 将已有因子作为"基因"，通过<strong>交叉</strong>（组合两个因子的优势）、<strong>变异</strong>（随机微调参数和结构）、<strong>元进化</strong>（让 AI 自主决定搜索方向）三条路径，自动探索更优因子。你只需要给出一个起点因子，剩下的交给算法。
  </p>
</div>

<!-- Security -->
<div style="background:#f0f9ff;border-left:3px solid #0ea5e9;padding:14px 18px;border-radius:0 8px 8px 0;margin:0 0 28px;">
  <p style="margin:0 0 6px;color:#0c4a6e;font-size:14px;font-weight:600;">安全升级</p>
  <p style="margin:0;color:#0369a1;font-size:13px;line-height:1.7;">
    策略代码传输全程加密，API 层面增加反爬保护。你的策略代码不会以明文暴露在网络传输中。
  </p>
</div>

<!-- CTA -->
<div style="text-align:center;margin:0 0 20px;">
  <a href="http://localhost:8003" style="display:inline-block;background:#f97316;color:#fff;padding:14px 40px;border-radius:10px;text-decoration:none;font-size:15px;font-weight:700;letter-spacing:0.5px;">
    立即体验 v2.5.0
  </a>
  <p style="color:#94a3b8;font-size:12px;margin:12px 0 0;">注册即可使用，完全免费</p>
</div>

<div style="border-top:1px solid #f1f5f9;padding-top:16px;margin-top:8px;">
  <p style="color:#94a3b8;font-size:11px;margin:0;line-height:1.6;">
    QuantGPT — AI 驱动的量化策略回测平台<br>
    如有任何问题或建议，直接回复此邮件或在平台内提交反馈。
  </p>
</div>
""")

asyncio.run(_send_email(TO, SUBJECT, html))
print(f"Email sent to {TO}")
