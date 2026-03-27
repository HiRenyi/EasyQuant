# 版本更新

根据当前会话中完成的工作，更新版本号和更新日志。

## 版本号规则

版本格式：`vX.Y.Z`

- **X（Major）**：重大更新 — 架构重构、新增核心功能模块、破坏性变更
- **Y（Minor）**：中度更新 — 新功能、功能增强、新增数据源/市场支持
- **Z（Patch）**：小更新 — Bug 修复、UI 微调、文案修改、配置调整

## 执行步骤

### 1. 判断更新级别

根据当前对话中完成的工作，判断属于 Major / Minor / Patch 更新。

### 2. 读取当前版本

读取 `frontend/src/components/Header.tsx`，找到 `APP_VERSION` 常量获取当前版本号。

### 3. 递增版本号

- Major 更新：X+1，Y 和 Z 归零（如 v2.2.0 → v3.0.0）
- Minor 更新：Y+1，Z 归零（如 v2.2.0 → v2.3.0）
- Patch 更新：Z+1（如 v2.2.0 → v2.2.1）

### 4. 更新文件

在 `frontend/src/components/Header.tsx` 中：

1. 更新 `APP_VERSION` 为新版本号
2. 在 `CHANGELOG` 数组**最前面**插入新版本条目：

```typescript
{
  version: "vX.Y.Z",
  date: "YYYY-MM-DD",  // 今天的日期
  items: [
    // 根据当前会话完成的工作，列出 3-6 条简洁的更新说明
    // 每条以动词开头：新增/修复/优化/重构/支持
  ],
},
```

### 5. 同步 pyproject.toml 和 api_server.py

将 `pyproject.toml` 的 `version` 字段和 `quantgpt/api_server.py` 中 FastAPI 的 `version` 参数也更新为新版本号（不带 v 前缀，如 `"2.3.0"`）。

### 6. 调用 /commit

完成以上所有更新后，调用 `/commit` skill 提交代码，commit message 格式：
```
chore: 版本更新至 vX.Y.Z，更新 changelog
```

## 注意事项

- 更新说明应简洁（每条不超过 30 字），用中文
- 只记录用户可感知的变化，不记录内部重构细节（除非是 Major 更新）
- 如果传入了参数（如 `$ARGUMENTS`），使用参数指定的更新级别（major/minor/patch）
