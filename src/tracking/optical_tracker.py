import os
import json
from typing import Tuple, List, Optional, Dict, Any
from pathlib import Path
import cv2
import numpy as np

from .rigid_registration import match_rigid_body_correspondence
from .surgical_tool import SurgicalTool

class OpticalTracker:
    """
    近红外手术器械高精度光学追踪器 (NDI Polaris / SciKit-Surgery 医疗级技术路线)
    
    流水线:
    1. 亚像素红外反光球斑点提取 (Intensity-Weighted Subpixel Centroid, 精度达 0.02 像素)
    2. 畸变校正与极线归一化映射 (cv2.undistortPoints)
    3. 双目极线几何立体交会 (Stereo Epipolar Matching & Triangulation -> 3D Markers)
    4. 无序反光球点集与 CAD 刚体模型自动匹配与 SVD 位姿解算 (6-DoF [R|T])
    5. 手术器械末端 (刀尖/针尖 Tool-Tip) 毫米级绝对三维空间坐标推算
    """

    def __init__(
        self,
        calib_path: Optional[str] = None,
        tool: Optional[SurgicalTool] = None,
        tool_config_path: Optional[str] = None
    ):
        # 默认定位工程根目录下的标定文件
        if calib_path is None:
            project_root = Path(__file__).resolve().parents[2]
            calib_path = str(project_root / "configs" / "calibration" / "stereo_calib_params.json")

        if not os.path.exists(calib_path):
            raise FileNotFoundError(f"标定参数文件不存在: {calib_path}，请先执行立体标定！")

        with open(calib_path, "r", encoding="utf-8") as f:
            self.calib = json.load(f)

        self.K1 = np.array(self.calib["K_left"], dtype=np.float64)
        self.D1 = np.array(self.calib.get("D_left", self.calib.get("dist_left")), dtype=np.float64)
        self.K2 = np.array(self.calib["K_right"], dtype=np.float64)
        self.D2 = np.array(self.calib.get("D_right", self.calib.get("dist_right")), dtype=np.float64)
        self.R1 = np.array(self.calib["R_left"], dtype=np.float64)
        self.R2 = np.array(self.calib["R_right"], dtype=np.float64)
        self.P1 = np.array(self.calib["P_left"], dtype=np.float64)
        self.P2 = np.array(self.calib["P_right"], dtype=np.float64)

        # 加载手术器械模型
        if tool is not None:
            self.tool = tool
        elif tool_config_path is not None:
            self.tool = SurgicalTool(tool_config_path)
        else:
            project_root = Path(__file__).resolve().parents[2]
            default_tool = project_root / "configs" / "tools" / "probe_4marker.json"
            self.tool = SurgicalTool(str(default_tool))

    def extract_subpixel_markers(
        self,
        gray_img: np.ndarray,
        threshold_val: int = 150,
        min_area: float = 8.0,
        max_area: float = 2000.0
    ) -> List[Tuple[float, float]]:
        """
        亚像素灰度加权质心法提取红外高亮斑点
        """
        _, thresh = cv2.threshold(gray_img, threshold_val, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        centroids = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if min_area < area < max_area:
                x, y, w, h = cv2.boundingRect(cnt)
                aspect_ratio = float(w) / h if h > 0 else 0
                if 0.5 < aspect_ratio < 2.0:
                    roi = gray_img[y:y+h, x:x+w].astype(np.float64)
                    roi_thresh = np.maximum(roi - threshold_val, 0)
                    total_intensity = np.sum(roi_thresh)
                    if total_intensity > 0:
                        grid_y, grid_x = np.indices((h, w))
                        cx = x + np.sum(grid_x * roi_thresh) / total_intensity
                        cy = y + np.sum(grid_y * roi_thresh) / total_intensity
                        centroids.append((cx, cy))

        return centroids

    def triangulate_markers(
        self,
        pts_l_raw: List[Tuple[float, float]],
        pts_r_raw: List[Tuple[float, float]],
        epipolar_tol_px: float = 4.0
    ) -> Tuple[np.ndarray, List[Tuple[float, float]], List[Tuple[float, float]]]:
        """
        通过相机内参与校正矩阵将亚像素原始点映射至极线对齐空间，并进行立体匹配与三角交会
        """
        if not pts_l_raw or not pts_r_raw:
            return np.empty((0, 3)), [], []

        # 畸变校正并投影到标准校正坐标系 (undistortPoints with R & P)
        arr_l = np.array(pts_l_raw, dtype=np.float64).reshape(-1, 1, 2)
        arr_r = np.array(pts_r_raw, dtype=np.float64).reshape(-1, 1, 2)

        undist_l = cv2.undistortPoints(arr_l, self.K1, self.D1, R=self.R1, P=self.P1).reshape(-1, 2)
        undist_r = cv2.undistortPoints(arr_r, self.K2, self.D2, R=self.R2, P=self.P2).reshape(-1, 2)

        matched_3d = []
        matched_l_raw = []
        matched_r_raw = []

        # 基于水平极线约束匹配 (在校正系中对应点拥有极度接近的 Y 坐标，且视差 x_L - x_R > 0)
        for i, pl in enumerate(undist_l):
            best_j = None
            min_y_diff = float("inf")
            for j, pr in enumerate(undist_r):
                y_diff = abs(pl[1] - pr[1])
                disparity = pl[0] - pr[0]
                if y_diff < epipolar_tol_px and disparity > 0:
                    if y_diff < min_y_diff:
                        min_y_diff = y_diff
                        best_j = j

            if best_j is not None:
                pr = undist_r[best_j]
                # 双目空间三角交会
                pt_l_h = np.array([pl[0], pl[1]], dtype=np.float64).reshape(2, 1)
                pt_r_h = np.array([pr[0], pr[1]], dtype=np.float64).reshape(2, 1)

                pt_4d = cv2.triangulatePoints(self.P1, self.P2, pt_l_h, pt_r_h)
                pt_3d = (pt_4d[:3] / pt_4d[3]).flatten()

                matched_3d.append(pt_3d)
                matched_l_raw.append(pts_l_raw[i])
                matched_r_raw.append(pts_r_raw[best_j])

        return np.array(matched_3d, dtype=np.float64), matched_l_raw, matched_r_raw

    def track(self, left_gray: np.ndarray, right_gray: np.ndarray) -> Dict[str, Any]:
        """
        单帧双目近红外图像手术器械追踪解算
        """
        # 1. 提取反光球亚像素斑点
        pts_l = self.extract_subpixel_markers(left_gray)
        pts_r = self.extract_subpixel_markers(right_gray)

        result: Dict[str, Any] = {
            "success": False,
            "tool_name": self.tool.name,
            "tip_position": None,
            "R": None,
            "T": None,
            "fre": float("inf"),
            "markers_3d": np.empty((0, 3)),
            "markers_2d_left": pts_l,
            "markers_2d_right": pts_r
        }

        if len(pts_l) < len(self.tool.model_points) or len(pts_r) < len(self.tool.model_points):
            return result

        # 2. 立体交会获取空间 3D 点云
        markers_3d, _, _ = self.triangulate_markers(pts_l, pts_r)
        result["markers_3d"] = markers_3d

        if len(markers_3d) < len(self.tool.model_points):
            return result

        # 3. 刚体点集对应关系匹配与 SVD 位姿估计
        R, T, fre, perm = match_rigid_body_correspondence(
            self.tool.model_points,
            markers_3d,
            max_fre_threshold=self.tool.max_fre_threshold_mm
        )

        if R is not None:
            result["success"] = True
            result["R"] = R
            result["T"] = T
            result["fre"] = fre
            # 4. 推算器械末端针尖空间绝对三维坐标
            result["tip_position"] = self.tool.compute_tool_tip(R, T)

        return result

    def render_overlay(self, left_img: np.ndarray, track_result: Dict[str, Any]) -> np.ndarray:
        """
        在左相机图像上可视化绘制追踪结果 (光斑绿圈、刚体连线、针尖红十字与位姿数据 HUD)
        """
        if len(left_img.shape) == 2:
            vis = cv2.cvtColor(left_img, cv2.COLOR_GRAY2BGR)
        else:
            vis = left_img.copy()

        # 绘制检测到的所有反光球
        for pt in track_result.get("markers_2d_left", []):
            cv2.circle(vis, (int(round(pt[0])), int(round(pt[1]))), 6, (0, 255, 0), 2)

        if track_result["success"]:
            tip = track_result["tip_position"]
            fre = track_result["fre"]
            # 投影针尖位置回左相机画面
            tip_cam = tip.reshape(3, 1)
            # 使用校正投影矩阵或左相机内参投影
            tip_2d, _ = cv2.projectPoints(tip_cam, np.zeros((3, 1)), np.zeros((3, 1)), self.K1, self.D1)
            tx, ty = int(round(tip_2d[0, 0, 0])), int(round(tip_2d[0, 0, 1]))

            # 绘制针尖红色十字准星
            if 0 <= tx < vis.shape[1] and 0 <= ty < vis.shape[0]:
                cv2.drawMarker(vis, (tx, ty), (0, 0, 255), cv2.MARKER_CROSS, 20, 2)
                cv2.putText(vis, f"Tip ({tip[0]:.1f}, {tip[1]:.1f}, {tip[2]:.1f})mm",
                            (tx + 10, ty - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

            # 绘制 HUD 状态栏
            cv2.putText(vis, f"STATUS: TRACKING [{self.tool.name}]", (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(vis, f"FRE: {fre:.3f} mm", (20, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(vis, f"Tip 3D: X={tip[0]:.2f} Y={tip[1]:.2f} Z={tip[2]:.2f} mm", (20, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        else:
            cv2.putText(vis, "STATUS: SEARCHING TOOL...", (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        return vis
