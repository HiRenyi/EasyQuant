"""Factor deep research report: Markdown → HTML email rendering + chart generation + sending."""

import io
import logging
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np


# ---------------------------------------------------------------------------
# Configure Chinese font for matplotlib
# ---------------------------------------------------------------------------
def _setup_chinese_font():
    """Find and configure a CJK font for matplotlib charts."""
    # Candidate font names in preference order
    candidates = [
        "Noto Sans CJK SC",  # Linux (yum install google-noto-sans-cjk-sc-fonts)
        "PingFang SC",       # macOS
        "Heiti TC",          # macOS fallback
        "STHeiti",           # macOS fallback
        "Arial Unicode MS",  # macOS/Windows fallback
        "SimHei",            # Windows
        "Microsoft YaHei",   # Windows
        "WenQuanYi Micro Hei",  # Linux fallback
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            return name
    return None

_CJK_FONT = _setup_chinese_font()
if _CJK_FONT:
    matplotlib.rcParams["font.sans-serif"] = [_CJK_FONT, "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False  # Fix minus sign display

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .email_service import _BRAND_COLOR, _send_email
from .models import User

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_REPORT_DIR = _PROJECT_ROOT / "factor_research"

# Brand colors for charts
_COLORS = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
           "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1",
           "#14b8a6", "#e11d48", "#a855f7"]
_BG_COLOR = "#ffffff"
_GRID_COLOR = "#f1f5f9"
_TEXT_COLOR = "#334155"
_MUTED_COLOR = "#94a3b8"


# ---------------------------------------------------------------------------
# Data extraction from Markdown
# ---------------------------------------------------------------------------

def _extract_factor_rankings(md: str) -> list[dict]:
    """Extract factor ranking data from the Markdown report table."""
    factors = []
    in_ranking_table = False
    for line in md.split("\n"):
        stripped = line.strip()
        if "因子排行榜" in stripped or "因子名称" in stripped:
            in_ranking_table = True
            continue
        if in_ranking_table and stripped.startswith("|"):
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 5:
                try:
                    rank = int(re.sub(r"[^\d]", "", cells[0]))
                    name = re.sub(r"\*\*(.+?)\*\*", r"\1", cells[1]).strip()
                    expr = re.sub(r"`(.+?)`", r"\1", cells[2]).strip()
                    category = re.sub(r"\*\*(.+?)\*\*", r"\1", cells[3]).strip()
                    score = float(re.sub(r"[^\d.]", "", cells[4]))
                    grade = re.sub(r"\*\*(.+?)\*\*", r"\1", cells[5]).strip() if len(cells) > 5 else ""
                    factors.append({
                        "rank": rank, "name": name, "expression": expr,
                        "category": category, "score": score, "grade": grade,
                    })
                except (ValueError, IndexError):
                    continue
        elif in_ranking_table and not stripped.startswith("|") and stripped and "---" not in stripped:
            in_ranking_table = False
    return factors


def _extract_top_factor_metrics(md: str) -> list[dict]:
    """Extract detailed metrics for top factors from the report."""
    top_factors = []
    current_factor = None
    in_metrics_table = False
    metrics_rows = []

    for line in md.split("\n"):
        stripped = line.strip()
        # Detect factor section header like "### No.1 低 PB 因子 — 77.3 分 / B 级"
        m = re.match(r"^###\s+No\.(\d+)\s+(.+?)[\s—]+([0-9.]+)\s*分", stripped)
        if m:
            if current_factor and metrics_rows:
                current_factor["metrics"] = _parse_metrics_rows(metrics_rows)
                top_factors.append(current_factor)
            current_factor = {
                "rank": int(m.group(1)),
                "name": m.group(2).strip(),
                "score": float(m.group(3)),
                "metrics": {},
            }
            in_metrics_table = False
            metrics_rows = []
            continue

        if current_factor and stripped.startswith("|") and ("指标" in stripped or "数值" in stripped):
            in_metrics_table = True
            continue
        if in_metrics_table and stripped.startswith("|"):
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            metrics_rows.append(stripped)
            continue
        elif in_metrics_table and not stripped.startswith("|"):
            in_metrics_table = False

    if current_factor and metrics_rows:
        current_factor["metrics"] = _parse_metrics_rows(metrics_rows)
        top_factors.append(current_factor)

    return top_factors


def _parse_metrics_rows(rows: list[str]) -> dict:
    """Parse metric table rows into a dict."""
    metrics = {}
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) >= 2:
            key = cells[0].strip()
            val_str = cells[1].strip()
            # Try to extract numeric value
            num_match = re.search(r"[-+]?[0-9]*\.?[0-9]+", val_str.replace("%", ""))
            if num_match:
                metrics[key] = float(num_match.group())
            else:
                metrics[key] = val_str
    return metrics


