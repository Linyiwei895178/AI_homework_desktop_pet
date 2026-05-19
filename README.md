# AI_Desktop_Pet 🐱

**具身AI桌面宠物** - 一个可交互的虚拟桌面宠物Demo

## 项目简介

AI_Desktop_Pet 是一个基于 Python/Tkinter 构建的桌面虚拟宠物程序。你可以在桌面上拖拽它、点击它，它会根据当前状态做出不同反应。项目采用模块化设计，预留了 Qwen-VL（多模态）、DeepSeek（文本生成）、TTS（语音输出）等AI能力接口，方便后续扩展。

## 功能特性

- ✅ 桌面显示桌宠图片（支持PNG格式）
- ✅ 鼠标拖拽移动桌宠
- ✅ 点击桌宠触发动作响应
- ✅ 状态系统（心情/能量/亲密度）
- ✅ 行为决策规则引擎
- ✅ 模块化架构，方便扩展
- 🔲 Qwen-VL多模态表情识别（Stub）
- 🔲 DeepSeek对话生成（Stub）
- 🔲 TTS语音输出（Stub）

## 项目结构

```
AI_Desktop_Pet/
├─ app/
│   ├─ main.py                 # 程序入口
│   ├─ ui/
│   │   ├─ desktop_pet.py      # 桌宠显示 & 鼠标事件
│   │   └─ widgets.py          # UI控件
│   └─ controller/
│       ├─ event_handler.py    # 事件处理
│       └─ pet_controller.py   # 动作触发
├─ models/
│   ├─ vision/
│   │   └─ qwen_vl_api.py      # Qwen-VL API
│   ├─ nlp/
│   │   └─ deepseek_api.py     # DeepSeek API
│   ├─ tts/
│   │   └─ tts_manager.py      # TTS语音
│   └─ state/
│       ├─ pet_state.py        # 桌宠状态
│       └─ behavior_rules.py   # 行为规则
├─ assets/
│   ├─ images/                 # 静态图片
│   ├─ animations/             # 动画序列
│   └─ sounds/                 # 语音/音效
├─ utils/
│   ├─ file_manager.py         # 资产管理
│   ├─ logger.py               # 日志
│   └─ config.py               # 配置
├─ tests/                      # 单元测试
├─ .env                        # API Key配置
├─ .gitignore
├─ requirements.txt
└─ README.md
```

## 快速开始

### 1. 克隆仓库
```bash
git clone https://github.com/SWT-0407/AI_homework_desktop_pet.git
cd AI_homework_desktop_pet
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 准备资源
将桌宠图片放入 `assets/images/` 目录（默认使用 `cat_image_smile_001.png`）

### 4. 运行程序
```bash
python app/main.py
```

## 资产命名规则

| 类型 | 命名格式 | 示例 |
|------|----------|------|
| 图片 | `{pet_id}_image_{state}_{seq}.png` | `cat_image_smile_001.png` |
| 动画 | `{pet_id}_anim_{action}_{seq}.png` | `cat_anim_walk_001.png` |
| 声音 | `{pet_id}_sound_{state}_{action}_{seq}.wav` | `cat_sound_happy_speak_001.wav` |

## API接口

| 接口 | 服务 | 用途 | 状态 |
|------|------|------|------|
| `get_user_expression(image_path)` | Qwen-VL | 图像 → 用户表情状态 | Stub |
| `generate_pet_reply(text_prompt)` | DeepSeek | 文本 → 桌宠对话 | Stub |
| `speak(text)` | TTS | 文本 → 语音输出 | Stub |

> Stub 函数在 demo 阶段返回 mock 数据，对接真实 API 只需在对应文件中补充逻辑。

## 配置

复制 `.env` 文件并填入你的 API Key：

```
QWEN_VL_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here
TTS_API_KEY=your_key_here
```

## 开发计划

- [x] 项目结构搭建
- [x] 桌宠显示 & 鼠标交互
- [x] 状态管理系统
- [x] 行为决策引擎
- [ ] 真实API对接
- [ ] 多桌宠支持
- [ ] 动画系统
- [ ] 语音交互
- [ ] 网络通信（多人互动）

## 许可证

MIT License
