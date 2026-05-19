"""
UI控件（按钮、状态面板等）
"""
import tkinter as tk


# TO_DO: 定义可扩展UI控件，如按钮、状态面板
# TO_DO: 提供接口供controller调用


class StatusPanel:
    """
    状态面板：显示桌宠当前心情、能量、亲密度
    """

    # TO_DO: 实现状态面板控件

    def __init__(self, parent=None):
        """
        初始化状态面板
        :param parent: 父级Tkinter容器
        """
        # TO_DO: 初始化状态面板UI
        self.parent = parent
        self.frame = None
        self.mood_label = None
        self.energy_label = None
        self.intimacy_label = None

        if parent:
            self._build_ui()

    def _build_ui(self):
        """构建UI控件"""
        # TO_DO: 创建标签显示心情、能量、亲密度
        self.frame = tk.Frame(self.parent, bg="lightgray", padx=10, pady=10)
        self.frame.pack(side=tk.TOP, fill=tk.X)

        tk.Label(self.frame, text="=== 桌宠状态 ===", bg="lightgray", font=("Arial", 10, "bold")).pack()

        self.mood_label = tk.Label(self.frame, text="心情: neutral", bg="lightgray")
        self.mood_label.pack(anchor=tk.W)

        self.energy_label = tk.Label(self.frame, text="能量: 100", bg="lightgray")
        self.energy_label.pack(anchor=tk.W)

        self.intimacy_label = tk.Label(self.frame, text="亲密度: 50", bg="lightgray")
        self.intimacy_label.pack(anchor=tk.W)

    def update_display(self, pet_state):
        """
        更新状态面板显示
        :param pet_state: PetState对象，包含mood/energy/intimacy属性
        """
        # TO_DO: 刷新UI显示最新状态数据
        if self.mood_label:
            self.mood_label.config(text=f"心情: {pet_state.mood}")
        if self.energy_label:
            self.energy_label.config(text=f"能量: {pet_state.energy}")
        if self.intimacy_label:
            self.intimacy_label.config(text=f"亲密度: {pet_state.intimacy}")


class ActionButtonPanel:
    """
    动作按钮面板：触发桌宠动作
    """

    # TO_DO: 实现按钮控件

    def __init__(self, parent=None, button_callbacks=None):
        """
        初始化按钮面板
        :param parent: 父级Tkinter容器
        :param button_callbacks: 按钮回调字典 {"按钮名": 回调函数}
        """
        # TO_DO: 初始化按钮面板UI
        self.parent = parent
        self.button_callbacks = button_callbacks or {}
        self.buttons = {}
        self.frame = None

        if parent:
            self._build_ui()

    def _build_ui(self):
        """构建按钮UI"""
        # TO_DO: 创建多个动作按钮
        self.frame = tk.Frame(self.parent, bg="lightblue", padx=5, pady=5)
        self.frame.pack(side=tk.BOTTOM, fill=tk.X)

        for btn_name, callback in self.button_callbacks.items():
            btn = tk.Button(
                self.frame,
                text=btn_name,
                command=callback,
                width=10
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.buttons[btn_name] = btn
