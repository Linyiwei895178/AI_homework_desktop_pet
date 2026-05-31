# AI_Desktop_Pet 🐱🎮

**具身AI桌面宠物** — 基于 PySide6 + Live2D 的智能桌面虚拟宠物程序

> 本项目是山东大学《人工智能引论》课程设计（大作业），由五人团队协作开发。
> 采用模块化接口架构，实现 **队员A (UI)**、**队员B (Vision)**、**队员C (TTS/NLP)**、**队员D (State)** 之间的低耦合协作。

## 项目简介

AI_Desktop_Pet 是一个基于 **PySide6 (Qt)** + **Live2D** 构建的智能桌面虚拟宠物程序。它是一款能"看见"你的状态、能主动和你聊天、能感知你电脑前活动的具身AI桌宠。项目采用模块化设计，内置四大模块的接口管理层，实现 **队员A (UI)**、**队员B (Vision)**、**队员C (TTS/NLP)**、**队员D (State)** 之间的低耦合协作。

## 功能特性

### ✅ 已实现

#### 🖥️ UI 交互（队员A）
- ✅ Live2D 模型渲染（基于 `live2d-py` + OpenGL），支持流畅动画
- ✅ 猫娘模型 `mao`（日文版）和 `mao_pro_zh`（中文版）双模型
- ✅ 桌面无边框置顶窗口，透明背景
- ✅ 鼠标拖拽移动桌宠 + 左键点击触发动作
- ✅ 右键菜单（退出、设置面板、切换角色）
- ✅ 弧形动作菜单（`ArcMotionMenu`）
- ✅ 设置面板（AI对话、语音包切换、TTS 设置、Pin顶置顶、悬浮淡出）
- ✅ 状态栏显示心情/能量/亲密度
- ✅ 聊天气泡/输入框（支持流式打字机效果）
- ✅ 控制台面板

#### 👁️ 视觉感知（队员B）
- ✅ 摄像头 → MediaPipe 人脸检测 → 用户状态分类（正常/专注/分心/疲劳/离开/返回）
- ✅ Qwen-VL API 接口（支持 stub 模拟和真实 API）
- ✅ 表情识别（基于 MediaPipe 人脸特征点）
- ✅ 低光照/长时间学习检测
- ✅ **电脑活动识别**：自动检测前台窗口（游戏/看剧/编程/办公/聊天/浏览等），低频陪伴式点评

#### 🗣️ TTS/NLP（队员C）
- ✅ **DeepSeek API 真实接口**（配置 `DEEPSEEK_API_KEY` 后调用，失败自动降级本地回复）
- ✅ **Edge TTS 神经语音**（微软在线语音，支持语速/音调/音量调节）
- ✅ **pyttsx3 离线回退**（无网络时可用）
- ✅ **自定义语音包导入与切换**
- ✅ 状态/情绪驱动的音频选择
- ✅ 聊天记忆（滚动窗口，支持 JSON 持久化）
- ✅ Prompt 构建器（根据用户状态/电脑活动动态生成系统提示词）
- ✅ 流式打字机效果 + 主动语音提示系统

#### 📊 状态管理（队员D）
- ✅ **三围状态系统**：`mood`（心情）/ `energy`（能量）/ `intimacy`（亲密度）
- ✅ 数值自然衰减与增长机制
- ✅ 用户状态映射到桌宠状态（疲惫→安抚、分心→提醒等）
- ✅ 行为决策规则引擎（基于当前状态自动选择动作）
- ✅ 对话后状态更新（消耗能量 + 增加亲密度）
- ✅ 持久化保存/恢复状态

#### 🎮 虚拟宠物系统（VPet 移植）
- ✅ **物品系统**：食物分类（主食/零食/功能食品）、道具
- ✅ **商店目录**：可配置的商品列表
- ✅ **打工系统**：多种工作类型，支持限时任务
- ✅ **主题系统**：可切换 UI 主题配色
- ✅ **游戏存档**：支持多种模式（标准/休闲/困难/自定义）
- ✅ **文本规则引擎**：根据状态自动匹配对话文本

#### 🧪 测试覆盖
- ✅ 状态模块测试（7 个测试用例）
- ✅ 队员C 模块测试（`test_team_c_module.py`）
- ✅ 虚拟宠物功能测试
- ✅ 电脑活动检测测试

### 🔲 待开发
- 🔲 动画系统增强（帧序列播放）
- 🔲 语音交互（麦克风输入）
- 🔲 多桌宠支持（同时显示多个角色）
- 🔲 网络通信（多人互动）
- 🔲 真实 Qwen-VL 视觉 API 全面对接

## 交互演示

