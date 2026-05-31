# AI_Desktop_Pet 🐱

**具身AI桌面宠物** - 一个可交互的虚拟桌面宠物Demo

## 项目简介

AI_Desktop_Pet 是一个基于 Python/Tkinter 构建的桌面虚拟宠物程序。你可以在桌面上拖拽它、点击它、右键弹出退出菜单，它会根据当前状态做出不同反应。项目采用模块化设计，内置四大模块的接口管理层，实现 **队员A (UI)**、**队员B (Vision)**、**队员C (TTS/NLP)**、**队员D (State)** 之间的低耦合协作。

## 功能特性

### ✅ 已实现
- ✅ 桌面显示桌宠图片（支持PNG格式，150×150缩放显示）
- ✅ 鼠标拖拽移动桌宠（无边框置顶窗口，透明背景）
- ✅ 左键点击桌宠触发动作响应（打印状态/动作 + 调用 API stub）
- ✅ 右键点击桌宠弹出"退出"菜单
- ✅ 确认退出提示框（askokcancel），用户确认后结束程序
- ✅ 状态系统（心情/能量/亲密度，含数值衰减与增长机制）
- ✅ 行为决策规则引擎（基于当前状态自动选择动作）
- ✅ 模块化架构，方便扩展
- ✅ 单元测试覆盖（7个测试用例全部通过）
- ✅ **队员D接口管理层**（EchoTeamDInterface）—— 13个API接口对接A/B/C三队
- ✅ **队员C接口管理层**（EchoTeamCInterface）—— 6个API接口对接A/D两队
- ✅ **队员B → 队员D 自动同步**（UserStateDetector → EchoTeamDInterface）
- ✅ **队员C ←→ 队员D 双向回调**（对话后更新状态、状态变化通知）
- ✅ **主动语音提示系统**（基于能量/亲密度/心情的阈值触发）
- ✅ **主循环集成**（3秒定时检测 + 自动回应 + 表情切换）
- ✅ **电脑状态陪伴点评**（识别前台游戏/看剧/视频状态，低频像朋友一样短评）

### 🔲 待开发（API Stub 就绪）
- 🔲 Qwen-VL多模态真实API对接（当前为Stub返回模拟数据）
- ✅ DeepSeek真实API对接（配置 `DEEPSEEK_API_KEY` 后调用真实接口，失败可降级本地回复）
- ✅ TTS语音播放（Edge 神经语音优先，pyttsx3/已有音频回退）
- 🔲 UI文字气泡显示（队员A）
- 🔲 动画系统（帧序列播放）

## 交互演示

| 操作 | 效果 |
|------|------|
| **左键点击** | 触发点击回调，打印桌宠位置与状态信息 |
| **左键拖拽** | 桌宠跟随鼠标移动 |
| **右键点击** | 弹出右键菜单，显示"退出"选项 |
| **退出确认** | 点击"退出" → 弹出"确定要退出桌宠吗？"对话框 → 确认后关闭程序 |

## 项目结构

```
AI_Desktop_Pet/
├─ app/
│   ├─ main.py                      # 程序入口（集成四模块接口）
│   ├─ ui/
│   │   ├─ desktop_pet.py           # 桌宠显示 & 鼠标事件（拖拽/左键/右键退出）
│   │   └─ widgets.py               # UI控件（状态面板、按钮面板）
│   └─ controller/
│       ├─ event_handler.py         # 事件处理
│       └─ pet_controller.py        # 动作触发
├─ models/
│   ├─ vision/
│   │   ├─ qwen_vl_api.py           # Qwen-VL API（Stub + 真实API就绪）
│   │   ├─ user_state_detector.py   # 用户状态感知（MediaPipe + OpenCV降级）
│   │   └─ computer_activity_detector.py # 电脑前台状态识别（游戏/看剧等）
│   ├─ nlp/
│   │   └─ deepseek_api.py          # DeepSeek API（真实接口 + 本地降级回复）
│   ├─ tts/
│   │   ├─ tts_manager.py           # TTS语音（Edge 神经语音 + 音色库 + 本地回退）
│   │   └─ echo_team_c_interface.py # 【队员C接口】对接UI和State
│   └─ state/
│       ├─ pet_state.py             # 桌宠状态（mood/energy/intimacy + 用户状态映射）
│       ├─ behavior_rules.py        # 行为决策规则引擎 + 主动语音提示 + 回调系统
│       └─ echo_team_d_interface.py # 【队员D接口】13个API对接A/B/C三队
├─ assets/
│   ├─ images/                      # 静态图片（cat_image_smile_001.png）
│   ├─ animations/                  # 动画序列（cat_anim_smile_001.png）
│   ├─ sounds/                      # 运行时生成/缓存的语音或本地音效
│   └─ voice_packs/                 # 可选本地音频包 / 每个桌宠的 TTS 音色配置
├─ utils/
│   ├─ file_manager.py              # 资产管理
│   ├─ logger.py                    # 日志记录（控制台 + 文件）
│   └─ config.py                    # .env 配置读取（单例）
├─ tests/                           # 单元测试
│   └─ test_pet_state.py            # 状态模块测试（7 cases ✅）
├─ .env                             # API Key 配置文件
├─ .gitignore
├─ requirements.txt
└─ README.md
```

