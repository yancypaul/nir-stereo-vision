"""
==============================================================================
海康双目工业相机 - 100% 纯净原画质实时预览与分会话采图系统 (Hikrobot Pure Preview)
==============================================================================
工作机制:
1. [每启动一次创建一个独立文件夹]:
   每次运行本程序，自动在 data/captured_images/ 下创建一个以启动时间命名的文件夹:
   data/captured_images/session_YYYYMMDD_HHMMSS/
2. [按次序保存 Left_x 与 Right_x]:
   在当前会话窗口中，每次按下 [S] 或 [空格]，自动递增保存:
   Left_1.png, Right_1.png
   Left_2.png, Right_2.png
   Left_3.png, Right_3.png
   ...
3. [同步更新最新工作文件]:
   最新拍摄的一组会同步复制到:
   data/hik_left.png 和 data/hik_right.png
   便于直接运行 3D 重建算法。
4. [100% 纯净原画质直出]:
   无任何辅助线、无任何文字遮挡、无任何降采样压缩。
==============================================================================
"""

import sys
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np

# 将项目根目录添加进系统路径
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.camera.hik_camera import HikStereoCamera


def main():
    # 1. 每次启动，自动创建专属的会话文件夹
    session_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = PROJECT_ROOT / "data" / "captured_images" / f"session_{session_time}"
    session_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("正在连接海康双目工业相机并启动 [100% 纯净原画质] 预览窗口...")
    print("=" * 70)
    print(f"本次运行保存目录: {session_dir}")
    print("保存命名格式: Left_1.png / Right_1.png, Left_2.png / Right_2.png ...")
    print("快捷键:")
    print("  [S] 或 [空格] : 抓拍并保存当前这一组原画质双目图像")
    print("  [Q] 或 [ESC]  : 退出程序并安全释放相机")
    print("=" * 70)

    cam = HikStereoCamera()
    if not cam.open():
        print("[Error] 相机打开失败，请确认两台相机 USB 均已插好且没有被其他软件占用。")
        return

    window_name = "Hikrobot Stereo Camera (100% Native Quality)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    # 默认设置双目 2560x1024 原尺寸 (可自由缩放或最大化全屏)
    cv2.resizeWindow(window_name, 2560, 1024)

    shot_index = 1

    try:
        while True:
            ok, frame_l, frame_r = cam.grab_stereo()
            if not ok or frame_l is None or frame_r is None:
                continue

            # 双目 100% 原生点对点并排直出，零遮挡、零线条、零文字
            canvas = np.hstack([frame_l, frame_r])

            # 信息只显示在最顶部的系统窗口标题栏，完全不遮挡画面内容
            cv2.setWindowTitle(
                window_name,
                f"{window_name} | Folder: {session_dir.name} | Captured: {shot_index - 1} pairs"
            )

            cv2.imshow(window_name, canvas)
            key = cv2.waitKey(1) & 0xFF

            # [Q] 或 [ESC] 退出
            if key in [ord('q'), ord('Q'), 27]:
                print("\n[Live Preview] 正在退出预览并释放相机...")
                break

            # [S] 或 [空格] 抓拍当前组
            elif key in [ord('s'), ord('S'), 32]:
                path_l = session_dir / f"Left_{shot_index}.png"
                path_r = session_dir / f"Right_{shot_index}.png"

                # 1. 保存到本次启动的独立文件夹中
                cv2.imwrite(str(path_l), frame_l)
                cv2.imwrite(str(path_r), frame_r)

                # 2. 同时更新到根目录工作缓存，方便直接跑 3D 点云
                cv2.imwrite(str(PROJECT_ROOT / "data" / "hik_left.png"), frame_l)
                cv2.imwrite(str(PROJECT_ROOT / "data" / "hik_right.png"), frame_r)

                print(f"[OK] 已成功保存第 {shot_index} 组图像:")
                print(f"     <- {path_l}")
                print(f"     -> {path_r}")

                shot_index += 1

    except KeyboardInterrupt:
        print("\n[Live Preview] 收到中断信号...")
    finally:
        cam.close()
        cv2.destroyAllWindows()
        print("[Live Preview] 相机与窗口已完全释放。")


if __name__ == "__main__":
    main()
