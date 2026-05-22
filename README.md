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

### 🔲 待开发（API Stub 就绪）
- 🔲 Qwen-VL多模态真实API对接（当前为Stub返回模拟数据）
- 🔲 DeepSeek真实API对接（当前为Stub返回模拟对话）
- 🔲 TTS语音真实API对接（当前为Stub打印路径）
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
│   │   └─ user_state_detector.py   # 用户状态感知（MediaPipe + OpenCV降级）
│   ├─ nlp/
│   │   └─ deepseek_api.py          # DeepSeek API（Stub，支持上下文感知回复）
│   ├─ tts/
│   │   ├─ tts_manager.py           # TTS语音（Stub）
│   │   └─ echo_team_c_interface.py # 【队员C接口】对接UI和State
│   └─ state/
│       ├─ pet_state.py             # 桌宠状态（mood/energy/intimacy + 用户状态映射）
│       ├─ behavior_rules.py        # 行为决策规则引擎 + 主动语音提示 + 回调系统
│       └─ echo_team_d_interface.py # 【队员D接口】13个API对接A/B/C三队
├─ assets/
│   ├─ images/                      # 静态图片（cat_image_smile_001.png）
│   ├─ animations/                  # 动画序列（cat_anim_smile_001.png）
│   └─ sounds/                      # 语音/音效（cat_sound_happy_speak_001.wav）
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

### 队员C接口一览（EchoTeamCInterface — 6个API）

| # | 接口 | 对接方 | 用途 |
|---|------|--------|------|
| 1 | `api_user_speak(text, state, cb)` | 队员A | 用户输入文本 → AI回复 + TTS |
| 2 | `api_play_system_voice(text)` | 队员A | 纯语音播放（绕过大模型） |
| 3 | `api_play_speech_hint(hint_text)` | 队员A | 播放主动语音提示 |
| 4 | `api_register_logic_callback(cb)` | 队员D | 注册对话结束回调 |
| 5 | `api_reset_ai_memory()` | 队员D | 清空对话记忆 |
| 6 | `api_get_last_chat()` | 队员A | 获取最近对话文本 |

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
- 控制台将每3秒输出模拟状态检测循环，展示队员B→D→C→A的完整数据流

### 4. 运行测试
```
python tests/test_pet_state.py
```

## API 接口（Stub）

| 接口 | 服务 | 用途 | 状态 |
|------|------|------|------|
| get_user_expression(image_path) | Qwen-VL | 图像 → 用户表情状态 | 🔲 Stub → "happy" |
| generate_pet_reply(text_prompt) | DeepSeek | 文本 → 桌宠对话 | 🔲 Stub → 上下文感知回复 |
| speak(text) | TTS | 文本 → 语音输出 | 🔲 Stub → 打印路径 |

> Stub 函数在 demo 阶段返回 mock 数据。所有 API 文件内含 `# TO_DO` 注释，对接真实 API 只需在对应文件中补充逻辑即可。

## 配置

项目根目录的 `.env` 文件（请勿提交到Git）：
```
QWEN_VL_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here
TTS_API_KEY=your_key_here

# 可选配置（有默认值）
QWEN_VL_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions
QWEN_VL_MODEL=qwen-vl-plus
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
- [ ] 真实API对接（Qwen-VL / DeepSeek / TTS）
- [ ] 多桌宠支持
- [ ] 动画系统（帧序列播放）
- [ ] UI文字气泡显示
- [ ] 语音交互
- [ ] 网络通信（多人互动）

## 许可证

MIT License
