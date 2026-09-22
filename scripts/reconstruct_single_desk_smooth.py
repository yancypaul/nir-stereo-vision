import os
import json
import cv2
import numpy as np
import open3d as o3d
from pathlib import Path
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
data_dir = PROJECT_ROOT / "data" / "single_desk"
out_dir = PROJECT_ROOT / "data" / "output" / "pointcloud"
out_dir.mkdir(parents=True, exist_ok=True)
brain_dir = Path(r"C:\Users\20124\.gemini\antigravity\brain\59fc0db1-4e78-4b50-b526-9e37cfb17234")

print("\n" + "="*70)
print("  [Single Desk] 工业级高精度抗梯田平滑重建 (Ultra-Smooth SGBM-HH)")
print("="*70)

f_px = 1000.0
cx = 1280.0 / 2.0
cy = 1024.0 / 2.0
f_b = 65.0
d_conv_offset = 65.0 / 1.95 # 33.3333

# 1. 采用完整的 8 方向 Hirschmüller SGM (MODE_HH)
# 块大小缩小为 3x3，大幅保留细金属腿轮廓；微调 P1/P2 允许曲面斜率平滑过渡，消除台阶
min_disp = -16
num_disp = 96
block_size = 3

matcher_hh = cv2.StereoSGBM_create(
    minDisparity=min_disp,
    numDisparities=num_disp,
    blockSize=block_size,
    P1=24,                       # 降低小变化惩罚，允许平滑斜面
    P2=96,                       # 降低大变化惩罚，消除死板阶梯锁定
    disp12MaxDiff=1,
    uniquenessRatio=5,
    speckleWindowSize=100,
    speckleRange=1,
    mode=cv2.STEREO_SGBM_MODE_HH # 8方向全向代价聚合
)

matcher_r = cv2.ximgproc.createRightMatcher(matcher_hh)
wls_filter = cv2.ximgproc.createDisparityWLSFilter(matcher_hh)
wls_filter.setLambda(6000.0)
wls_filter.setSigmaColor(1.0)

views = ["front", "rear"]
clouds_dict = {}

for v in views:
    left_p = data_dir / f"{v}_L.png"
    right_p = data_dir / f"{v}_R.png"
    pose_p = data_dir / f"{v}_pose.json"
    
    if not (left_p.exists() and right_p.exists() and pose_p.exists()):
        print(f"  [等待] 视图 {v} 尚未就绪...")
        continue
        
    print(f"\n>>> 处理视图: {v.upper()} (SGBM-HH 8方向 + 引导滤波)...")
    with open(pose_p, "r", encoding="utf-8") as f:
        pose = json.load(f)
        
    img_l = cv2.imread(str(left_p))
    img_r = cv2.imread(str(right_p))
    gray_l = cv2.cvtColor(img_l, cv2.COLOR_BGR2GRAY)
    gray_r = cv2.cvtColor(img_r, cv2.COLOR_BGR2GRAY)
    
    # 8方向立体匹配 + WLS 双向滤波
    disp_l = matcher_hh.compute(gray_l, gray_r)
    disp_r = matcher_r.compute(gray_r, gray_l)
    filtered_disp = wls_filter.filter(disp_l, gray_l, disparity_map_right=disp_r)
    disp_float = filtered_disp.astype(np.float32) / 16.0
    
    # 有效区域掩膜
    raw_invalid = (filtered_disp <= (min_disp + 0.5) * 16) | (disp_l <= min_disp * 16)
    
    # 引导滤波：利用左图真实灰度高频引导，将离散量化台阶平滑为连续曲面
    disp_clean = disp_float.copy()
    disp_clean[raw_invalid] = 0
    disp_smooth = cv2.ximgproc.guidedFilter(guide=gray_l, src=disp_clean, radius=4, eps=0.03)
    
    # 替换回有效区域
    disp_final = disp_smooth.copy()
    disp_final[raw_invalid] = np.nan
    
    denom = d_conv_offset + disp_final
    valid = (~raw_invalid) & (disp_final > (min_disp + 1.0)) & (denom > 5.0)
    z_map = np.zeros_like(disp_final)
    z_map[valid] = f_b / denom[valid]
    
    # 深度范围限制: 只保留课桌椅主体 (0.85米 ~ 2.10米)
    valid_mask = valid & (z_map >= 0.85) & (z_map <= 2.10)
    
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
    
    # 裁切课桌椅局部边界
    box_mask = (
        (pts_world[:, 0] >= -0.25) & (pts_world[:, 0] <= 0.60) &
        (pts_world[:, 1] >= -0.40) & (pts_world[:, 1] <= 0.42) &
        (pts_world[:, 2] >= -0.01) & (pts_world[:, 2] <= 0.86)
    )
    pts_box = pts_world[box_mask]
    cols_box = cols[box_mask]
    
    # Open3D 离群噪点滤除
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts_box)
    pcd.colors = o3d.utility.Vector3dVector(cols_box.astype(np.float64) / 255.0)
    pcd_clean, ind = pcd.remove_statistical_outlier(nb_neighbors=25, std_ratio=1.5)
    
    pts_clean = np.asarray(pcd_clean.points)
    cols_clean = (np.asarray(pcd_clean.colors) * 255.0).astype(np.uint8)
    
    clouds_dict[v] = (pts_clean, cols_clean)
    print(f"  [√] 视图 {v} 平滑点云处理完毕: {len(pts_clean):,} 点")

