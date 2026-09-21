import bpy

blend_path = r"H:\antigravity\stereo vision\blender_assets\cameras\hikrobot_stereo_rig.blend"

# 1. 载入所有相机与机身物体
with bpy.data.libraries.load(blend_path) as (data_from, data_to):
    data_to.objects = data_from.objects

# 2. 链接到当前激活集合
collection = bpy.context.collection or bpy.context.scene.collection
for obj in data_to.objects:
    if obj.name not in collection.objects:
        collection.objects.link(obj)

# 3. 选中主根节点并设为活动物体
root = bpy.data.objects.get("Hikrobot_Stereo_Rig_Root")
if root:
    for o in bpy.context.selected_objects:
        o.select_set(False)
    root.select_set(True)
    bpy.context.view_layer.objects.active = root
    print("[√] 海康 MV-CU013-A0UM 双目相机已成功添加到当前场景中！")

