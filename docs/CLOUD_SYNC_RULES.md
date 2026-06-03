# ☁️ 云端同步规则

## 0. 第一版架构说明

- **主键策略**：使用 `room_code`（text）作为共享房间主键，无需用户登录。
- **同步方式**：异步同步（手动触发或定时），**不做实时 Realtime**。
- **后端**：Supabase REST API（通过 `SupabaseCloudService` 封装）。
- **前端对接**：`SharedPetRoomManager` 封装同步逻辑，UI 层不直接调用 Supabase。

## 1. 云端同步字段

以下字段会被**上传**到 Supabase 的 `cloud_pets` 表：

| 字段 | 类型 | 说明 |
|------|------|------|
| `level` | int | 等级 |
| `exp` | int | 经验值 |
| `coins` | int | 金币 |
| `mood` | text | 心情 |
| `energy` | int | 精力 |
| `intimacy` | int | 亲密度 |
| `hunger` | int | 饱腹度 |
| `bond_score` | int | 羁绊值 |
| `pet_name` | text | 宠物名称 |
| `pet_id` | text | 宠物类型 ID |
| `updated_at` | timestamptz | 最后更新时间 |

互动事件会上传到 `pet_events` 表：

| 字段 | 说明 |
|------|------|
| `event_type` | 事件类型（如 interaction） |
| `action_type` | 具体行为（如 feed, play, pet, level_up） |
| `actor_name` | 执行者名称 |
| `delta` | 状态变化数值（JSON） |
| `message` | 可选描述文字 |

## 2. 本地保留字段（不上传）

以下数据**只保留在本地**，不会同步到云端：

- 🗨️ **聊天记录** — 本地 `assets/chat_history/`
- 🧠 **AI memory** — 本地 `assets/ai_memory/`
- 🔊 **TTS 设置** — 语音包、音色、语速等
- 🎨 **UI 设置** — 窗口位置、透明度、主题等
- 🔑 **真实 API Key** — DeepSeek、Qwen-VL 等（不会打印完整 key，仅前6位用于调试）
- 👤 **本地用户画像中的敏感内容**

## 3. 第一版同步策略

### 3.1 触发方式
- **手动触发**：用户在 UI 中点击"同步"按钮
- **定时同步**（可选）：每隔 N 分钟自动同步一次
- **❌ 不做实时同步**（第一版不接入 Supabase Realtime）

### 3.2 冲突解决
- 当前策略：**以 `updated_at` 较新的状态为准**
- 流程：pull 远程 → 比较时间戳 → 最新覆盖 → push
- TODO: 后续改为**事件增量合并**（基于 event log 重放）

### 3.3 同步流程
