#!/usr/bin/env python3
import os, sys, json, time, re, urllib.request

RESULTS_FILE = '/home/kevin/github/QuantGPT/回测结果.md'
STRATEGIES_DIR = '/home/kevin/github/QuantGPT/聚宽2025年精选/'
API_BASE = 'http://localhost:8003'

# Get completed filenames
with open(RESULTS_FILE, 'r') as f:
    content = f.read()

completed = []
for line in content.split('\n'):
    if '**文件**:' in line:
        fname = line.split('**文件**:', 1)[1].strip().strip('`').strip()
        completed.append(fname)

print(f'Completed: {len(completed)}')

# Sort by file size (shortest first) for faster iteration
all_files = sorted(
    [f for f in os.listdir(STRATEGIES_DIR) if f.endswith(('.py', '.txt')) and f not in completed],
    key=lambda f: os.path.getsize(os.path.join(STRATEGIES_DIR, f))
)

# Pick shortest uncompleted
for fname in all_files:
    if fname not in completed:
        print(f'NEXT: {fname}')
        fpath = os.path.join(STRATEGIES_DIR, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            raw = f.read()

        if fname.endswith('.txt'):
            lines = raw.split('\n')
            start = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('import ') or stripped.startswith('from '):
                    start = i
                    break
            code = '\n'.join(lines[start:])
        else:
            code = raw

        title = os.path.splitext(fname)[0]
        title = re.sub(r'^\d+', '', title)

        print(f'TITLE: {title}')
        print(f'CODE_LEN: {len(code)}')

        payload = json.dumps({
            'strategyName': title,
            'code': code,
            'start_date': '2025-01-01',  # Reduced to 1 year to save points
            'end_date': '2025-12-31'
        }).encode('utf-8')
        req = urllib.request.Request(
            f'{API_BASE}/api/v1/strategy-backtest',
            data=payload,
            headers={'Content-Type': 'application/json'}
        )
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())
        task_id = result.get('task_id', result.get('taskId', ''))
        print(f'TASK_ID: {task_id}')

        max_wait = 7200
        elapsed = 0

        # First, check validation status
        time.sleep(10)
        req_check = urllib.request.Request(f'{API_BASE}/api/v1/tasks/{task_id}')
        resp_check = urllib.request.urlopen(req_check)
        task_data = json.loads(resp_check.read())
        validation = task_data.get('validation')
        if validation and not validation.get('valid', True):
            errors = validation.get('errors', [])
            print(f'VALIDATION FAILED: {errors}')
            # Mark as skipped in results file
            with open(RESULTS_FILE, 'a', encoding='utf-8') as rf:
                rf.write(f'\n## {title}（验证失败跳过）\n\n- **文件**: `{fname}`\n- **原因**: {"; ".join(errors)}\n\n')
            sys.exit(0)

        while elapsed < max_wait:
            time.sleep(20)
            elapsed += 20
            req2 = urllib.request.Request(f'{API_BASE}/api/v1/tasks/{task_id}')
            resp2 = urllib.request.urlopen(req2)
            status_data = json.loads(resp2.read())

            if status_data.get('error'):
                err = status_data['error']
                print(f'ERROR: {err}')
                # Check for negative points error
                if '积分' in err or '积分为负' in err:
                    with open(RESULTS_FILE, 'a', encoding='utf-8') as rf:
                        rf.write(f'\n## {title}（积分不足跳过）\n\n- **文件**: `{fname}`\n- **原因**: 聚宽账户积分为负，请充值后继续\n\n')
                    print('SKIPPED: negative points')
                break

            progress = status_data.get('progress', [])
            if progress:
                latest = progress[-1]
                status = latest.get('status', '')
                print(f'[{elapsed}s] {status}')

                if status == 'completed':
                    result_data = latest.get('result', {})
                    annual = result_data.get('annual_return', 'N/A')
                    drawdown = result_data.get('max_drawdown', 'N/A')
                    sharpe = result_data.get('sharpe_ratio', 'N/A')
                    print(f'DONE: 年化={annual}% 回撤={drawdown}% 夏普={sharpe}')
                    break
                elif status == 'failed':
                    print(f'FAILED: {latest.get("error", "unknown")}')
                    break

        sys.exit(0)

print('ALL DONE')
