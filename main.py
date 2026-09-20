import os
import sys
import argparse
import time
from pathlib import Path
import cv2
import numpy as np

# 加入项目根目录到模块搜索路径
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.calibration.calibrate_stereo import run_stereo_calibration
from src.camera import HikStereoCamera, MockStereoCamera
from src.tracking import OpticalTracker, SurgicalTool
from src.stereo.stereo_matcher import StereoVisionPipeline

def cmd_calibrate(args):
    """执行双目相机立体标定"""
    img_dir = args.images_dir or str(PROJECT_ROOT / "data" / "calibration_images")
    output_cfg = str(PROJECT_ROOT / "configs" / "calibration" / "stereo_calib_params.json")
    cache_dir = str(PROJECT_ROOT / "data" / "calibration_results")

    print("\n>>> 开始执行双目立体标定流程...")
    run_stereo_calibration(
        images_dir=img_dir,
        output_config_json=output_cfg,
        cache_dir=cache_dir,
        inner_corners=(11, 9),
        square_size_mm=20.0
    )

def cmd_track(args):
    """执行近红外手术器械光学追踪"""
    calib_cfg = str(PROJECT_ROOT / "configs" / "calibration" / "stereo_calib_params.json")
    tool_cfg = args.tool_config or str(PROJECT_ROOT / "configs" / "tools" / "probe_4marker.json")

    if not os.path.exists(calib_cfg):
        print(f"[Error] 未找到标定文件 {calib_cfg}，请先执行: python main.py --calibrate")
        return

    # 1. 初始化跟踪器
    tool = SurgicalTool(tool_cfg)
    tracker = OpticalTracker(calib_path=calib_cfg, tool=tool)
    print(f"\n>>> 手术导航追踪器已初始化:")
    print(f"  器械模型: {tool.name}")
    print(f"  标记球数量: {len(tool.model_points)}")
    print(f"  针尖偏移: {tool.tool_tip_offset} mm")

    # 2. 硬件抽象层初始化相机
    if args.camera == "hik":
        cam_cfg = str(PROJECT_ROOT / "configs" / "cameras" / "hikrobot_dual_mono.json")
        camera = HikStereoCamera(cam_cfg)
        print(f">>> 连接海康双目工业相机 (实机模式)...")
    else:
        # Mock 模式 (离线仿真/测试回放)
        mock_dir = args.input_dir or str(PROJECT_ROOT / "data" / "simulation")
        camera = MockStereoCamera(
            image_dir=mock_dir,
            left_img_path=args.left,
            right_img_path=args.right,
            fps=30.0,
            loop=True
        )
        print(f">>> 启动离线仿真/测试相机 (Mock 模式)...")

    if not camera.open():
        print(f"[Error] 相机打开失败，退出追踪。")
        return

    print(">>> 开始实时追踪循环 (按 'q' 键退出)...")
    frame_count = 0
    try:
        while True:
            ret, img_l, img_r = camera.grab_stereo()
            if not ret or img_l is None or img_r is None:
                time.sleep(0.01)
                continue

            frame_count += 1
            # 算法追踪解算
            result = tracker.track(img_l, img_r)

            # 可视化渲染
            vis = tracker.render_overlay(img_l, result)
            cv2.imshow("NIR Surgical Optical Tracking (Left Eye)", vis)

            if result["success"]:
                tip = result["tip_position"]
                print(f"\r[Frame {frame_count:04d}] TRACKING OK | FRE: {result['fre']:.3f} mm | Tip 3D: ({tip[0]:.2f}, {tip[1]:.2f}, {tip[2]:.2f}) mm", end="")
            else:
                print(f"\r[Frame {frame_count:04d}] SEARCHING... Markers 2D: L={len(result['markers_2d_left'])} R={len(result['markers_2d_right'])}", end="")

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
    finally:
        camera.close()
        cv2.destroyAllWindows()
        print("\n>>> 追踪已停止。")

