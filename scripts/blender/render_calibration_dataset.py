import bpy
import os
import math

# 1. 创建纯净标定环境
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
scene.cycles.samples = 16
scene.cycles.use_denoising = True

scene.render.resolution_x = 1280
scene.render.resolution_y = 960
scene.render.resolution_percentage = 100
scene.render.image_settings.color_mode = 'BW'

out_dir = r"H:\antigravity\stereo vision\data\calibration_images"
os.makedirs(out_dir, exist_ok=True)

# 纯色背景
world = bpy.data.worlds.new('CleanStudioWorld')
scene.world = world
bg = world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.22, 0.22, 0.22, 1.0)

# 柔和面光源 (无反光倒影)
l_data = bpy.data.lights.new('SoftLight', 'AREA')
l_data.energy = 300
l_data.size = 2.5
l_obj = bpy.data.objects.new('SoftLight', l_data)
scene.collection.objects.link(l_obj)
l_obj.location = (0, -0.6, 1.0)
l_obj.rotation_euler = (math.radians(35), 0, 0)

# 相机 (8mm 镜头, 1/1.8" 传感器, 基线 60mm)
cam_data = bpy.data.cameras.new('StereoCam')
cam_data.lens = 8.0
cam_data.sensor_width = 7.2
cam_obj = bpy.data.objects.new('StereoCamera', cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

base_cam_loc = (0, -0.70, 0) # 0.70 米拍摄距离
cam_obj.location = base_cam_loc
cam_obj.rotation_euler = (math.radians(90), 0, 0)
baseline = 0.060 # 60mm

# 创建原生高精度 11x9 20mm 标定板实体 (0.28m x 0.24m)
bpy.ops.mesh.primitive_plane_add(size=1.0)
board = bpy.context.active_object
board.name = 'CalibrationBoard_11x9'
board.scale = (0.28, 0.24, 1.0)
bpy.ops.object.transform_apply(scale=True)

# 赋予黑白棋盘格材质
tex_path = r'H:\antigravity\stereo vision\blender_assets\calibration_board\chessboard_11x9_20mm.png'
mat = bpy.data.materials.new('ChessboardMaterial')
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get('Principled BSDF')
tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
tex_node.image = bpy.data.images.load(tex_path)
mat.node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.6
board.data.materials.append(mat)

# 保存 .blend 文件供用户随时在 Blender 里打开查看
studio_blend = r'H:\antigravity\stereo vision\blender_assets\calibration_board\calibration_studio.blend'
bpy.ops.wm.save_as_mainfile(filepath=studio_blend)

# 12 组真实的标定板空间姿态 (倾斜、俯仰、微旋、远近、偏角)
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

print(f">>> 开始批量渲染 {len(poses)} 组双目标定图片对 (纯净背景 + 亚像素棋盘格)...")

right_vec = (1.0, 0.0, 0.0) # 水平 X 轴为相机平移方向

for i, (px, py, pz, r_x, r_y, r_z) in enumerate(poses, start=1):
    board.location = (px, py, pz)
    board.rotation_euler = (
        math.radians(-90 + r_x),
        math.radians(r_y),
        math.radians(r_z)
    )

    # 1. 渲染左相机 (X 偏 -30mm)
    cam_obj.location = (base_cam_loc[0] - baseline/2.0, base_cam_loc[1], base_cam_loc[2])
    scene.render.filepath = os.path.join(out_dir, f"left_{i:02d}.png")
    bpy.ops.render.render(write_still=True)

    # 2. 渲染右相机 (X 偏 +30mm)
    cam_obj.location = (base_cam_loc[0] + baseline/2.0, base_cam_loc[1], base_cam_loc[2])
    scene.render.filepath = os.path.join(out_dir, f"right_{i:02d}.png")
    bpy.ops.render.render(write_still=True)

    print(f"[{i:02d}/{len(poses):02d}] 成功渲染标定图对: left_{i:02d}.png & right_{i:02d}.png")

cam_obj.location = base_cam_loc
print(f"\n>>> 12 组全姿态标定图集渲染全部完成！保存至: {out_dir}")