## 团队分工与接口架构

```
┌────────────────────────────────────────────────────────────┐
│                        app/main.py                          │
│                      （主循环调度器）                         │
└──────────┬──────────────┬──────────────┬───────────────────┘
           │              │              │
     ┌─────▼──────┐ ┌────▼─────┐ ┌─────▼──────┐ ┌─────▼──────┐
     │  队员A     │ │  队员B   │ │  队员C     │ │  队员D     │
     │   (UI)    │ │ (Vision) │ │ (TTS/NLP) │ │  (State)  │
     │           │ │          │ │           │ │           │
     │DesktopPet │ │UserState │ │EchoTeamC  │ │EchoTeamD  │
     │EventHandler│ │Detector  │ │Interface  │ │Interface  │
     │PetCtrl    │ │QwenVL    │ │DeepSeek   │ │PetState   │
     │widgets    │ │          │ │TTS        │ │BehaviorRls│
     └───────────┘ └──────────┘ └───────────┘ └───────────┘
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

### 队员C接口一览（EchoTeamCInterface — 7个API）

| # | 接口 | 对接方 | 用途 |
|---|------|--------|------|
| 1 | `api_user_speak(text, state, cb)` | 队员A | 用户输入文本 → AI回复 + TTS |
| 2 | `api_play_system_voice(text)` | 队员A | 纯语音播放（绕过大模型） |
| 3 | `api_play_speech_hint(hint_text)` | 队员A | 播放主动语音提示 |
| 4 | `api_register_logic_callback(cb)` | 队员D | 注册对话结束回调 |
| 5 | `api_reset_ai_memory()` | 队员D | 清空对话记忆 |
| 6 | `api_get_last_chat()` | 队员A | 获取最近对话文本 |
| 7 | `api_set_pet_id(pet_id)` | 队员A/D | 同步当前桌宠ID，用于语音文件命名和音色选择 |

## 资产清单

| 文件 | 类型 | 说明 |
|------|------|------|
| assets/images/cat_image_smile_001.png | 🖼️ 图片 | 桌宠默认显示图片（150×150） |
| assets/animations/cat_anim_smile_001.png | 🎞️ 动画 | 微笑动画序列帧 |
| assets/sounds/cat_sound_happy_speak_001.wav | 🔊 音效 | 开心语音音效 |

### 资产命名规则

| 类型 | 命名格式                                    | 示例 |
|------|-----------------------------------------|------|
| 图片 | `{pet_id}_image_{state}_{seq}.png `       | `cat_image_smile_001.png` |
| 动画 | `{pet_id}_anim_{action}_{seq}.png  `      | `cat_anim_walk_001.png` |
| 声音 | `{pet_id}_sound_{state}_{action}_{seq}.wav` | `cat_sound_happy_speak_001.wav` |

## 快速开始

### 1. 克隆仓库
```
git clone https://github.com/SWT-0407/AI_homework_desktop_pet.git
cd AI_homework_desktop_pet
```

### 2. 安装依赖
```
pip install -r requirements.txt
```

### 3. 运行程序
```
python app/main.py
```

桌宠窗口将出现在桌面左上角 (100, 100) 位置，你可以：
- **左键拖拽**移动它
- **左键点击**触发动作
- **右键点击** → 点击"退出" → 确认退出
- 默认保持安静陪伴；如需演示旧版模拟状态循环，可设置 `DESKTOP_PET_MOCK_USER_STATE=true`

### 4. 运行测试
```
python tests/test_pet_state.py
```

## API 接口（Stub）

| 接口 | 服务 | 用途 | 状态 |
|------|------|------|------|
| get_user_expression(image_path) | Qwen-VL | 图像 → 用户表情状态 | 🔲 Stub → "happy" |
| generate_pet_reply(text_prompt) | DeepSeek | 文本 → 桌宠对话 | ✅ 真实API优先，未配置/失败时本地降级 |
| speak(text) | TTS | 文本 → 语音输出 | ✅ Edge TTS 优先，按 pet_state 状态/动作选择音色，离线/已有音频回退 |

> Stub 函数在 demo 阶段返回 mock 数据。所有 API 文件内含 `# TO_DO` 注释，对接真实 API 只需在对应文件中补充逻辑即可。

