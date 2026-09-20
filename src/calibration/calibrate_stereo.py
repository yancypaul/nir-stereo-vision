import os
import glob
import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import numpy as np
import cv2

def run_stereo_calibration(
    images_dir: Optional[str] = None,
    output_config_json: Optional[str] = None,
    cache_dir: Optional[str] = None,
    inner_corners: Tuple[int, int] = (11, 9),
    square_size_mm: float = 20.0
) -> Dict[str, Any]:
    """
    双目立体标定主程序 (适配 11x9 内角点, 20mm 方格高精度黑白标定板)
    """
    project_root = Path(__file__).resolve().parents[2]

    if images_dir is None:
        images_dir = str(project_root / "data" / "calibration_images")
    if output_config_json is None:
        output_config_json = str(project_root / "configs" / "calibration" / "stereo_calib_params.json")
    if cache_dir is None:
        cache_dir = str(project_root / "data" / "calibration_results")

    os.makedirs(os.path.dirname(output_config_json), exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)
    vis_dir = os.path.join(cache_dir, "corner_visualizations")
    os.makedirs(vis_dir, exist_ok=True)

    # 1. 准备物理世界 3D 坐标点 (以 mm 为单位, 设 Z=0)
    pattern_size = inner_corners
    objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2) * square_size_mm

    objpoints = []
    imgpoints_l = []
    imgpoints_r = []

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)

    left_images = sorted(glob.glob(os.path.join(images_dir, "left_*.png")))
    right_images = sorted(glob.glob(os.path.join(images_dir, "right_*.png")))

    if not left_images or len(left_images) != len(right_images):
        raise ValueError(f"左右图片数量不匹配或为空! 左图: {len(left_images)}, 右图: {len(right_images)}")

    print(f"\n=======================================================")
    print(f" 开始双目相机立体标定 (共 {len(left_images)} 组图片对)")
    print(f" 棋盘格规格: {inner_corners[0]}x{inner_corners[1]} 内角点, 边长 {square_size_mm} mm")
    print(f"=======================================================\n")

    img_shape = None
    valid_pairs = 0

    for idx, (l_path, r_path) in enumerate(zip(left_images, right_images), start=1):
        img_l = cv2.imread(l_path, cv2.IMREAD_GRAYSCALE)
        img_r = cv2.imread(r_path, cv2.IMREAD_GRAYSCALE)

        if img_l is None or img_r is None:
            continue

        if img_shape is None:
            img_shape = (img_l.shape[1], img_l.shape[0])

        flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_FAST_CHECK
        ret_l, corners_l = cv2.findChessboardCorners(img_l, pattern_size, flags)
        ret_r, corners_r = cv2.findChessboardCorners(img_r, pattern_size, flags)

        if ret_l and ret_r:
            valid_pairs += 1
            corners_l_sub = cv2.cornerSubPix(img_l, corners_l, (11, 11), (-1, -1), criteria)
            corners_r_sub = cv2.cornerSubPix(img_r, corners_r, (11, 11), (-1, -1), criteria)

            objpoints.append(objp)
            imgpoints_l.append(corners_l_sub)
            imgpoints_r.append(corners_r_sub)

            vis_l = cv2.cvtColor(img_l, cv2.COLOR_GRAY2BGR)
            cv2.drawChessboardCorners(vis_l, pattern_size, corners_l_sub, ret_l)
            vis_path = os.path.join(vis_dir, f"detected_corners_{idx:02d}.png")
            cv2.imwrite(vis_path, vis_l)

            print(f"  [√] 组 {idx:02d}: 角点检测成功且亚像素对齐")
        else:
            print(f"  [X] 组 {idx:02d}: 未能同时在左右图中检测到完整角点")

    if valid_pairs < 5:
        raise RuntimeError(f"有效角点组数过少 ({valid_pairs})，建议至少 5 组以上！")

    print(f"\n有效标定样本对: {valid_pairs}/{len(left_images)}")
    print("正在计算左右单目内参矩阵与畸变系数...")

    ret_l, K_l, D_l, _, _ = cv2.calibrateCamera(objpoints, imgpoints_l, img_shape, None, None)
    ret_r, K_r, D_r, _, _ = cv2.calibrateCamera(objpoints, imgpoints_r, img_shape, None, None)

    print(f"  左相机单目重投影误差 (RMS): {ret_l:.4f} 像素")
    print(f"  右相机单目重投影误差 (RMS): {ret_r:.4f} 像素")

    print("\n正在执行双目联合立体标定 (stereoCalibrate)...")
    stereo_flags = cv2.CALIB_FIX_INTRINSIC
    criteria_stereo = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-5)

    ret_stereo, K_l, D_l, K_r, D_r, R, T, E, F = cv2.stereoCalibrate(
        objpoints, imgpoints_l, imgpoints_r,
        K_l, D_l, K_r, D_r,
        img_shape,
        criteria=criteria_stereo,
        flags=stereo_flags
    )

    baseline_calculated = float(np.linalg.norm(T))
    print(f"  双目系统总体 RMS 误差: {ret_stereo:.4f} 像素 (优秀标准 < 0.5 像素)")
    print(f"  计算得出的双目物理基线距离 (Baseline): {baseline_calculated:.2f} mm")

    print("\n计算极线校正矩阵与 Q 深度重投影矩阵...")
    R_l, R_r, P_l, P_r, Q, validPixROI1, validPixROI2 = cv2.stereoRectify(
        K_l, D_l, K_r, D_r,
        img_shape, R, T,
        flags=cv2.CALIB_ZERO_DISPARITY,
        alpha=0.0
    )

    calib_data = {
        "image_width": img_shape[0],
        "image_height": img_shape[1],
        "rms_error": float(ret_stereo),
        "baseline_mm": baseline_calculated,
        "K_left": K_l.tolist(),
        "dist_left": D_l.tolist(),
        "D_left": D_l.tolist(),
        "K_right": K_r.tolist(),
        "dist_right": D_r.tolist(),
        "D_right": D_r.tolist(),
        "R": R.tolist(),
        "T_mm": T.tolist(),
        "R_left": R_l.tolist(),
        "R_right": R_r.tolist(),
        "P_left": P_l.tolist(),
        "P_right": P_r.tolist(),
        "Q": Q.tolist()
    }

    with open(output_config_json, "w", encoding="utf-8") as f:
        json.dump(calib_data, f, indent=4, ensure_ascii=False)

    # 缓存本地查找表
    map_lx, map_ly = cv2.initUndistortRectifyMap(K_l, D_l, R_l, P_l, img_shape, cv2.CV_32FC1)
    map_rx, map_ry = cv2.initUndistortRectifyMap(K_r, D_r, R_r, P_r, img_shape, cv2.CV_32FC1)
    npz_path = os.path.join(cache_dir, "stereo_calib_params.npz")
    np.savez(
        npz_path,
        map_lx=map_lx, map_ly=map_ly,
        map_rx=map_rx, map_ry=map_ry,
        Q=Q, K_l=K_l, D_l=D_l, K_r=K_r, D_r=D_r, R=R, T=T
    )

    print(f"\n>>> 标定参数已成功写入配置中心:")
    print(f"  - 配置文件: {output_config_json}")
    print(f"  - 缓存映射表: {npz_path}")
    print(f"=======================================================\n")
    return calib_data

if __name__ == "__main__":
    run_stereo_calibration()
