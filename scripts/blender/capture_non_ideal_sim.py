import bpy
import os
import math
import mathutils
from pathlib import Path

PROJECT_ROOT = Path(r"H:\antigravity\stereo vision")
calib_dir = PROJECT_ROOT / "data" / "non_ideal_sim" / "calibration_images"
desk_dir = PROJECT_ROOT / "data" / "non_ideal_sim" / "desk_stereo"
tex_path = str(PROJECT_ROOT / "blender_assets" / "calibration_board" / "chessboard_11x9_20mm.png")
studio_blend = str(PROJECT_ROOT / "blender_assets" / "calibration_board" / "calibration_studio.blend")
classroom_blend = str(PROJECT_ROOT / "blender_assets" / "classroom" / "classroom.blend")

calib_dir.mkdir(parents=True, exist_ok=True)
desk_dir.mkdir(parents=True, exist_ok=True)

print("\n" + "="*70)
print("  🎯 启动 真实感非理想双目 (轻微桶形畸变 + 2.4° 斗鸡眼内敛 + 1.5mm 装配高低差) 仿真采集")
print("="*70)

# ==============================================================================
# 第一部分：在虚拟标定暗室渲染 12 组“斗鸡眼+高低差”标定板图对
# ==============================================================================
print("\n>>> [第一阶段] 渲染 12 组非理想双目标定图集...")
bpy.ops.wm.open_mainfile(filepath=studio_blend)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
if hasattr(scene.cycles, 'samples'):
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True

scene.render.resolution_x = 1280
scene.render.resolution_y = 960
scene.render.image_settings.color_mode = 'BW'

cam_obj = scene.camera
base_cam_loc = (0, -0.70, 0)
baseline = 0.060 # 60mm 基线
toe_angle = math.radians(1.2) # 左右各 1.2 度内敛 (总斗鸡眼内敛角 2.4 度)
height_offset = 0.0015 # 1.5mm 机械制造高低差

board = bpy.data.objects.get('CalibrationBoard_11x9')
if not board:
    # 查找 mesh plane
    for obj in scene.objects:
        if 'CalibrationBoard' in obj.name or 'Plane' in obj.name:
            board = obj
            break

poses = [
    ( 0.00,  0.00,  0.00,   0,   0,   0),  # 正中水平
    (-0.06, -0.04,  0.04, -12,   8,   5),  # 左上微倾
    ( 0.06, -0.04,  0.04,  12,   8,  -5),  # 右上微倾
    (-0.06,  0.04, -0.04,  -8, -12,  -5),  # 左下微倾
    ( 0.06,  0.04, -0.04,   8, -12,   5),  # 右下微倾
    ( 0.00, -0.10,  0.00,   0,  15,   0),  # 近距离俯视
    ( 0.00,  0.10,  0.00,   0, -15,   0),  # 远距离仰视
    (-0.08,  0.00,  0.00, -16,   0,  10),  # 左偏
    ( 0.08,  0.00,  0.00,  16,   0, -10),  # 右偏
    ( 0.00,  0.00,  0.05,   0,  10,  15),  # 上偏自旋
    ( 0.00,  0.00, -0.05,   0, -10, -15),  # 下偏自旋
    ( 0.04, -0.05, -0.03,  10,  -6,  10),  # 综合偏角
]

for i, (px, py, pz, r_x, r_y, r_z) in enumerate(poses, start=1):
    if board:
        board.location = (px, py, pz)
        board.rotation_euler = (
            math.radians(-90 + r_x),
            math.radians(r_y),
            math.radians(r_z)
        )

    # 左相机: 向右内倾 +1.2 度 (局部 Y 轴)
    cam_obj.location = (base_cam_loc[0] - baseline/2.0, base_cam_loc[1], base_cam_loc[2])
    cam_obj.rotation_euler = (math.radians(90), toe_angle, 0)
    scene.render.filepath = str(calib_dir / f"left_{i:02d}.png")
    bpy.ops.render.render(write_still=True)

    # 右相机: 向左内倾 -1.2 度 + 1.5mm 高度差
    cam_obj.location = (base_cam_loc[0] + baseline/2.0, base_cam_loc[1], base_cam_loc[2] + height_offset)
    cam_obj.rotation_euler = (math.radians(90), -toe_angle, 0)
    scene.render.filepath = str(calib_dir / f"right_{i:02d}.png")
    bpy.ops.render.render(write_still=True)

    print(f"  [标定图对 {i:02d}/12 就绪] left_{i:02d}.png & right_{i:02d}.png")

print("  [√] 12 组非理想标定图对渲染完毕！")

# ==============================================================================
# 第二部分：在教室场景拍摄同一台“非理想斗鸡眼相机”下的课桌椅
# ==============================================================================
print("\n>>> [第二阶段] 在教室场景拍摄非理想双目课桌椅图对...")
bpy.ops.wm.open_mainfile(filepath=classroom_blend)
scene = bpy.context.scene
scene.render.resolution_x = 1280
scene.render.resolution_y = 1024
scene.render.image_settings.color_mode = 'RGB'
if hasattr(scene.cycles, 'samples'):
    scene.cycles.samples = 32

cam = scene.camera
cam.animation_data_clear()
for c in list(cam.constraints):
    cam.constraints.remove(c)
cam.scale = (1.0, 1.0, 1.0)
cam.data.dof.use_dof = False

desk_target = mathutils.Vector((0.1674, 0.0376, 0.4000))
center_loc = mathutils.Vector((0.1674, 1.4000, 0.8500))

# 计算基准朝向四元数
base_dir = desk_target - center_loc
base_rot = base_dir.to_track_quat('-Z', 'Y')

# 基准局部坐标系 (X: 右, Y: 上, Z: 后/光轴反向)
mat_base = base_rot.to_matrix()
right_vec = mat_base @ mathutils.Vector((1, 0, 0))
up_vec = mat_base @ mathutils.Vector((0, 1, 0))

# 1. 渲染左相机 (向左平移 32.5mm，光轴向内偏转 +1.2 度)
cam_l_loc = center_loc - right_vec * (0.065 / 2.0)
rot_l = base_rot.copy()
# 在局部 Y 轴 (Up) 上旋转 +toe_angle
q_yaw_l = mathutils.Quaternion(up_vec, toe_angle)
cam.location = cam_l_loc
cam.rotation_euler = (q_yaw_l @ rot_l).to_euler()
scene.render.filepath = str(desk_dir / "desk_raw_L.png")
bpy.ops.render.render(write_still=True)
print("  [√] 非理想课桌左图已就绪: desk_raw_L.png")

# 2. 渲染右相机 (向右平移 32.5mm + 上抬 1.5mm，光轴向内偏转 -1.2 度)
cam_r_loc = center_loc + right_vec * (0.065 / 2.0) + up_vec * height_offset
rot_r = base_rot.copy()
q_yaw_r = mathutils.Quaternion(up_vec, -toe_angle)
cam.location = cam_r_loc
cam.rotation_euler = (q_yaw_r @ rot_r).to_euler()
scene.render.filepath = str(desk_dir / "desk_raw_R.png")
bpy.ops.render.render(write_still=True)
print("  [√] 非理想课桌右图已就绪: desk_raw_R.png")

print("\n" + "="*70)
print("🎉 非理想几何物理数据渲染全部完成！")
print("="*70 + "\n")

