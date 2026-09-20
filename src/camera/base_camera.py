from abc import ABC, abstractmethod
from typing import Tuple, Optional
import numpy as np

class BaseStereoCamera(ABC):
    """
    双目立体相机硬件抽象基类 (HAL - Hardware Abstraction Layer)
    
    统一实机相机驱动 (HikStereoCamera) 与离线/仿真相机 (MockStereoCamera) 的接口。
    上层算法与业务逻辑完全面向此基类编程，实现软硬件彻底解耦。
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self._is_opened = False

    @abstractmethod
    def open(self) -> bool:
        """打开并初始化双目相机硬件/数据源"""
        pass

    @abstractmethod
    def grab_stereo(self) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """
        采集一对同步的双目图像 (Mono8 灰度图)
        返回: (success, left_img, right_img)
        """
        pass

    @abstractmethod
    def close(self):
        """释放相机资源或关闭数据流"""
        pass

    def is_opened(self) -> bool:
        """检查相机是否处于打开状态"""
        return self._is_opened

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