# ---------------------------------------------------------------------------
# Chart generation (matplotlib → base64 PNG)
# ---------------------------------------------------------------------------

# Directory for chart images served via /charts/ URL
_CHARTS_DIR = Path(__file__).resolve().parent.parent / "reports" / "charts"

# Accumulates (filename, png_bytes) during render; cleared at start of each render.
_embedded_images: list[tuple[str, bytes]] = []

# Base URL for chart images in emails
_CHARTS_BASE_URL = "http://localhost:8003/charts"


def _img_tag(fig: plt.Figure, alt: str = "") -> str:
    """Save chart to disk and return an HTML img tag with public URL."""
    _CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"chart_{len(_embedded_images)}.png"
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=_BG_COLOR, edgecolor="none", pad_inches=0.15)
    plt.close(fig)
    buf.seek(0)
    png_bytes = buf.read()
    (_CHARTS_DIR / filename).write_bytes(png_bytes)
    _embedded_images.append((filename, png_bytes))
    url = f"{_CHARTS_BASE_URL}/{filename}"
    return (f'<img src="{url}" alt="{alt}" '
            f'style="width:100%;max-width:720px;height:auto;display:block;margin:16px auto;border-radius:8px;">')


def _style_chart(ax: plt.Axes, title: str = "", ylabel: str = "") -> None:
    """Apply consistent styling to chart axes."""
    ax.set_facecolor(_BG_COLOR)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(_GRID_COLOR)
    ax.spines["bottom"].set_color(_GRID_COLOR)
    ax.tick_params(colors=_TEXT_COLOR, labelsize=9)
    ax.yaxis.set_tick_params(labelcolor=_MUTED_COLOR)
    ax.xaxis.set_tick_params(labelcolor=_TEXT_COLOR)
    if title:
        ax.set_title(title, fontsize=13, fontweight="600", color="#1e293b",
                      pad=12, loc="left")
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9, color=_MUTED_COLOR)
    ax.grid(axis="y", color=_GRID_COLOR, linewidth=0.8, alpha=0.7)


def generate_score_bar_chart(factors: list[dict]) -> str:
    """Generate horizontal bar chart of factor scores, colored by grade."""
    if not factors:
        return ""
    # Sort by score ascending for horizontal bar (top = highest)
    factors = sorted(factors, key=lambda f: f["score"])

    fig, ax = plt.subplots(figsize=(7, max(3.5, len(factors) * 0.38)))
    fig.set_facecolor(_BG_COLOR)

    names = [f["name"] for f in factors]
    scores = [f["score"] for f in factors]
    colors = []
    for f in factors:
        g = f.get("grade", "")
        if "A" in g:
            colors.append("#10b981")
        elif "B" in g:
            colors.append("#2563eb")
        elif "C" in g:
            colors.append("#f59e0b")
        else:
            colors.append("#ef4444")

    bars = ax.barh(range(len(names)), scores, color=colors, height=0.65, edgecolor="none")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=10, color=_TEXT_COLOR)
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))

    # Add score labels
    for bar, score, grade in zip(bars, scores, [f.get("grade", "") for f in factors]):
        g = re.sub(r"\*", "", grade)
        ax.text(score + 1.5, bar.get_y() + bar.get_height() / 2,
                f"{score:.0f} ({g})" if g else f"{score:.0f}",
                va="center", fontsize=9, color=_TEXT_COLOR, fontweight="500")

    _style_chart(ax, "因子评分排行", "")
    ax.set_xlabel("综合评分 (0-100)", fontsize=9, color=_MUTED_COLOR)

    # Legend
    from matplotlib.patches import Patch
    legend_items = [
        Patch(facecolor="#10b981", label="A 级"),
        Patch(facecolor="#2563eb", label="B 级"),
        Patch(facecolor="#f59e0b", label="C 级"),
        Patch(facecolor="#ef4444", label="D 级"),
    ]
    ax.legend(handles=legend_items, loc="lower right", fontsize=8,
              frameon=False, ncol=4)

    fig.tight_layout()
    return _img_tag(fig, "因子评分排行")


