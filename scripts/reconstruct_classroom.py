import os
import sys
import cv2
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

try:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
except Exception:
    PROJECT_ROOT = Path(os.getcwd())

out_dir = PROJECT_ROOT / "data" / "output"
os.makedirs(out_dir, exist_ok=True)

left_path = str(PROJECT_ROOT / "data" / "blender_sim" / "0001_L.png")
right_path = str(PROJECT_ROOT / "data" / "blender_sim" / "0001_R.png")

print(f"\n>>> 载入教室室内立体图像对:")
print(f"  左目: {left_path}")
print(f"  右目: {right_path}")

img_l = cv2.imread(left_path)
img_r = cv2.imread(right_path)

if img_l is None or img_r is None:
    raise FileNotFoundError("未找到教室仿真图像对！")

# 1. 保存单目灰度图
gray_l = cv2.cvtColor(img_l, cv2.COLOR_BGR2GRAY)
gray_r = cv2.cvtColor(img_r, cv2.COLOR_BGR2GRAY)
cv2.imwrite(str(out_dir / "classroom_gray.png"), gray_l)
print("  [1/4] 灰度图已就绪: data/output/classroom_gray.png")

# 2. 真实几何参数 (Blender 渲染摄像机实际参数)
# 焦距 f = 25mm, 传感器尺寸 32mm, 分辨率 1280x1024
# 基线 B = 65mm = 0.065m, 离轴收敛平面 Z_conv = 1.95m
f_px = 1000.0 # 25.0 / 32.0 * 1280.0
B_m = 0.065
Z_conv = 1.95

# 3. 广域 SGBM 视差计算 + WLS 边缘保边平滑滤波 (涵盖负视差至正视差: -32 ~ +64)
print("  [2/4] 执行大景深 SGBM 稠密匹配与 WLS 滤波...")
matcher = cv2.StereoSGBM_create(
    minDisparity=-32,
    numDisparities=96,
    blockSize=7,
    P1=8 * 7 * 7,
    P2=32 * 7 * 7,
    disp12MaxDiff=2,
    uniquenessRatio=5,
    speckleWindowSize=100,
    speckleRange=2,
    mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
)

right_matcher = cv2.ximgproc.createRightMatcher(matcher)
wls = cv2.ximgproc.createDisparityWLSFilter(matcher)
wls.setLambda(8000.0)
wls.setSigmaColor(1.5)

disp_l = matcher.compute(gray_l, gray_r)
disp_r = right_matcher.compute(gray_r, gray_l)
disp_wls = wls.filter(disp_l, gray_l, disparity_map_right=disp_r)
disp = disp_wls.astype(np.float32) / 16.0

# 4. 基于离轴收敛几何解算物理绝对深度: 1/Z = 1/Z_conv + disp / (f * B)
print("  [3/4] 解算物理绝对深度 (Metric Depth Map in meters)...")
valid = disp > -31
inv_Z = (1.0 / Z_conv) + (disp[valid] / (f_px * B_m))
depth_m = np.zeros_like(disp)
depth_m[valid] = np.where(inv_Z > 0.05, 1.0 / np.maximum(inv_Z, 0.05), 0)

valid_range = (depth_m >= 0.5) & (depth_m <= 10.0)

# 生成 Turbo 伪彩深度图 (近暖远冷: 0.5m ~ 9.0m)
norm_depth = np.zeros_like(disp, dtype=np.uint8)
norm_depth[valid_range] = np.clip((depth_m[valid_range] - 0.5) / (9.0 - 0.5) * 255.0, 0, 255).astype(np.uint8)
colored_depth = cv2.applyColorMap(norm_depth, cv2.COLORMAP_TURBO)
colored_depth[~valid_range] = [0, 0, 0]

depth_save_path = str(out_dir / "classroom_depth_map.png")
cv2.imwrite(depth_save_path, colored_depth)
print(f"  [√] 完美消除黑洞！全覆盖真实深度图已保存: {depth_save_path}")

# 5. 反投影生成 3D 空间彩色点云 (PLY)
print("  [4/4] 生成三维空间彩色点云 (PLY)...")
h, w = gray_l.shape
cx, cy = w / 2.0, h / 2.0
grid_y, grid_x = np.indices((h, w))

pts_z = depth_m[valid_range]
pts_x = (grid_x[valid_range] - cx) * pts_z / f_px
pts_y = (grid_y[valid_range] - cy) * pts_z / f_px

points = np.stack([pts_x, pts_y, pts_z], axis=1)
colors = img_l[valid_range][:, [2, 1, 0]] # BGR -> RGB

ply_path = str(out_dir / "classroom_pointcloud.ply")
with open(ply_path, "w") as f:
    f.write("ply\nformat ascii 1.0\n")
    f.write(f"element vertex {len(points)}\n")
    f.write("property float x\nproperty float y\nproperty float z\n")
    f.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
    f.write("end_header\n")
    for p, c in zip(points[::2], colors[::2]): # 降采样存储，兼顾轻量与高密
        f.write(f"{p[0]:.3f} {p[1]:.3f} {p[2]:.3f} {c[0]} {c[1]} {c[2]}\n")

print(f"  [√] 包含 {len(points)} 个真实三维点的空间点云已保存: {ply_path}")

# 6. 生成多视角 3D 点云渲染预览图
print(">>> 正在生成 3D 点云多重视角高清预览图...")
num_samples = min(50000, len(points))
idx = np.random.choice(len(points), num_samples, replace=False)
sub_pts = points[idx]
sub_cols = colors[idx] / 255.0

fig = plt.figure(figsize=(16, 7), dpi=120)
fig.patch.set_facecolor("#181818")

# 透视图
ax1 = fig.add_subplot(1, 2, 1, projection="3d")
ax1.set_facecolor("#181818")
ax1.scatter(sub_pts[:, 0], sub_pts[:, 2], -sub_pts[:, 1], c=sub_cols, s=1.0, alpha=0.85)
ax1.view_init(elev=18, azim=-60)
ax1.set_title("3D Classroom Point Cloud (Perspective View)", color="white", fontsize=13)
ax1.set_xlabel("X (m, Width)", color="gray")
ax1.set_ylabel("Z (m, Depth)", color="gray")
ax1.set_zlabel("Y (m, Height)", color="gray")
ax1.tick_params(colors="gray")

# 顶视俯瞰图
ax2 = fig.add_subplot(1, 2, 2, projection="3d")
ax2.set_facecolor("#181818")
ax2.scatter(sub_pts[:, 0], sub_pts[:, 2], -sub_pts[:, 1], c=sub_cols, s=1.0, alpha=0.85)
ax2.view_init(elev=78, azim=-90)
ax2.set_title("Bird's Eye View (Desk Rows & Spatial Layout)", color="white", fontsize=13)
ax2.set_xlabel("X (m)", color="gray")
ax2.set_ylabel("Depth Z (m)", color="gray")
ax2.tick_params(colors="gray")

plt.tight_layout()
preview_path = str(out_dir / "classroom_pointcloud_preview.png")
plt.savefig(preview_path, facecolor=fig.get_facecolor(), edgecolor="none")
plt.close()
print(f"  [√] 3D 点云可视化大图已生成: {preview_path}\n")
