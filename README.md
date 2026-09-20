# 近红外双目手术导航追踪与三维视觉系统 (NIR Stereo Vision System)

面向医疗外科手术导航（骨科 / 神经外科）的高精度近红外（NIR）双目光学追踪系统，采用 **NDI Polaris / SciKit-Surgery** 同款亚像素光斑提取、极线立体几何三角交会与 Kabsch/Arun's SVD 6-DoF 刚体位姿估计路线。

---

## 🌟 核心特性 (Key Features)

1. **医疗级光学追踪管线**:
   - **亚像素提取**: 灰度加权质心法（Intensity-Weighted Centroid），斑点定位精度达 0.02 像素。
   - **极线三角交会**: 空间立体交会解算标记球毫米级 3D 绝对坐标。
   - **刚体位姿估计**: 基于 SVD 的 Kabsch 算法，自动求解手术器械 6-DoF 位姿 $[R|T]$，并推算针尖/刀尖（Tool-Tip）空间坐标。
   - **自适应排列匹配**: 自动处理视场中反光球乱序问题，实时输出配准残差（FRE）。
2. **软硬件彻底解耦（HAL 架构）**:
   - **宿舍离线开发 (Mock)**: 支持直接回放 Blender 物理仿真渲染图或录制序列。
   - **实验室实机联调 (Hikrobot)**: 深度封装海康威视（Hikrobot MVS）双目黑白工业相机，配置微秒级低曝光过滤可见光环境杂波。
3. **Blender 数字孪生实验室**:
   - 自动生成 11x9 20mm 物理标定板并批量渲染 12 组多姿态标定图对。
   - 提供 4 标记球探针物理仿真环境与绝对真值（Ground Truth）闭环精度评估。

---

## 📁 工程目录架构 (Project Structure)

```text
nir-stereo-vision/
├── configs/                            # [配置中心] 统一管理所有硬件、算法与器械参数
│   ├── calibration/                    # 标定结果 (受 Git 跟踪)
│   │   └── stereo_calib_params.json    # 相机内参、畸变、基线与极线校正投影矩阵
│   ├── cameras/                        # 相机硬件配置
│   │   ├── hikrobot_dual_mono.json     # 海康工业相机实机配置 (Mono8, 5000μs 曝光)
│   │   └── mock_camera.json            # 仿真回放相机参数
│   └── tools/                          # 手术器械 CAD 刚体几何定义
│       └── probe_4marker.json          # 4球探针局部坐标与针尖偏置
│
├── src/                                # [核心源码库]
│   ├── camera/                         # 硬件抽象层 (Base, Hik, Mock)
│   ├── calibration/                    # 双目相机几何标定算法
│   ├── tracking/                       # 核心：手术器械高精度追踪与 SVD 解算
│   └── stereo/                         # (备用) 稠密视差与点云重建
│
├── scripts/                            # [实用工具与仿真脚本]
│   └── blender/                        # Blender 自动化生成与批量渲染脚本
│
├── tests/                              # [自动化单元测试]
│   ├── test_svd_registration.py        # Kabsch 算法与乱序排列测试
│   └── test_optical_tracker.py         # 亚像素斑点提取与流水线测试
│
├── data/                               # [本地数据] (被 .gitignore 排除，防仓库膨胀)
├── main.py                             # 统一系统入口终端
├── requirements.txt                    # 依赖清单
└── README.md                           # 工程说明
```

---

## 🚀 快速上手 (Quick Start)

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 运行单元测试
```bash
python main.py test
```

### 3. 执行双目相机立体标定
```bash
python main.py calibrate
```
标定参数将自动更新写入 `configs/calibration/stereo_calib_params.json`。

### 4. 运行手术器械近红外追踪
- **模式 A：宿舍离线回放/仿真测试**
  ```bash
  python main.py track --camera mock
  ```
- **模式 B：实验室海康实机联调**
  ```bash
  python main.py track --camera hik
  ```

### 5. 稠密三维点云重建 (SGBM)
```bash
python main.py reconstruct --left data/calibration_images/left_01.png --right data/calibration_images/right_01.png
```
