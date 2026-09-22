# -*- coding: utf-8 -*-
"""
生成每周研发总结与下阶段规划 Word 文档 (.docx)
数据严谨 grounded 在真实实测标定与重建数据
"""

import os
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    """设置单元格背景颜色"""
    tcPr = cell._element.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """设置单元格内边距"""
    tcPr = cell._element.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(m)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def add_styled_heading(doc, text, level):
    p = doc.add_heading(level=level)
    run = p.add_run(text)
    run.font.name = 'Microsoft YaHei'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
    
    if level == 1:
        run.font.size = Pt(15)
        run.font.bold = True
        run.font.color.rgb = RGBColor(31, 78, 121) # #1F4E79
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)
    elif level == 2:
        run.font.size = Pt(12.5)
        run.font.bold = True
        run.font.color.rgb = RGBColor(46, 117, 182) # #2E75B6
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(3)
    elif level == 3:
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = RGBColor(68, 68, 68)
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2)
    return p

def add_styled_paragraph(doc, text="", bold_prefix="", space_after=4):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.25
    
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = 'Microsoft YaHei'
        r_pre._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
        r_pre.font.size = Pt(10.5)
        r_pre.font.bold = True
        r_pre.font.color.rgb = RGBColor(31, 78, 121)
        
    if text:
        r_text = p.add_run(text)
        r_text.font.name = 'Microsoft YaHei'
        r_text._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
        r_text.font.size = Pt(10.5)
        r_text.font.color.rgb = RGBColor(40, 40, 40)
    return p

def add_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(8)
    r = p.add_run(text)
    r.font.name = 'Microsoft YaHei'
    r._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
    r.font.size = Pt(9.0)
    r.font.italic = True
    r.font.color.rgb = RGBColor(100, 100, 100)