# 保存单视角 smooth front
if "front" in clouds_dict:
    pts_f, cols_f = clouds_dict["front"]
    out_front_smooth = out_dir / "single_desk_smooth_front.ply"
    with open(out_front_smooth, "w", encoding="utf-8") as f:
        f.write(f"ply\nformat ascii 1.0\nelement vertex {len(pts_f)}\n")
        f.write("property float x\nproperty float y\nproperty float z\n")
        f.write("property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
        for pt, col in zip(pts_f, cols_f):
            f.write(f"{pt[0]:.4f} {pt[1]:.4f} {pt[2]:.4f} {col[0]} {col[1]} {col[2]}\n")
    print(f"\n[√] 导出单视角平滑点云: {out_front_smooth.name}")

# 如果两站都有，进行微体素融合
if len(clouds_dict) == 2:
    all_p = np.vstack([clouds_dict["front"][0], clouds_dict["rear"][0]])
    all_c = np.vstack([clouds_dict["front"][1], clouds_dict["rear"][1]])
    voxel_size = 0.003 # 3毫米微体素
    voxel_indices = np.floor(all_p / voxel_size).astype(np.int32)
    voxel_dict = {}
    for i in range(len(all_p)):
        k = (voxel_indices[i, 0], voxel_indices[i, 1], voxel_indices[i, 2])
        if k not in voxel_dict:
            voxel_dict[k] = [all_p[i], all_c[i].astype(np.float32), 1]
        else:
            voxel_dict[k][0] += all_p[i]
            voxel_dict[k][1] += all_c[i].astype(np.float32)
            voxel_dict[k][2] += 1
            
    fused_p = []
    fused_c = []
    for val in voxel_dict.values():
        cnt = val[2]
        fused_p.append(val[0] / cnt)
        fused_c.append((val[1] / cnt).astype(np.uint8))
        
    fused_p = np.array(fused_p, dtype=np.float32)
    fused_c = np.array(fused_c, dtype=np.uint8)
    
    out_smooth_fused = out_dir / "single_desk_smooth.ply"
    with open(out_smooth_fused, "w", encoding="utf-8") as f:
        f.write(f"ply\nformat ascii 1.0\nelement vertex {len(fused_p)}\n")
        f.write("property float x\nproperty float y\nproperty float z\n")
        f.write("property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
        for pt, col in zip(fused_p, fused_c):
            f.write(f"{pt[0]:.4f} {pt[1]:.4f} {pt[2]:.4f} {col[0]} {col[1]} {col[2]}\n")
    print(f"[√] 导出 360° 正反双向融合平滑点云: {out_smooth_fused.name} ({len(fused_p):,} 点)")
else:
    out_smooth_fused = out_dir / "single_desk_smooth.ply"
    pts_f, cols_f = clouds_dict["front"]
    with open(out_smooth_fused, "w", encoding="utf-8") as f:
        f.write(f"ply\nformat ascii 1.0\nelement vertex {len(pts_f)}\n")
        f.write("property float x\nproperty float y\nproperty float z\n")
        f.write("property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
        for pt, col in zip(pts_f, cols_f):
            f.write(f"{pt[0]:.4f} {pt[1]:.4f} {pt[2]:.4f} {col[0]} {col[1]} {col[2]}\n")
    print(f"[√] 导出单站平滑点云: {out_smooth_fused.name}")

# 3. 生成直观的 Before / After 对比图
print("\n>>> 正在渲染 Before vs After 点云平滑度对比图...")
fig, axes = plt.subplots(1, 2, figsize=(16, 8), subplot_kw={'projection': '3d'})

# 加载原始未经平滑的点云 (single_desk_pure.ply)
pcd_orig = o3d.io.read_point_cloud(str(out_dir / "single_desk_pure.ply"))
pts_o = np.asarray(pcd_orig.points)
cols_o = np.asarray(pcd_orig.colors)

# 加载新的平滑点云
pcd_s = o3d.io.read_point_cloud(str(out_smooth_fused))
pts_s = np.asarray(pcd_s.points)
cols_s = np.asarray(pcd_s.colors)

# 统一视角参数 (接近用户在 CloudCompare 中的观察角度)
elev = 25
azim = -65

# 绘制原始点云
idx_o = np.random.choice(len(pts_o), min(45000, len(pts_o)), replace=False)
axes[0].scatter(pts_o[idx_o, 0], pts_o[idx_o, 1], pts_o[idx_o, 2], c=cols_o[idx_o], s=1.2, alpha=0.9)
axes[0].view_init(elev=elev, azim=azim)
axes[0].set_title("BEFORE: Original SGBM-3WAY\n(Notice Terraced Steps on Chair Seat & Holes in Legs)", fontsize=11, pad=12)
axes[0].set_xlabel("X (m)")
axes[0].set_ylabel("Y (m)")
axes[0].set_zlabel("Z (m)")

# 绘制平滑优化后的点云
idx_s = np.random.choice(len(pts_s), min(45000, len(pts_s)), replace=False)
axes[1].scatter(pts_s[idx_s, 0], pts_s[idx_s, 1], pts_s[idx_s, 2], c=cols_s[idx_s], s=1.2, alpha=0.9)
axes[1].view_init(elev=elev, azim=azim)
axes[1].set_title("AFTER: SGBM-HH (8-Way) + Guided Sub-pixel\n(Smooth Continuous Surfaces, Restored Legs)", fontsize=11, pad=12)
axes[1].set_xlabel("X (m)")
axes[1].set_ylabel("Y (m)")
axes[1].set_zlabel("Z (m)")

plt.tight_layout()
cmp_path = brain_dir / "single_desk_smooth_comparison.png"
plt.savefig(str(cmp_path), dpi=180)
plt.close()
print(f"[√] 对比图已保存: {cmp_path}")

