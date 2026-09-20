import os
import json
from typing import Optional
import numpy as np

class SurgicalTool:
    """
    手术器械数据实体类 (解析与管理器械 CAD 刚体几何与针尖参数)
    """

    def __init__(self, config_path: str):
        self.config_path = config_path
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"未找到手术器械定义文件: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.name = data.get("tool_name", "Unknown_Tool")
        self.description = data.get("description", "")
        self.marker_diameter_mm = data.get("marker_diameter_mm", 12.0)
        self.max_fre_threshold_mm = data.get("max_fre_threshold_mm", 2.0)

        # 加载标记球局部坐标
        markers = data.get("markers", [])
        pts = [m["position_local_mm"] for m in markers]
        self.model_points = np.array(pts, dtype=np.float64)

        # 加载针尖偏移向量
        self.tool_tip_offset = np.array(data.get("tool_tip_offset_mm", [0.0, 0.0, 0.0]), dtype=np.float64)

    def compute_tool_tip(self, R: np.ndarray, T: np.ndarray) -> np.ndarray:
        """
        根据当前器械在相机坐标系下的 6-DoF 位姿 [R|T]，解算器械末端 (刀尖/针尖) 的绝对 3D 坐标
        P_tip_cam = R * P_tip_local + T
        """
        return np.dot(R, self.tool_tip_offset) + T

    def transform_model_to_camera(self, R: np.ndarray, T: np.ndarray) -> np.ndarray:
        """计算各反光球在当前相机坐标系下的理论空间坐标"""
        return np.dot(self.model_points, R.T) + T

