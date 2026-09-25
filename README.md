# 近红外双目手术导航追踪与三维视觉系统 (NIR Stereo Vision System)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-orange.svg)](https://pytorch.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.8%2B-green.svg)](https://opencv.org/)

面向微创外科手术导航与工业视觉引导的高精度近红外（NIR）双目视觉系统。兼备**亚毫米级近红外反光标记球 6-DoF 刚体定位追踪**与**大面积弱纹理场景高稠密三维点云重建**能力。

---

## 🌟 核心特性与技术架构 (Key Features)

### 1. 深度学习 SOTA 三维稠密点云重建 (GREAT-Stereo ICCV 2025)
- **内嵌前沿模型**：仓库直接内嵌整合了 ICCV 2025 前沿立体匹配模型 **GREAT-Stereo**（基于全局循环注意力与多尺度代价体），位于 `third_party/GREAT-Stereo`。
- **全稠密视差覆盖**：攻克传统匹配算法在白墙、平整台面、橱柜等弱纹理区域的视差空洞缺陷，实机测试达成 **100% 全稠密视差**覆盖，单帧重构 **125.6 万点**真实点云。
- **自适应显存保护桥接 (Adapter Bridge)**：通过 `src/stereo/great_adapter.py` 实现软硬件解耦与 4GB 显存保护机制（自动自适应下采样与 FP16 混合精度推理），在入门级显卡（如 GTX 1650 Ti）上安全流畅运行，不发生显存溢出。
- **双模态立体匹配**：支持深度学习（`great`）与传统经典算法（`sgbm`，OpenCV SGBM-HH + WLS 双向保边滤波）任意无缝切换。

### 2. 医疗级近红外刚体光学定位追踪 (Optical Tracking)
- **亚像素光斑提取**：采用灰度加权质心法（Intensity-Weighted Centroid），单标记球中心重复性可达 0.02 像素。
- **极线三角交会与 SVD 刚体配准**：利用空间立体交会与 Kabsch / Arun's SVD 算法，实时解算 4 球探针 6-DoF 空间位姿 $[R|T]$，并精准推算探针针尖空间瞬时坐标。
- **Blender 数字孪生验证**：在数字化 1:1 实木课桌模型上完成 30° 大摆幅进动基准测试（FRE 达 0.035 mm，针尖定点贴合误差 0.079 mm）。

### 3. 工业双目实机标定与极线校正 (Stereo Calibration)
- **海康威视实机**：基于海康工业近红外黑白全局快门相机（MV-CU013-A0UM，1280×960，12mm 定焦镜头，实测物理基线 60.01 mm）。
- **实测试验标定精度**：基于 11×9 (20mm) 平面标定板 12 组多姿态像对，重投影误差 **RMS = 0.077 px**（亚像素级几何对齐），构建严格共面行对齐极线映射查找表。

---

## 📁 协同开发代码目录结构 (Project Directory Structure)

```text
nir-stereo-vision/
├── configs/                            # [配置中心] 统一管理硬件、算法与器械配置
│   ├── calibration/                    # 标定结果配置文件
│   │   └── stereo_calib_params.json    # 实测相机内参、畸变、基线与校正矩阵
│   ├── cameras/                        # 相机硬件驱动配置 (Hikrobot 实机 / Mock 仿真)
│   ├── reconstruction/                 # 三维点云重建主配置文件
│   │   └── default.yaml                # 默认重建配置 (支持 sgbm / great 引擎切换)
│   └── tools/                          # 手术器械 CAD 刚体模型定义
│       └── probe_4marker.json          # 4 标记球局部坐标与针尖偏置
│
├── src/                                # [核心源码库]
│   ├── camera/                         # 相机硬件抽象层 (Base, Hikrobot MVS, Mock)
│   ├── calibration/                    # 张友祥标定法与极线校正算法
│   ├── tracking/                       # 近红外多球提取、立体交会与 SVD 刚体配准
│   └── stereo/                         # 稠密立体匹配与点云生成
│       ├── great_adapter.py            # 【核心桥梁】GREAT-Stereo 适配器 (显存自适应、接口统一)
│       ├── reconstructor.py            # 通用工业级点云重建引擎
│       └── stereo_matcher.py           # 传统 SGBM-HH + WLS 重建流水线
│
├── third_party/                        # [第三方算法库] (开箱即用，协作无门槛)
│   └── GREAT-Stereo/                   # ICCV 2025 SOTA 深度立体匹配网络
│       ├── models/                     # 神经网络结构 (GREAT-Stereo, IGEV)
│       ├── modules/                    # 注意力模块与循环更新块
│       ├── utils/                      # 张量变换与几何工具
│       └── checkpoints/                # 预训练权重文件 (58MB, 已纳入仓库)
│
├── scripts/                            # [工具与实验脚本]
│   ├── blender/                        # Blender 数字孪生与仿真动画脚本
│   ├── calibrate_hik_stereo.py         # 海康实机立体标定脚本
│   ├── generate_docx_weekly_report.py  # 符合中国科技报告国标的 Word 报告生成器
│   └── track_desk_probe_and_synthesize.py # 探针 30° 摆动追踪合成脚本
│
├── reports/                            # [归档技术报告] (规范 Word 报告归档)
│   └── 每周总结1.docx                  # 阶段综合技术总结报告 (严格国标排版、实测数据)
│
├── tests/                              # [自动化单元测试]
│   ├── test_svd_registration.py        # Kabsch 刚体配准与乱序匹配测试
│   └── test_optical_tracker.py         # 亚像素斑点提取测试
│
├── data/                               # [本地数据与产物] (点云输出位于 data/output/)
├── run_reconstruction.py               # 通用三维点云重建便捷执行入口
├── main.py                             # 统一系统终端入口 (标定/追踪/重建/测试)
├── requirements.txt                    # 团队协同环境依赖清单
└── README.md                           # 工程主说明文档
```