## 配置

项目根目录的 `.env` 文件（请勿提交到Git）：
```
QWEN_VL_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here

# 可选配置（有默认值）
QWEN_VL_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_THINKING=disabled
DEEPSEEK_FORCE_MOCK=false
DEEPSEEK_FALLBACK_TO_MOCK=true
QWEN_VL_MODEL=qwen-vl-plus
TTS_PROVIDER=auto
EDGE_TTS_VOICE=zh-CN-XiaoyiNeural
EDGE_TTS_RATE=+8%
EDGE_TTS_PITCH=+12Hz
EDGE_TTS_VOLUME=+8%
TTS_RATE=168
TTS_VOLUME=0.95
TTS_PITCH_SHIFT=1.06
TTS_CUTE_STYLE=true
VOICE_PACK_ID=
VOICE_PACK_ENABLED=true
VOICE_PACK_MODE=prefer
VOICE_PACK_AUTO_BY_PET=true
COMPUTER_ACTIVITY_ENABLED=true
COMPUTER_ACTIVITY_POLL_MS=1000
COMPUTER_ACTIVITY_MIN_DURATION=0
COMPUTER_ACTIVITY_COMMENT_COOLDOWN=150
DEBUG=True
LOG_LEVEL=INFO
```

## 开发计划

- [x] 项目结构搭建
- [x] 桌宠显示 & 鼠标交互（拖拽/左键点击）
- [x] 右键退出功能（弹出菜单 + 确认对话框）
- [x] 状态管理系统（mood/energy/intimacy）
- [x] 行为决策引擎
- [x] 单元测试覆盖
- [x] 图片/动画/音效资产
- [x] .gitignore 允许音频文件上传
- [x] **队员D接口管理层**（EchoTeamDInterface）
- [x] **队员C接口管理层**（EchoTeamCInterface）
- [x] **队员B→D自动同步**（Vision → State）
- [x] **队员C←→D双向回调**（TTS ↔ State）
- [x] **主动语音提示系统**
- [x] **主循环集成**（定时检测+自动回应）
- [ ] 真实API对接（Qwen-VL）
- [x] DeepSeek 真实 API 对接
- [x] pet_state 情绪/动作与 TTS 语音反馈同步
- [x] 每个桌宠可选 TTS 音色配置
- [ ] 多桌宠支持
- [ ] 动画系统（帧序列播放）
- [ ] UI文字气泡显示
- [ ] 语音交互
- [ ] 网络通信（多人互动）

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

仓库里已经放了 `sweet_girl`（甜妹）、`mature_sister`（御姐）、`playful_child`（顽皮童声）三个纯 TTS 参数包。打开桌宠右键菜单 → 设置面板 → AI对话，可在“语音包”列表里和“对话角色”并列切换；在“语音包选择”页点击“导入语音包”，填写名称、选择语言并导入一个或多个本地音频样本后，新语音包会以“语言名称”的形式自动出现在列表里。支持 `.wav`、`.mp3`、`.m4a`、`.flac`、`.ogg`、`.aac`、`.wma` 和 `.mp4`；导入 `.mp4` 时会用 ffmpeg 抽取音轨转成 `.mp3` 参与解析，原视频会保留。导入 WAV 样本时会额外生成轻度降噪副本用于后续分析参考，原始音频始终保留且优先。

`playful_child` 只是调皮童声 TTS 参数包，不包含也不模拟任何具体角色原声；如果要导入真实声音包，请只放入你有权使用的音频文件。

## 许可证

MIT License
