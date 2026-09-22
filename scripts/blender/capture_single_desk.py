import bpy
import mathutils
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(r"H:\antigravity\stereo vision")
out_dir = PROJECT_ROOT / "data" / "single_desk"
out_dir.mkdir(parents=True, exist_ok=True)

scene = bpy.context.scene
cam = scene.camera

# 1. 工业双目物理参数 (全景深清晰，无动画，无约束)
scene.render.resolution_x = 1280
scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'

cam.animation_data_clear()
for c in list(cam.constraints):
    cam.constraints.remove(c)
cam.scale = (1.0, 1.0, 1.0)
cam.data.dof.use_dof = False

# 目标: 第一排中间一体式课桌椅 chair.019 (中心: [0.17, 0.04, 0.40])
desk_target = (0.1674, 0.0376, 0.4000)

desk_stations = [
    {
        "id": "front",
        "name": "desk_front",
        "desc": "课桌正面特写 (直视桌面、前桌斗内胆与前桌腿)",
        "loc": (0.1674, 1.4000, 0.8500),
        "target": desk_target
    },
    {
        "id": "rear",
        "name": "desk_rear",
        "desc": "课桌椅背面特写 (直视椅背反面、座垫与后支架)",
        "loc": (0.1674, -1.3000, 0.8500),
        "target": desk_target
    }
]

print("\n" + "="*65)
print("  🎯 启动 单套课桌椅 (chair.019) 近距超高清双目对拍流水线")
print(f"  工作距离: ~1.40 米 | 输出目录: {out_dir}")
print("="*65)

for st in desk_stations:
    s_id = st["id"]
    print(f"\n>>> [机位: {st['desc']}]")
    
    # 定位与朝向
    cam.location = mathutils.Vector(st["loc"])
    direction = mathutils.Vector(st["target"]) - cam.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    
    bpy.context.view_layer.update()
    mat_world = [list(row) for row in cam.matrix_world]
    
    # 记录位姿元数据
    pose_info = {
        "station_id": s_id,
        "name": st["name"],
        "description": st["desc"],
        "location": list(cam.location),
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
    print("  [渲染中...] 正在调用 Cycles 物理光线追踪渲染高精图对...")
    bpy.ops.render.render(write_still=True)
    
    # 整理重命名
    for suf in ['_L.png', '_R.png', '__L.png', '__R.png']:
        p = out_dir / (f"temp_{s_id}" + suf)
        if p.exists():
            dst = left_target if 'L' in suf else right_target
            if dst.exists(): os.remove(dst)
            os.rename(p, dst)
            
    print(f"  [√] 图像对就绪: {left_target.name}, {right_target.name}")

print("\n" + "="*65)
print("🎉 单套课桌椅近距特写图对采集全部圆满完成！")
print("="*65 + "\n")

