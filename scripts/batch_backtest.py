#!/usr/bin/env python3
"""批量回测聚宽2025年精选策略。

逐个读取策略文件，提交到 QuantGPT API 进行聚宽回测，结果记录到 回测结果.md。
支持断点续传：已完成的策略自动跳过。
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

API_BASE = "http://localhost:8003/api/v1"
STRATEGY_DIR = Path(__file__).resolve().parent.parent / "聚宽2025年精选"
RESULT_FILE = Path(__file__).resolve().parent.parent / "回测结果.md"


def natural_key(name: str) -> tuple:
    m = re.match(r"(\d+)", name)
    return (int(m.group(1)) if m else 9999, name)


def http_post(path: str, data: dict, timeout: int = 30) -> dict:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else str(e)
        return {"error": f"HTTP {e.code}: {body[:300]}"}
    except Exception as e:
        return {"error": str(e)}


def http_get(path: str, timeout: int = 15) -> dict:
    url = f"{API_BASE}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def extract_code(filepath: Path) -> str | None:
    """从策略文件中提取纯 Python 代码。兼容 .py 和 .txt 文件。

    返回 None 表示无法提取可运行策略代码（如研究笔记）。
    """
    text = filepath.read_text(encoding="utf-8")

    if filepath.suffix == ".py":
        # Jupyter notebook 导出的 .py 文件：检查是否有 def initialize
        if "def initialize" in text:
            return text.strip()
        # 可能是研究笔记，尝试提取策略部分
        return None

    # .txt 文件：找到代码起始位置（第一个 from/import 行，或 def initialize）
    lines = text.split('\n')
    code_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        # 跳过文章标题和描述
        if stripped.startswith('# 克隆自') or stripped.startswith('# 标题') or stripped.startswith('# 作者'):
            continue
        if stripped.startswith('from ') or stripped.startswith('import ') or stripped == 'def initialize(context):':
            code_start = i
            break

    if code_start is None:
        # 尝试找 def initialize
        if "def initialize" in text:
            code_start = text.index("def initialize")
            # 往前找最近的空行前的 import/from
            before = text[:code_start].split('\n')
            for j in range(len(before) - 1, -1, -1):
                if before[j].strip().startswith(('from ', 'import ')):
                    code_start = text.index(before[j])
                    break
            return text[code_start:].strip()
        return None

    code = '\n'.join(lines[code_start:]).strip()
    if len(code) < 200:
        return None
    return code


def get_title(filename: str) -> str:
    """从文件名提取策略标题（去掉前导数字和后缀）。"""
    name = filename.rsplit(".", 1)[0]
    # 去掉前导数字（如 "1", "10.", "99"）
    name = re.sub(r"^\d+\.?\s*", "", name)
    # 去掉前导的 "、" 符号
    name = re.sub(r"^[、，,]\s*", "", name)
    return name.strip()


def scrape_metrics(task_result: dict) -> dict:
    """从 task_result 中提取回测指标。"""
    result_data = task_result.get("result", {})
    metrics = result_data.get("metrics", {})
    if not metrics:
        return {}
    return {
        "策略收益": metrics.get("total_return"),
        "策略年化收益": metrics.get("annual_return"),
        "超额收益": metrics.get("excess_return"),
        "基准收益": metrics.get("benchmark_return"),
        "阿尔法": metrics.get("alpha"),
        "贝塔": metrics.get("beta"),
        "夏普比率": metrics.get("sharpe_ratio"),
        "胜率": metrics.get("win_rate"),
        "盈亏比": metrics.get("profit_loss_ratio"),
        "最大回撤": metrics.get("max_drawdown"),
        "索提诺比率": metrics.get("sortino_ratio"),
        "信息比率": metrics.get("information_ratio"),
        "策略波动率": metrics.get("volatility"),
        "基准波动率": metrics.get("benchmark_volatility"),
        "盈利次数": metrics.get("win_count"),
        "亏损次数": metrics.get("loss_count"),
    }


def record_initialized():
    """初始化结果文件（如果不存在）。"""
    if not RESULT_FILE.exists():
        RESULT_FILE.write_text(
            "# 聚宽2025年精选策略 — 回测结果汇总\n\n"
            f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "说明：所有策略使用统一参数回测（2023-01-01 至 2025-12-31，初始资金 100 万，基准 000300.XSHG）\n\n---\n",
            encoding="utf-8",
        )


def record_result(filename: str, title: str, status: str, detail: str, metrics: dict = None):
    """追加一条回测结果到 回测结果.md。"""
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    entry = f"\n## {title}\n\n"
    entry += f"- **文件**: `{filename}`\n"
    entry += f"- **测试时间**: {now}\n"
    entry += f"- **状态**: {status}\n"

    if metrics and status == "完成":
        entry += f"\n### 回测指标\n\n"
        entry += f"| 指标 | 值 |\n|---|---|\n"
        for k, v in metrics.items():
            if v is not None:
                if isinstance(v, float) and k != "盈利次数" and k != "亏损次数":
                    entry += f"| {k} | {v:.4f} |\n"
                else:
                    entry += f"| {k} | {v} |\n"

    if detail:
        entry += f"\n### 备注\n\n{detail}\n"

    entry += "\n---\n"

    with open(RESULT_FILE, "a", encoding="utf-8") as fp:
        fp.write(entry)


def main():
    # 初始检查
    health = http_get("/health")
    if health.get("status") != "ok":
        print("API 不可用，退出")
        sys.exit(1)

    record_initialized()

    # 读取已完成策略（断点续传）
    completed = set()
    if RESULT_FILE.exists():
        content = RESULT_FILE.read_text(encoding="utf-8")
        for m in re.finditer(r"文件.*?`(.+?)`", content):
            completed.add(m.group(1))

    strategy_files = sorted(
        [f for f in STRATEGY_DIR.iterdir() if f.suffix in (".py", ".txt")],
        key=lambda f: natural_key(f.name),
    )

    total = len(strategy_files)
    print(f"共 {total} 个策略文件，已完成 {len(completed)} 个\n")

    stats = {"success": len(completed), "failed": 0, "timeout": 0, "skipped": 0}

    for idx, f in enumerate(strategy_files):
        filename = f.name
        title = get_title(filename)

        if filename in completed:
            stats["skipped"] += 1
            continue

        print(f"[{idx+1}/{total}] {title}")
        print(f"  文件: {filename}")

        # 提取代码
        code = extract_code(f)
        if not code:
            print(f"  ⚠️ 无法提取策略代码（研究笔记/jupyter文件）")
            record_result(filename, title, "跳过", "无法提取可运行的策略代码（可能是研究笔记或 Jupyter notebook 导出文件）")
            stats["skipped"] += 1
            continue

        if len(code) < 200:
            print(f"  ⚠️ 代码过短 ({len(code)} 字符)")
            record_result(filename, title, "跳过", f"提取到 {len(code)} 字符，疑似不含完整策略代码")
            stats["skipped"] += 1
            continue

        print(f"  代码: {len(code)} 字符", end="")

        # 提交任务
        payload = {
            "name": title,
            "code": code,
            "start_date": "2023-01-01",
            "end_date": "2025-12-31",
            "initial_capital": 1_000_000.0,
            "benchmark": "000300.XSHG",
        }
        task_resp = http_post("/strategy-backtest", payload)

        if "error" in task_resp:
            error_msg = task_resp["error"]
            print(f" → 提交失败: {error_msg}")
            record_result(filename, title, "提交失败", f"API 返回: {error_msg}")
            stats["failed"] += 1
            time.sleep(3)
            continue

        task_id = task_resp.get("task_id")
        if not task_id:
            print(f" → 无 task_id: {task_resp}")
            record_result(filename, title, "提交异常", f"响应异常: {json.dumps(task_resp, ensure_ascii=False)[:500]}")
            stats["failed"] += 1
            continue

        print(f" → task={task_id}", end="", flush=True)

        # 轮询等待（最多 25 分钟，JQ 超时 1200s + 缓冲）
        max_wait = 1500
        interval = 20
        waited = 0
        done = False
        last_status = ""

        while waited < max_wait:
            time.sleep(interval)
            waited += interval

            task_info = http_get(f"/tasks/{task_id}")
            status = task_info.get("status", "unknown")

            if status != last_status:
                last_status = status
                print(f" [{waited}s:{status}]", end="", flush=True)

            if status == "completed":
                result_data = task_info.get("result", {})
                metrics = scrape_metrics(task_info)
                print(f" ✓")
                if metrics:
                    ar = metrics.get("策略年化收益", "N/A")
                    md = metrics.get("最大回撤", "N/A")
                    sr = metrics.get("夏普比率", "N/A")
                    print(f"  年化={ar} 回撤={md} 夏普={sr}")
                record_result(filename, title, "完成", "", metrics)
                stats["success"] += 1
                done = True
                break

            elif status == "failed":
                error_msg = task_info.get("error", "未知错误")
                print(f" ✗ ({error_msg[:100]}...)")
                record_result(filename, title, "失败", f"错误: {error_msg}")
                stats["failed"] += 1
                done = True
                break

        if not done:
            print(f" ⏱ 超时 ({max_wait}s)")
            record_result(filename, title, "超时", f"等待 {max_wait}s 未完成，任务ID: {task_id}")

        # 策略间冷却
        time.sleep(5)

    # 汇总
    print(f"\n{'='*50}")
    print(f"全部完成: 成功={stats['success']} 失败={stats['failed']} 超时={stats['timeout']} 跳过={stats['skipped']}")
    print(f"结果文件: {RESULT_FILE}")


if __name__ == "__main__":
    main()