---

## 🛠️ 环境准备与快速上手 (Quick Start)

### 1. 克隆代码仓库 (Clone)
本仓库已将核心桥梁代码、标定参数与 GREAT-Stereo 模型网络直接包含，克隆后即可直接运行：
```bash
git clone https://github.com/yancypaul/nir-stereo-vision.git
cd nir-stereo-vision
```

### 2. 配置 Python 环境与安装依赖
推荐使用 Python 3.10+ 及 Conda 虚拟环境：
```bash
# 创建虚拟环境
conda create -n stereo python=3.10 -y
conda activate stereo

# 安装基础依赖
pip install -r requirements.txt

# 如需使用 GPU 运行 GREAT-Stereo，请根据本机 CUDA 版本安装 PyTorch (推荐 CUDA 12.1+):
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

### 3. 一键运行三维点云重建 (3D Reconstruction)

- **使用最新深度学习 GREAT-Stereo 引擎（推荐，弱纹理无空洞）：**
  ```bash
  python run_reconstruction.py --matcher great
  # 或者通过 main.py 执行
  python main.py reconstruct --left data/hik_left.png --right data/hik_right.png --matcher great
  ```
- **使用传统 CPU 算法（SGBM-HH + WLS）：**
  ```bash
  python run_reconstruction.py --matcher sgbm
  ```
  重建完成后，输出的 `model_*.ply` 三维点云、`disparity_*.png` 视差图与 `depth_*.png` 物理深度图将统一保存至 `data/output/hk_real_output/` 目录中，可直接拖入 **CloudCompare** 或 **MeshLab** 查验。

### 4. 运行近红外手术器械光学追踪 (Optical Tracking)
- **离线回放/仿真测试 (Mock 模式)：**
  ```bash
  python main.py track --camera mock
  ```
- **实验室海康工业相机实机联调 (Hik 模式)：**
  ```bash
  python main.py track --camera hik
  ```

### 5. 执行双目立体几何标定 (Calibration)
```bash
python main.py calibrate --images-dir data/calibration_images
```
解算完成的内参矩阵、畸变系数与外参基线将自动保存至 `configs/calibration/stereo_calib_params.json`。

### 6. 运行自动化单元测试 (Unit Tests)
```bash
python main.py test
```

---

## 📊 测量精度与物理规律客观说明

本工程秉持实事求是、科学严谨原则，严格区分实机实测与仿真测试：
1. **真实相机标定重投影误差**：$\text{RMS} = 0.07697\text{ px} \approx 0.077\text{ 像素}$，满足工业视觉立体标定合格要求（$< 0.1\text{ px}$），物理基线 $60.01\text{ mm}$。
2. **三维点云测距精度规律**：双目测距遵循光学三角交会几何定律 $\Delta Z \approx \frac{Z^2}{f \cdot B}\Delta d$。在 $f=1421.5\text{ px}, B=60.01\text{ mm}$ 条件下：
   - 近景工作区（$1.0\text{ m}$）：理论测距分辨率约为 **$1.2\text{ mm}$**；
   - 中景过渡区（$2.5\text{ m}$）：理论测距误差约为 **$7.3\text{ mm}$**；
   - 远景环境区（$3.5\text{ m} \sim 4.5\text{ m}$）：测距误差按距离平方放大至 **$1.4\text{ cm} \sim 2.4\text{ cm}$ 厘米级**。
3. **探针追踪精度**：在 Blender 数字孪生仿真理想条件下，探针 30° 摆幅定点贴合误差为 $0.079\text{ mm}$（FRE $0.035\text{ mm}$）；受物理反光球加工公差（约 $\pm 0.03\sim 0.05\text{ mm}$）与环境杂散光影响，物理实装后的实测精度预计在 $0.3\text{ mm} \sim 0.6\text{ mm}$。

---

## 👥 团队协作与贡献指南 (Collaboration)

1. **分支管理**：建议团队成员拉取独立特性分支进行开发：
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. **保持配置相对路径**：所有输入输出与权重配置均使用相对项目根目录的路径（如 `third_party/GREAT-Stereo/...`），严禁写入包含个人盘符的绝对路径，确保在不同操作系统（Windows / Linux）之间无缝协作。
3. **提交规范**：遵循规范的 Git Commit 消息规范（如 `feat: ...`, `fix: ...`, `docs: ...`）。

---

## 📄 开源许可证

本项目核心源码遵循 MIT License 协议。引用的第三方模型权重与算法遵循其各自开源许可证声明。
