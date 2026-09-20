import os
import glob
import time
from typing import Tuple, Optional, List
import cv2
import numpy as np

from .base_camera import BaseStereoCamera

class MockStereoCamera(BaseStereoCamera):
    """
    离线仿真/回放双目相机 (供宿舍开发、算法单元测试和离线演示使用)
    
    支持从目录循环读取 Blender 渲染图、已采集图像对，或者单一图像对。
    """

    def __init__(
        self,
        image_dir: Optional[str] = None,
        left_img_path: Optional[str] = None,
        right_img_path: Optional[str] = None,
        fps: float = 30.0,
        loop: bool = True
    ):
        super().__init__()
        self.image_dir = image_dir
        self.left_img_path = left_img_path
        self.right_img_path = right_img_path
        self.fps = fps
        self.loop = loop
        self.pairs: List[Tuple[str, str]] = []
        self.current_idx = 0

    def open(self) -> bool:
        """加载图像对列表"""
        self.pairs = []
        if self.left_img_path and self.right_img_path:
            if os.path.exists(self.left_img_path) and os.path.exists(self.right_img_path):
                self.pairs.append((self.left_img_path, self.right_img_path))
        elif self.image_dir and os.path.exists(self.image_dir):
            # 自动寻找匹配的 left_*.png 与 right_*.png 或 *_L.png 与 *_R.png
            left_files = sorted(glob.glob(os.path.join(self.image_dir, "*left*.png")) +
                                sorted(glob.glob(os.path.join(self.image_dir, "*_L.png"))))
            for l_path in left_files:
                basename = os.path.basename(l_path)
                r_name = basename.replace("left", "right").replace("_L.", "_R.")
                r_path = os.path.join(self.image_dir, r_name)
                if os.path.exists(r_path):
                    self.pairs.append((l_path, r_path))

        if not self.pairs:
            print(f"[MockStereoCamera Warning] 未找到任何有效的双目图像对！")
            self._is_opened = False
            return False

        print(f"[MockStereoCamera] 成功加载 {len(self.pairs)} 组双目仿真/回放图对。")
        self.current_idx = 0
        self._is_opened = True
        return True

    def grab_stereo(self) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """按帧率回放抓取下一对双目图像"""
        if not self._is_opened or not self.pairs:
            return False, None, None

        if self.current_idx >= len(self.pairs):
            if self.loop:
                self.current_idx = 0
            else:
                return False, None, None

        l_path, r_path = self.pairs[self.current_idx]
        self.current_idx += 1

        img_l = cv2.imread(l_path, cv2.IMREAD_GRAYSCALE)
        img_r = cv2.imread(r_path, cv2.IMREAD_GRAYSCALE)

        if img_l is None or img_r is None:
            return False, None, None

        # 模拟工业相机帧率延时
        if self.fps > 0:
            time.sleep(1.0 / self.fps)

        return True, img_l, img_r

    def close(self):
        """重置状态"""
        self._is_opened = False
        self.current_idx = 0