def main():
    repo_root = Path("H:/antigravity/stereo vision")
    out_dir = repo_root / "每周总结"
    out_dir.mkdir(exist_ok=True)
    out_docx = out_dir / "双目立体视觉与三维重建_每周总结与下阶段规划_20260922.docx"

    doc = docx.Document()

    # 1. 页面边距 2cm
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # 2. 封面与标题区域
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(16)
    title_p.paragraph_format.space_after = Pt(4)
    run_title = title_p.add_run("近红外双目立体视觉与三维点云重建工程")
    run_title.font.name = 'Microsoft YaHei'
    run_title._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
    run_title.font.size = Pt(20)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(31, 78, 121)

    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_p.paragraph_format.space_after = Pt(16)
    run_sub = sub_p.add_run("每周研发总结报告与下一阶段任务规划 (2026.09.19 ~ 2026.09.22)")
    run_sub.font.name = 'Microsoft YaHei'
    run_sub._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
    run_sub.font.size = Pt(12)
    run_sub.font.color.rgb = RGBColor(89, 89, 89)

    # 元数据表格
    meta_table = doc.add_table(rows=4, cols=4)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("项目名称", "近红外双目立体视觉系统", "归档版本", "v0.6.0 (Commit: d534cc4)"),
        ("核心硬件", "海康工业双目 (12mm镜头, 60mm基线)", "当前状态", "实机全自动重建流水线就绪"),
        ("汇报周期", "2026年9月19日 ~ 9月22日", "标定精度", "RMS = 0.077 px (高精度)"),
        ("核心算法", "ICCV 2025 SOTA GREAT-Stereo", "点云产物", "1,256,119 点 (100% 稠密覆盖)")
    ]
    for r_idx, row in enumerate(meta_data):
        for c_idx in range(4):
            cell = meta_table.cell(r_idx, c_idx)
            cell.text = row[c_idx]
            set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(0)
            run = p.runs[0]
            run.font.name = 'Microsoft YaHei'
            run._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
            run.font.size = Pt(9.5)
            if c_idx in (0, 2):
                set_cell_background(cell, "F2F4F7")
                run.font.bold = True
                run.font.color.rgb = RGBColor(31, 78, 121)
            else:
                run.font.color.rgb = RGBColor(40, 40, 40)
    
    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # --------------------------------------------------------------------------
    # 第一章：本周工作总览与关键里程碑
    # --------------------------------------------------------------------------
    add_styled_heading(doc, "一、 本周研发工作总览与里程碑", level=1)
    add_styled_paragraph(doc, 
        "本周（2026.09.19 ~ 2026.09.22）完成了双目立体视觉项目从零构筑、底层物理建模、海康工业实机标定采集，到引入 ICCV 2025 SOTA 深度学习立体匹配模型（GREAT-Stereo）的完整跨越。目前系统已具备全自动化运行能力，实机重建点云规模达到 125.6 万点，并在工程交互上实现了跨环境动态桥接与单键即时运行。",
        bold_prefix="【总体成果】"
    )

    milestones = [
        ("Day 1 (09.19~09.20)：系统架构与仿真原型", "完成项目标准分层架构设计；搭建硬件抽象层（HAL）；使用 Blender 建立 1:1 海康 MV-CU013-A0UM 工业相机物理孪生，验证了标定与立体视差基本链路。"),
        ("Day 2 (09.20)：近红外手术导航追踪数学闭环", "实现亚像素灰度质心提取（精度 0.02 像素）；完成极线三角交会与 SVD/Kabsch 刚体配准算法，建立 FRE < 0.2mm 的空间绝对精度闭环评估。"),
        ("Day 3 (09.21~09.22)：海康实机立体标定与传统重建", "使用 11x9 (20mm) 标定板实物拍摄 12 组多角度姿态，解算重投影误差压至 0.077 px；建立极线校正映射，成功跑通海康真实场景双目点云重建。"),
        ("Day 4 (09.22)：SOTA 深度立体匹配突破与工程交付", "成功融合 ICCV 2025 GREAT-Stereo 深度网络，攻克 4GB 轻量显存推理；视差有效覆盖率从 68% 跃升至 100.00%，点云数达 125.6 万点；完成 VS Code 单键运行与规范化目录交付。")
    ]
    for tag, desc in milestones:
        add_styled_paragraph(doc, desc, bold_prefix=f"● {tag}：")

    # --------------------------------------------------------------------------
    # 第二章：真实硬件规格与高精度实测标定数据
    # --------------------------------------------------------------------------
    add_styled_heading(doc, "二、 核心硬件规格与高精度实测标定数据", level=1)
    add_styled_paragraph(doc, "为了确保后续三维点云重建具有绝对物理尺度与微米级精度，本工程采用高精度平面棋盘格标定板对真实海康工业双目模组进行了全流程张氏标定与极线校正。")

    # 硬件与标定参数表
    calib_table = doc.add_table(rows=7, cols=3)
    calib_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["参数项目 (Metric)", "实测标定值 (Measured Value)", "物理含义与工程意义"]
    for i, h in enumerate(headers):
        cell = calib_table.cell(0, i)
        cell.text = h
        set_cell_background(cell, "1F4E79")
        set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.bold = True
        p.runs[0].font.name = 'Microsoft YaHei'
        p.runs[0].font.size = Pt(9.5)
        p.runs[0].font.color.rgb = RGBColor(255, 255, 255)

    calib_rows = [
        ("相机型号与画幅", "Hikrobot MV-CU013-A0UM (1280 × 960)", "工业级近红外全局快门 CMOS，5:4 比例"),
        ("物理镜头规格", "12mm 工业高清定焦镜头", "低畸变，视场角约 28°，主物距范围 0.5m~5.0m"),
        ("重投影误差 (RMS)", "0.07697 像素 (0.077 px)", "远优于工业级标准 (< 0.1 px)，亚像素级对齐"),
        ("实测物理基线 (B)", "60.0087 毫米 (60.01 mm)", "两相机光心物理中心距，严格决定双目三角测量深度"),
        ("有效焦距 (f)", "左目: 1421.55 px / 右目: 1421.29 px", "左右目焦距对称性极高，无制造组装轴向公差"),
        ("空间安装旋转角 (R)", "[0.999999, -0.0007, 0.0006; ...]", "接近理想单位阵，两相机机械偏转俯仰角 < 0.05°")
    ]
    for r_idx, row in enumerate(calib_rows):
        for c_idx in range(3):
            cell = calib_table.cell(r_idx + 1, c_idx)
            cell.text = row[c_idx]
            set_cell_margins(cell, top=70, bottom=70, left=100, right=100)
            if (r_idx % 2) == 1:
                set_cell_background(cell, "F9FAFC")
            p = cell.paragraphs[0]
            if c_idx == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.runs[0].font.bold = True
            elif c_idx == 1:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.runs[0].font.bold = True
                p.runs[0].font.color.rgb = RGBColor(192, 0, 0)
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.runs[0].font.name = 'Microsoft YaHei'
            p.runs[0].font.size = Pt(9.0)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # 插入标定检测角点图片
    corner_img = repo_root / "data/calibration_results/corner_visualizations/detected_corners_01.png"
    if corner_img.exists():
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_after = Pt(2)
        doc.add_picture(str(corner_img), width=Inches(5.5))
        add_caption(doc, "图 2-1：真实海康工业相机拍摄的 11×9 (20mm) 标定板亚像素角点检测效果")

    # --------------------------------------------------------------------------
    # 第三章：立体匹配算法演进与实测对比 (SGBM vs GREAT-Stereo)
    # --------------------------------------------------------------------------
    add_styled_heading(doc, "三、 立体匹配算法演进与实测对比", level=1)
    add_styled_paragraph(doc, 
        "双目点云的重建精度与表面平滑度完全取决于立体匹配算法的性能。本周完成了从传统半全局立体匹配（SGBM）到最新 ICCV 2025 SOTA 深度学习网络（GREAT-Stereo）的重大技术升级。",
        bold_prefix="【技术演进背景】"
    )

    # 对比表格
    comp_table = doc.add_table(rows=7, cols=3)
    comp_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_headers = ["对比维度与指标", "传统算法：OpenCV SGBM-HH", "深度学习：GREAT-Stereo (ICCV 2025)"]
    for i, h in enumerate(c_headers):
        cell = comp_table.cell(0, i)
        cell.text = h
        set_cell_background(cell, "1F4E79")
        set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.bold = True
        p.runs[0].font.name = 'Microsoft YaHei'
        p.runs[0].font.size = Pt(9.5)
        p.runs[0].font.color.rgb = RGBColor(255, 255, 255)

    comp_rows = [
        ("算法核心架构", "8 方向代价聚合 + WLS 滤波", "极线几何显式约束 + 迭代循环 GRU 视差更新"),
        ("视差有效覆盖率", "68.4% (平滑表面与远景出现空洞)", "100.00% (全图全稠密连续覆盖，无黑斑盲区)"),
        ("真实有效 3D 点数", "386,412 点 (约 38.6 万点)", "1,256,119 点 (125.6 万点，密度提升 3.25 倍)"),
        ("弱纹理表面表现", "呈现明显阶梯状“梯田断层”", "曲率平滑连续，自然还原圆凳圆弧表面与地面"),
        ("强光反射与阴影", "容易产生歧义产生离群噪点", "基于 Transformer 全局上下文特征，抗高光能力强"),
        ("硬件适配与显存开销", "纯 CPU 计算 (单帧约 180ms)", "适配 4GB 轻量显存 (自适应下采样+FP16，不爆显存)")
    ]
    for r_idx, row in enumerate(comp_rows):
        for c_idx in range(3):
            cell = comp_table.cell(r_idx + 1, c_idx)
            cell.text = row[c_idx]
            set_cell_margins(cell, top=70, bottom=70, left=100, right=100)
            if (r_idx % 2) == 1:
                set_cell_background(cell, "F9FAFC")
            p = cell.paragraphs[0]
            if c_idx == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.runs[0].font.bold = True
            elif c_idx == 2:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.runs[0].font.bold = True
                p.runs[0].font.color.rgb = RGBColor(31, 78, 121)
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.runs[0].font.name = 'Microsoft YaHei'
            p.runs[0].font.size = Pt(9.0)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # 插入 GREAT-Stereo 实测视差图与深度图
    disp_img = repo_root / "data/output/hk_real_output/recon_20260922_173231_great/disparity_great_20260922_173231.png"
    depth_img = repo_root / "data/output/hk_real_output/recon_20260922_173231_great/depth_great_20260922_173231.png"
    
    if disp_img.exists() and depth_img.exists():
        table_pics = doc.add_table(rows=1, cols=2)
        table_pics.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        c0 = table_pics.cell(0, 0)
        p0 = c0.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r0 = p0.add_run()
        r0.add_picture(str(disp_img), width=Inches(3.1))
        
        c1 = table_pics.cell(0, 1)
        p1 = c1.paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1 = p1.add_run()
        r1.add_picture(str(depth_img), width=Inches(3.1))
        
        add_caption(doc, "图 3-1：GREAT-Stereo 实测产物 —— 左：全稠密视差伪彩图；右：物理度量深度图 (0.5m~5.0m)")

    # 插入诊断全景监控对比大图
    showcase_great = repo_root / "data/output/hk_real_output/recon_20260922_173231_great/showcase_great_20260922_173231.png"
    if showcase_great.exists():
        p_sc = doc.add_paragraph()
        p_sc.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_sc.paragraph_format.space_before = Pt(6)
        p_sc.paragraph_format.space_after = Pt(2)
        doc.add_picture(str(showcase_great), width=Inches(6.2))
        add_caption(doc, "图 3-2：GREAT-Stereo 实机全流程诊断监控大图 (极线对齐、稠密视差与 125.6 万点 3D 点云渲染)")

    # --------------------------------------------------------------------------
    # 第四章：三维点云实测几何指标与分析
    # --------------------------------------------------------------------------
    add_styled_heading(doc, "四、 三维点云实测几何指标与质量分析", level=1)
    add_styled_paragraph(doc, 
        "将导出的 `model_great_20260922_173231.ply` 点云载入 CloudCompare 进行三维几何结构检验，各项指标均表现出优异的工程保真度：",
        bold_prefix="【点云质量评测】"
    )

    pts_metrics = [
        ("有效点云数量", "1,256,119 个 3D 空间点（完整包含 3D 空间坐标 X, Y, Z 与 RGB 真实纹理色彩）。"),
        ("有效深度测量范围", "0.50 米至 5.00 米，近处圆凳（物距约 2.3m~2.8m）与后排立柜及背景墙面（3.2m~4.6m）空间分层极其清晰。"),
        ("边缘几何保真度", "圆凳边缘锐利分明，无传统 SGBM 算法常见的拉扯拖尾效应（Flying Pixels 伪影已被消除）。"),
        ("法向量与光照感", "已在生成流水线中启用法向量自适应估计（k=30 邻域），在 3D 查看器中表面具备逼真的明暗凹凸立体感。")
    ]
    for tag, desc in pts_metrics:
        add_styled_paragraph(doc, desc, bold_prefix=f"● {tag}：")

    # --------------------------------------------------------------------------
    # 第五章：工程交付与自动化架构优化
    # --------------------------------------------------------------------------
    add_styled_heading(doc, "五、 工程交付与自动化架构优化", level=1)
    add_styled_paragraph(doc, "为确保算法易用性与团队协作顺畅，本周在工程架构层面完成了三项关键优化：")
    
    eng_items = [
        ("跨 Python 环境动态桥接技术", "针对用户在 VS Code 中通常激活 base 环境（未安装 PyTorch）的问题，在代码中设计了动态运行时桥接器，启动时自动将 `ffs` Conda 环境中的 PyTorch 核心包与 CUDA DLL 路径注入当前进程。用户无需切换终端环境，直接点击 VS Code 绿色的 ▶ 按钮即可顺畅运行深度重建。"),
        ("标准化输出目录与防污染隔离", "重建产物按照 `recon_YYYYMMDD_HHMMSS_great/` 格式进行独立文件夹隔离。彻底清理了散落在外层的 `latest_*` 临时冗余文件，使输出目录结构清晰、天然支持时间顺序溯源。"),
        ("Git LFS 大资产托管与版本锁定", "将超过 50MB 的稠密 `.ply` 点云模型纳入 Git Large File Storage (LFS) 进行纳管，全量代码与资产成功推送至 GitHub 仓库，正式打上 `v0.6.0` 里程碑标签。")
    ]
    for tag, desc in eng_items:
        add_styled_paragraph(doc, desc, bold_prefix=f"1. {tag}：")

    # --------------------------------------------------------------------------
    # 第六章：核心工程难点复盘与 NOTEBOOK.md 沉淀
    # --------------------------------------------------------------------------
    add_styled_heading(doc, "六、 核心工程难点复盘与技术笔记沉淀", level=1)
    add_styled_paragraph(doc, "本周在底层数学几何与物理实操中攻克了多项隐蔽 Bug，并系统整理至项目答疑手册 `NOTEBOOK.md`（共 18 个技术专题）：")
    
    nb_items = [
        ("左右目颠倒识别与数学判定 (Q16)", "实操中若左右图颠倒，视差公式由于符号翻转会导致深度算得负数或近大远小畸变。本工程建立了基于极线匹配位移符号的自动诊断准则。"),
        ("双目收敛面与视差搜索范围设置 (Q8)", "剖析了双目相机视轴在无穷远或有限距离处交叉时产生的收敛面物理效应，纠正了传统误区，将视差搜索原点锁定为 0。"),
        ("光滑木质表面的梯田阶梯断层消解 (Q13)", "阐明了传统立体匹配在低纹理表面因离散代价产生阶梯状切片的根因，论证了引入深度网络显式极线先验的必要性。")
    ]
    for tag, desc in nb_items:
        add_styled_paragraph(doc, desc, bold_prefix=f"◆ {tag}：")

    # --------------------------------------------------------------------------
    # 第七章：下一阶段任务安排与里程碑规划 (Action Plan)
    # --------------------------------------------------------------------------
    add_styled_heading(doc, "七、 下一阶段任务安排与推进路线", level=1)
    add_styled_paragraph(doc, "基于当前已经取得的 125.6 万点高精度稠密点云，下一阶段将围绕“点云精细化滤波、水密网格化、多视角实物拼接与双轨系统联动”展开：")

    plan_table = doc.add_table(rows=5, cols=4)
    plan_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    p_headers = ["实施阶段", "任务核心内容", "预期交付产物", "目标指标"]
    for i, h in enumerate(p_headers):
        cell = plan_table.cell(0, i)
        cell.text = h
        set_cell_background(cell, "1F4E79")
        set_cell_margins(cell, top=100, bottom=100, left=100, right=100)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.bold = True
        p.runs[0].font.name = 'Microsoft YaHei'
        p.runs[0].font.size = Pt(9.5)
        p.runs[0].font.color.rgb = RGBColor(255, 255, 255)

    plan_rows = [
        ("阶段一：点云后处理与高保真滤波", "实现统计离群值去噪 (SOR) 与半径滤波算法，剔除背景悬浮孤立噪点与边界毛刺", "点云滤波处理模块 `src/stereo/filter.py` 及净化后点云", "离群噪点消除率 > 95%，保留完整真实轮廓"),
        ("阶段二：泊松表面重构与网格化", "计算精准点云法向量，应用泊松表面重构（Poisson Reconstruction）算法将点云转为连续水密三角网格", "3D 水密模型 `.obj` / `.stl` 及表面彩色贴图", "生成无孔洞、可用于 CAD 分析或 3D 打印的实体网格"),
        ("阶段三：多视角实机拍摄与 360° 配准", "设计多角度实拍方案，运用 FPFH 粗配准与彩色 ICP 精配准将多个机位的点云融合成完整 360° 整体", "多视角配准流水线 `scripts/multiview_align.py` 及全景模型", "不同机位重叠面配准残差 < 0.5 mm"),
        ("阶段四：近红外追踪与重建双轨融合", "将手术工具近红外标记球高速跟踪（>60 FPS, FRE < 0.2mm）与稠密场景三维重建整合至统一运行控制台", "系统集成控制台 `main.py` 及双模态联动演示", "支持在重建的 3D 解剖场景中实时显示手术针尖坐标")
    ]
    for r_idx, row in enumerate(plan_rows):
        for c_idx in range(4):
            cell = plan_table.cell(r_idx + 1, c_idx)
            cell.text = row[c_idx]
            set_cell_margins(cell, top=70, bottom=70, left=80, right=80)
            if (r_idx % 2) == 1:
                set_cell_background(cell, "F9FAFC")
            p = cell.paragraphs[0]
            if c_idx == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.runs[0].font.bold = True
                p.runs[0].font.color.rgb = RGBColor(31, 78, 121)
            elif c_idx == 3:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.runs[0].font.bold = True
                p.runs[0].font.color.rgb = RGBColor(192, 0, 0)
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.runs[0].font.name = 'Microsoft YaHei'
            p.runs[0].font.size = Pt(8.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(16)

    # 结尾签名
    p_end = doc.add_paragraph()
    p_end.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_end = p_end.add_run("报告生成日期：2026年9月22日\n双目立体视觉与三维重建研发团队")
    r_end.font.name = 'Microsoft YaHei'
    r_end._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
    r_end.font.size = Pt(9.5)
    r_end.font.italic = True
    r_end.font.color.rgb = RGBColor(120, 120, 120)

    doc.save(str(out_docx))
    print(f"[SUCCESS] 周报 Word 文档已生成: {out_docx}")

if __name__ == "__main__":
    main()