| 操作 | 效果 |
|------|------|
| **左键点击** | 触发点击回调，桌宠做出反应动作 |
| **左键拖拽** | 桌宠跟随鼠标移动 |
| **右键点击** | 弹出右键菜单（设置、切换角色、退出等） |
| **设置面板** | 可配置 AI 对话角色、语音包、TTS 参数、Pin顶置顶 |
| **聊天输入** | 输入文字与桌宠 AI 对话，流式显示在气泡中 |
| **自动感知** | 桌宠每 3 秒检测用户状态，主动关心/提醒/陪伴 |

## 项目结构

```
AI_Desktop_Pet/
├── app/                              # 应用程序入口和UI
│   ├── main.py                       # 🚀 程序入口（集成四模块接口）
│   ├── __init__.py
│   ├── ui/
│   │   ├── desktop_pet.py (139KB)    # 🐱 Live2D 桌宠主窗口（含 OpenGL 渲染）
│   │   └── widgets.py   (125KB)      # 🎨 UI控件（菜单、气泡、设置面板等）
│   └── controller/
│       ├── event_handler.py          # 🖱️ 事件处理（鼠标/键盘）
│       └── pet_controller.py         # 🎮 动作触发（表情/动画切换）
│
├── models/                           # 🧠 核心业务逻辑
│   ├── nlp/                          #   自然语言处理（队员C）
│   │   ├── deepseek_api.py           #      DeepSeek API 调用 + 本地降级
│   │   ├── prompt_builder.py         #      Prompt 构建器
│   │   └── chat_memory.py            #      聊天记忆（滚动窗口+持久化）
│   ├── tts/                          #   语音合成（队员C）
│   │   ├── tts_manager.py            #      TTS 管理器（Edge / pyttsx3 路由）
│   │   ├── ai_voice_assistant.py     #      AI 对话语音助手（核心类）
│   │   ├── echo_team_c_interface.py  #      【队员C接口层】8个API
│   │   └── voice_pack.py             #      语音包管理
│   ├── vision/                       #   视觉感知（队员B）
│   │   ├── user_state_detector.py    #      用户状态检测器（摄像头→MediaPipe）
│   │   ├── computer_activity_detector.py # 💻 电脑活动检测（前台窗口分析）
│   │   ├── emotion_recognizer.py     #      表情识别（MediaPipe特征点）
│   │   └── qwen_vl_api.py            #      Qwen-VL API（Stub + 真实API）
│   ├── state/                        #   状态管理（队员D）
│   │   ├── pet_state.py              #      桌宠三围状态（mood/energy/intimacy）
│   │   ├── behavior_rules.py         #      行为决策引擎
│   │   └── echo_team_d_interface.py  #      【队员D接口层】13个API
│   └── vpet/                         #   🎮 虚拟宠物系统（VPet 移植）
│       ├── items.py                  #      物品/食物定义
│       ├── catalog.py                #      商店目录
│       ├── work.py                   #      打工系统
│       ├── service.py                #      功能服务
│       ├── texts.py                  #      文本规则引擎
│       ├── themes.py                 #      UI主题
│       ├── save.py                   #      游戏存档
│       └── lps.py                    #      LPS 文件解析器
│
├── assets/                           # 🎨 资源文件
│   ├── models/                       #   Live2D 模型
│   │   ├── mao/                      #     猫娘模型 mao（日文版）
│   │   └── mao_pro_zh/               #     猫娘模型 mao_pro_zh（中文版）
│   ├── images/                       #   静态图片
│   │   ├── cat_image_smile_001.png
│   │   ├── 这狗_idle_frame.png
│   │   └── 这狗_idle_frame_001.png
│   ├── animations/                   #   GIF 动画
│   │   └── 这狗_anim_*.gif           #     柴犬动画（待机/吃饭/幸福/生气等）
│   ├── voice_packs/                  #   🎵 语音包（TTS 音色配置，可从 UI 导入）
│   ├── chat_history/                 #   聊天历史存档
│   ├── sounds/                       #   运行时生成的语音缓存
│   ├── synonyms.json                 #   情绪→动作 映射表
│   ├── pet_memory.json               #   桌宠记忆（持久化状态）
│   └── action_mapping.json           #   动作映射表
│
├── data/                             # 📊 运行时配置数据
│   └── pet_ui_settings.json          #   UI 设置持久化
│
├── tests/                            # 🧪 单元测试
│   ├── test_pet_state.py             #   状态模块测试
│   ├── test_team_c_module.py         #   队员C模块测试
│   ├── test_vpet_features.py         #   虚拟宠物功能测试
│   └── test_computer_activity_detector.py  # 电脑活动检测测试
│
├── utils/                            # 🔧 工具模块
│   ├── config.py                     #   .env 配置读取（单例）
│   ├── logger.py                     #   日志记录
│   └── file_manager.py               #   资产管理
│
├── requirements.txt                  # 📦 Python 依赖
├── README.md                         # 📖 本文件
├── .gitignore                        # Git 忽略规则
└── .env                              # 🔑 API Key 配置（不提交到Git）
```

