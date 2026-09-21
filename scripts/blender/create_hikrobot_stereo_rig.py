import bpy
import os
import math
from pathlib import Path

# 自动推导工程根目录
try:
    SCRIPT_PATH = Path(__file__).resolve()
    PROJECT_ROOT = SCRIPT_PATH.parents[2]
except Exception:
    PROJECT_ROOT = Path(os.getcwd())

out_dir = PROJECT_ROOT / "blender_assets" / "cameras"
out_dir.mkdir(parents=True, exist_ok=True)
out_blend = str(out_dir / "hikrobot_stereo_rig.blend")

# 1. 初始化空场景
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 32

# 2. 设置海康 MV-CU013-A0UM 真实物理参数
RESOLUTION_X = 1280
RESOLUTION_Y = 1024
PIXEL_SIZE_UM = 4.8            # 4.8 微米像元
SENSOR_WIDTH_MM = 1280 * 0.0048   # 6.144 mm
SENSOR_HEIGHT_MM = 1024 * 0.0048  # 4.9152 mm
LENS_FOCAL_MM = 12.0          # 12mm C口镜头
BASELINE_M = 0.060             # 60mm 双目基线 (0.06m)
THEORETICAL_FX_PX = (LENS_FOCAL_MM / SENSOR_WIDTH_MM) * RESOLUTION_X # 2500.0 px

scene.render.resolution_x = RESOLUTION_X
scene.render.resolution_y = RESOLUTION_Y
scene.render.pixel_aspect_x = 1.0
scene.render.pixel_aspect_y = 1.0
scene.render.resolution_percentage = 100

# 3. 创建材质：工业黑色磨砂机身与高反金属接环
mat_body = bpy.data.materials.new(name="Hik_Anodized_Metal")
mat_body.use_nodes = True
bsdf_body = mat_body.node_tree.nodes.get("Principled BSDF")
if bsdf_body:
    bsdf_body.inputs["Base Color"].default_value = (0.04, 0.04, 0.05, 1.0) # 暗黑深灰铝合金
    bsdf_body.inputs["Metallic"].default_value = 0.85
    bsdf_body.inputs["Roughness"].default_value = 0.35

mat_ring = bpy.data.materials.new(name="Hik_Lens_Ring")
mat_ring.use_nodes = True
bsdf_ring = mat_ring.node_tree.nodes.get("Principled BSDF")
if bsdf_ring:
    bsdf_ring.inputs["Base Color"].default_value = (0.8, 0.1, 0.05, 1.0) # 海康经典红色标识圈
    bsdf_ring.inputs["Metallic"].default_value = 0.2
    bsdf_ring.inputs["Roughness"].default_value = 0.3

# 4. 创建双目主挂载节点 (Rig Root)
rig_root = bpy.data.objects.new(name="Hikrobot_Stereo_Rig_Root", object_data=None)
rig_root.empty_display_type = 'ARROWS'
rig_root.empty_display_size = 0.05
scene.collection.objects.link(rig_root)

# 5. 分别创建左相机与右相机的光学参数与 1:1 机身外壳
cameras_info = [
    {"name": "Hikrobot_Left_Cam", "x": -BASELINE_M / 2.0, "role": "LEFT"},
    {"name": "Hikrobot_Right_Cam", "x": +BASELINE_M / 2.0, "role": "RIGHT"}
]

for cam_info in cameras_info:
    # 5.1 创建 Blender 相机核心数据
    cam_data = bpy.data.cameras.new(name=cam_info["name"] + "_Data")
    cam_data.sensor_fit = 'HORIZONTAL'
    cam_data.sensor_width = SENSOR_WIDTH_MM
    cam_data.sensor_height = SENSOR_HEIGHT_MM
    cam_data.lens = LENS_FOCAL_MM
    cam_data.clip_start = 0.1
    cam_data.clip_end = 20.0
    cam_data.display_size = 0.03

    cam_obj = bpy.data.objects.new(name=cam_info["name"], object_data=cam_data)
    cam_obj.location = (cam_info["x"], 0, 0)
    cam_obj.rotation_euler = (math.radians(90), 0, 0) # 镜头朝向 +Y 轴正前方
    cam_obj.parent = rig_root
    scene.collection.objects.link(cam_obj)

    # 5.2 模拟 29mm x 29mm x 30mm 真实机身实体
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    body_obj = bpy.context.active_object
    body_obj.name = f"{cam_info['name']}_Body"
    body_obj.scale = (0.029 / 2.0, 0.030 / 2.0, 0.029 / 2.0) # 半径
    body_obj.location = (cam_info["x"], -0.015, 0)            # 光心在前端，机身向后延展
    body_obj.data.materials.append(mat_body)
    body_obj.parent = rig_root

    # 5.3 模拟 12mm C口镜头镜筒
    bpy.ops.mesh.primitive_cylinder_add(radius=0.014, depth=0.025)
    lens_obj = bpy.context.active_object
    lens_obj.name = f"{cam_info['name']}_Lens_Barrel"
    lens_obj.rotation_euler = (math.radians(90), 0, 0)
    lens_obj.location = (cam_info["x"], 0.0125, 0)            # 镜头向前延伸
    lens_obj.data.materials.append(mat_body)
    lens_obj.data.materials.append(mat_ring)
    lens_obj.parent = rig_root

# 6. 保存为独立的 .blend 资产库
bpy.ops.wm.save_as_mainfile(filepath=out_blend)

print(f"\n=======================================================")
print(f"[√] 成功生成海康威视 MV-CU013-A0UM 物理级双目数字孪生！")
print(f"  分辨率: {RESOLUTION_X} x {RESOLUTION_Y} (像元 {PIXEL_SIZE_UM} um)")
print(f"  靶面尺寸: {SENSOR_WIDTH_MM:.3f} mm x {SENSOR_HEIGHT_MM:.3f} mm (1/2 英寸)")
print(f"  镜头焦距: {LENS_FOCAL_MM} mm C-Mount")
print(f"  理论像素焦距 fx/fy: {THEORETICAL_FX_PX:.2f} px")
print(f"  立体基线: {BASELINE_M * 1000.0:.1f} mm")
print(f"  保存文件: {out_blend}")
print(f"=======================================================\n")
