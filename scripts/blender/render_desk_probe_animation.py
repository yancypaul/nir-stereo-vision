import bpy
import os
import sys
import math
import json
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path("H:/antigravity/stereo vision blender")
out_dir = PROJECT_ROOT / "data" / "simulation" / "desk_pivot"
vis_dir = out_dir / "vis_frames"
os.makedirs(vis_dir, exist_ok=True)

# 1. 打开探针模型场景
probe_blend = PROJECT_ROOT / "blender_assets" / "tools" / "probe_tool.blend"
bpy.ops.wm.open_mainfile(filepath=str(probe_blend))

# 2. 载入真实教室讲台课桌 teacherDesk
desk_blend = PROJECT_ROOT / "blender_assets" / "classroom" / "assets" / "desks" / "desks.blend"
desk_obj_names = ['ChamferBox01', 'ChamferBox01.001', 'Line03', 'Line04', 'Line192', 'Line193', 'Line194', 'Line195', 'Line196', 'Line197']
with bpy.data.libraries.load(str(desk_blend), link=False) as (data_from, data_to):
    data_to.objects = desk_obj_names

desk_parent = bpy.data.objects.new('Desk_Group', None)
bpy.context.scene.collection.objects.link(desk_parent)

for o in data_to.objects:
    if o:
        bpy.context.scene.collection.objects.link(o)
        o.parent = desk_parent

# 课桌表面对齐至 Z = -0.010
desk_parent.location = (0.0, 0.18, -0.9269)

# 3. 定点枢轴设置 (Pivot Anchor)
tip_obj = bpy.data.objects.get('Needle_Tip_Pointer')
p_tip = np.array(tip_obj.location)

pivot_anchor = bpy.data.objects.new('Pivot_Anchor', None)
bpy.context.scene.collection.objects.link(pivot_anchor)
contact_pt = (0.0, 0.15, -0.010)
pivot_anchor.location = contact_pt

probe_root = bpy.data.objects.get('Surgical_Probe')
probe_root.parent = pivot_anchor

# 探针姿态：针尖在桌面上，柄身斜向上立起面对摄像机
rx = math.radians(-115)
Rx = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
T_root = - Rx @ p_tip
probe_root.location = tuple(T_root)
probe_root.rotation_euler = (rx, 0, 0)

# 4. 完美特写单反视角相机 (Perfect Framing Close-up Camera)
look_target = bpy.data.objects.new('Look_Target', None)
bpy.context.scene.collection.objects.link(look_target)
look_target.location = (0.0, 0.15, 0.06)

cam_obj = bpy.data.objects.get('PreviewCamera')
cam_obj.location = (0.35, -0.22, 0.22)
tt = cam_obj.constraints.new(type='TRACK_TO')
tt.target = look_target
tt.track_axis = 'TRACK_NEGATIVE_Z'
tt.up_axis = 'UP_Y'
bpy.context.scene.camera = cam_obj

# 5. 灯光优化
sun = bpy.data.objects.get('SunLight')
if sun:
    sun.data.energy = 5.0
    sun.location = (0.5, -1.0, 1.5)
    sun.rotation_euler = (math.radians(45), math.radians(-25), math.radians(20))

# 6. 设置 20 秒 (500 帧 @ 25 FPS) 大幅度锥形进动动画 (30度摆幅)
TOTAL_FRAMES = 500
CYCLES = 4 # 20 秒内平稳完成 4 圈大幅度伞状回旋
CONE_ANGLE_RAD = math.radians(30.0) # 30度超大幅度摆动

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = TOTAL_FRAMES
scene.render.fps = 25

marker_names = [
    'Marker_1_Base_Marker',
    'Marker_2_Right_Marker',
    'Marker_3_Left_Marker',
    'Marker_4_Elevated_Marker'
]
marker_objs = [bpy.data.objects.get(name) for name in marker_names]

gt_trajectory = []

# 为 pivot_anchor 逐帧设置关键帧并记录三维坐标真值
for f_idx in range(1, TOTAL_FRAMES + 1):
    scene.frame_set(f_idx)
    t = (f_idx - 1) / TOTAL_FRAMES
    phi = 2.0 * math.pi * CYCLES * t
    
    rot_x = CONE_ANGLE_RAD * math.cos(phi)
    rot_y = CONE_ANGLE_RAD * math.sin(phi)
    rot_z = 0.25 * CONE_ANGLE_RAD * math.sin(2.0 * phi)
    
    pivot_anchor.rotation_euler = (rot_x, rot_y, rot_z)
    pivot_anchor.keyframe_insert(data_path="rotation_euler", frame=f_idx)
    
    bpy.context.view_layer.update()
    
    tip_world = list(tip_obj.matrix_world.translation)
    markers_world = {
        m_name: list(m_obj.matrix_world.translation)
        for m_name, m_obj in zip(marker_names, marker_objs)
    }
    
    # 提取当前相机世界矩阵，用于二维像素投影
    cam_mw = [list(row) for row in cam_obj.matrix_world]
    
    gt_trajectory.append({
        "frame": f_idx,
        "tip_world_m": [round(v, 6) for v in tip_world],
        "markers_world_m": {k: [round(v, 6) for v in val] for k, val in markers_world.items()},
        "cam_matrix_world": cam_mw
    })

# 保存真值数据
with open(out_dir / "probe_motion_gt.json", "w", encoding="utf-8") as f:
    json.dump({
        "total_frames": TOTAL_FRAMES,
        "fps": 25,
        "cone_angle_deg": 30.0,
        "contact_pt_m": list(contact_pt),
        "cam_focal_mm": cam_obj.data.lens,
        "cam_sensor_w_mm": cam_obj.data.sensor_width,
        "trajectory": gt_trajectory
    }, f, indent=2)

print(f"[Blender] 500 帧关键帧动画与空间坐标真值已就绪！")

# 7. 执行批量渲染
scene.render.engine = 'BLENDER_EEVEE'
scene.eevee.taa_render_samples = 4
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.filepath = str(vis_dir / "frame_")

print(f"[Blender] 开始极速渲染 500 帧高清 3D 动画序列...")
bpy.ops.render.render(animation=True)
print(f"[Blender] 500 帧动画渲染全部完成！保存目录: {vis_dir}")
