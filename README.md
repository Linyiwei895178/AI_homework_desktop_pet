# AI_Desktop_Pet 🐱

**具身AI桌面宠物** - 一个可交互的虚拟桌面宠物Demo

## 项目简介

AI_Desktop_Pet 是一个基于 Python/Tkinter 构建的桌面虚拟宠物程序。你可以在桌面上拖拽它、点击它、右键弹出退出菜单，它会根据当前状态做出不同反应。项目采用模块化设计，预留了 Qwen-VL（多模态）、DeepSeek（文本生成）、TTS（语音输出）等AI能力接口，方便后续扩展。

## 功能特性

### ✅ 已实现
- ✅ 桌面显示桌宠图片（支持PNG格式，150×150缩放显示）
- ✅ 鼠标拖拽移动桌宠（无边框置顶窗口，透明背景）
- ✅ 左键点击桌宠触发动作响应（打印状态/动作 + 调用 API stub）
- ✅ 右键点击桌宠弹出“退出”菜单
- ✅ 确认退出提示框（askokcancel），用户确认后结束程序
- ✅ 状态系统（心情/能量/亲密度，含数值衰减与增长机制）
- ✅ 行为决策规则引擎（基于当前状态自动选择动作）
- ✅ 模块化架构，方便扩展
- ✅ 单元测试覆盖（7个测试用例全部通过）

### 🔲 待开发（API Stub 就绪）
- 🔲 Qwen-VL多模态表情识别（Stub 返回 “happy”）
- 🔲 DeepSeek对话生成（Stub 返回 “Hello! I’m your pet.”）
- 🔲 TTS语音输出（Stub 保存 .wav 文件路径）

## 交互演示

| 操作 | 效果 |
|------|------|
| **左键点击** | 触发点击回调，打印桌宠位置与状态信息 |
| **左键拖拽** | 桌宠跟随鼠标移动 |
| **右键点击** | 弹出右键菜单，显示“退出”选项 |
| **退出确认** | 点击“退出” → 弹出“确定要退出桌宠吗？”对话框 → 确认后关闭程序 |

## 项目结构

`
AI_Desktop_Pet/
├─ app/
│   ├─ main.py                 # 程序入口
│   ├─ ui/
│   │   ├─ desktop_pet.py      # 桌宠显示 & 鼠标事件（拖拽/左键/右键退出）
│   │   └─ widgets.py          # UI控件
│   └─ controller/
│       ├─ event_handler.py    # 事件处理
│       └─ pet_controller.py   # 动作触发
├─ models/
│   ├─ vision/
│   │   └─ qwen_vl_api.py      # Qwen-VL API (Stub)
│   ├─ nlp/
│   │   └─ deepseek_api.py     # DeepSeek API (Stub)
│   ├─ tts/
│   │   └─ tts_manager.py      # TTS语音 (Stub)
│   └─ state/
│       ├─ pet_state.py        # 桌宠状态（mood/energy/intimacy）
│       └─ behavior_rules.py   # 行为决策规则引擎
├─ assets/
│   ├─ images/                 # 静态图片（cat_image_smile_001.png）
│   ├─ animations/             # 动画序列（cat_anim_smile_001.png）
│   └─ sounds/                 # 语音/音效（cat_sound_happy_speak_001.wav）
├─ utils/
│   ├─ file_manager.py         # 资产管理
│   ├─ logger.py               # 日志记录
│   └─ config.py               # .env 配置读取
├─ tests/                      # 单元测试
│   └─ test_pet_state.py       # 状态模块测试（7 cases ✅）
├─ .env                        # API Key 配置文件
├─ .gitignore
├─ requirements.txt
└─ README.md
`

## 资产清单

| 文件 | 类型 | 说明 |
|------|------|------|
| assets/images/cat_image_smile_001.png | 🖼️ 图片 | 桌宠默认显示图片（150×150） |
| assets/animations/cat_anim_smile_001.png | 🎞️ 动画 | 微笑动画序列帧 |
| assets/sounds/cat_sound_happy_speak_001.wav | 🔊 音效 | 开心语音音效 |

### 资产命名规则

| 类型 | 命名格式 | 示例 |
|------|----------|------|
| 图片 | {pet_id}_image_{state}_{seq}.png | cat_image_smile_001.png |
| 动画 | {pet_id}_anim_{action}_{seq}.png | cat_anim_walk_001.png |
| 声音 | {pet_id}_sound_{state}_{action}_{seq}.wav | cat_sound_happy_speak_001.wav |

## 快速开始

### 1. 克隆仓库
\\ash
git clone https://github.com/SWT-0407/AI_homework_desktop_pet.git
cd AI_homework_desktop_pet
\
### 2. 安装依赖
\\ash
pip install -r requirements.txt
\
### 3. 运行程序
\\ash
python app/main.py
\
桌宠窗口将出现在桌面左上角 (100, 100) 位置，你可以：
- **左键拖拽**移动它
- **左键点击**触发动作
- **右键点击** → 点击“退出” → 确认退出

### 4. 运行测试
\\ash
python tests/test_pet_state.py
\
## API 接口（Stub）

| 接口 | 服务 | 用途 | 状态 |
|------|------|------|------|
| get_user_expression(image_path) | Qwen-VL | 图像 → 用户表情状态 | 🔲 Stub → “happy” |
| generate_pet_reply(text_prompt) | DeepSeek | 文本 → 桌宠对话 | 🔲 Stub → “Hello! I’m your pet.” |
| speak(text) | TTS | 文本 → 语音输出 | 🔲 Stub → path/to/output.wav |

> Stub 函数在 demo 阶段返回 mock 数据。所有 API 文件内含 # TO_DO 注释，对接真实 API 只需在对应文件中补充逻辑即可。

## 配置

复制 .env 文件并填入你的 API Key（当前 demo 阶段可使用默认值）：

\QWEN_VL_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here
TTS_API_KEY=your_key_here
\
## 开发计划

- [x] 项目结构搭建
- [x] 桌宠显示 & 鼠标交互（拖拽/左键点击）
- [x] 右键退出功能（弹出菜单 + 确认对话框）
- [x] 状态管理系统（mood/energy/intimacy）
- [x] 行为决策引擎
- [x] 单元测试覆盖
- [x] 图片/动画/音效资产
- [x] .gitignore 允许音频文件上传
- [ ] 真实API对接（Qwen-VL / DeepSeek / TTS）
- [ ] 多桌宠支持
- [ ] 动画系统（帧序列播放）
- [ ] 语音交互
- [ ] 网络通信（多人互动）

## 许可证

MIT License
