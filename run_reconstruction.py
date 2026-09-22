"""
run_reconstruction.py
=====================
工业级通用双目立体视觉与 3D 点云重建主入口

使用方式:
1. 最简运行 (直接读取 configs/reconstruction/default.yaml):
   python run_reconstruction.py

2. 指定配置文件运行:
   python run_reconstruction.py --config configs/reconstruction/my_task.yaml

3. 命令行快速覆盖参数:
   python run_reconstruction.py --left path/to/L.png --right path/to/R.png --num-disp 224
"""

import sys
import argparse
from pathlib import Path

# 将项目根目录加入模块搜索路径
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.stereo.reconstructor import StereoReconstructor
import yaml

def main():
    parser = argparse.ArgumentParser(description="工业级通用双目立体视觉与 3D 点云重建主入口")
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=str(PROJECT_ROOT / "configs" / "reconstruction" / "default.yaml"),
        help="配置文件路径 (默认: configs/reconstruction/default.yaml)"
    )
    # 支持命令行临时覆盖
    parser.add_argument("--left", "-l", type=str, default=None, help="覆盖左图路径")
    parser.add_argument("--right", "-r", type=str, default=None, help="覆盖右图路径")
    parser.add_argument("--calib", type=str, default=None, help="覆盖标定文件路径")
    parser.add_argument("--mode", choices=["ideal", "file", "auto_board"], default=None, help="覆盖标定模式")
    parser.add_argument("--num-disp", type=int, default=None, help="覆盖 num_disparities")
    parser.add_argument("--min-disp", type=int, default=None, help="覆盖 min_disparity")
    parser.add_argument("--ply", "-o", type=str, default=None, help="覆盖输出 PLY 路径")

    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = PROJECT_ROOT / cfg_path

    if not cfg_path.exists():
        print(f"❌ 错误: 未找到配置文件: {cfg_path}")
        sys.exit(1)

    with open(cfg_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 处理自动选取最新采集图对
    if args.left is None and args.right is None:
        captured_base = PROJECT_ROOT / "data" / "captured_images"
        latest_l, latest_r, session_name, shot_idx = StereoReconstructor.find_latest_captured_pair(captured_base)
        if latest_l and latest_r:
            config["input"]["left_image"] = latest_l
            config["input"]["right_image"] = latest_r
            print("=" * 70)
            print(f"[Auto-Select] 自动锁定最新采集会话: {session_name}")
            print(f"  -> 选用最新第 {shot_idx} 组图像对: Left_{shot_idx}.png 与 Right_{shot_idx}.png")
            print("=" * 70)

    # 处理命令行参数显式覆盖
    if args.left:
        config["input"]["left_image"] = args.left
    if args.right:
        config["input"]["right_image"] = args.right
    if args.mode:
        config["calibration"]["mode"] = args.mode
    if args.calib:
        config["calibration"]["param_file"] = args.calib
    if args.num_disp:
        config["matcher"]["num_disparities"] = args.num_disp
    if args.min_disp is not None:
        config["matcher"]["min_disparity"] = args.min_disp
    if args.ply:
        config["output"]["pointcloud_ply"] = args.ply

    # 实例化并运行通用引擎
    reconstructor = StereoReconstructor(config)
    reconstructor.run()

if __name__ == "__main__":
    main()

