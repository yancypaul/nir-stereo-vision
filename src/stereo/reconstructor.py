"""
src/stereo/reconstructor.py
===========================
工业级通用双目立体视觉与三维重建引擎 (Universal Stereo Vision Reconstructor)

核心特性:
1. 配置驱动 (Config-Driven): 支持从 YAML / JSON 或 Python 字典初始化全套参数。
2. 自动防反检测 (Auto LR Check): 基于 SIFT/ORB 特征位移自动判定左右目是否颠倒，若颠倒自动在内存中纠正。
3. 三合一标定适配器:
   - "ideal": 适用于理想仿真无畸变镜头 (Blender 渲染对);
   - "file": 载入外部已保存的双目标定文件 (JSON / NPZ);
   - "auto_board": 自动读取标定板图片文件夹，现场完成立体几何解算与 Bouguet 校正。
4. 高性能立体匹配: 支持 Hirschmüller 全向 8 方向 SGBM-HH 与 WLS 左右一致性保边滤波。
5. 高度量 3D 点云后处理: 支持有效深度截断、Open3D 统计滤波去噪 (SOR)、法向量估计与标准 PLY 导出。
6. 自动化诊断多合一面板: 自动生成包含极线对齐、视差热力图、空间俯视图的多合一预览图。
"""

import os
import glob
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import cv2
import numpy as np
import open3d as o3d
import matplotlib.pyplot as plt


