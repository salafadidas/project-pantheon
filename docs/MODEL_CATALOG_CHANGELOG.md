# Model Catalog Changelog

每次 `llm/model_catalog.py` 有定價或模型異動，皆記錄於此。
每版更新後同步至 NotebookLM（Project Pantheon notebook）作為長期知識庫。

---

## v2 — 2026-05-04 (commit `40d494c`)

**觸發原因：** 週期性定價審查（Anthropic Opus 大幅降價、o3 大降、Gemini 2.5 Flash 漲價、2 個 Google 模型廢棄）

### Diff 表

| Provider  | Model                | Field                    | Old          | New          | Status     |
|-----------|----------------------|--------------------------|--------------|--------------|------------|
| Anthropic | claude-opus          | display_name             | Opus 4       | Opus 4.7     | UPDATED    |
| Anthropic | claude-opus          | price_input_per_1m       | $15.00       | $5.00        | ↓ 67%      |
| Anthropic | claude-opus          | price_output_per_1m      | $75.00       | $25.00       | ↓ 67%      |
| Anthropic | claude-opus          | context_window_k         | 200K         | 1,000K       | ↑ 5×       |
| Anthropic | claude-sonnet        | display_name             | Sonnet 4.5   | Sonnet 4.6   | UPDATED    |
| Anthropic | claude-sonnet        | context_window_k         | 200K         | 1,000K       | ↑ 5×       |
| Anthropic | claude-sonnet        | price (input/output)     | $3 / $15     | $3 / $15     | UNCHANGED  |
| Anthropic | claude-haiku         | price_input_per_1m       | $0.80        | $1.00        | ↑ 25%      |
| Anthropic | claude-haiku         | price_output_per_1m      | $4.00        | $5.00        | ↑ 25%      |
| OpenAI    | o3                   | price_input_per_1m       | $10.00       | $2.00        | ↓ 80%      |
| OpenAI    | o3                   | price_output_per_1m      | $40.00       | $8.00        | ↓ 80%      |
| OpenAI    | o4-mini              | price (input/output)     | $1.10 / $4.40| $1.10 / $4.40| UNCHANGED  |
| OpenAI    | gpt-4.1              | price (input/output)     | $2 / $8      | $2 / $8      | UNCHANGED  |
| OpenAI    | gpt-4.1-mini         | price (input/output)     | $0.40 / $1.60| (assumed same)| RECHECK   |
| OpenAI    | gpt-4o               | price (input/output)     | $2.50 / $10  | (assumed same)| RECHECK   |
| OpenAI    | gpt-4o-mini          | price (input/output)     | $0.15 / $0.60| (assumed same)| RECHECK   |
| OpenAI    | gpt-5                | —                        | —            | $1.25 / $10  | **NEW**    |
| Google    | gemini-2.5-pro       | price (input/output)     | $1.25 / $10  | $1.25–2.50 / $10–15* | TIERED |
| Google    | gemini-2.5-flash     | price_input_per_1m       | $0.15        | $0.30        | ↑ 100%     |
| Google    | gemini-2.5-flash     | price_output_per_1m      | $0.60        | $2.50        | ↑ 317%     |
| Google    | gemini-2.0-flash     | status                   | active       | DEPRECATED   | ⚠️ Jun 1   |
| Google    | gemini-2.0-flash-lite| status                   | active       | DEPRECATED   | ⚠️ Jun 1   |
| Google    | gemini-2.5-flash-lite| —                        | —            | $0.10 / $0.40| **NEW**    |

> \* gemini-2.5-pro 超過 200K context tokens 後切換至較高價格段（TIERED pricing）

### 未套用項目（待下版確認）

| Provider | Model           | 說明                                         |
|----------|-----------------|----------------------------------------------|
| OpenAI   | gpt-5.4         | 新旗艦 $2.50/$15（截圖顯示，待官方確認）       |
| Google   | gemini-3.1-pro-preview | Preview 定價 $2–4 / $12–18（preview 狀態）|
| OpenAI   | gpt-4.1-mini / gpt-4o / gpt-4o-mini | 需直接查 openai.com 確認現行定價 |
| Google   | gemini-2.5-pro  | TIERED 定價尚未在 catalog 拆分（仍用舊 flat rate）|

### 套用的 commit
```
40d494c  chore(catalog): update model pricing — Opus 67% drop, o3 80% drop, Gemini 2.5 Flash increase, 2 deprecated, 2 new
```

---

## v1 — 2026-04-25 (initial state, tag `v0.2.0-streaming`)

**初始 catalog 建立** — 15 個模型：3 Anthropic + 6 OpenAI + 4 Google + 2 NVIDIA NIM

| Provider  | Model                 | Input/1M | Output/1M | Context |
|-----------|-----------------------|----------|-----------|---------|
| Anthropic | claude-opus           | $15.00   | $75.00    | 200K    |
| Anthropic | claude-sonnet         | $3.00    | $15.00    | 200K    |
| Anthropic | claude-haiku          | $0.80    | $4.00     | 200K    |
| OpenAI    | o3                    | $10.00   | $40.00    | 200K    |
| OpenAI    | o4-mini               | $1.10    | $4.40     | 200K    |
| OpenAI    | gpt-4.1               | $2.00    | $8.00     | 1M      |
| OpenAI    | gpt-4.1-mini          | $0.40    | $1.60     | 1M      |
| OpenAI    | gpt-4o                | $2.50    | $10.00    | 128K    |
| OpenAI    | gpt-4o-mini           | $0.15    | $0.60     | 128K    |
| Google    | gemini-2.5-pro        | $1.25    | $10.00    | 1M      |
| Google    | gemini-2.5-flash      | $0.15    | $0.60     | 1M      |
| Google    | gemini-2.0-flash      | $0.10    | $0.40     | 1M      |
| Google    | gemini-2.0-flash-lite | $0.075   | $0.30     | 1M      |
| NVIDIA    | deepseek-v3           | free     | free      | 128K    |
| NVIDIA    | kimi-k2               | free     | free      | 128K    |

---

## 版本管理規則

1. **觸發時機：** 每次 `llm/model_catalog.py` 有任何定價、display_name、context_window、新增/棄用模型異動
2. **記錄格式：** 版本號（v1、v2…）+ 日期 + commit hash + Diff 表 + 未套用項目
3. **NotebookLM 同步：** 每版更新後執行 `scripts/sync_catalog_to_nlm.sh`，替換 notebook 中的舊 source
4. **週期審查：** 每週一 09:00 Asia/Taipei 自動觸發（由 `model-price-check` scheduled task 執行）

---

*Last updated: 2026-05-04 | Catalog v2 | 17 models (15 active + 2 deprecated)*
