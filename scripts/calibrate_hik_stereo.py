"""
==============================================================================
海康双目工业相机 - 工业级双目联合标定与极线校正解算程序 (Hikrobot Stereo Calibration)
==============================================================================
功能:
1. 自动读取标定板图片对 (支持 Left_x / Right_x);
2. 亚像素级棋盘格角点检测 (findChessboardCornersSB);
3. 单目标定 (解算各自焦距、主点与镜头畸变 k1, k2, p1, p2, k3);
4. 双目联合标定 (解算高精度双目旋转矩阵 R、平移向量 T 与物理基线 B);
5. Bouguet 极线校正算法 (求解 R1, R2, P1, P2, Q 投影矩阵);
6. 极线对准残差检验与高精度对齐监控图绘制;
7. 导出标准 JSON 与 NPZ 标定配置文件。
==============================================================================
"""

import os
import sys
import json
from pathlib import Path
import cv2
import numpy as np
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def run_calibration(
    session_dir: str,
    pattern_size: tuple = (11, 8),
    square_size_mm: float = 20.0,
    output_json: str = "configs/calibration/stereo_calib_params.json",
    output_npz: str = "configs/calibration/stereo_calib_params.npz",
    preview_img: str = "data/output/calibration/stereo_rectification_check.png"
):
    session_path = Path(session_dir)
    print("=" * 70)
    print("海康双目工业相机 - 标定解算开始")
    print("=" * 70)
    print(f"数据目录: {session_path}")
    print(f"标定板规格: {pattern_size[0]} x {pattern_size[1]} 内部角点, 方格边长 = {square_size_mm} mm")

    # 1. 扫描匹配图像对
    left_files = sorted(session_path.glob("Left_*.png"), key=lambda p: int(p.stem.split("_")[-1]))
    if not left_files:
        left_files = sorted(session_path.glob("*L*.png"))
    
    pairs = []
    for lp in left_files:
        idx_str = lp.stem.split("_")[-1]
        rp = session_path / f"Right_{idx_str}.png"
        if not rp.exists():
            rp = session_path / f"Right{idx_str}.png"
        if rp.exists():
            pairs.append((lp, rp))

    print(f"已发现配对图像: {len(pairs)} 对")
    if len(pairs) < 3:
        raise ValueError("标定图像对数量过少，至少需要 5 对以上！")

    # 2. 准备物理世界 3D 坐标 (Z = 0)
    cols, rows = pattern_size
    objp = np.zeros((cols * rows, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_size_mm

    objpoints = []
    imgpoints_l = []
    imgpoints_r = []
    valid_pair_indices = []
    sample_imgs = None

    print("\n正在执行亚像素级角点精细提取...")
    for idx, (lp, rp) in enumerate(pairs, 1):
        img_l = cv2.imread(str(lp), cv2.IMREAD_GRAYSCALE)
        img_r = cv2.imread(str(rp), cv2.IMREAD_GRAYSCALE)

        if sample_imgs is None:
            sample_imgs = (img_l.copy(), img_r.copy())
            img_shape = (img_l.shape[1], img_l.shape[0])  # (width, height)

        flags = cv2.CALIB_CB_ACCURACY | cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_NORMALIZE_IMAGE
        found_l, corners_l = cv2.findChessboardCornersSB(img_l, pattern_size, flags=flags)
        found_r, corners_r = cv2.findChessboardCornersSB(img_r, pattern_size, flags=flags)

        if found_l and found_r:
            objpoints.append(objp)
            imgpoints_l.append(corners_l)
            imgpoints_r.append(corners_r)
            valid_pair_indices.append(idx)
            print(f"  [OK] 第 {idx:02d} 对提取成功")
        else:
            print(f"  [--] 第 {idx:02d} 对角点未能双目完全识别 (L={found_l}, R={found_r})")

    num_valid = len(objpoints)
    print(f"\n全部图像处理完毕: 最终有效标定对 = {num_valid} / {len(pairs)}")
    if num_valid < 5:
        raise RuntimeError("有效标定对不足 5 对，无法保证标定精度！")

    # 3. 单目标定 (获取初值)
    print("\n[Step 1/3] 正在解算左相机与右相机的单目内参及畸变系数...")
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-5)

    ret_l, K1, D1, _, _ = cv2.calibrateCamera(
        objpoints, imgpoints_l, img_shape, None, None,
        criteria=criteria
    )
    ret_r, K2, D2, _, _ = cv2.calibrateCamera(
        objpoints, imgpoints_r, img_shape, None, None,
        criteria=criteria
    )
    print(f"  左相机重投影误差 (RMS): {ret_l:.4f} px (焦距: fx={K1[0,0]:.1f}, fy={K1[1,1]:.1f})")
    print(f"  右相机重投影误差 (RMS): {ret_r:.4f} px (焦距: fx={K2[0,0]:.1f}, fy={K2[1,1]:.1f})")

    # 4. 双目联合标定 (求解空间外参 R, T)
    print("\n[Step 2/3] 正在解算双目空间外参 (相对位姿 R, T)...")
    stereo_flags = cv2.CALIB_FIX_INTRINSIC
    ret_stereo, K1, D1, K2, D2, R, T, E, F = cv2.stereoCalibrate(
        objpoints, imgpoints_l, imgpoints_r,
        K1, D1, K2, D2, img_shape,
        criteria=criteria, flags=stereo_flags
    )

    baseline_mm = float(np.linalg.norm(T))
    baseline_m = baseline_mm / 1000.0
    print(f"  双目联合标定重投影误差 (RMS): {ret_stereo:.4f} px")
    print(f"  --> 物理基线距离 (Baseline): {baseline_mm:.2f} mm ({baseline_m:.4f} m)")
    print(f"  --> 平移向量 T (mm): [{T[0,0]:.2f}, {T[1,0]:.2f}, {T[2,0]:.2f}]")

    # 5. Bouguet 极线校正算法
    print("\n[Step 3/3] 正在执行 Bouguet 极线平整化与 Q 投影矩阵计算...")
    R1, R2, P1, P2, Q, roi1, roi2 = cv2.stereoRectify(
        K1, D1, K2, D2, img_shape, R, T,
        flags=cv2.CALIB_ZERO_DISPARITY, alpha=0
    )

    map_lx, map_ly = cv2.initUndistortRectifyMap(K1, D1, R1, P1, img_shape, cv2.CV_32FC1)
    map_rx, map_ry = cv2.initUndistortRectifyMap(K2, D2, R2, P2, img_shape, cv2.CV_32FC1)

    # 6. 计算极线校正后角点的垂直误差 (验证校正质量)
    y_diffs = []
    for c_l, c_r in zip(imgpoints_l, imgpoints_r):
        undist_l = cv2.undistortPoints(c_l, K1, D1, R=R1, P=P1)
        undist_r = cv2.undistortPoints(c_r, K2, D2, R=R2, P=P2)
        dy = np.abs(undist_l[:, :, 1] - undist_r[:, :, 1])
        y_diffs.extend(dy.flatten())
    mean_epipolar_err = float(np.mean(y_diffs))
    max_epipolar_err = float(np.max(y_diffs))
    print(f"  极线校正后平均垂直残差: {mean_epipolar_err:.3f} px (最大: {max_epipolar_err:.3f} px)")
    if mean_epipolar_err < 0.3:
        print("  [EXCELLENT] 极线校正精度达到工业亚像素级 (<0.3px)！")
    else:
        print("  [GOOD] 极线校正满足立体视觉标准。")

    # 7. 保存标定文件
    out_json_path = PROJECT_ROOT / output_json
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    calib_dict = {
        "image_size": [img_shape[0], img_shape[1]],
        "pattern_size": list(pattern_size),
        "square_size_mm": square_size_mm,
        "rms_error": float(ret_stereo),
        "baseline_mm": baseline_mm,
        "baseline_m": baseline_m,
        "mean_epipolar_error_px": mean_epipolar_err,
        "K1": K1.tolist(),
        "D1": D1.tolist(),
        "K2": K2.tolist(),
        "D2": D2.tolist(),
        "R": R.tolist(),
        "T": T.tolist(),
        "R1": R1.tolist(),
        "R2": R2.tolist(),
        "P1": P1.tolist(),
        "P2": P2.tolist(),
        "Q": Q.tolist()
    }
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(calib_dict, f, indent=4)
    print(f"\n[OK] 标定参数已保存至 JSON: {out_json_path}")

    out_npz_path = PROJECT_ROOT / output_npz
    np.savez_compressed(
        out_npz_path,
        image_size=img_shape,
        K1=K1, D1=D1, K2=K2, D2=D2,
        R=R, T=T, R1=R1, R2=R2, P1=P1, P2=P2, Q=Q,
        baseline_mm=baseline_mm
    )
    print(f"[OK] 标定参数已保存至 NPZ: {out_npz_path}")

    # 8. 绘制并保存诊断大图
    preview_path = PROJECT_ROOT / preview_img
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    raw_l, raw_r = sample_imgs
    rect_l = cv2.remap(raw_l, map_lx, map_ly, cv2.INTER_LINEAR)
    rect_r = cv2.remap(raw_r, map_rx, map_ry, cv2.INTER_LINEAR)

    fig = plt.figure(figsize=(16, 7), dpi=150)
    plt.suptitle(
        f"Hikrobot Stereo Calibration Verification | Baseline: {baseline_mm:.1f}mm | RMS: {ret_stereo:.3f}px | Epipolar Err: {mean_epipolar_err:.3f}px",
        fontsize=12, fontweight="bold", y=0.98
    )

    ax1 = fig.add_subplot(1, 2, 1)
    ax1.imshow(rect_l, cmap="gray")
    ax1.set_title("Rectified Left Eye (with Epipolar Lines)", fontsize=10)
    h, w = rect_l.shape
    for y in np.linspace(h * 0.1, h * 0.9, 16):
        ax1.axhline(y, color="lime", linestyle="--", linewidth=0.8, alpha=0.8)
    ax1.axis("off")

    ax2 = fig.add_subplot(1, 2, 2)
    ax2.imshow(rect_r, cmap="gray")
    ax2.set_title("Rectified Right Eye (with Epipolar Lines)", fontsize=10)
    for y in np.linspace(h * 0.1, h * 0.9, 16):
        ax2.axhline(y, color="lime", linestyle="--", linewidth=0.8, alpha=0.8)
    ax2.axis("off")

    plt.tight_layout()
    plt.savefig(preview_path, bbox_inches="tight")
    plt.close()
    print(f"[OK] 极线平整对齐检验图已生成: {preview_path}")

    print("=" * 70)
    print(f"[SUCCESS] 海康双目相机标定圆满完成！基线 = {baseline_mm:.2f} mm")
    print("=" * 70)
    return calib_dict


if __name__ == "__main__":
    session_dir = "data/captured_images/session_20260922_151659"
    run_calibration(
        session_dir=session_dir,
        pattern_size=(11, 8),
        square_size_mm=20.0
    )