def generate_category_pie_chart(factors: list[dict]) -> str:
    """Generate pie chart showing factor category distribution."""
    if not factors:
        return ""
    cats = {}
    for f in factors:
        c = f.get("category", "其他")
        cats[c] = cats.get(c, 0) + 1

    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    fig.set_facecolor(_BG_COLOR)

    labels = list(cats.keys())
    sizes = list(cats.values())
    colors = _COLORS[:len(labels)]

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors, autopct="%1.0f%%",
        startangle=90, pctdistance=0.75,
        textprops={"fontsize": 10, "color": _TEXT_COLOR},
    )
    for t in autotexts:
        t.set_fontsize(9)
        t.set_color("#fff")
        t.set_fontweight("600")

    ax.set_title("因子类别分布", fontsize=13, fontweight="600", color="#1e293b", pad=8)
    fig.tight_layout()
    return _img_tag(fig, "因子类别分布")


def generate_top_factors_radar(top_factors: list[dict]) -> str:
    """Generate radar/spider chart comparing top factors across key metrics."""
    if not top_factors:
        return ""

    # Normalize metrics to 0-1 scale for radar
    metric_keys = ["IC 均值", "IC IR", "单调性", "头组夏普", "最大回撤", "换手率"]
    metric_labels = ["IC均值", "IC IR", "单调性", "头组夏普", "回撤控制", "低换手"]

    # Collect raw values
    raw_data = {}
    for f in top_factors[:5]:
        m = f.get("metrics", {})
        vals = []
        for k in metric_keys:
            v = m.get(k)
            if isinstance(v, (int, float)):
                vals.append(v)
            else:
                vals.append(0)
        raw_data[f["name"]] = vals

    if not raw_data:
        return ""

    # Normalize: for max_drawdown and turnover, lower is better → invert
    all_vals = list(raw_data.values())
    n_metrics = len(metric_keys)
    mins = [min(v[i] for v in all_vals) for i in range(n_metrics)]
    maxs = [max(v[i] for v in all_vals) for i in range(n_metrics)]

    def normalize(vals):
        normed = []
        for i, v in enumerate(vals):
            if maxs[i] == mins[i]:
                normed.append(0.5)
            else:
                n = (v - mins[i]) / (maxs[i] - mins[i])
                # Invert for "lower is better" metrics (drawdown, turnover)
                if i in (4, 5):  # 最大回撤, 换手率
                    n = 1 - n
                normed.append(max(0, min(1, n)))
        return normed

    # Create radar chart
    angles = np.linspace(0, 2 * np.pi, n_metrics, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
    fig.set_facecolor(_BG_COLOR)
    ax.set_facecolor(_BG_COLOR)

    for idx, (name, vals) in enumerate(list(raw_data.items())[:5]):
        normed = normalize(vals)
        normed += normed[:1]
        color = _COLORS[idx % len(_COLORS)]
        ax.plot(angles, normed, "o-", linewidth=1.8, markersize=4,
                color=color, label=name)
        ax.fill(angles, normed, alpha=0.08, color=color)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metric_labels, fontsize=9, color=_TEXT_COLOR)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["", "", "", ""], fontsize=7, color=_MUTED_COLOR)
    ax.spines["polar"].set_color(_GRID_COLOR)
    ax.grid(color=_GRID_COLOR, linewidth=0.6)

    ax.set_title("Top 因子多维对比", fontsize=13, fontweight="600",
                  color="#1e293b", pad=20, y=1.08)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1),
              fontsize=8, frameon=False)

    fig.tight_layout()
    return _img_tag(fig, "Top 因子多维对比")


