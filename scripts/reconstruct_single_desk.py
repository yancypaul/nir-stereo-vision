import os
import json
import cv2
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
data_dir = PROJECT_ROOT / "data" / "single_desk"
out_dir = PROJECT_ROOT / "data" / "output" / "pointcloud"
out_dir.mkdir(parents=True, exist_ok=True)

print("\n" + "="*65)
print("  🔬 单套课桌椅 (chair.019) 毫米级近距高保真双目重建系统")
print("="*65)

f_px = 1000.0
cx = 1280.0 / 2.0
cy = 1024.0 / 2.0
f_b = 65.0
d_conv_offset = 65.0 / 1.95 # 33.3333

min_disp = -16
num_disp = 96
block_size = 5

matcher_l = cv2.StereoSGBM_create(
    minDisparity=min_disp,
    numDisparities=num_disp,
    blockSize=block_size,
    P1=8 * 1 * block_size * block_size,
    P2=32 * 1 * block_size * block_size,
    disp12MaxDiff=1,
    uniquenessRatio=8,
    speckleWindowSize=80,
    speckleRange=2,
    mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
)
matcher_r = cv2.ximgproc.createRightMatcher(matcher_l)
wls_filter = cv2.ximgproc.createDisparityWLSFilter(matcher_l)
wls_filter.setLambda(8000.0)
wls_filter.setSigmaColor(1.2)

views = ["front", "rear"]
station_clouds = {}

for v in views:
    left_p = data_dir / f"{v}_L.png"
    right_p = data_dir / f"{v}_R.png"
    pose_p = data_dir / f"{v}_pose.json"
    
    if not (left_p.exists() and right_p.exists() and pose_p.exists()):
        print(f"  [等待] 视图 {v} 尚未就绪...")
        continue
        
    print(f"\n>>> 处理视图: {v.upper()}...")
    with open(pose_p, "r", encoding="utf-8") as f:
        pose = json.load(f)
        
    img_l = cv2.imread(str(left_p))
    img_r = cv2.imread(str(right_p))
    gray_l = cv2.cvtColor(img_l, cv2.COLOR_BGR2GRAY)
    gray_r = cv2.cvtColor(img_r, cv2.COLOR_BGR2GRAY)
    
    disp_l = matcher_l.compute(gray_l, gray_r)
    disp_r = matcher_r.compute(gray_r, gray_l)
    filtered_disp = wls_filter.filter(disp_l, gray_l, disparity_map_right=disp_r)
    disp_float = filtered_disp.astype(np.float32) / 16.0
    
    # 过滤失配
    raw_invalid = (filtered_disp <= (min_disp + 0.5) * 16) | (disp_l <= min_disp * 16)
    disp_float[raw_invalid] = np.nan
    
    denom = d_conv_offset + disp_float
    valid = (~raw_invalid) & (disp_float > (min_disp + 1.0)) & (denom > 5.0)
    z_map = np.zeros_like(disp_float)
    z_map[valid] = f_b / denom[valid]
    
    # 关键特写深度范围限制: 只保留课桌自身 (0.85米 ~ 2.10米)，彻底过滤背景墙壁与其他排课桌
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
    
    # 单独导出单视角高清点云 (用于零重影基准对比)
    single_ply = out_dir / f"single_desk_{v}_only.ply"
    with open(single_ply, "w", encoding="utf-8") as f:
        f.write(f"ply\nformat ascii 1.0\nelement vertex {len(pts_world)}\n")
        f.write("property float x\nproperty float y\nproperty float z\n")
        f.write("property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
        for pt, col in zip(pts_world, cols):
            f.write(f"{pt[0]:.4f} {pt[1]:.4f} {pt[2]:.4f} {col[0]} {col[1]} {col[2]}\n")
            
    print(f"  [√] 单视角 {v} 重建完成: {len(pts_world):,} 点 -> {single_ply.name}")
    station_clouds[v] = (pts_world, cols)

# 融合两站
if len(station_clouds) == 2:
    print("\n>>> 开始执行单套课桌椅正反双向融合与体素微米级去重...")
    all_p = np.vstack([station_clouds["front"][0], station_clouds["rear"][0]])
    all_c = np.vstack([station_clouds["front"][1], station_clouds["rear"][1]])
    
    # 4毫米精细微体素降采样 (保留钢管细腿与桌板厚度)
    voxel_size = 0.004
    voxel_indices = np.floor(all_p / voxel_size).astype(np.int32)
    voxel_dict = {}
    for i in range(len(all_p)):
        k = (voxel_indices[i, 0], voxel_indices[i, 1], voxel_indices[i, 2])
        if k not in voxel_dict:
            voxel_dict[k] = [all_p[i], all_c[i], 1]
        else:
            voxel_dict[k][0] += all_p[i]
            voxel_dict[k][1] = voxel_dict[k][1].astype(np.int32) + all_c[i].astype(np.int32)
            voxel_dict[k][2] += 1
            
    fused_p = []
    fused_c = []
    for val in voxel_dict.values():
        cnt = val[2]
        fused_p.append(val[0] / cnt)
        fused_c.append((val[1] / cnt).astype(np.uint8))
        
    fused_p = np.array(fused_p, dtype=np.float32)
    fused_c = np.array(fused_c, dtype=np.uint8)
    
    fused_ply = out_dir / "single_desk_fused_360.ply"
    with open(fused_ply, "w", encoding="utf-8") as f:
        f.write(f"ply\nformat ascii 1.0\nelement vertex {len(fused_p)}\n")
        f.write("property float x\nproperty float y\nproperty float z\n")
        f.write("property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
        for pt, col in zip(fused_p, fused_c):
            f.write(f"{pt[0]:.4f} {pt[1]:.4f} {pt[2]:.4f} {col[0]} {col[1]} {col[2]}\n")
            
    print(f"\n[√] 单套课桌椅 360° 正反闭合融合点云已导出！")
    print(f"  合并总规模: {len(fused_p):,} 个精细实体点")
    print(f"  文件路径: {fused_ply}")