## 团队分工与接口架构

```
┌────────────────────────────────────────────────────────────────────┐
│                         app/main.py                                │
│                       （主循环调度器）                               │
│              每3秒检测→状态同步→决策动作→触发UI                      │
└────┬──────────────┬──────────────┬──────────────┬─────────────────┘
     │              │              │              │
┌────▼──────┐ ┌────▼─────┐ ┌─────▼──────┐ ┌─────▼──────┐
│  队员A    │ │  队员B   │ │  队员C     │ │  队员D     │
│   (UI)   │ │ (Vision) │ │ (TTS/NLP) │ │  (State)  │
│          │ │          │ │           │ │           │
│DesktopPet│ │UserState │ │EchoTeamC  │ │EchoTeamD  │
│EventHndlr│ │Detector  │ │Interface  │ │Interface  │
│PetCtrl   │ │QwenVL    │ │AIChatVoice│ │PetState   │
│widgets   │ │Computer  │ │Assistant  │ │BehaviorRls│
│          │ │Activity  │ │TTSManager │ │           │
│          │ │Detector  │ │ChatMemory │ │           │
└──────────┘ └──────────┘ └───────────┘ └───────────┘
     │              │              │              │
     └──────────────┴──────────────┴──────────────┘
                  接口调用关系:
             A←D: 获取状态/决策动作
             B→D: 用户状态同步（摄像头/电脑活动）
             C↔D: 对话回调 + 状态事件通知（双向）
```

### 数据流示例

```
[队员B] 摄像头/电脑活动检测
    │  api_apply_user_state(user_state)
    ▼
[队员D] 更新 mood/energy/intimacy
    │  api_decide_action()
    ├─▶ [队员A] 切换桌宠表情/动画
    │  api_should_speak() → api_get_speech_hint()
    └─▶ [队员C] 触发 AI 对话 + TTS 语音
         │  api_on_chat_finished(word_count)
         └─▶ [队员D] 更新亲密度/能量
```

### 队员D接口一览（EchoTeamDInterface — 13个API）

| # | 接口 | 对接方 | 用途 |
|---|------|--------|------|
| 1 | `api_get_pet_status()` | 队员A | 获取桌宠当前状态 |
| 2 | `api_decide_action()` | 队员A | 决策当前动作 |
| 3 | `api_get_status_history(n)` | 队员A | 获取状态变化历史 |
| 4 | `api_apply_user_state(user_state)` | 队员B | 接收用户检测状态 |
| 5 | `api_bind_vision_detector(detector)` | 队员B | 一键绑定视觉检测器 |
| 6 | `api_on_chat_finished(word_count)` | 队员C | 对话后更新状态 |
| 7 | `api_get_speech_hint()` | 队员C | 获取主动语音提示 |
| 8 | `api_should_speak()` | 队员C | 判断是否该主动说话 |
| 9 | `api_get_pet_id()` | 队员C | 获取桌宠ID |
| 10 | `api_register_status_listener(cb)` | 队员C | 注册状态监听回调 |
| 11 | `api_reset_state_memory()` | 队员C | 重置状态记忆 |
| 12 | `api_save_state(filepath)` | 队员C | 持久化状态 |
| 13 | `api_load_state(filepath)` | 队员C | 恢复状态 |

### 队员C接口一览（EchoTeamCInterface — 8个API）

| # | 接口 | 对接方 | 用途 |
|---|------|--------|------|
| 1 | `api_user_speak(text, state, cb)` | 队员A | 用户输入文本 → AI回复（流式） + TTS |
| 2 | `api_play_system_voice(text)` | 队员A | 纯语音播放（绕过大模型） |
| 3 | `api_play_speech_hint(hint_text)` | 队员A | 播放主动语音提示 |
| 4 | `api_register_logic_callback(cb)` | 队员D | 注册对话结束回调 |
| 5 | `api_reset_ai_memory()` | 队员D | 清空对话记忆 |
| 6 | `api_get_last_chat()` | 队员A | 获取最近对话文本 |
| 7 | `api_set_pet_id(pet_id)` | 队员A/D | 同步当前桌宠ID |
| 8 | `api_set_tts_settings(settings)` | 队员A | 运行时更新 TTS 参数 |