def generate_metrics_comparison_chart(top_factors: list[dict]) -> str:
    """Generate grouped bar chart comparing key metrics of top factors."""
    if not top_factors:
        return ""

    metric_pairs = [
        ("IC 均值", "IC均值"),
        ("IC IR", "IC IR"),
        ("头组夏普", "头组夏普"),
        ("多空夏普", "多空夏普"),
    ]

    names = [f["name"] for f in top_factors[:5]]
    # Use 2x2 grid to avoid crowding
    fig, axes = plt.subplots(2, 2, figsize=(7, 5.5))
    fig.set_facecolor(_BG_COLOR)
    axes_flat = axes.flatten()

    for ax_idx, (key, label) in enumerate(metric_pairs):
        ax = axes_flat[ax_idx]
        vals = []
        for f in top_factors[:5]:
            v = f.get("metrics", {}).get(key, 0)
            vals.append(v if isinstance(v, (int, float)) else 0)

        colors = [_COLORS[i % len(_COLORS)] for i in range(len(vals))]
        bars = ax.bar(range(len(vals)), vals, color=colors, width=0.55, edgecolor="none")
        ax.set_xticks(range(len(vals)))
        short_names = [n[:6] for n in names]
        ax.set_xticklabels(short_names, fontsize=9, color=_TEXT_COLOR, rotation=15, ha="right")
        _style_chart(ax, label, "")

        # Value labels on bars
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f"{val:.3f}" if abs(val) < 1 else f"{val:.2f}",
                    ha="center", va="bottom", fontsize=8, color=_MUTED_COLOR)

    fig.suptitle("Top 因子关键指标对比", fontsize=13, fontweight="600",
                 color="#1e293b", y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return _img_tag(fig, "关键指标对比")


def generate_grade_summary_card(factors: list[dict]) -> str:
    """Generate HTML summary cards showing grade distribution."""
    grades = {"A": 0, "B": 0, "C": 0, "D": 0}
    for f in factors:
        g = re.sub(r"\*", "", f.get("grade", ""))
        if g in grades:
            grades[g] += 1

    grade_colors = {"A": "#10b981", "B": "#2563eb", "C": "#f59e0b", "D": "#ef4444"}
    cards = ""
    for g, count in grades.items():
        color = grade_colors[g]
        cards += (
            f'<div style="flex:1;text-align:center;padding:12px 8px;background:{color}10;'
            f'border-radius:8px;border:1px solid {color}30;">'
            f'<div style="font-size:24px;font-weight:700;color:{color};">{count}</div>'
            f'<div style="font-size:12px;color:{_MUTED_COLOR};margin-top:2px;">{g} 级因子</div>'
            f'</div>'
        )

    total = len(factors)
    best = max(factors, key=lambda f: f["score"]) if factors else None
    best_info = f'{best["name"]} ({best["score"]:.0f}分)' if best else "-"

    return f"""
    <div style="display:flex;gap:12px;margin:16px 0;">
        <div style="flex:1;text-align:center;padding:12px 8px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;">
            <div style="font-size:24px;font-weight:700;color:#1e293b;">{total}</div>
            <div style="font-size:12px;color:{_MUTED_COLOR};margin-top:2px;">筛选因子数</div>
        </div>
        {cards}
    </div>
    <div style="background:#f8fafc;border-radius:8px;padding:12px 16px;margin:8px 0 16px;">
        <span style="color:{_MUTED_COLOR};font-size:12px;">本期最高分：</span>
        <span style="color:#1e293b;font-size:14px;font-weight:600;">{best_info}</span>
    </div>
    """


# ---------------------------------------------------------------------------
# Markdown → HTML (email-safe, inline styles only)
# ---------------------------------------------------------------------------

def _md_to_email_html(md: str) -> str:
    """Convert Markdown to email-compatible HTML with inline styles."""
    lines = md.split("\n")
    html_parts: list[str] = []
    in_table = False
    table_rows: list[str] = []
    in_code_block = False
    code_lines: list[str] = []
    in_blockquote = False
    bq_lines: list[str] = []

    def _flush_table():
        nonlocal in_table, table_rows
        if not table_rows:
            return
        tbl = '<table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;">'
        for i, row in enumerate(table_rows):
            cells = [c.strip() for c in row.strip("|").split("|")]
            tag = "th" if i == 0 else "td"
            style_cell = (
                "padding:8px 10px;border:1px solid #e2e8f0;text-align:left;"
                + ("background:#f1f5f9;font-weight:600;" if i == 0 else "")
            )
            tbl += "<tr>" + "".join(
                f'<{tag} style="{style_cell}">{_inline_format(c)}</{tag}>'
                for c in cells
            ) + "</tr>"
        tbl += "</table>"
        html_parts.append(tbl)
        in_table = False
        table_rows = []

    def _flush_code():
        nonlocal in_code_block, code_lines
        code = "\n".join(code_lines)
        html_parts.append(
            f'<pre style="background:#f1f5f9;padding:12px 16px;border-radius:8px;'
            f'font-size:13px;font-family:monospace;overflow-x:auto;margin:12px 0;">'
            f"<code>{_escape(code)}</code></pre>"
        )
        in_code_block = False
        code_lines = []

    def _flush_blockquote():
        nonlocal in_blockquote, bq_lines
        content = "<br>".join(_inline_format(l) for l in bq_lines)
        html_parts.append(
            f'<div style="border-left:3px solid {_BRAND_COLOR};padding:12px 16px;'
            f'margin:12px 0;color:#475569;background:#f8fafc;border-radius:0 8px 8px 0;">'
            f"{content}</div>"
        )
        in_blockquote = False
        bq_lines = []

    for line in lines:
        # Code block toggle
        if line.strip().startswith("```"):
            if in_code_block:
                _flush_code()
            else:
                if in_table:
                    _flush_table()
                if in_blockquote:
                    _flush_blockquote()
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        stripped = line.strip()

        if not stripped:
            if in_table:
                _flush_table()
            if in_blockquote:
                _flush_blockquote()
            continue

        if re.match(r"^-{3,}$", stripped) or re.match(r"^\*{3,}$", stripped):
            if in_table:
                _flush_table()
            if in_blockquote:
                _flush_blockquote()
            html_parts.append('<hr style="border:0;border-top:1px solid #e2e8f0;margin:20px 0;">')
            continue

        if "|" in stripped and stripped.startswith("|"):
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            if not in_table:
                if in_blockquote:
                    _flush_blockquote()
                in_table = True
            table_rows.append(stripped)
            continue
        else:
            if in_table:
                _flush_table()

        if stripped.startswith(">"):
            if not in_blockquote:
                in_blockquote = True
            bq_lines.append(stripped.lstrip("> "))
            continue
        else:
            if in_blockquote:
                _flush_blockquote()

        m = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if m:
            level = len(m.group(1))
            text = _inline_format(m.group(2))
            sizes = {1: "22px", 2: "18px", 3: "16px", 4: "14px"}
            margins = {1: "24px 0 12px", 2: "20px 0 10px", 3: "16px 0 8px", 4: "12px 0 6px"}
            html_parts.append(
                f'<h{level} style="margin:{margins[level]};font-size:{sizes[level]};'
                f'color:#1e293b;font-weight:600;">{text}</h{level}>'
            )
            continue

        m = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if m:
            html_parts.append(
                f'<p style="margin:4px 0;padding-left:20px;color:#334155;font-size:14px;line-height:1.6;">'
                f'{m.group(1)}. {_inline_format(m.group(2))}</p>'
            )
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            text = _inline_format(stripped[2:])
            html_parts.append(
                f'<p style="margin:4px 0;padding-left:20px;color:#334155;font-size:14px;line-height:1.6;">'
                f'&bull; {text}</p>'
            )
            continue

        html_parts.append(
            f'<p style="margin:8px 0;color:#334155;font-size:14px;line-height:1.6;">'
            f'{_inline_format(stripped)}</p>'
        )

    if in_table:
        _flush_table()
    if in_code_block:
        _flush_code()
    if in_blockquote:
        _flush_blockquote()

    return "\n".join(html_parts)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline_format(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r'<strong style="color:#0f172a;">\1</strong>', text)
    text = re.sub(
        r"`(.+?)`",
        r'<code style="background:#f1f5f9;padding:2px 6px;border-radius:4px;font-size:12px;'
        r'font-family:monospace;color:#dc2626;">\1</code>',
        text,
    )
    text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", text)
    return text


# ---------------------------------------------------------------------------
# Render full email with charts
# ---------------------------------------------------------------------------

def render_weekly_report_email(md_content: str, unsubscribe_url: str = "") -> str:
    """Convert Markdown weekly report to branded HTML email with chart images.

    Charts are saved to reports/charts/ and referenced via public URLs.
    """
    _embedded_images.clear()

    # Extract structured data for chart generation
    factors = _extract_factor_rankings(md_content)
    top_factors = _extract_top_factor_metrics(md_content)

    # Generate charts
    charts_html = ""
    if factors:
        charts_html += generate_grade_summary_card(factors)
        charts_html += generate_score_bar_chart(factors)
    if factors:
        charts_html += generate_category_pie_chart(factors)
    if top_factors:
        charts_html += generate_top_factors_radar(top_factors)
        charts_html += generate_metrics_comparison_chart(top_factors)

    # Convert markdown body to HTML
    body_html = _md_to_email_html(md_content)

    # Insert charts after the first section (after 本期概要)
    insert_marker = "因子排行榜"
    marker_pos = body_html.find(insert_marker)
    if marker_pos > 0:
        # Find the start of the heading tag containing the marker
        tag_start = body_html.rfind("<h", 0, marker_pos)
        if tag_start > 0:
            charts_section = (
                '<hr style="border:0;border-top:1px solid #e2e8f0;margin:20px 0;">'
                f'<h2 style="margin:20px 0 10px;font-size:18px;color:#1e293b;font-weight:600;">数据概览</h2>'
                f'{charts_html}'
                '<hr style="border:0;border-top:1px solid #e2e8f0;margin:20px 0;">'
            )
            body_html = body_html[:tag_start] + charts_section + body_html[tag_start:]

    unsub = ""
    if unsubscribe_url:
        unsub = (
            f'<p style="margin:16px 0 0;text-align:center;font-size:12px;color:#94a3b8;">'
            f'<a href="{unsubscribe_url}" style="color:#94a3b8;">退订因子研究报告</a></p>'
        )

    _BRAND_BG = "#f8fafc"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{_BRAND_BG};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:780px;margin:24px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
  <div style="background:{_BRAND_COLOR};padding:20px 28px;">
    <span style="color:#fff;font-size:18px;font-weight:600;">QuantGPT</span>
    <span style="color:rgba(255,255,255,0.7);font-size:13px;margin-left:12px;">因子深度研究</span>
  </div>
  <div style="padding:28px 32px;">{body_html}</div>
  {unsub}
  <div style="padding:16px 32px;border-top:1px solid #f1f5f9;color:#94a3b8;font-size:12px;">
    此邮件由 QuantGPT 自动发送，无需回复。
  </div>
</div>
</body></html>"""
    return html


# ---------------------------------------------------------------------------
# Send functions
# ---------------------------------------------------------------------------

def get_latest_report_path() -> Path | None:
    """Find the latest .md report in marketing/weekly_report/."""
    if not _REPORT_DIR.exists():
        return None
    files = sorted(_REPORT_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    return files[0] if files else None


def get_latest_report_content() -> str | None:
    """Read the latest weekly report Markdown content."""
    path = get_latest_report_path()
    if path is None:
        return None
    return path.read_text(encoding="utf-8")


async def send_weekly_report_to(email: str, md_content: str) -> bool:
    """Send weekly report to a single email address. Returns True on success."""
    try:
        html = render_weekly_report_email(md_content)
        first_line = md_content.strip().split("\n")[0].lstrip("# ").strip()
        subject = f"QuantGPT — {first_line}"
        await _send_email(email, subject, html)
        return True
    except Exception as e:
        logger.error(f"Failed to send weekly report to {email}: {e}")
        return False


async def send_weekly_report(db: AsyncSession, md_content: str) -> dict:
    """Send weekly report to all subscribed active users."""
    result = await db.execute(
        select(User.email).where(
            User.subscribe_weekly == True,  # noqa: E712
            User.is_active == True,  # noqa: E712
        )
    )
    emails = [row[0] for row in result.all()]

    sent = 0
    failed = 0
    for email in emails:
        ok = await send_weekly_report_to(email, md_content)
        if ok:
            sent += 1
        else:
            failed += 1

    stats = {"total": len(emails), "sent": sent, "failed": failed}
    logger.info(f"Weekly report sent: {stats}")
    return stats
