import os
import json
import cv2
import numpy as np
import open3d as o3d
from pathlib import Path
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
data_dir = PROJECT_ROOT / "data" / "single_desk_orbit"
out_dir = PROJECT_ROOT / "data" / "output" / "pointcloud"
out_dir.mkdir(parents=True, exist_ok=True)
brain_dir = Path(r"C:\Users\20124\.gemini\antigravity\brain\59fc0db1-4e78-4b50-b526-9e37cfb17234")

print("\n" + "="*70)
print("  [Single Desk Orbit] 360° 圆周 8 机位无死角全息多视角点云融合重构")
print("="*70)

f_px = 1000.0
cx = 1280.0 / 2.0
cy = 1024.0 / 2.0
f_b = 65.0
d_conv_offset = 65.0 / 1.95 # 33.3333

# 8方向全向 Hirschmüller SGM + 3x3 小核 + 连续微调
min_disp = -16
num_disp = 96
block_size = 3

matcher_hh = cv2.StereoSGBM_create(
    minDisparity=min_disp,
    numDisparities=num_disp,
    blockSize=block_size,
    P1=24,
    P2=96,
    disp12MaxDiff=1,
    uniquenessRatio=5,
    speckleWindowSize=100,
    speckleRange=1,
    mode=cv2.STEREO_SGBM_MODE_HH
)

matcher_r = cv2.ximgproc.createRightMatcher(matcher_hh)
wls_filter = cv2.ximgproc.createDisparityWLSFilter(matcher_hh)
wls_filter.setLambda(6000.0)
wls_filter.setSigmaColor(1.0)

station_keys = [
    "front", "front_right", "right", "rear_right",
    "rear", "rear_left", "left", "front_left"
]

all_pts_list = []
all_cols_list = []

for idx, s_id in enumerate(station_keys):
    left_p = data_dir / f"{s_id}_L.png"
    right_p = data_dir / f"{s_id}_R.png"
    pose_p = data_dir / f"{s_id}_pose.json"
    
    if not (left_p.exists() and right_p.exists() and pose_p.exists()):
        print(f"  [跳过] 机位 {s_id} 数据未就绪...")
        continue
        
    print(f"\n>>> 处理机位 {idx+1}/8: [{s_id.upper()}]...")
    with open(pose_p, "r", encoding="utf-8") as f:
        pose = json.load(f)
        
    img_l = cv2.imread(str(left_p))
    img_r = cv2.imread(str(right_p))
    gray_l = cv2.cvtColor(img_l, cv2.COLOR_BGR2GRAY)
    gray_r = cv2.cvtColor(img_r, cv2.COLOR_BGR2GRAY)
    
    disp_l = matcher_hh.compute(gray_l, gray_r)
    disp_r = matcher_r.compute(gray_r, gray_l)
    filtered_disp = wls_filter.filter(disp_l, gray_l, disparity_map_right=disp_r)
    disp_float = filtered_disp.astype(np.float32) / 16.0
    
    raw_invalid = (filtered_disp <= (min_disp + 0.5) * 16) | (disp_l <= min_disp * 16)
    
    # 引导滤波平滑
    disp_clean = disp_float.copy()
    disp_clean[raw_invalid] = 0
    disp_smooth = cv2.ximgproc.guidedFilter(guide=gray_l, src=disp_clean, radius=4, eps=0.03)
    
    disp_final = disp_smooth.copy()
    disp_final[raw_invalid] = np.nan
    
    denom = d_conv_offset + disp_final
    valid = (~raw_invalid) & (disp_final > (min_disp + 1.0)) & (denom > 5.0)
    z_map = np.zeros_like(disp_final)
    z_map[valid] = f_b / denom[valid]
    
    # 距离掩膜: 只取 0.8m ~ 2.0m 内的目标物体
    valid_mask = valid & (z_map >= 0.80) & (z_map <= 2.05)
    
    h, w = gray_l.shape
    grid_y, grid_x = np.indices((h, w))
    pz = z_map[valid_mask]
    px = (grid_x[valid_mask] - cx) * pz / f_px
    py = (grid_y[valid_mask] - cy) * pz / f_px
    
    pts_bl = np.stack([px, -py, -pz], axis=1)
    
    mat_world = np.array(pose["matrix_world"], dtype=np.float32)
    R_cam = mat_world[0:3, 0:3].copy()
    T_cam = mat_world[0:3, 3].copy()
    col_scales = np.linalg.norm(R_cam, axis=0, keepdims=True)
    R_cam = R_cam / np.maximum(col_scales, 1e-6)
    
    pts_world = (R_cam @ pts_bl.T).T + T_cam
    cols = img_l[valid_mask][:, ::-1] # BGR -> RGB
    
    # 课桌椅精确空间包围盒剪裁
    box_mask = (
        (pts_world[:, 0] >= -0.25) & (pts_world[:, 0] <= 0.60) &
        (pts_world[:, 1] >= -0.40) & (pts_world[:, 1] <= 0.42) &
        (pts_world[:, 2] >= -0.01) & (pts_world[:, 2] <= 0.86)
    )
    pts_box = pts_world[box_mask]
    cols_box = cols[box_mask]
    
    if len(pts_box) < 50:
        continue
        
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts_box)
    pcd.colors = o3d.utility.Vector3dVector(cols_box.astype(np.float64) / 255.0)
    pcd_clean, _ = pcd.remove_statistical_outlier(nb_neighbors=25, std_ratio=1.5)
    
    pts_clean = np.asarray(pcd_clean.points)
    cols_clean = (np.asarray(pcd_clean.colors) * 255.0).astype(np.uint8)
    
    all_pts_list.append(pts_clean)
    all_cols_list.append(cols_clean)
    print(f"  [√] 机位 {s_id} 贡献点数: {len(pts_clean):,}")