## 资产系统

### Live2D 模型

| 模型 | 路径 | 说明 |
|------|------|------|
| **mao** (日文版) | `assets/models/mao/` | 猫娘 Live2D 模型，含 8 种表情 + 7 套动作 + 物理动画 |
| **mao_pro_zh** (中文版) | `assets/models/mao_pro_zh/` | 同上模型的中文版（含独立 runtime） |

### 柴犬动画 GIF

| 动画 | 文件 | 说明 |
|------|------|------|
| 🐕 待机 | `这狗_anim_idle.gif` | 默认待机动作 |
| 🐕 吃饭 | `这狗_anim_吃饭.gif` | 饥饿状态动作 |
| 🐕 幸福 | `这狗_anim_幸福.gif` | 开心/亲密度高 |
| 🐕 想吃 | `这狗_anim_想吃.gif` | 讨食动作 |
| 🐕 敬礼 | `这狗_anim_敬礼.gif` | 可爱动作 |
| 🐕 爱你 | `这狗_anim_爱你.gif` | 高亲密度动作 |
| 🐕 生气 | `这狗_anim_生气.gif` | 生气状态动作 |
| 🐕 星星眼 | `这狗_anim_星星眼.gif` | 期待状态 |

### 语音包

| 角色 | 路径 | 说明 |
|------|------|------|
默认不内置角色语音包。通过“语音包选择”页导入本地音频样本后，新语音包会自动出现在列表里。

### 资产命名规则

| 类型 | 命名格式 | 示例 |
|------|---------|------|
| 图片 | `{pet_id}_image_{state}_{seq}.png` | `cat_image_smile_001.png` |
| 动画 | `{pet_id}_anim_{state}_{seq}.gif` | `这狗_anim_吃饭.gif` |
| 声音 | `{pet_id}_sound_{state}_{action}_{seq}.wav` | `cat_sound_happy_speak_001.wav` |

## 快速开始

### 环境要求

- **Python**: 3.10+（推荐 3.10~3.12，3.14 部分包需降级）
- **操作系统**: Windows 10/11（pywin32 依赖）
- **可选**: 摄像头（用于用户状态检测）

### 1️⃣ 克隆仓库

```
git clone https://github.com/SWT-0407/AI_homework_desktop_pet.git
cd AI_homework_desktop_pet
```

### 2️⃣ 安装依赖

```
pip install -r requirements.txt
```

> ⚠️ **Python 3.14 用户注意**：
> - `deepface` + `tensorflow` 不支持 Python 3.14（表情识别功能暂不可用，不影响核心功能）
> - `PyAudio` 无预编译包（语音输入暂不可用，TTS 语音输出正常）
> - 建议使用 Python 3.10~3.12 获得完整功能

### 3️⃣ 配置环境变量

创建 `.env` 文件：

```
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

> 至少需要配置 `DEEPSEEK_API_KEY` 才能使用 AI 对话功能。
> 未配置时会自动使用本地降级回复。

### 4️⃣ 运行程序

```
python app/main.py
```

桌宠窗口将出现在桌面左上角，你可以：
- 🖱️ **左键拖拽** 移动桌宠
- 🖱️ **左键点击** 触发动作
- 🖱️ **右键点击** → 设置/切换角色/退出
- 💬 **输入文字** 与桌宠 AI 对话
- 👀 程序每 3 秒自动检测模拟用户状态并主动回应

### 5️⃣ 运行测试

```
pytest tests/
```
或单独运行：
```
python -m pytest tests/test_pet_state.py -v
python -m pytest tests/test_team_c_module.py -v
```

## 配置文件

项目根目录的 `.env` 文件（请勿提交到 Git）：

```
# ==== API Keys（必需） ====
DEEPSEEK_API_KEY=your_key_here
QWEN_VL_API_KEY=your_key_here

# ==== DeepSeek 配置 ====
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_THINKING=disabled
DEEPSEEK_FORCE_MOCK=false
DEEPSEEK_FALLBACK_TO_MOCK=true

# ==== Qwen-VL 视觉模型 ====
QWEN_VL_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
QWEN_VL_MODEL=qwen-vl-plus

# ==== TTS 语音 ====
TTS_PROVIDER=auto
EDGE_TTS_VOICE=zh-CN-XiaoyiNeural
EDGE_TTS_RATE=+8%
EDGE_TTS_PITCH=+12Hz
EDGE_TTS_VOLUME=+8%
TTS_RATE=168
TTS_VOLUME=0.95
TTS_PITCH_SHIFT=1.06
TTS_CUTE_STYLE=true

