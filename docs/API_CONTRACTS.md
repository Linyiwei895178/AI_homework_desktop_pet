# API Contracts — 云端共养对接文档

> 本文档定义各模块间 API 合约，供 A/C/D/E 四方协作时参考。

---

## 角色分工

| 角色 | 职责 | 对接方式 |
|------|------|----------|
| **A** | UI 层 | 调用 `SharedPetRoomManager`，不直接请求 Supabase |
| **C** | 话术（chat） | 只负责 `cloud_pet_event` 话术内容，不直接请求 Supabase |
| **D** | 状态管理 | 负责 `PetState` 与 `SharedPetRoomManager` 的同步，以及投喂/陪玩/打工/升级后的云端保存和事件上传 |
| **E** | 基础设施 | 负责 Supabase 配置、SQL 表、环境变量、GitHub 合并、测试脚本 |

---

## A — UI 对接

### A.1 初始化

```python
from models.cloud.shared_pet_room import SharedPetRoomManager
from models.cloud.cloud_service import SupabaseCloudService

svc = SupabaseCloudService()
mgr = SharedPetRoomManager(svc, room_code="TEAMROOM001")
```

### A.2 加入房间 / 创建宠物

```python
result = mgr.join_room("TEAMROOM001", "Echo")
# {"ok": True, "error": None, "data": {"room": ..., "pet": ...}}
```

### A.3 触发同步

```python
result = mgr.sync_now(local_state_dict)
# {"ok": True, "error": None, "data": {"pulled": ..., "pushed": ...}}
```

### A.4 推送本地状态到云端

```python
result = mgr.push_local_state(state_dict)
# {"ok": True, "error": None, "data": {"updated": True, "pet": {...}}}
```

### A.5 拉取远程状态到本地

```python
result = mgr.pull_remote_state()
# {"ok": True, "error": None, "data": {"pet": {...}}}
```

### A.6 上传互动事件

```python
result = mgr.append_interaction(action_type="feed", actor_name="我", delta={"hunger": 10})
# {"ok": True, "error": None, "data": {"inserted": True, ...}}
```

### A.7 获取最近事件

```python
result = mgr.fetch_recent_events(limit=20)
# {"ok": True, "error": None, "data": {"events": [...]}}
```

### A.8 事件回调

```python
def on_event(event_dict):
    print("New event:", event_dict)

mgr.set_on_event_callback(on_event)
```

### A.9 离开房间

```python
result = mgr.leave_room()
# {"ok": True, "error": None}
```

---

## C — 话术对接

> C 负责生成 `cloud_pet_event` 相关话术内容，不直接调用 Supabase。

C 只需定义事件数据结构给 D：

```python
event = {
    "event_type": "interaction",
    "action_type": "feed",          # 行为类型
    "actor_name": "队友名字",        # 执行者
    "message": "给宠物喂了一条鱼",    # 描述文字（可选）
    "delta": {"hunger": -20, "exp": 5, "coins": 1},  # 数值变化
}
```

将 event dict 交给 D，由 D 调用 `mgr.append_interaction(...)` 上传。

---

## D — 状态管理对接

> D 负责宠物状态的生命周期管理。

### D.1 初始化状态

```python
from models.cloud.cloud_models import CloudPetState

# 构建默认状态
state = CloudPetState(room_code="TEAMROOM001")
state_dict = state.to_dict()
# {
#   "room_code": "TEAMROOM001",
#   "pet_id": "cat",
#   "pet_name": "Echo",
#   "mood": "neutral",
#   "energy": 100,
#   "intimacy": 50,
#   "level": 1,
#   "exp": 0,
#   "coins": 0,
#   "hunger": 50,
#   "bond_score": 0,
#   "updated_at": "..."
# }
```

### D.2 投喂 / 陪玩 / 打工 / 升级后的流程

```python
# 1. 修改本地状态
state_dict["hunger"] = 30
state_dict["energy"] = 90
state_dict["exp"] += 5

# 2. 推送云端
result = mgr.push_local_state(state_dict)

# 3. 上传事件
mgr.append_interaction(
    action_type="feed",
    actor_name="我",
    delta={"hunger": -20, "exp": 5}
)
```

### D.3 定时同步

```python
# 从云端拉取最新状态
remote = mgr.pull_remote_state()
if remote["ok"]:
    latest_pet = remote["data"]["pet"]
    # 与本地合并（以 updated_at 最新的为准）
```

---

## E — 基础设施对接

### E.1 Supabase 配置

创建 Supabase 项目后，在 `.env` 中配置：

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
```

### E.2 数据库表

运行 `docs/SUPABASE_SCHEMA.sql` 在 Supabase SQL Editor 中创建表。

### E.3 测试

```bash
# 单元测试（mock 模式，不需要网络）
pytest tests/test_cloud_service_stub.py -v

# 真实连通性测试（需要 .env 和 Supabase 表）
python scripts/test_supabase_real_connection.py
```

### E.4 安全注意事项

- ❌ 不要提交 `.env` 文件
- ✅ 可以提交 `.env.example`（占位）
- ✅ 日志中 API key 只显示前 6 位

---

## 统一返回格式

所有云端方法返回统一格式：

```python
{"ok": True/False, "error": None|str, "data": Any}
```

### 成功

```json
{"ok": true, "error": null, "data": {...}}
```

### 未配置 Supabase

```json
{"ok": false, "error": "not_configured", "data": null}
```

### HTTP 错误

```json
{
  "ok": false,
  "error": "HTTP 409 Conflict — POST https://.../rest/v1/pet_rooms\n  response: {\"code\":\"23505\",...}",
  "data": null
}
```

### 业务层错误

```json
{"ok": false, "error": "not_in_room", "data": null}
```