if not all_pts_list:
    print("没有有效点云数据！")
    exit(1)

# 多视角体素融合去重
print("\n>>> 开始执行 8 机位 360° 环绕点云体素微米级多视融合...")
raw_pts = np.vstack(all_pts_list)
raw_cols = np.vstack(all_cols_list)
print(f"  原始累积点云规模: {len(raw_pts):,} 点")

voxel_size = 0.003 # 3mm 超微精细体素
voxel_indices = np.floor(raw_pts / voxel_size).astype(np.int32)
voxel_dict = {}
for i in range(len(raw_pts)):
    k = (voxel_indices[i, 0], voxel_indices[i, 1], voxel_indices[i, 2])
    if k not in voxel_dict:
        voxel_dict[k] = [raw_pts[i], raw_cols[i].astype(np.float32), 1]
    else:
        voxel_dict[k][0] += raw_pts[i]
        voxel_dict[k][1] += raw_cols[i].astype(np.float32)
        voxel_dict[k][2] += 1

fused_p = []
fused_c = []
for val in voxel_dict.values():
    cnt = val[2]
    fused_p.append(val[0] / cnt)
    fused_c.append((val[1] / cnt).astype(np.uint8))

fused_p = np.array(fused_p, dtype=np.float32)
fused_c = np.array(fused_c, dtype=np.uint8)

# 再次做一次整体轻微滤波消除边缘游离点
final_pcd = o3d.geometry.PointCloud()
final_pcd.points = o3d.utility.Vector3dVector(fused_p)
final_pcd.colors = o3d.utility.Vector3dVector(fused_c.astype(np.float64) / 255.0)
final_clean, _ = final_pcd.remove_statistical_outlier(nb_neighbors=30, std_ratio=1.4)

fused_p = np.asarray(final_clean.points)
fused_c = (np.asarray(final_clean.colors) * 255.0).astype(np.uint8)

out_desk_dir = out_dir / "single_desk"
out_desk_dir.mkdir(parents=True, exist_ok=True)
out_ply = out_desk_dir / "single_desk_orbit_360.ply"
with open(out_ply, "w", encoding="utf-8") as f:
    f.write(f"ply\nformat ascii 1.0\nelement vertex {len(fused_p)}\n")
    f.write("property float x\nproperty float y\nproperty float z\n")
    f.write("property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
    for pt, col in zip(fused_p, fused_c):
        f.write(f"{pt[0]:.4f} {pt[1]:.4f} {pt[2]:.4f} {col[0]} {col[1]} {col[2]}\n")

print("\n" + "="*70)
print(f"[OK] 360 degree orbit pointcloud reconstruction successful!")
print(f"  Final point count: {len(fused_p):,} points")
print(f"  Export file: {out_ply}")
print("="*70)

# 4视角展示全景：3D鸟瞰、侧面图、正面图、俯视图
print("\n>>> 正在渲染 4 视角全方位质感全景图...")
fig = plt.figure(figsize=(18, 14))

idx_sub = np.random.choice(len(fused_p), min(60000, len(fused_p)), replace=False)
p_sub = fused_p[idx_sub]
c_sub = fused_c[idx_sub] / 255.0

# 1. 3D 透视图
ax1 = fig.add_subplot(2, 2, 1, projection='3d')
ax1.scatter(p_sub[:, 0], p_sub[:, 1], p_sub[:, 2], c=c_sub, s=1.5)
ax1.view_init(elev=20, azim=45)
ax1.set_title("3D Isometric Orbit View (Full 360° Coverage)", fontsize=13, pad=10)
ax1.set_xlabel("X (m)")
ax1.set_ylabel("Y (m)")
ax1.set_zlabel("Z (m)")

# 2. 侧面剖面图 (YZ - 展现此前完全缺失的左右侧面钢管与侧边构件)
ax2 = fig.add_subplot(2, 2, 2)
ax2.scatter(p_sub[:, 1], p_sub[:, 2], c=c_sub, s=2.0)
ax2.set_title("Side View (YZ) - Side Tubular Legs & Shelf Fully Closed", fontsize=13)
ax2.set_xlabel("Y (m) [Front <---> Back]")
ax2.set_ylabel("Z (m) [Height]")
ax2.set_aspect('equal')
ax2.grid(True, alpha=0.3)

# 3. 正面视图 (XZ)
ax3 = fig.add_subplot(2, 2, 3)
ax3.scatter(p_sub[:, 0], p_sub[:, 2], c=c_sub, s=2.0)
ax3.set_title("Front View (XZ) - Front Legs & Table Board Symmetry", fontsize=13)
ax3.set_xlabel("X (m) [Left <---> Right]")
ax3.set_ylabel("Z (m) [Height]")
ax3.set_aspect('equal')
ax3.grid(True, alpha=0.3)

# 4. 俯视鸟瞰图 (XY - 展现桌板与椅面完全密闭致密表面)
ax4 = fig.add_subplot(2, 2, 4)
ax4.scatter(p_sub[:, 0], p_sub[:, 1], c=c_sub, s=2.0)
ax4.set_title("Top-Down View (XY) - Continuous Solid Table & Chair Surfaces", fontsize=13)
ax4.set_xlabel("X (m)")
ax4.set_ylabel("Y (m)")
ax4.set_aspect('equal')
ax4.grid(True, alpha=0.3)

plt.tight_layout()
preview_path = brain_dir / "single_desk_orbit_360_preview.png"
plt.savefig(str(preview_path), dpi=180)
plt.close()
print(f"[√] 全景预览图已保存: {preview_path}")
