import bpy

l_cam = bpy.data.objects.get('Hikrobot_Left_Cam')
r_cam = bpy.data.objects.get('Hikrobot_Right_Cam')

if l_cam and r_cam:
    # 1. 右相机刚性焊接绑定在左相机上 (基线 60mm)
    r_cam.parent = l_cam
    r_cam.location = (0.060, 0, 0)
    r_cam.rotation_euler = (0, 0, 0)

    # 2. 机身与镜筒全部焊接在左相机上
    parts = [
        ('Hikrobot_Left_Cam_Body', (0, -0.015, 0)),
        ('Hikrobot_Left_Cam_Lens_Barrel', (0, 0.0125, 0)),
        ('Hikrobot_Right_Cam_Body', (0.060, -0.015, 0)),
        ('Hikrobot_Right_Cam_Lens_Barrel', (0.060, 0.0125, 0))
    ]
    for name, offset in parts:
        obj = bpy.data.objects.get(name)
        if obj:
            obj.parent = l_cam
            obj.location = offset
            obj.rotation_euler = (0, 0, 0)

    # 3. 选中左相机并设为主相机
    for o in bpy.context.selected_objects:
        o.select_set(False)
    l_cam.select_set(True)
    bpy.context.view_layer.objects.active = l_cam
    bpy.context.scene.camera = l_cam

    print("=" * 55)
    print("[√] 海康双目相机已完美刚性锁定！基线严密锁定为 60.0 mm！")
    print("    以后只需移动/旋转左相机，右相机 100% 自动同步跟随！")
    print("=" * 55)

