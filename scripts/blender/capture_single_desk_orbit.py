import bpy
import mathutils
import math
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(r"H:\antigravity\stereo vision")
out_dir = PROJECT_ROOT / "data" / "single_desk_orbit"
out_dir.mkdir(parents=True, exist_ok=True)

scene = bpy.context.scene
cam = scene.camera

# 1. 工业双目物理参数 (全景深清晰，无动画，无约束)
scene.render.resolution_x = 1280
scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'

# 优化采样，保证Cycles光追质量的同时快速出图 (32 samples + 降噪)
if hasattr(scene.cycles, 'samples'):
    scene.cycles.samples = 32

cam.animation_data_clear()
for c in list(cam.constraints):
    cam.constraints.remove(c)
cam.scale = (1.0, 1.0, 1.0)
cam.data.dof.use_dof = False

# 目标: 第一排中间一体式课桌椅 chair.019 (中心: [0.1674, 0.0376, 0.4000])
target_center = mathutils.Vector((0.1674, 0.0376, 0.4000))
radius = 1.35
cam_z = 0.90 # 稍高视角，俯仰角约 20° 俯视课桌椅，兼顾桌面、椅面、四根桌腿与靠背

# 8个圆周环绕视角 (0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°)
stations = []
names = [
    ("front", "正前方 (0°)"),
    ("front_right", "右前方 (45°)"),
    ("right", "正右方 (90°)"),
    ("rear_right", "右后方 (135°)"),
    ("rear", "正后方 (180°)"),
    ("rear_left", "左后方 (225°)"),
    ("left", "正左方 (270°)"),
    ("front_left", "左前方 (315°)")
]

for idx, (s_id, s_desc) in enumerate(names):
    angle_deg = idx * 45
    angle_rad = math.radians(angle_deg)
    # y轴正向为前方, x轴正向为右方
    cam_x = target_center.x + radius * math.sin(angle_rad)
    cam_y = target_center.y + radius * math.cos(angle_rad)
    stations.append({
        "id": s_id,
        "index": idx,
        "angle_deg": angle_deg,
        "desc": s_desc,
        "loc": (cam_x, cam_y, cam_z)
    })

print("\n" + "="*70)
print(f"  🎯 启动 课桌椅 360° 圆周 8 机位无死角全息扫描流水线")
print(f"  扫描半径: {radius:.2f}m | 镜头高度: {cam_z:.2f}m | 输出目录: {out_dir}")
print("="*70)

for st in stations:
    s_id = st["id"]
    print(f"\n>>> [机位 {st['index']+1}/8: {st['desc']} - 角度 {st['angle_deg']}°]")
    
    # 定位与对准课桌椅中心
    cam.location = mathutils.Vector(st["loc"])
    direction = target_center - cam.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    
    bpy.context.view_layer.update()
    mat_world = [list(row) for row in cam.matrix_world]
    
    # 记录精确实时位姿
    pose_info = {
        "station_id": s_id,
        "index": st["index"],
        "angle_deg": st["angle_deg"],
        "description": st["desc"],
        "location": list(cam.location),
        "target": list(target_center),
        "rotation_euler": [float(r) for r in cam.rotation_euler],
        "matrix_world": mat_world,
        "lens_focal_length_mm": float(cam.data.lens),
        "sensor_width_mm": float(cam.data.sensor_width),
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "stereo_interocular": float(cam.data.stereo.interocular_distance),
        "stereo_convergence": float(cam.data.stereo.convergence_distance),
        "stereo_pivot": cam.data.stereo.pivot
    }
    
    pose_file = out_dir / f"{s_id}_pose.json"
    with open(pose_file, "w", encoding="utf-8") as f:
        json.dump(pose_info, f, indent=2, ensure_ascii=False)
        
    left_target = out_dir / f"{s_id}_L.png"
    right_target = out_dir / f"{s_id}_R.png"
    
    render_prefix = str(out_dir / f"temp_{s_id}")
    scene.render.filepath = render_prefix
    print(f"  [渲染中...] 渲染立体双目图像对 ({st['desc']})...")
    bpy.ops.render.render(write_still=True)
    
    # 整理重命名
    for suf in ['_L.png', '_R.png', '__L.png', '__R.png']:
        p = out_dir / (f"temp_{s_id}" + suf)
        if p.exists():
            dst = left_target if 'L' in suf else right_target
            if dst.exists(): os.remove(dst)
            os.rename(p, dst)
            
    print(f"  [√] 图像对就绪: {left_target.name}, {right_target.name}")

print("\n" + "="*70)
print("🎉 360° 圆周 8 机位图对采集全部圆满完成！")
print("="*70 + "\n")

