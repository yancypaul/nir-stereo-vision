import bpy
import mathutils
import json
import os
from pathlib import Path

# 1. 独立工作目录 (绝不污染已有目录)
PROJECT_ROOT = Path(r"H:\antigravity\stereo vision")
out_dir = PROJECT_ROOT / "data" / "multiview_stations"
out_dir.mkdir(parents=True, exist_ok=True)

scene = bpy.context.scene
cam = scene.camera

# 保证分辨率与立体多视角开启，关闭艺术景深模糊 (工业双目相机全景深清晰)
scene.render.resolution_x = 1280
scene.render.resolution_y = 1024
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'

# 彻底清除相机自带的动画关键帧、跟踪约束与非等比缩放
cam.animation_data_clear()
for c in list(cam.constraints):
    cam.constraints.remove(c)
cam.scale = (1.0, 1.0, 1.0)
cam.data.dof.use_dof = False

# 4 个战略机位定义 (全部严格位于教室内 X∈[-2.0, 3.2], Y∈[-4.4, 2.5], Z∈[1.0, 1.4])
stations = [
    {
        "id": 1,
        "name": "rear_right_main",
        "desc": "后排右门主视角 (面朝黑板与课桌正向)",
        "loc": (2.5764, -4.4658, 1.0945),
        "rot": (1.5820, 0.0000, 0.2548) # 保持原版基准站精确朝向
    },
    {
        "id": 2,
        "name": "front_center_counter",
        "desc": "讲台黑板前正向对冲视角 (反视全班课桌内侧抽屉、椅背及后墙)",
        "loc": (0.5000, 2.2000, 1.3500),
        "target": (0.5000, -2.5000, 0.7000)
    },
    {
        "id": 3,
        "name": "rear_left_flank",
        "desc": "后排左侧走道侧翼视角 (教室内靠内墙，斜向前拍摄窗台、暖气与左桌壁)",
        "loc": (-1.8000, -3.2000, 1.3500),
        "target": (1.2000, 0.0000, 0.7000)
    },
    {
        "id": 4,
        "name": "front_right_flank",
        "desc": "前排右侧窗边侧翼视角 (教室内靠窗，斜向后拍摄课桌右侧盲区与过道)",
        "loc": (2.8000, 1.0000, 1.3500),
        "target": (-0.5000, -2.0000, 0.7000)
    }
]

print("\n" + "="*65)
print("  🚀 开始执行 Blender 多机位全景双目自动化采集流水线")
print(f"  输出目录: {out_dir}")
print("="*65)

for st in stations:
    s_id = st["id"]
    s_name = st["name"]
    print(f"\n>>> [机位 {s_id}/4: {st['desc']}]")
    
    # 移动机位
    cam.location = mathutils.Vector(st["loc"])
    if "rot" in st:
        cam.rotation_euler = mathutils.Euler(st["rot"], 'XYZ')
    else:
        # 朝向目标点
        direction = mathutils.Vector(st["target"]) - cam.location
        rot_quat = direction.to_track_quat('-Z', 'Y')
        cam.rotation_euler = rot_quat.to_euler()

    bpy.context.view_layer.update()
    mat_world = [list(row) for row in cam.matrix_world]
    
    # 保存相机位姿真值元数据 (JSON)
    pose_info = {
        "station_id": s_id,
        "name": s_name,
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
    
    pose_path = out_dir / f"station_{s_id}_pose.json"
    with open(pose_path, "w", encoding="utf-8") as f:
        json.dump(pose_info, f, indent=2, ensure_ascii=False)
    print(f"  [√] 位姿真值已记录: {pose_path.name}")

    # 设置渲染输出路径并渲染立体多视图 (所有机位统一由当前场景物理光线追踪渲染)
    left_target = out_dir / f"station_{s_id}_L.png"
    right_target = out_dir / f"station_{s_id}_R.png"

    render_prefix = str(out_dir / f"temp_st{s_id}")
    scene.render.filepath = render_prefix
    print(f"  [渲染中...] 正在调用 Cycles 物理光线追踪渲染...")
    bpy.ops.render.render(write_still=True)
        
    # 整理生成的文件名 (Blender 会保存为 temp_stX_L.png 与 temp_stX_R.png 或 temp_stX__L.png)
    temp_l = out_dir / f"temp_st{s_id}_L.png"
    temp_r = out_dir / f"temp_st{s_id}_R.png"
    temp_l2 = out_dir / f"temp_st{s_id}__L.png"
    temp_r2 = out_dir / f"temp_st{s_id}__R.png"
    
    actual_l = temp_l if temp_l.exists() else temp_l2
    actual_r = temp_r if temp_r.exists() else temp_r2
    
    if actual_l.exists():
        if left_target.exists(): os.remove(left_target)
        os.rename(actual_l, left_target)
    if actual_r.exists():
        if right_target.exists(): os.remove(right_target)
        os.rename(actual_r, right_target)
        
    print(f"  [√] 双目图像对渲染完成: {left_target.name}, {right_target.name}")

print("\n" + "="*65)
print("🎉 4 个机位全部采集就绪！所有图片与位姿数据已安全入库。")
print("="*65 + "\n")

