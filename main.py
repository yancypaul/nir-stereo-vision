import os
import sys
import argparse
import cv2
import numpy as np

# 加入本地包路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.calibration.calibrate_stereo import run_stereo_calibration
from src.stereo.stereo_matcher import StereoVisionPipeline

def cmd_calibrate():
    """执行双目立体标定"""
    print("\n>>> 开始执行双目立体标定流程...")
    run_stereo_calibration(
        images_dir=r"H:\antigravity\stereo vision\data\calibration_images",
        output_dir=r"H:\antigravity\stereo vision\data\calibration_results",
        inner_corners=(11, 9),
        square_size_mm=20.0
    )

def cmd_reconstruct(left_img_path, right_img_path, output_ply="classroom_pointcloud.ply"):
    """执行立体匹配与 3D 点云重建"""
    calib_npz = r"H:\antigravity\stereo vision\data\calibration_results\stereo_calib_params.npz"
    if not os.path.exists(calib_npz):
        print(f"[Error] 未找到标定参数 {calib_npz}，请先运行: python main.py --calibrate")
        return

    pipeline = StereoVisionPipeline(calib_npz)

    print(f"\n>>> 载入双目待测图像对:")
    print(f"  左图: {left_img_path}")
    print(f"  右图: {right_img_path}")

    img_l = cv2.imread(left_img_path)
    img_r = cv2.imread(right_img_path)

    if img_l is None or img_r is None:
        print("[Error] 图像载入失败，请检查文件路径！")
        return

    # 1. 极线立体校正
    print("1. 正在执行极线校正 (水平极线对齐)...")
    rect_l, rect_r = pipeline.rectify(img_l, img_r)

    # 2. SGBM 视差匹配
    print("2. 正在执行 SGBM 半全局块匹配 + WLS 边缘滤波...")
    disparity = pipeline.compute_disparity(rect_l, rect_r)

    # 3. 视差热力图可视化保存
    disp_vis = cv2.normalize(disparity, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    disp_color = cv2.applyColorMap(disp_vis, cv2.COLORMAP_JET)
    
    disp_save_path = r"H:\antigravity\stereo vision\data\disparity_result.png"
    cv2.imwrite(disp_save_path, disp_color)
    print(f"  视差彩色热力图已保存至: {disp_save_path}")

    # 4. 生成 3D 空间点云并保存为 PLY 格式
    print("3. 正在通过 Q 矩阵反投影生成 3D 毫米级点云...")
    points, colors = pipeline.disparity_to_pointcloud(disparity, rect_l, max_depth_m=10.0)
    
    ply_save_path = os.path.join(r"H:\antigravity\stereo vision\data", output_ply)
    pipeline.save_ply(ply_save_path, points, colors)
    print(f"\n>>> 重建完成！3D 点云已就绪: {ply_save_path}")
    print(f">>> 你可以使用 MeshLab、CloudCompare 或直接拖进 Blender 查看 3D 空间结构！\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="近红外双目成像与三维重建系统")
    parser.add_argument("--calibrate", action="store_true", help="运行双目标定程序")
    parser.add_argument("--reconstruct", action="store_true", help="执行三维点云重建")
    parser.add_argument("--left", type=str, default="", help="左图路径")
    parser.add_argument("--right", type=str, default="", help="右图路径")
    
    args = parser.parse_args()

    if args.calibrate:
        cmd_calibrate()
    elif args.reconstruct:
        if not args.left or not args.right:
            print("请指定 --left 和 --right 图片路径！")
        else:
            cmd_reconstruct(args.left, args.right)
    else:
        print("请指定命令参数，例如: python main.py --calibrate")

