"""
桌宠物动画显示 & 鼠标事件（拖拽/点击）
"""
import os
import tkinter as tk
from PIL import Image, ImageTk


class DesktopPet:
    """
    桌宠类 DesktopPet
    属性:
        image_path: 图片路径
        position(x,y): 桌宠位置
        current_state: 当前状态
    方法:
        draw()           # 绘制桌宠
        on_drag(event)   # 鼠标拖动
        on_click(event)  # 鼠标点击
    """

    # TO_DO: 定义桌宠类 DesktopPet
    #   属性: image_path, position(x,y), current_state
    #   方法:
    #     draw()  # 绘制桌宠
    #     on_drag(event)  # 鼠标拖动
    #     on_click(event) # 鼠标点击

    def __init__(self, image_path: str, position: tuple = (100, 100)):
        """
        初始化桌宠
        :param image_path: 桌宠图片路径
        :param position: 初始位置 (x, y)
        """
        # TO_DO: 初始化桌宠属性
        self.image_path = image_path
        self.position = list(position)  # [x, y]
        self.current_state = "smile"     # 当前表情状态
        self.pet_id = "cat"             # 桌宠ID

        # Tkinter相关
        self.root = None
        self.label = None
        self.tk_image = None
        self._drag_data = {"x": 0, "y": 0}

        # 回调函数（由外部绑定）
        self.on_drag_callback = None
        self.on_click_callback = None

        # 初始化UI
        self._init_ui()

    def _init_ui(self):
        """初始化Tkinter窗口"""
        # TO_DO: 创建无边框窗口，显示桌宠图片
        self.root = tk.Tk()
        self.root.overrideredirect(True)  # 无边框
        self.root.attributes("-topmost", True)  # 置顶
        self.root.wm_geometry(f"+{self.position[0]}+{self.position[1]}")

        # 加载图片
        self._load_image()

        # 创建标签显示图片
        self.label = tk.Label(self.root, image=self.tk_image, bd=0, bg="white")
        self.label.pack()

        # 设置窗口透明色
        self.root.wm_attributes("-transparentcolor", "white")

        # TO_DO: 绑定鼠标拖动事件和点击事件
        self.label.bind("<ButtonPress-1>", self._on_drag_start)
        self.label.bind("<B1-Motion>", self._on_drag_motion)
        self.label.bind("<ButtonRelease-1>", self._on_drag_end)
        self.label.bind("<Button-1>", self._on_click)

    def _load_image(self):
        """加载并缩放图片"""
        # TO_DO: 从 image_path 加载图片到 tk_image
        if os.path.exists(self.image_path):
            pil_image = Image.open(self.image_path)
            pil_image = pil_image.resize((150, 150), Image.Resampling.LANCZOS)
            self.tk_image = ImageTk.PhotoImage(pil_image)
        else:
            # 若图片不存在，创建一个占位图片
            print(f"[WARNING] 图片不存在: {self.image_path}")
            pil_image = Image.new("RGBA", (150, 150), (255, 0, 0, 128))
            self.tk_image = ImageTk.PhotoImage(pil_image)

    # TO_DO: draw() 方法 - 绘制桌宠
    def draw(self):
        """
        绘制桌宠（更新Tkinter显示）
        """
        # TO_DO: 实现桌宠绘制逻辑
        self.root.update()
        self.root.update_idletasks()

    # TO_DO: on_drag(event) 方法 - 鼠标拖动
    def _on_drag_start(self, event):
        """拖动开始：记录鼠标按下位置"""
        # TO_DO: 记录拖拽起始位置
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag_motion(self, event):
        """拖动中：根据鼠标移动更新窗口位置"""
        # TO_DO: 计算新位置并移动窗口
        x = self.root.winfo_x() + event.x - self._drag_data["x"]
        y = self.root.winfo_y() + event.y - self._drag_data["y"]
        self.root.geometry(f"+{x}+{y}")
        self.position = [x, y]

        # 调用拖动回调
        if self.on_drag_callback:
            self.on_drag_callback(event)

    def _on_drag_end(self, event):
        """拖动结束"""
        # TO_DO: 拖动结束后更新位置
        self.position = [self.root.winfo_x(), self.root.winfo_y()]
        if self.on_drag_callback:
            self.on_drag_callback(event)

    def on_drag(self, event):
        """
        鼠标拖动（外部调用接口）
        """
        # TO_DO: 处理鼠标拖动逻辑
        pass

    # TO_DO: on_click(event) 方法 - 鼠标点击
    def _on_click(self, event):
        """
        鼠标点击事件处理
        """
        # TO_DO: 处理鼠标点击逻辑
        print(f"[DesktopPet] 桌宠被点击 (position: {self.position}, state: {self.current_state})")
        if self.on_click_callback:
            self.on_click_callback(event)

    def on_click(self, event):
        """
        鼠标点击（外部调用接口）
        """
        # TO_DO: 处理鼠标点击逻辑
        pass

    def set_image(self, image_path: str):
        """
        动态更换桌宠图片
        :param image_path: 新图片路径
        """
        # TO_DO: 更换桌宠图片
        self.image_path = image_path
        self._load_image()
        if self.label:
            self.label.config(image=self.tk_image)

    def run(self):
        """启动Tkinter主循环"""
        self.root.mainloop()

    def close(self):
        """关闭桌宠窗口"""
        if self.root:
            self.root.quit()
            self.root.destroy()