# ==== 语音包 ====
VOICE_PACK_ID=
VOICE_PACK_ENABLED=true
VOICE_PACK_MODE=prefer
VOICE_PACK_AUTO_BY_PET=true

# ==== 电脑活动检测 ====
COMPUTER_ACTIVITY_ENABLED=true
COMPUTER_ACTIVITY_POLL_MS=1000
COMPUTER_ACTIVITY_MIN_DURATION=0
COMPUTER_ACTIVITY_COMMENT_COOLDOWN=150

# ==== 调试 ====
DEBUG=True
LOG_LEVEL=INFO
```

## 开发计划

### ✅ 已完成
- [x] 项目结构搭建
- [x] 桌宠显示 & 鼠标交互（拖拽/左键/右键菜单）
- [x] 状态管理系统（mood/energy/intimacy）
- [x] 行为决策引擎 + 主动语音提示系统
- [x] 单元测试覆盖
- [x] **队员D接口管理层**（EchoTeamDInterface，13个API）
- [x] **队员C接口管理层**（EchoTeamCInterface，8个API）
- [x] **队员B→D 自动同步**（Vision → State）
- [x] **队员C↔D 双向回调**（TTS ↔ State）
- [x] **主循环集成**（3秒定时检测 + 自动回应 + 表情切换）
- [x] DeepSeek 真实 API 对接 + 本地降级
- [x] Edge TTS 神经语音 + pyttsx3 离线回退
- [x] pet_state 情绪/动作与 TTS 语音反馈同步
- [x] 自定义语音包导入与切换
- [x] **Live2D 模型渲染**（mao 日文版 + mao_pro_zh 中文版）
- [x] **电脑活动识别**（游戏/看剧/编程/办公/聊天等）
- [x] **聊天记忆系统**（滚动窗口 + JSON 持久化）
- [x] Prompt 构建器（动态状态感知提示词）
- [x] **虚拟宠物系统**（VPet 移植：物品/商店/打工/存档）
- [x] 流式打字机效果（分块推送到 UI 气泡）
- [x] 表情识别（MediaPipe 特征点）

### 🔲 待开发
- [ ] 真实 Qwen-VL 视觉 API 全面对接
- [ ] 动画系统增强（帧序列播放）
- [ ] 语音交互（麦克风输入）
- [ ] 多桌宠支持（同时显示多个角色）
- [ ] 网络通信（多人互动）
- [ ] Mac/Linux 跨平台支持

## 外部声音包 / 音色库

项目现在支持两种语音素材方式：可以把本地声音包作为桌宠语音来源，也可以只在 `voice_pack.json` 里存 TTS 音色参数，不放任何音频文件。请只导入你有权使用的音频/视频文件；不要提交或分发未经授权的语音资源。

1. 如果要放音频，把文件放到 `assets/voice_packs/<pack_id>/`，例如 `assets/voice_packs/daji/click_001.wav`。
2. 如果只用 API/TTS，在同目录 `voice_pack.json` 写 `voice_profiles` 即可。
3. `neutral.click`、`happy.speak`、`speak` 等键会按当前 `pet_state` 的情绪/动作匹配。
4. 在 `.env` 开启声音包或音色库：

```env
VOICE_PACK_ID=
VOICE_PACK_ENABLED=true
VOICE_PACK_MODE=prefer
VOICE_PACK_AUTO_BY_PET=true
```

`VOICE_PACK_ID` 为空且 `VOICE_PACK_AUTO_BY_PET=true` 时，会自动尝试读取 `assets/voice_packs/<pet_id>/voice_pack.json`。例如当前桌宠 ID 是 `cat`，就会读取 `assets/voice_packs/cat/voice_pack.json`。

`VOICE_PACK_MODE=prefer` 会优先播放声音包，找不到匹配音频时自动回退到现有 TTS。也可以改成 `fallback`，让 TTS 失败后才尝试声音包；`off` 会同时关闭本地音频包和音色配置。

打开桌宠右键菜单 → 设置面板 → AI对话，可在“语音包选择”页点击“导入语音包”，填写名称、选择语言并导入一个或多个本地音频样本后，新语音包会以“语言名称”的形式自动出现在列表里。支持 `.wav`、`.mp3`、`.m4a`、`.flac`、`.ogg`、`.aac`、`.wma` 和 `.mp4`；导入 `.mp4` 时会用 ffmpeg 抽取音轨转成 `.mp3` 参与解析，原视频会保留。导入 WAV 样本时会额外生成轻度降噪副本用于后续分析参考，原始音频始终保留且优先。

## 许可证

MIT License

Copyright (c) 2024 SWT-0407

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
