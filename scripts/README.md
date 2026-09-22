# 脚本与管线功能索引 (Scripts Directory Guide)

本目录包含海康双目相机仿真、Blender 光追合成采集与三维立体匹配点云重建的完整脚本库。

---

## 📂 目录结构与执行入口

### 1. 核心三维双目匹配与点云融合脚本 (`scripts/`)

| 脚本文件 | 功能说明 | 对应输出成果 |
| :--- | :--- | :--- |
| **`reconstruct_single_desk_orbit.py`** | **★ 8机位 360° 环绕微米级融合**：针对单套课桌椅，加载 8 个环绕视角图对，采用 SGBM-HH 8方向匹配 + 引导滤波平滑 + 3mm 微体素融合。 | `data/output/pointcloud/single_desk/single_desk_orbit_360.ply` |
| **`reconstruct_multiview_fusion.py`** | **★ 全教室 4 机位大场景刚体融合**：加载教室 4 个主站图对与位姿矩阵，融合生成全教室 360° 点云并自动裁切生成“室内桌椅专注版”。 | `data/output/pointcloud/classroom/classroom_interior_focused.ply` |
| **`reconstruct_single_desk_smooth.py`** | 单课桌前/后双向平滑验证脚本（消除了阶梯效应与梯田断层）。 | `data/output/pointcloud/single_desk/single_desk_smooth.ply` |
| **`reconstruct_hikrobot.py`** | 海康双目单视角基础三维点云重建基准脚本。 | `data/output/pointcloud/classroom/hik_classroom_pointcloud.ply` |
| **`reconstruct_classroom.py`** | 早期单目立体匹配验证脚本（历史基准）。 | `data/output/pointcloud/classroom/classroom_pointcloud.ply` |

---

### 2. Blender Cycles 数据自动化采集脚本 (`scripts/blender/`)

在 Blender 命令行模式（Headless）下自动运行，负责物理相机定位、位姿矩阵记录与左右眼物理双目光追渲染：

| 脚本文件 | 用途 |
| :--- | :--- |
| **`capture_single_desk_orbit.py`** | **8 机位环绕采集**：围绕第一排中间一体课桌椅 `chair.019`，按圆周 45° 间隔生成 8 个俯视机位，输出图对至 `data/single_desk_orbit/`。 |
| **`capture_multiview_stations.py`** | **全教室 4 大主视角采集**：讲台前视、后视、左侧视、右侧视，输出图对至 `data/multiview_stations/`。 |
| **`capture_single_desk.py`** | 单课桌正前/正后两站采集脚本。 |
| **`create_hikrobot_stereo_rig.py`** | 在 Blender 中创建符合海康相机真实参数的虚拟物理双目相机 Rig。 |
| **`lock_stereo_rig.py`** | 固化双目相机的平行光轴与立体会聚约束。 |
| **`render_calibration_dataset.py`** | 自动生成多姿态棋盘格标定板图对（用于 OpenCV 立体标定）。 |