def cmd_reconstruct(args):
    """稠密立体匹配点云重建 (SGBM + WLS)"""
    calib_npz = str(PROJECT_ROOT / "data" / "calibration_results" / "stereo_calib_params.npz")
    if not os.path.exists(calib_npz):
        print(f"[Error] 未找到高速标定缓存 {calib_npz}，请先运行: python main.py --calibrate")
        return

    if not args.left or not args.right:
        print("[Error] 请指定 --left 和 --right 图片路径！")
        return

    pipeline = StereoVisionPipeline(calib_npz)
    img_l = cv2.imread(args.left)
    img_r = cv2.imread(args.right)

    if img_l is None or img_r is None:
        print("[Error] 图像载入失败，请检查文件路径！")
        return

    print("1. 正在执行极线校正...")
    rect_l, rect_r = pipeline.rectify(img_l, img_r)

    print("2. 正在执行 SGBM 稠密匹配与 WLS 滤波...")
    disparity = pipeline.compute_disparity(rect_l, rect_r)

    output_dir = PROJECT_ROOT / "data" / "output"
    os.makedirs(output_dir, exist_ok=True)

    disp_save_path = str(output_dir / "disparity_result.png")
    disp_vis = cv2.normalize(disparity, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    cv2.imwrite(disp_save_path, cv2.applyColorMap(disp_vis, cv2.COLORMAP_JET))
    print(f"  视差图已保存: {disp_save_path}")

    ply_save_path = str(output_dir / (args.output_ply or "reconstructed_pointcloud.ply"))
    points, colors = pipeline.disparity_to_pointcloud(disparity, rect_l, max_depth_m=10.0)
    pipeline.save_ply(ply_save_path, points, colors)
    print(f"  3D 空间点云已保存: {ply_save_path}")

def cmd_test():
    """运行工程自动化测试"""
    import unittest
    suite = unittest.defaultTestLoader.discover(str(PROJECT_ROOT / "tests"), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)

def main():
    parser = argparse.ArgumentParser(description="近红外双目手术导航追踪与三维视觉系统")
    subparsers = parser.add_subparsers(dest="command", help="选择子命令")

    # 1. 标定命令
    calib_p = subparsers.add_parser("calibrate", help="运行双目立体几何标定")
    calib_p.add_argument("--images-dir", type=str, default=None, help="标定板图像对目录")

    # 2. 追踪命令
    track_p = subparsers.add_parser("track", help="运行近红外手术器械光学追踪")
    track_p.add_argument("--camera", choices=["mock", "hik"], default="mock", help="相机驱动类型 (默认: mock 离线仿真)")
    track_p.add_argument("--tool-config", type=str, default=None, help="手术器械定义 JSON 路径")
    track_p.add_argument("--input-dir", type=str, default=None, help="Mock 模式图像目录")
    track_p.add_argument("--left", type=str, default=None, help="单帧左图路径")
    track_p.add_argument("--right", type=str, default=None, help="单帧右图路径")

    # 3. 稠密重建命令
    recon_p = subparsers.add_parser("reconstruct", help="执行 SGBM 稠密点云重建")
    recon_p.add_argument("--left", type=str, required=True, help="待测左图路径")
    recon_p.add_argument("--right", type=str, required=True, help="待测右图路径")
    recon_p.add_argument("--output-ply", type=str, default="classroom_pointcloud.ply", help="输出点云文件名")

    # 4. 单元测试命令
    subparsers.add_parser("test", help="运行所有单元测试")

    # 兼容老版直接参数 (--calibrate / --track)
    parser.add_argument("--calibrate", action="store_true", help="[简写] 运行标定")
    parser.add_argument("--track", action="store_true", help="[简写] 运行追踪")
    parser.add_argument("--camera", choices=["mock", "hik"], default="mock", help="相机模式")
    parser.add_argument("--left", type=str, default="", help="左图")
    parser.add_argument("--right", type=str, default="", help="右图")

    args = parser.parse_args()

    if args.command == "calibrate" or args.calibrate:
        cmd_calibrate(args)
    elif args.command == "track" or args.track:
        cmd_track(args)
    elif args.command == "reconstruct":
        cmd_reconstruct(args)
    elif args.command == "test":
        cmd_test()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
