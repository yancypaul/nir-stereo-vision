import bpy
import os
from pathlib import Path

# 1. 确定工程输出目录
out_dir = Path(r"H:\antigravity\stereo vision\data\simulation")
out_dir.mkdir(parents=True, exist_ok=True)

left_img_path = str(out_dir / "my_hik_left.png")
right_img_path = str(out_dir / "my_hik_right.png")

scene = bpy.context.scene

# 2. 锁定海康 1280x1024 黑白相机参数
scene.render.resolution_x = 1280
scene.render.resolution_y = 1024
scene.render.image_settings.color_mode = 'BW' # 纯黑白 Mono8
scene.render.image_settings.file_format = 'PNG'

# 3. 拍摄左目 (Hikrobot_Left_Cam)
print(">>> 正在采集海康左目画面 (Left Eye)...")
scene.camera = bpy.data.objects.get("Hikrobot_Left_Cam")
scene.render.filepath = left_img_path
bpy.ops.render.render(write_still=True)

# 4. 拍摄右目 (Hikrobot_Right_Cam)
print(">>> 正在采集海康右目画面 (Right Eye)...")
scene.camera = bpy.data.objects.get("Hikrobot_Right_Cam")
scene.render.filepath = right_img_path
bpy.ops.render.render(write_still=True)

print("\n" + "="*55)
print("[√] 海康双目立体图像对采集成功！")
print(f"  左目图像: {left_img_path}")
print(f"  右目图像: {right_img_path}")
print("="*55 + "\n")

