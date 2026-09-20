import os
import json
import numpy as np
import cv2

class StereoVisionPipeline:
    """
    近红外双目立体视觉核心处理管线:
    1. 极线立体校正 (Remap Rectification)
    2. SGBM 视差计算 + WLS 边缘平滑滤波 (Disparity Estimation)
    3. 视差转深度与 3D 点云生成 (3D Reconstruction)
    """

    def __init__(self, calib_npz_path=r"H:\antigravity\stereo vision\data\calibration_results\stereo_params.npz"):
        self.calib_npz_path = calib_npz_path
        self.is_calibrated = False

        if os.path.exists(calib_npz_path):
            self.load_calibration(calib_npz_path)
        else:
            print(f"[Warning] 标定参数文件尚未找到: {calib_npz_path}，请先执行标定！")

        # 初始化 SGBM 立体匹配器
        self.init_sgbm()

    def load_calibration(self, npz_path):
        data = np.load(npz_path)
        self.map_lx = data['map_lx']
        self.map_ly = data['map_ly']
        self.map_rx = data['map_rx']
        self.map_ry = data['map_ry']
        self.Q = data['Q']
        self.is_calibrated = True
        print(f"[Pipeline] 成功加载双目标定参数与极线映射表: {npz_path}")

    def init_sgbm(self, num_disparities=128, block_size=7):
        """初始化 SGBM 及 WLS 滤波参数"""
        self.num_disparities = num_disparities
        self.block_size = block_size

        self.left_matcher = cv2.StereoSGBM_create(
            minDisparity=0,
            numDisparities=num_disparities,
            blockSize=block_size,
            P1=8 * 1 * block_size ** 2,
            P2=32 * 1 * block_size ** 2,
            disp12MaxDiff=1,
            uniquenessRatio=10,
            speckleWindowSize=100,
            speckleRange=2,
            preFilterCap=63,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
        )

        # 尝试构建带左右一致性校验的 WLS 滤波器
        try:
            self.right_matcher = cv2.ximgproc.createRightMatcher(self.left_matcher)
            self.wls_filter = cv2.ximgproc.createDisparityWLSFilter(self.left_matcher)
            self.wls_filter.setLambda(8000.0)
            self.wls_filter.setSigmaColor(1.5)
            self.has_wls = True
        except Exception:
            self.has_wls = False

    def rectify(self, img_l, img_r):
        """执行硬件级快速极线重映射校正"""
        if not self.is_calibrated:
            return img_l, img_r
        rect_l = cv2.remap(img_l, self.map_lx, self.map_ly, cv2.INTER_LINEAR)
        rect_r = cv2.remap(img_r, self.map_rx, self.map_ry, cv2.INTER_LINEAR)
        return rect_l, rect_r

    def compute_disparity(self, rect_l, rect_r):
        """计算视差图并应用边缘保持滤波"""
        # 近红外图像通常为单通道，如为3通道先转灰度
        if len(rect_l.shape) == 3:
            gray_l = cv2.cvtColor(rect_l, cv2.COLOR_BGR2GRAY)
            gray_r = cv2.cvtColor(rect_r, cv2.COLOR_BGR2GRAY)
        else:
            gray_l, gray_r = rect_l, rect_r

        # CLAHE 近红外局部自适应对比度增强
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray_l_enh = clahe.apply(gray_l)
        gray_r_enh = clahe.apply(gray_r)

        if self.has_wls:
            disp_l = self.left_matcher.compute(gray_l_enh, gray_r_enh)
            disp_r = self.right_matcher.compute(gray_r_enh, gray_l_enh)
            filtered_disp = self.wls_filter.filter(disp_l, gray_l_enh, disparity_map_right=disp_r)
            disparity = filtered_disp.astype(np.float32) / 16.0
        else:
            disp_l = self.left_matcher.compute(gray_l_enh, gray_r_enh)
            disparity = disp_l.astype(np.float32) / 16.0

        return disparity

    def disparity_to_pointcloud(self, disparity, rgb_img=None, max_depth_m=8.0):
        """
        利用 Q 矩阵反投影生成 3D 空间点云 (X, Y, Z, R, G, B)
        """
        points_3d = cv2.reprojectImageTo3D(disparity, self.Q)

        # 过滤无效深度的点 (视差 <= 0 或深度过大)
        mask = (disparity > 0) & (points_3d[:, :, 2] > 0) & (points_3d[:, :, 2] < max_depth_m * 1000.0)

        valid_points = points_3d[mask]

        if rgb_img is not None:
            if len(rgb_img.shape) == 2:
                colors = np.repeat(rgb_img[mask, np.newaxis], 3, axis=1)
            else:
                colors = rgb_img[mask][:, [2, 1, 0]] # BGR -> RGB
        else:
            colors = np.ones((valid_points.shape[0], 3), dtype=np.uint8) * 200

        return valid_points, colors

    def save_ply(self, ply_path, points, colors):
        """保存为标准的 3D 点云 PLY 文件，可用 MeshLab, CloudCompare, Blender 打开"""
        num_points = points.shape[0]
        with open(ply_path, 'w') as f:
            f.write("ply\n")
            f.write("format ascii 1.0\n")
            f.write(f"element vertex {num_points}\n")
            f.write("property float x\n")
            f.write("property float y\n")
            f.write("property float z\n")
            f.write("property uchar red\n")
            f.write("property uchar green\n")
            f.write("property uchar blue\n")
            f.write("end_header\n")
            for p, c in zip(points, colors):
                f.write(f"{p[0]:.3f} {p[1]:.3f} {p[2]:.3f} {c[0]} {c[1]} {c[2]}\n")
        print(f"[Pipeline] 3D 点云已保存: {ply_path} (包含 {num_points} 个三维点)")

