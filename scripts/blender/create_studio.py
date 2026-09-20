import bpy
import os
import math

# 1. 清空默认物体，创建全新空场景
bpy.ops.wm.read_factory_settings(use_empty=True)

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
scene.cycles.samples = 16
scene.cycles.use_denoising = True

# 2. 设置分辨率 (1280x960 工业相机经典 4:3 比例)
scene.render.resolution_x = 1280
scene.render.resolution_y = 960
scene.render.resolution_percentage = 100

# 3. 开启双目立体设置
scene.render.use_multiview = True
scene.render.views_format = 'MULTIVIEW'

# 4. 纯净暗灰背景与柔和环境面光 (零背景杂质)
world = bpy.data.worlds.new('CleanStudioWorld')
scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get('Background')
if bg_node:
    bg_node.inputs['Color'].default_value = (0.20, 0.20, 0.20, 1.0)
    bg_node.inputs['Strength'].default_value = 1.0

# 大面积柔和主面光 (无影灯)
light_data = bpy.data.lights.new(name='SoftKeyLight', type='AREA')
light_data.energy = 200
light_data.size = 2.0
light_obj = bpy.data.objects.new(name='SoftKeyLight', object_data=light_data)
scene.collection.objects.link(light_obj)
light_obj.location = (0, -0.6, 1.0)
light_obj.rotation_euler = (math.radians(35), 0, 0)

# 5. 放置双目主相机 (60mm 基线，8mm 镜头，距离标定板约 0.7 米，让标定板占画面 50% 左右)
cam_data = bpy.data.cameras.new(name='StereoCam')
cam_data.lens = 8.0 # 8mm 镜头
cam_data.sensor_width = 7.2 # 1/1.8" 传感器尺寸
cam_data.stereo.convergence_mode = 'OFFAXIS'
cam_data.stereo.interocular_distance = 0.060 # 60mm 基线

cam_obj = bpy.data.objects.new(name='StereoCamera', object_data=cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

cam_obj.location = (0, -0.70, 0) # 0.70米拍摄距离，棋盘格清晰填满画面
cam_obj.rotation_euler = (math.radians(90), 0, 0)

# 6. 导入专属 11x9 20mm 标定板
obj_path = r'H:\antigravity\stereo vision\blender_assets\calibration_board\calibration_board_11x9_20mm.obj'
bpy.ops.wm.obj_import(filepath=obj_path)

board = None
for obj in scene.collection.objects:
    if 'CalibrationBoard' in obj.name:
        board = obj
        board.location = (0, 0, 0)
        board.rotation_euler = (math.radians(90), 0, 0)
        break

# 7. 为标定板绑定 Cycles 材质与棋盘格贴图节点 (确保黑白棋盘格 100% 渲染显示)
tex_img_path = r'H:\antigravity\stereo vision\blender_assets\calibration_board\chessboard_11x9_20mm.png'
mat = bpy.data.materials.new(name='BoardShaderMat')
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links

bsdf = nodes.get('Principled BSDF')
tex_node = nodes.new('ShaderNodeTexImage')
tex_node.image = bpy.data.images.load(tex_img_path)
links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.8 # 哑光表面

if board:
    board.data.materials.clear()
    board.data.materials.append(mat)

# 8. 保存工程
out_blend = r'H:\antigravity\stereo vision\blender_assets\calibration_board\calibration_studio.blend'
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print('>>> Clean Studio Blend saved successfully!')
