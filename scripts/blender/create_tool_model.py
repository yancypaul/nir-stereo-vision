import bpy
import os
import json
import math
from pathlib import Path
import numpy as np

try:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
except Exception:
    PROJECT_ROOT = Path(os.getcwd())

tool_json_path = PROJECT_ROOT / "configs" / "tools" / "probe_4marker.json"
out_blend = str(PROJECT_ROOT / "blender_assets" / "tools" / "probe_tool.blend")
out_obj = str(PROJECT_ROOT / "blender_assets" / "tools" / "probe_tool.obj")

os.makedirs(os.path.dirname(out_blend), exist_ok=True)

with open(tool_json_path, "r", encoding="utf-8") as f:
    tool_def = json.load(f)

# 1. 创建全新场景
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# 2. 材质定义
# 反光球高反光/发光材质
mat_sphere = bpy.data.materials.new(name="NIR_Reflective_Sphere_Mat")
mat_sphere.use_nodes = True
bsdf_sphere = mat_sphere.node_tree.nodes.get("Principled BSDF")
if bsdf_sphere:
    bsdf_sphere.inputs["Base Color"].default_value = (0.95, 0.95, 0.95, 1.0)
    bsdf_sphere.inputs["Metallic"].default_value = 0.2
    bsdf_sphere.inputs["Roughness"].default_value = 0.1
    # 增加微弱自发光方便观察
    if "Emission Color" in bsdf_sphere.inputs:
        bsdf_sphere.inputs["Emission Color"].default_value = (0.8, 0.8, 0.8, 1.0)
        bsdf_sphere.inputs["Emission Strength"].default_value = 2.0

# 手术器械金属/碳纤维手柄材质 (暗银黑)
mat_handle = bpy.data.materials.new(name="Tool_Metal_Body_Mat")
mat_handle.use_nodes = True
bsdf_handle = mat_handle.node_tree.nodes.get("Principled BSDF")
if bsdf_handle:
    bsdf_handle.inputs["Base Color"].default_value = (0.08, 0.08, 0.09, 1.0)
    bsdf_handle.inputs["Metallic"].default_value = 0.9
    bsdf_handle.inputs["Roughness"].default_value = 0.3

# 针尖高亮警示材质 (医疗金/红)
mat_tip = bpy.data.materials.new(name="Tip_Gold_Mat")
mat_tip.use_nodes = True
bsdf_tip = mat_tip.node_tree.nodes.get("Principled BSDF")
if bsdf_tip:
    bsdf_tip.inputs["Base Color"].default_value = (0.9, 0.7, 0.1, 1.0)
    bsdf_tip.inputs["Metallic"].default_value = 0.8

# 3. 创建器械刚体根节点
tool_root = bpy.data.objects.new("Surgical_Probe", None)
scene.collection.objects.link(tool_root)

# 4. 生成 4 个反光标记球 (物理尺寸 12mm 直径 = 6mm 半径)
marker_radius_m = (tool_def["marker_diameter_mm"] / 2.0) / 1000.0
marker_positions_m = []

for m in tool_def["markers"]:
    pos_mm = m["position_local_mm"]
    # 转换为米 (Blender 默认单位)
    pos_m = (pos_mm[0]/1000.0, pos_mm[1]/1000.0, pos_mm[2]/1000.0)
    marker_positions_m.append(pos_m)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=marker_radius_m, segments=32, ring_count=16, location=pos_m)
    sphere = bpy.context.active_object
    sphere.name = f"Marker_{m['id']}_{m['name']}"
    sphere.data.materials.append(mat_sphere)
    sphere.parent = tool_root

# 5. 生成刚体连接支架 (Frame Bracket - 骨科导航器械常见三角叉结构)
# 将 Marker 1 分别与 Marker 2, 3, 4 用细金属杆连接
def add_strut(p1, p2, radius=0.002, mat=mat_handle, name="Strut"):
    v1 = np.array(p1)
    v2 = np.array(p2)
    diff = v2 - v1
    length = np.linalg.norm(diff)
    if length < 1e-5:
        return None
    center = (v1 + v2) / 2.0
    
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=length, location=center)
    cyl = bpy.context.active_object
    cyl.name = name
    cyl.data.materials.append(mat)
    cyl.parent = tool_root

    # 定向圆柱体
    phi = math.atan2(diff[1], diff[0])
    theta = math.acos(diff[2] / length)
    cyl.rotation_euler = (0, theta, phi)
    return cyl

# 支架连线
add_strut(marker_positions_m[0], marker_positions_m[1], radius=0.0025, name="Strut_1_2")
add_strut(marker_positions_m[0], marker_positions_m[2], radius=0.0025, name="Strut_1_3")
add_strut(marker_positions_m[1], marker_positions_m[3], radius=0.0025, name="Strut_2_4")
add_strut(marker_positions_m[2], marker_positions_m[3], radius=0.0025, name="Strut_3_4")

# 6. 生成手术探针金属杆与针尖 (Needle Shaft & Tip)
tip_offset_mm = tool_def["tool_tip_offset_mm"]
tip_pos_m = (tip_offset_mm[0]/1000.0, tip_offset_mm[1]/1000.0, tip_offset_mm[2]/1000.0)

# 从 Marker 1 连接到针尖
add_strut(marker_positions_m[0], tip_pos_m, radius=0.002, mat=mat_handle, name="Probe_Needle_Shaft")

# 在针尖处放置一个小圆锥作为指针尖锐点
v_shaft = np.array(tip_pos_m) - np.array(marker_positions_m[0])
l_shaft = np.linalg.norm(v_shaft)
bpy.ops.mesh.primitive_cone_add(radius1=0.002, radius2=0.0002, depth=0.015, location=tip_pos_m)
cone = bpy.context.active_object
cone.name = "Needle_Tip_Pointer"
cone.data.materials.append(mat_tip)
cone.parent = tool_root

# 7. 添加观察摄像机与灯光
cam_data = bpy.data.cameras.new(name="PreviewCamera")
cam_data.lens = 35.0
cam_obj = bpy.data.objects.new("PreviewCamera", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj
cam_obj.location = (0.25, -0.30, 0.20)
cam_obj.rotation_euler = (math.radians(65), 0, math.radians(45))

light_data = bpy.data.lights.new(name="SunLight", type="SUN")
light_data.energy = 4.0
light_obj = bpy.data.objects.new("SunLight", light_data)
scene.collection.objects.link(light_obj)
light_obj.rotation_euler = (math.radians(45), math.radians(30), 0)

# 8. 保存 .blend 文件与导出 .obj 格式
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print(f">>> 手术器械 3D 模型已生成并保存至:")
print(f"  - Blender 工程: {out_blend}")

try:
    bpy.ops.wm.obj_export(filepath=out_obj)
    print(f"  - 通用 3D OBJ 文件: {out_obj}")
except Exception:
    pass

