import bpy
import os
import math
import json
from pathlib import Path
import numpy as np

# 推导工程路径
try:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
except Exception:
    PROJECT_ROOT = Path(os.getcwd())

out_dir = PROJECT_ROOT / "data" / "simulation"
tool_json_path = PROJECT_ROOT / "configs" / "tools" / "probe_4marker.json"
os.makedirs(out_dir, exist_ok=True)

with open(tool_json_path, "r", encoding="utf-8") as f:
    tool_def = json.load(f)

# 1. 初始化纯黑近红外环境
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
scene.cycles.samples = 32
scene.cycles.use_denoising = True

scene.render.resolution_x = 1280
scene.render.resolution_y = 960
scene.render.resolution_percentage = 100
scene.render.image_settings.color_mode = 'BW'

# 纯黑背景 (NIR 滤光片滤除可见光环境)
world = bpy.data.worlds.new('NIRWorld')
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    bg.inputs['Strength'].default_value = 0.0

# 2. 放置双目相机系统 (与标定暗室严格一致: 60mm 基线, 8mm 镜头)
cam_data = bpy.data.cameras.new('StereoCam')
cam_data.lens = 8.0
cam_data.sensor_width = 7.2
cam_obj = bpy.data.objects.new('StereoCamera', cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# 相机位于 (0, 0, 0), 朝向 +Y (即 Blender 中朝前)
# Blender 中相机的默认镜头朝 -Z，故需旋转 90 度让其朝 +Y
cam_base_loc = (0.0, 0.0, 0.0)
cam_obj.location = cam_base_loc
cam_obj.rotation_euler = (math.radians(90), 0, 0)
baseline = 0.060 # 60mm 基线

# 3. 创建反光球发光材质 (模拟主动近红外高亮反射球)
sphere_mat = bpy.data.materials.new(name="ReflectiveMarkerMat")
sphere_mat.use_nodes = True
nodes = sphere_mat.node_tree.nodes
links = sphere_mat.node_tree.links
nodes.clear()

node_emission = nodes.new(type='ShaderNodeEmission')
node_emission.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
node_emission.inputs['Strength'].default_value = 50.0

node_output = nodes.new(type='ShaderNodeOutputMaterial')
links.new(node_emission.outputs['Emission'], node_output.inputs['Surface'])

# 4. 创建手术探针刚体装配父对象 (Rig)
probe_rig = bpy.data.objects.new("SurgicalProbeRig", None)
scene.collection.objects.link(probe_rig)

# 根据 JSON 配置创建 4 个反光球
marker_radius_m = (tool_def["marker_diameter_mm"] / 2.0) / 1000.0 # 半径米
for m in tool_def["markers"]:
    pos_mm = m["position_local_mm"]
    pos_m = (pos_mm[0]/1000.0, pos_mm[1]/1000.0, pos_mm[2]/1000.0)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=marker_radius_m, segments=32, ring_count=16)
    sphere = bpy.context.active_object
    sphere.name = m["name"]
    sphere.location = pos_m
    sphere.data.materials.append(sphere_mat)
    sphere.parent = probe_rig

# 5. 设置探针在双目相机前方的位姿 (例如前方 650mm 处，带微倾角)
# 注意：Blender 相机坐标系: X 向右, Y 向上, 视线向 -Z (或绕X旋转90后视线向 +Y)
probe_x_m = 0.015   # 右偏 15mm
probe_y_m = 0.650   # 相机正前方 650mm
probe_z_m = -0.020  # 下方 20mm
probe_rig.location = (probe_x_m, probe_y_m, probe_z_m)
probe_rig.rotation_euler = (math.radians(10), math.radians(15), math.radians(-25))

# 强制更新 Blender 依赖图以计算世界变换矩阵
bpy.context.view_layer.update()

# 6. 计算真值 (Ground Truth): 各标记球与针尖在左相机坐标系下的 3D 坐标 (mm)
# 左相机位于 (-0.030, 0, 0)
left_cam_loc = np.array([-baseline / 2.0, 0.0, 0.0])

# 获取探针世界变换矩阵
rig_mat = np.array(probe_rig.matrix_world)

# 针尖本地坐标 (米)
tip_local_m = np.array([
    tool_def["tool_tip_offset_mm"][0] / 1000.0,
    tool_def["tool_tip_offset_mm"][1] / 1000.0,
    tool_def["tool_tip_offset_mm"][2] / 1000.0,
    1.0
])
tip_world = np.dot(rig_mat, tip_local_m)[:3]

# 转换到计算机视觉标准相机坐标系 (X向右, Y向下, Z沿光轴向深处)
# Blender 世界坐标: X右, Y深处(前), Z上
# 对应 CV 坐标: X_cv = X_blender - X_cam, Y_cv = -(Z_blender - Z_cam), Z_cv = Y_blender - Y_cam
def blender_to_cv_left(blender_pt_m):
    x_cv = float((blender_pt_m[0] - left_cam_loc[0]) * 1000.0)
    y_cv = float(-(blender_pt_m[2] - left_cam_loc[2]) * 1000.0)
    z_cv = float((blender_pt_m[1] - left_cam_loc[1]) * 1000.0)
    return [round(x_cv, 4), round(y_cv, 4), round(z_cv, 4)]

tip_gt_cv = blender_to_cv_left(tip_world)

# 保存真值元数据
gt_info = {
    "description": "Blender 数字孪生近红外手术探针测试帧绝对真值 (Ground Truth)",
    "tip_ground_truth_mm": tip_gt_cv,
    "probe_rig_location_m": list(probe_rig.location),
    "probe_rig_rotation_deg": [math.degrees(r) for r in probe_rig.rotation_euler]
}

gt_save_path = str(out_dir / "probe_ground_truth.json")
with open(gt_save_path, "w", encoding="utf-8") as f:
    json.dump(gt_info, f, indent=4, ensure_ascii=False)

print(f"\n>>> 探针世界姿态已就绪，针尖左眼真实坐标: {tip_gt_cv} mm")

# 7. 渲染左相机图像
cam_obj.location = (cam_base_loc[0] - baseline/2.0, cam_base_loc[1], cam_base_loc[2])
scene.render.filepath = str(out_dir / "probe_test_01_L.png")
bpy.ops.render.render(write_still=True)
print(f"  [√] 左相机图像渲染完成: {scene.render.filepath}")

# 8. 渲染右相机图像
cam_obj.location = (cam_base_loc[0] + baseline/2.0, cam_base_loc[1], cam_base_loc[2])
scene.render.filepath = str(out_dir / "probe_test_01_R.png")
bpy.ops.render.render(write_still=True)
print(f"  [√] 右相机图像渲染完成: {scene.render.filepath}")

# 重置相机
cam_obj.location = cam_base_loc
print(f"\n>>> 仿真测试图对生成完毕！已就绪供追踪算法测试验证。\n")