class StereoReconstructor:
    """通用双目立体匹配与三维点云重建器"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化重建器
        :param config: 解析后的配置字典
        """
        self.config = config
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.is_calibrated = False
        self.map_lx = None
        self.map_ly = None
        self.map_rx = None
        self.map_ry = None
        self.Q = None
        self.focal_length_px = None
        self.baseline_m = None

        self._init_calibration()
        self._init_matcher()

    @staticmethod
    def find_latest_captured_pair(search_dir: Path) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[int]]:
        """
        在 captured_images 目录中自动寻找最新会话文件夹及其最新编号的图像对 (Left_x, Right_x)
        :param search_dir: Path 对象，例如 PROJECT_ROOT / "data" / "captured_images"
        :return: (left_image_path, right_image_path, session_name, shot_index)
        """
        if not search_dir.exists():
            return None, None, None, None

        # 查找所有 session_* 文件夹并按名称 (内含 YYYYMMDD_HHMMSS 时间戳) 排序
        sessions = sorted(
            [d for d in search_dir.iterdir() if d.is_dir() and d.name.startswith("session_")],
            key=lambda d: d.name
        )
        if not sessions:
            return None, None, None, None

        latest_session = sessions[-1]
        left_files = list(latest_session.glob("Left_*.*"))
        if not left_files:
            return None, None, None, None

        def extract_idx(f: Path) -> int:
            parts = f.stem.split("_")
            return int(parts[-1]) if len(parts) >= 2 and parts[-1].isdigit() else 0

        left_files.sort(key=extract_idx)
        latest_left = left_files[-1]
        idx = extract_idx(latest_left)
        latest_right = latest_session / f"Right_{idx}{latest_left.suffix}"

        if not latest_right.exists():
            r_matches = list(latest_session.glob(f"Right_{idx}.*"))
            if r_matches:
                latest_right = r_matches[0]
            else:
                return None, None, None, None

        return str(latest_left), str(latest_right), latest_session.name, idx

    def _resolve_path(self, p: Optional[str]) -> Optional[str]:
        if not p:
            return p
        path = Path(p)
        if not path.is_absolute():
            path = self.project_root / path
        return str(path)

    @classmethod
    def from_yaml(cls, yaml_path: str):
        """从 YAML 配置文件创建重建器"""
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cls(cfg)

    @classmethod
    def from_json(cls, json_path: str):
        """从 JSON 配置文件创建重建器"""
        with open(json_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cls(cfg)

    # =========================================================================
    # 1. 标定与极线校正准备
    # =========================================================================
    def _init_calibration(self):
        calib_cfg = self.config.get("calibration", {})
        mode = calib_cfg.get("mode", "ideal").lower()

        if mode == "ideal":
            self.focal_length_px = float(calib_cfg.get("focal_length_px", 1000.0))
            self.baseline_m = float(calib_cfg.get("baseline_m", 0.065))
            cx = float(calib_cfg.get("principal_point_x", 640.0))
            cy = float(calib_cfg.get("principal_point_y", 512.0))
            tx_m = self.baseline_m  # meters

            # 若有收敛平面 (如 Blender 双目收敛设置), 视差存在平移偏移 d_offset = (f * B) / Z_conv
            # 对应的 Q[3, 3] = d_offset / B = f / Z_conv
            conv_dist_m = calib_cfg.get("convergence_distance_m", None)
            q33 = 0.0
            if conv_dist_m is not None and float(conv_dist_m) > 0:
                conv_dist_m = float(conv_dist_m)
                d_offset = (self.focal_length_px * self.baseline_m) / conv_dist_m
                q33 = self.focal_length_px / conv_dist_m
                print(f"[Calibration] 已启用双目会聚平面校正: Z_conv={conv_dist_m:.2f}m, 视差偏移={d_offset:.2f}px")

            # 构建理想共面行对齐 Q 矩阵 (输出单位为米)
            self.Q = np.array([
                [1.0, 0.0, 0.0, -cx],
                [0.0, 1.0, 0.0, -cy],
                [0.0, 0.0, 0.0, self.focal_length_px],
                [0.0, 0.0, 1.0 / tx_m, q33]
            ], dtype=np.float64)
            self.is_calibrated = True
            print(f"[Calibration] 已初始化理想相机几何 (f={self.focal_length_px}px, B={self.baseline_m*1000:.1f}mm)")

        elif mode == "file":
            param_file = self._resolve_path(calib_cfg.get("param_file", ""))
            if not os.path.exists(param_file):
                raise FileNotFoundError(f"未找到标定配置文件: {param_file}")
            self._load_calib_from_file(param_file)

        elif mode == "auto_board":
            self._run_auto_board_calibration(calib_cfg)

        else:
            raise ValueError(f"不支持的标定模式: {mode} (仅支持 ideal, file, auto_board)")

    def _load_calib_from_file(self, file_path: str):
        """从 JSON / NPZ 加载标定参数并生成 Bouguet 极线映射"""
        if file_path.endswith(".json"):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            K1 = np.array(data["K1"], dtype=np.float64)
            D1 = np.array(data["D1"], dtype=np.float64)
            K2 = np.array(data["K2"], dtype=np.float64)
            D2 = np.array(data["D2"], dtype=np.float64)
            R = np.array(data["R"], dtype=np.float64)
            T = np.array(data["T"], dtype=np.float64)
            img_size = tuple(data.get("image_size", [1280, 1024]))
        elif file_path.endswith(".npz"):
            data = np.load(file_path)
            K1, D1 = data["K1"], data["D1"]
            K2, D2 = data["K2"], data["D2"]
            R, T = data["R"], data["T"]
            img_size = tuple(data["image_size"])
        else:
            raise ValueError("标定文件必须是 .json 或 .npz 格式")

        w, h = img_size
        R1, R2, P1, P2, self.Q, _, _ = cv2.stereoRectify(
            K1, D1, K2, D2, (w, h), R, T,
            flags=cv2.CALIB_ZERO_DISPARITY, alpha=0
        )
        self.map_lx, self.map_ly = cv2.initUndistortRectifyMap(K1, D1, R1, P1, (w, h), cv2.CV_32FC1)
        self.map_rx, self.map_ry = cv2.initUndistortRectifyMap(K2, D2, R2, P2, (w, h), cv2.CV_32FC1)
        self.baseline_m = float(np.linalg.norm(T)) / 1000.0
        self.focal_length_px = float(P1[0, 0])
        self.is_calibrated = True
        print(f"[Calibration] 从文件成功加载参数: Baseline={self.baseline_m*1000:.2f}mm, f={self.focal_length_px:.1f}px")

    def _run_auto_board_calibration(self, calib_cfg: Dict[str, Any]):
        """根据给定的标定板图片文件夹自动计算标定参数"""
        board_l_dir = self._resolve_path(calib_cfg.get("board_left_dir", ""))
        board_r_dir = self._resolve_path(calib_cfg.get("board_right_dir", ""))
        save_json = self._resolve_path(calib_cfg.get("save_param_file"))
        pattern_size = tuple(calib_cfg.get("pattern_size", [11, 8]))
        square_size_mm = float(calib_cfg.get("square_size_mm", 20.0))

        left_imgs = sorted(glob.glob(os.path.join(board_l_dir, "*.png")) + glob.glob(os.path.join(board_l_dir, "*.jpg")))
        right_imgs = sorted(glob.glob(os.path.join(board_r_dir, "*.png")) + glob.glob(os.path.join(board_r_dir, "*.jpg")))

        if len(left_imgs) == 0 or len(left_imgs) != len(right_imgs):
            raise ValueError(f"标定板图片对数量不匹配或为空: Left={len(left_imgs)}, Right={len(right_imgs)}")

        print(f"[Calibration] 开始自动标定: 正在分析 {len(left_imgs)} 对标定板图像 (角点={pattern_size}, 格宽={square_size_mm}mm)...")

        objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2) * square_size_mm

        objpoints, imgpoints_l, imgpoints_r = [], [], []
        subpix_crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)

        for lf, rf in zip(left_imgs, right_imgs):
            img_l = cv2.imread(lf, cv2.IMREAD_GRAYSCALE)
            img_r = cv2.imread(rf, cv2.IMREAD_GRAYSCALE)
            flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
            ret_l, c_l = cv2.findChessboardCorners(img_l, pattern_size, flags)
            ret_r, c_r = cv2.findChessboardCorners(img_r, pattern_size, flags)
            if ret_l and ret_r:
                c_l = cv2.cornerSubPix(img_l, c_l, (11, 11), (-1, -1), subpix_crit)
                c_r = cv2.cornerSubPix(img_r, c_r, (11, 11), (-1, -1), subpix_crit)
                objpoints.append(objp)
                imgpoints_l.append(c_l)
                imgpoints_r.append(c_r)

        print(f"[Calibration] 成功提取有效角点对: {len(objpoints)} / {len(left_imgs)}")
        h, w = img_l.shape[:2]

        # 单目标定 + 双目联合立体标定
        _, K1, D1, _, _ = cv2.calibrateCamera(objpoints, imgpoints_l, (w, h), None, None)
        _, K2, D2, _, _ = cv2.calibrateCamera(objpoints, imgpoints_r, (w, h), None, None)
        stereo_crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-6)
        rms, K1, D1, K2, D2, R, T, _, _ = cv2.stereoCalibrate(
            objpoints, imgpoints_l, imgpoints_r,
            K1, D1, K2, D2, (w, h),
            criteria=stereo_crit, flags=cv2.CALIB_FIX_INTRINSIC
        )

        R1, R2, P1, P2, self.Q, _, _ = cv2.stereoRectify(
            K1, D1, K2, D2, (w, h), R, T,
            flags=cv2.CALIB_ZERO_DISPARITY, alpha=0
        )
        self.map_lx, self.map_ly = cv2.initUndistortRectifyMap(K1, D1, R1, P1, (w, h), cv2.CV_32FC1)
        self.map_rx, self.map_ry = cv2.initUndistortRectifyMap(K2, D2, R2, P2, (w, h), cv2.CV_32FC1)
        self.baseline_m = float(np.linalg.norm(T)) / 1000.0
        self.focal_length_px = float(P1[0, 0])
        self.is_calibrated = True

        print(f"[Calibration] 标定完成! RMS={rms:.4f}px, Baseline={self.baseline_m*1000:.2f}mm, f={self.focal_length_px:.1f}px")

        # 保存结果缓存
        save_json = calib_cfg.get("save_param_file")
        if save_json:
            os.makedirs(os.path.dirname(os.path.abspath(save_json)), exist_ok=True)
            res_dict = {
                "rms_stereo": rms,
                "image_size": [w, h],
                "baseline_mm": self.baseline_m * 1000.0,
                "K1": K1.tolist(), "D1": D1.tolist(),
                "K2": K2.tolist(), "D2": D2.tolist(),
                "R": R.tolist(), "T": T.tolist()
            }
            with open(save_json, "w", encoding="utf-8") as f:
                json.dump(res_dict, f, indent=4)
            print(f"[Calibration] 标定参数已存入: {save_json}")

    # =========================================================================
    # 2. 立体匹配器初始化 (SGBM-HH + WLS 或 GREAT-Stereo 深度神经网络)
    # =========================================================================
    def _init_matcher(self):
        m_cfg = self.config.get("matcher", {})
        self.matcher_type = m_cfg.get("type", "sgbm").lower()
        self.min_disp = int(m_cfg.get("min_disparity", 0))
        self.num_disp = int(m_cfg.get("num_disparities", 192))

        if self.matcher_type == "great":
            from src.stereo.great_adapter import GreatStereoMatcher
            ckpt = self._resolve_path(m_cfg.get("checkpoint_path", "../GREAT-Stereo/checkpoints/great-igev-middlebury-submit.pth"))
            repo = self._resolve_path(m_cfg.get("great_repo_path", "../GREAT-Stereo"))
            device = m_cfg.get("device", "cuda")
            iters = int(m_cfg.get("iters", 22))
            downsample = bool(m_cfg.get("auto_downsample_4gb", True))
            mixed_prec = bool(m_cfg.get("mixed_precision", True))

            self.great_matcher = GreatStereoMatcher(
                checkpoint_path=ckpt,
                great_repo_path=repo,
                device=device,
                iters=iters,
                auto_downsample_4gb=downsample,
                mixed_precision=mixed_prec
            )
            print(f"[Matcher] 已切换至 ICCV 2025 SOTA 深度立体匹配: GREAT-Stereo")
            return

        # 默认使用 SGBM-HH + WLS 算法
        self.block_size = int(m_cfg.get("block_size", 5))
        mode_str = m_cfg.get("mode", "HH").upper()
        sgbm_mode = cv2.STEREO_SGBM_MODE_HH if mode_str == "HH" else cv2.STEREO_SGBM_MODE_SGBM_3WAY

        self.left_matcher = cv2.StereoSGBM_create(
            minDisparity=self.min_disp,
            numDisparities=self.num_disp,
            blockSize=self.block_size,
            P1=8 * 1 * self.block_size ** 2,
            P2=32 * 1 * self.block_size ** 2,
            disp12MaxDiff=int(m_cfg.get("disp12_max_diff", 1)),
            uniquenessRatio=int(m_cfg.get("uniqueness_ratio", 10)),
            speckleWindowSize=int(m_cfg.get("speckle_window_size", 100)),
            speckleRange=int(m_cfg.get("speckle_range", 2)),
            mode=sgbm_mode
        )

        self.use_wls = bool(m_cfg.get("wls_filter", True))
        if self.use_wls:
            self.right_matcher = cv2.ximgproc.createRightMatcher(self.left_matcher)
            self.wls_filter = cv2.ximgproc.createDisparityWLSFilter(self.left_matcher)
            self.wls_filter.setLambda(float(m_cfg.get("wls_lambda", 8000.0)))
            self.wls_filter.setSigmaColor(float(m_cfg.get("wls_sigma", 1.5)))

    # =========================================================================
    # 3. 核心流水线算法
    # =========================================================================
    def check_and_correct_lr(self, img_l: np.ndarray, img_r: np.ndarray) -> Tuple[np.ndarray, np.ndarray, bool]:
        """
        利用特征匹配分析水平位移:
        x_left - x_right = f * B / Z > 0 (严格正值定理)
        如果位移中位数为负，则绝对判定左右目命名颠倒，自动在内存中对调！
        """
        gray_l = cv2.cvtColor(img_l, cv2.COLOR_BGR2GRAY) if len(img_l.shape) == 3 else img_l
        gray_r = cv2.cvtColor(img_r, cv2.COLOR_BGR2GRAY) if len(img_r.shape) == 3 else img_r

        sift = cv2.SIFT_create(nfeatures=500)
        kp1, des1 = sift.detectAndCompute(gray_l, None)
        kp2, des2 = sift.detectAndCompute(gray_r, None)

        if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
            print("[Auto-LR] 特征较少，跳过自动左右目判定")
            return img_l, img_r, False

        bf = cv2.BFMatcher(cv2.NORM_L2)
        matches = bf.knnMatch(des1, des2, k=2)
        shifts_x = []
        for m, n in matches:
            if m.distance < 0.75 * n.distance:
                pt_l = kp1[m.queryIdx].pt
                pt_r = kp2[m.trainIdx].pt
                shifts_x.append(pt_l[0] - pt_r[0])

        if len(shifts_x) >= 8:
            median_shift = float(np.median(shifts_x))
            if median_shift < -15.0:
                print(f"\n[Auto-LR WARNING] 检测到左右目图像命名颠倒! (水平特征位移={median_shift:.2f}px < -15.0)")
                print(f"    --> 算法已自动在内存中将两张图片对调修正为物理左右目！\n")
                return img_r, img_l, True
            else:
                print(f"[Auto-LR OK] 左右目方向正确 (特征位移={median_shift:.2f}px)")
        return img_l, img_r, False

    def rectify(self, img_l: np.ndarray, img_r: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """极线校正"""
        if self.map_lx is not None and self.map_rx is not None:
            rect_l = cv2.remap(img_l, self.map_lx, self.map_ly, cv2.INTER_LINEAR)
            rect_r = cv2.remap(img_r, self.map_rx, self.map_ry, cv2.INTER_LINEAR)
            return rect_l, rect_r
        return img_l, img_r

    def compute_disparity(self, rect_l: np.ndarray, rect_r: np.ndarray) -> np.ndarray:
        """稠密视差计算 (支持 SGBM-HH + WLS 滤波 或 GREAT-Stereo 深度神经网络)"""
        if getattr(self, "matcher_type", "sgbm") == "great":
            return self.great_matcher.compute_disparity(rect_l, rect_r)

        gray_l = cv2.cvtColor(rect_l, cv2.COLOR_BGR2GRAY) if len(rect_l.shape) == 3 else rect_l
        gray_r = cv2.cvtColor(rect_r, cv2.COLOR_BGR2GRAY) if len(rect_r.shape) == 3 else rect_r

        if self.use_wls:
            disp_l = self.left_matcher.compute(gray_l, gray_r)
            disp_r = self.right_matcher.compute(gray_r, gray_l)
            filtered = self.wls_filter.filter(disp_l, gray_l, disparity_map_right=disp_r)
            disp = filtered.astype(np.float32) / 16.0
        else:
            disp_l = self.left_matcher.compute(gray_l, gray_r)
            disp = disp_l.astype(np.float32) / 16.0

        return disp

    def reconstruct_pointcloud(
        self,
        disparity: np.ndarray,
        color_image: np.ndarray,
        min_depth_m: float = 0.5,
        max_depth_m: float = 6.0,
        remove_outliers: bool = True,
        nb_neighbors: int = 30,
        std_ratio: float = 1.2,
        estimate_normals: bool = True
    ) -> o3d.geometry.PointCloud:
        """生成物理米制 3D 点云并进行去噪与法向量估计"""
        points_3d = cv2.reprojectImageTo3D(disparity, self.Q)

        # 动态自适应毫米 (mm) 与米 (m) 单位统一转为米
        valid_disp = (disparity > self.min_disp) & np.isfinite(points_3d[:, :, 2])
        if np.any(valid_disp):
            median_z = float(np.median(np.abs(points_3d[valid_disp, 2])))
            if median_z > 50.0:  # 单位为 mm
                points_3d_m = points_3d / 1000.0
            else:
                points_3d_m = points_3d
        else:
            points_3d_m = points_3d

        depth_m = points_3d_m[:, :, 2]
        valid_mask = valid_disp & (depth_m > min_depth_m) & (depth_m < max_depth_m) & np.isfinite(points_3d_m).all(axis=2)

        pts = points_3d_m[valid_mask]
        if len(color_image.shape) == 3:
            cols = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)[valid_mask] / 255.0
        else:
            cols = np.repeat(color_image[valid_mask, None], 3, axis=1) / 255.0

        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(pts)
        pcd.colors = o3d.utility.Vector3dVector(cols)

        if remove_outliers and len(pts) > 100:
            pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=nb_neighbors, std_ratio=std_ratio)

        if estimate_normals and len(pcd.points) > 100:
            pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.08, max_nn=30))
            pcd.orient_normals_towards_camera_location(camera_location=np.array([0.0, 0.0, 0.0]))

        return pcd, depth_m

    # =========================================================================
    # 4. 执行全流程
    # =========================================================================
    def run(self):
        """一键执行完整流程"""
        in_cfg = self.config.get("input", {})
        left_path = self._resolve_path(in_cfg.get("left_image"))
        right_path = self._resolve_path(in_cfg.get("right_image"))

        if not os.path.exists(left_path) or not os.path.exists(right_path):
            raise FileNotFoundError(f"未找到输入图像: Left='{left_path}', Right='{right_path}'")

        print("=" * 70)
        print("[Pipeline] 启动工业级通用立体视觉与 3D 点云重建流水线")
        print("=" * 70)
        print(f"  输入左图: {left_path}")
        print(f"  输入右图: {right_path}")

        raw_l = cv2.imread(left_path)
        raw_r = cv2.imread(right_path)

        # 1. 自动左右目反转检测
        if in_cfg.get("auto_detect_lr_swap", True):
            raw_l, raw_r, swapped = self.check_and_correct_lr(raw_l, raw_r)

        # 2. 极线校正
        rect_l, rect_r = self.rectify(raw_l, raw_r)

        # 3. 稠密视差计算
        matcher_desc = "ICCV 2025 SOTA GREAT-Stereo 深度神经网络" if getattr(self, "matcher_type", "sgbm") == "great" else "SGBM-HH + WLS 滤波"
        print(f"[Matcher] 正在计算稠密视差图 ({matcher_desc})...")
        disparity = self.compute_disparity(rect_l, rect_r)
        min_disp_thresh = getattr(self, "min_disp", 0)
        valid_cov = np.sum(disparity > min_disp_thresh) / (disparity.shape[0] * disparity.shape[1]) * 100.0
        print(f"  视差有效覆盖率: {valid_cov:.2f}%")

        # 4. 三维点云反投影
        pt_cfg = self.config.get("pointcloud", {})
        min_depth_val = float(pt_cfg.get("min_depth_m", 0.5))
        max_depth_val = float(pt_cfg.get("max_depth_m", 5.0))
        print("[PointCloud] 正在反投影三维点云并执行离群点滤除...")
        pcd, depth_m = self.reconstruct_pointcloud(
            disparity=disparity,
            color_image=rect_l,
            min_depth_m=min_depth_val,
            max_depth_m=max_depth_val,
            remove_outliers=bool(pt_cfg.get("remove_outliers", True)),
            nb_neighbors=int(pt_cfg.get("outlier_nb_neighbors", 30)),
            std_ratio=float(pt_cfg.get("outlier_std_ratio", 1.2)),
            estimate_normals=bool(pt_cfg.get("estimate_normals", True))
        )
        print(f"  最终有效三维点数: {len(pcd.points):,} 点")

        # 5. 统一输出与保存至 hk_real_output 下的时间序独立子文件夹
        out_cfg = self.config.get("output", {})
        base_out_dir = Path(self._resolve_path(out_cfg.get("output_dir", "data/output/hk_real_output")))
        base_out_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        matcher_tag = "great" if getattr(self, "matcher_type", "sgbm") == "great" else "sgbm"
        # 每次重建创建独立的专属文件夹，并标注算法类型 (recon_great_... 或 recon_sgbm_...)
        recon_dir = base_out_dir / f"recon_{matcher_tag}_{timestamp}"
        recon_dir.mkdir(parents=True, exist_ok=True)

        # 5.1 保存 3D 点云 (.ply)
        ply_path = recon_dir / f"model_{matcher_tag}_{timestamp}.ply"
        o3d.io.write_point_cloud(str(ply_path), pcd)
        o3d.io.write_point_cloud(str(base_out_dir / "latest_model.ply"), pcd)
        print(f"  [OK] 3D 点云已保存至专属目录: {ply_path}")

        # 5.2 保存稠密视差伪彩图 (.png)
        disp_vis = cv2.normalize(disparity, None, 0, 255, cv2.NORM_MINMAX)
        disp_vis = np.uint8(disp_vis)
        disp_color = cv2.applyColorMap(disp_vis, cv2.COLORMAP_JET)
        disp_color[disparity <= self.min_disp] = 0
        disp_path = recon_dir / f"disparity_{matcher_tag}_{timestamp}.png"
        cv2.imwrite(str(disp_path), disp_color)
        cv2.imwrite(str(base_out_dir / "latest_disparity.png"), disp_color)
        print(f"  [OK] 稠密视差图已保存: {disp_path}")

        # 5.3 保存真实物理深度伪彩图 (.png)
        valid_depth = (depth_m >= min_depth_val) & (depth_m <= max_depth_val) & np.isfinite(depth_m)
        depth_norm = np.zeros_like(depth_m, dtype=np.uint8)
        if np.any(valid_depth):
            depth_scaled = 255.0 * (depth_m - min_depth_val) / max(max_depth_val - min_depth_val, 1e-3)
            depth_norm[valid_depth] = np.clip(depth_scaled[valid_depth], 0, 255).astype(np.uint8)
        depth_color = cv2.applyColorMap(depth_norm, cv2.COLORMAP_TURBO)
        depth_color[~valid_depth] = 0
        depth_path = recon_dir / f"depth_{matcher_tag}_{timestamp}.png"
        cv2.imwrite(str(depth_path), depth_color)
        cv2.imwrite(str(base_out_dir / "latest_depth.png"), depth_color)
        print(f"  [OK] 物理深度图已保存: {depth_path}")

        # 5.4 保存校正灰度图 / 引导图 (.png)
        gray_left = cv2.cvtColor(rect_l, cv2.COLOR_BGR2GRAY) if len(rect_l.shape) == 3 else rect_l
        gray_path = recon_dir / f"gray_left_{timestamp}.png"
        cv2.imwrite(str(gray_path), gray_left)
        cv2.imwrite(str(base_out_dir / "latest_gray_left.png"), gray_left)
        print(f"  [OK] 引导灰度图已保存: {gray_path}")

        # 5.5 保存全流程诊断监控大图 (.png)
        if out_cfg.get("generate_preview", True):
            preview_path = recon_dir / f"showcase_{matcher_tag}_{timestamp}.png"
            self._render_showcase(rect_l, rect_r, disparity, pcd, str(preview_path))
            self._render_showcase(rect_l, rect_r, disparity, pcd, str(base_out_dir / "latest_showcase.png"))
            print(f"  [OK] 诊断监控大图已保存: {preview_path}")

        print("=" * 70)
        print(f"[SUCCESS] 流水线执行完毕！本轮产物已完整归档至: {recon_dir}")
        print(f"         (根目录下 latest_model.ply 已同步更新)")
        print("=" * 70)
        return pcd

    def _render_showcase(self, rect_l, rect_r, disparity, pcd, save_path):
        """生成极线对齐、视差热力图、空间俯视图的多合一监控大图"""
        h, w = rect_l.shape[:2]
        fig = plt.figure(figsize=(16, 10), dpi=150)

        # 1. 左校正图 + 极线
        ax1 = fig.add_subplot(2, 3, 1)
        ax1.imshow(cv2.cvtColor(rect_l, cv2.COLOR_BGR2RGB))
        ax1.set_title("Rectified Left Image", fontsize=10, fontweight="bold")
        for y in np.linspace(h * 0.15, h * 0.85, 7):
            ax1.axhline(y, color="lime", linestyle="--", linewidth=0.8, alpha=0.7)
        ax1.axis("off")

        # 2. 右校正图 + 极线
        ax2 = fig.add_subplot(2, 3, 2)
        ax2.imshow(cv2.cvtColor(rect_r, cv2.COLOR_BGR2RGB))
        ax2.set_title("Rectified Right Image", fontsize=10, fontweight="bold")
        for y in np.linspace(h * 0.15, h * 0.85, 7):
            ax2.axhline(y, color="lime", linestyle="--", linewidth=0.8, alpha=0.7)
        ax2.axis("off")

        # 3. 视差热力图
        ax3 = fig.add_subplot(2, 3, 3)
        valid = disparity > self.min_disp
        disp_norm = np.zeros_like(disparity)
        disp_norm[valid] = (disparity[valid] - self.min_disp) / self.num_disp
        disp_norm = np.clip(disp_norm, 0, 1.0)
        im3 = ax3.imshow(disp_norm, cmap="turbo")
        title_tag = "GREAT-Stereo (ICCV 2025)" if getattr(self, "matcher_type", "sgbm") == "great" else "SGBM-HH + WLS"
        ax3.set_title(f"Dense Disparity Map ({title_tag})", fontsize=10, fontweight="bold")
        ax3.axis("off")
        plt.colorbar(im3, ax=ax3, fraction=0.046, pad=0.04)

        # 4. 点云俯视图 (X vs Z)
        pts = np.asarray(pcd.points)
        cols = np.asarray(pcd.colors)
        ax4 = fig.add_subplot(2, 3, 4)
        if len(pts) > 0:
            stride = max(1, len(pts) // 30000)
            sample_pts = pts[::stride]
            scatter4 = ax4.scatter(sample_pts[:, 0], sample_pts[:, 2], c=sample_pts[:, 2], cmap="viridis", s=1.0, alpha=0.8)
            ax4.set_title("Floorplan Top-Down View (X vs Z [Depth])", fontsize=10, fontweight="bold")
            ax4.set_xlabel("X (m)", fontsize=8)
            ax4.set_ylabel("Depth Z (m)", fontsize=8)
            ax4.grid(True, linestyle=":", alpha=0.5)
            plt.colorbar(scatter4, ax=ax4, fraction=0.046, pad=0.04)

        # 5. 3D 透视角度 (散点)
        ax5 = fig.add_subplot(2, 3, 5, projection="3d")
        if len(pts) > 0:
            ax5.scatter(sample_pts[:, 0], sample_pts[:, 2], -sample_pts[:, 1], c=sample_pts[:, 2], cmap="plasma", s=1.0, alpha=0.7)
            ax5.view_init(elev=20, azim=-60)
            ax5.set_title("3D Space Clusters (Perspective)", fontsize=10, fontweight="bold")
            ax5.set_xlabel("X (m)", fontsize=7)
            ax5.set_ylabel("Depth Z (m)", fontsize=7)
            ax5.set_zlabel("Height -Y (m)", fontsize=7)

        # 6. 3D 真实颜色点云
        ax6 = fig.add_subplot(2, 3, 6, projection="3d")
        if len(pts) > 0:
            sample_cols = cols[::stride]
            ax6.scatter(sample_pts[:, 0], sample_pts[:, 2], -sample_pts[:, 1], c=sample_cols, s=1.0, alpha=0.85)
            ax6.view_init(elev=20, azim=-60)
            ax6.set_title("3D Model (True Grayscale/Color)", fontsize=10, fontweight="bold")
            ax6.set_xlabel("X (m)", fontsize=7)
            ax6.set_ylabel("Depth Z (m)", fontsize=7)
            ax6.set_zlabel("Height -Y (m)", fontsize=7)

        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
