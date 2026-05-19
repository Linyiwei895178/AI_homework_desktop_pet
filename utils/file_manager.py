"""
资产和日志管理
"""
import os

# TO_DO: 提供接口读取 assets/images/animations/sounds
# 例： get_pet_image(pet_id, state), get_pet_animation(pet_id, action), get_pet_sound(pet_id, state, action)


class FileManager:
    """
    文件管理器

    提供资产文件的读取接口，管理 assets 目录下的图片、动画、声音资源

    TO_DO:
    - 提供接口读取 assets/images/animations/sounds
    - 例： get_pet_image(pet_id, state), get_pet_animation(pet_id, action), get_pet_sound(pet_id, state, action)
    - 缓存已加载的资源
    - 处理文件不存在的情况
    """

    def __init__(self, base_dir: str = None):
        """
        初始化文件管理器
        :param base_dir: 项目根目录，默认为当前文件所在项目的根目录
        """
        if base_dir is None:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        else:
            self.base_dir = base_dir

        self.assets_dir = os.path.join(self.base_dir, "assets")
        self._cache = {}

    # TO_DO: 提供接口读取 assets/images/animations/sounds
    # 例： get_pet_image(pet_id, state), get_pet_animation(pet_id, action), get_pet_sound(pet_id, state, action)

    def get_pet_image(self, pet_id: str, state: str, sequence: int = 1) -> str:
        """
        获取桌宠图片路径

        :param pet_id: 桌宠ID（如 "cat", "dog"）
        :param state: 状态（如 "smile", "happy", "sad"）
        :param sequence: 序列号，默认为1
        :return: 图片文件路径

        命名规则: {pet_id}_image_{state}_{sequence}.png
        """
        # TO_DO: 构建图片路径并返回
        filename = f"{pet_id}_image_{state}_{sequence:03d}.png"
        filepath = os.path.join(self.assets_dir, "images", filename)

        if os.path.exists(filepath):
            return filepath
        else:
            print(f"[FileManager] 图片不存在: {filepath}")
            return None

    def get_pet_animation(self, pet_id: str, action: str, sequence: int = 1) -> str:
        """
        获取桌宠动画序列图片路径

        :param pet_id: 桌宠ID（如 "cat", "dog"）
        :param action: 动作（如 "walk", "jump", "wave"）
        :param sequence: 序列号，默认为1
        :return: 动画图片文件路径

        命名规则: {pet_id}_anim_{action}_{sequence}.png
        """
        # TO_DO: 构建动画路径并返回
        filename = f"{pet_id}_anim_{action}_{sequence:03d}.png"
        filepath = os.path.join(self.assets_dir, "animations", filename)

        if os.path.exists(filepath):
            return filepath
        else:
            print(f"[FileManager] 动画不存在: {filepath}")
            return None

    def get_pet_sound(self, pet_id: str, state: str, action: str, sequence: int = 1) -> str:
        """
        获取桌宠音效文件路径

        :param pet_id: 桌宠ID（如 "cat", "dog"）
        :param state: 状态（如 "happy", "sad"）
        :param action: 动作（如 "speak", "move"）
        :param sequence: 序列号，默认为1
        :return: 音效文件路径

        命名规则: {pet_id}_sound_{state}_{action}_{sequence}.wav
        """
        # TO_DO: 构建音效路径并返回
        filename = f"{pet_id}_sound_{state}_{action}_{sequence:03d}.wav"
        filepath = os.path.join(self.assets_dir, "sounds", filename)

        if os.path.exists(filepath):
            return filepath
        else:
            print(f"[FileManager] 音效不存在: {filepath}")
            return None

    def list_images(self, pet_id: str = None) -> list:
        """
        列出所有可用的图片资源
        :param pet_id: 可选，筛选指定桌宠的图片
        :return: 图片路径列表
        """
        images_dir = os.path.join(self.assets_dir, "images")
        if not os.path.exists(images_dir):
            return []

        result = []
        for f in os.listdir(images_dir):
            if pet_id is None or f.startswith(pet_id):
                result.append(os.path.join(images_dir, f))
        return sorted(result)


# 全局文件管理器实例
file_manager = FileManager()
