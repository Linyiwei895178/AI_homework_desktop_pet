"""
资产和日志管理，带缓存支持。

提供接口读取 assets/images/animations/sounds，
以及 get_pet_image(), get_pet_animation(), get_pet_sound() 等。
"""
import os
from typing import Dict, List, Optional, Tuple


class FileManager:
    """文件管理器：提供资产文件的读取接口，管理 assets 目录下的图片、动画、声音资源。"""

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        else:
            self.base_dir = base_dir
        self.assets_dir = os.path.join(self.base_dir, "assets")
        self._cache: Dict[str, str] = {}

    def get_pet_image(self, pet_id: str, state: str, sequence: int = 1) -> Optional[str]:
        """获取桌宠图片路径。命名规则: {pet_id}_image_{state}_{sequence:03d}.png"""
        filename = f"{pet_id}_image_{state}_{sequence:03d}.png"
        return self._get_cached(os.path.join(self.assets_dir, "images", filename))

    def get_pet_animation(self, pet_id: str, action: str, sequence: int = 1) -> Optional[str]:
        """获取桌宠动画序列图片路径。命名规则: {pet_id}_anim_{action}_{sequence:03d}.png"""
        filename = f"{pet_id}_anim_{action}_{sequence:03d}.png"
        return self._get_cached(os.path.join(self.assets_dir, "animations", filename))

    def get_pet_sound(self, pet_id: str, state: str, action: str, sequence: int = 1) -> Optional[str]:
        """获取桌宠音效文件路径。命名规则: {pet_id}_sound_{state}_{action}_{sequence:03d}.wav"""
        filename = f"{pet_id}_sound_{state}_{action}_{sequence:03d}.wav"
        return self._get_cached(os.path.join(self.assets_dir, "sounds", filename))

    def list_images(self, pet_id: Optional[str] = None) -> List[str]:
        """列出所有可用的图片资源。"""
        images_dir = os.path.join(self.assets_dir, "images")
        if not os.path.exists(images_dir):
            return []
        result = []
        for f in sorted(os.listdir(images_dir)):
            if pet_id is None or f.startswith(pet_id):
                result.append(os.path.join(images_dir, f))
        return result

    def list_animations(self, pet_id: Optional[str] = None) -> List[str]:
        """列出所有可用的动画资源。"""
        anim_dir = os.path.join(self.assets_dir, "animations")
        if not os.path.exists(anim_dir):
            return []
        return [os.path.join(anim_dir, f) for f in sorted(os.listdir(anim_dir))
                if pet_id is None or f.startswith(pet_id)]

    def list_sounds(self, pet_id: Optional[str] = None) -> List[str]:
        """列出所有可用的音效资源。"""
        sound_dir = os.path.join(self.assets_dir, "sounds")
        if not os.path.exists(sound_dir):
            return []
        return [os.path.join(sound_dir, f) for f in sorted(os.listdir(sound_dir))
                if pet_id is None or f.startswith(pet_id)]

    def get_state_image(self, pet_id: str, mood: str) -> Optional[str]:
        """根据心情获取对应的表情图片。简写 get_pet_image(pet_id, mood)."""
        return self.get_pet_image(pet_id, mood)

    def get_action_animation_sequence(self, pet_id: str, action: str) -> List[str]:
        """获取某个动作的所有动画帧路径（按 sequence 编号排序）。"""
        frames = []
        seq = 1
        while True:
            path = self.get_pet_animation(pet_id, action, seq)
            if path is None:
                break
            frames.append(path)
            seq += 1
        return frames

    def clear_cache(self) -> None:
        self._cache.clear()

    def _get_cached(self, filepath: str) -> Optional[str]:
        if filepath in self._cache:
            cached = self._cache[filepath]
            return cached if os.path.exists(cached) else None
        if os.path.exists(filepath):
            self._cache[filepath] = filepath
            return filepath
        return None


# 全局文件管理器实例
file_manager = FileManager()
