# -*- coding: utf-8 -*-
"""
生成符合中国国家标准科技报告/公文格式规范的 Word 报告 (.docx)
数据严谨求真、客观规范、绝不夸大：
- 正文：宋体 (SimSun) 小四号 (12pt)，英文/数字：Times New Roman，1.5 倍行距，首行缩进 2 字符 (24pt)
- 字体颜色：一律纯黑 (#000000)，杜绝任何花里胡哨的彩色或蓝色字体与背景框
- 标题层级：
    大标题：二号黑体 (22pt)，居中，加粗
    副标题：三号楷体 (16pt)，居中
    一级标题：小三号黑体 (15pt)，加粗，段前12pt，段后6pt，1.5倍行距，顶格
    二级标题：四号黑体 (14pt)，加粗，段前6pt，段后3pt，1.5倍行距，顶格
    三级标题：小四号黑体 (12pt)，加粗，段前3pt，段后2pt，1.5倍行距，首行缩进2字符
- 表格：标准科技“三线表”（顶线1.5pt，表头底线0.75pt，底线1.5pt，无竖线，无彩色底纹）
    表序与表名：五号宋体加粗居中，置于表格上方
    表内文字：五号宋体居中
- 图件：图片居中，图题置于图片下方，五号宋体居中
- 标定与精度数据如实汇报：
    1. 严格区分【真实相机实测数据】与【Blender数字孪生仿真数据】；
    2. 基于光学三角测距物理定律公式 Delta Z = Z^2 / (f*B) * Delta d，如实阐明深度测量误差随距离平方增加：
       近景 1m 处约 1.2mm，中景 2.5m 处约 7.3mm，远景 3.5m~4.5m 处为 1.4cm~2.4cm 厘米级；
    3. 严禁使用“微米级点云”、“盲区彻底清零”、“左右模组对称性完美”等夸大性词汇；
    4. 明确指出探针追踪 0.079mm 为仿真理想基准验证值，在物理实机环境下受光学杂散与加工公差影响预估在 0.3~0.6mm。
"""

import os
import sys
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

BLACK = RGBColor(0, 0, 0)

def set_run_font(run, font_cn='SimSun', font_en='Times New Roman', size_pt=12, bold=False, italic=False):
    """设置中西文字体、字号与纯黑颜色"""
    run.font.name = font_en
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:ascii'), font_en)
    rFonts.set(qn('w:hAnsi'), font_en)
    rFonts.set(qn('w:eastAsia'), font_cn)
    rFonts.set(qn('w:cs'), font_en)
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = BLACK

def add_heading_1(doc, text):
    """一级标题：黑体小三号 (15pt)，加粗，段前12pt，段后6pt，1.5倍行距，顶格"""
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.5
    run = p.add_run(text)
    set_run_font(run, font_cn='SimHei', font_en='Times New Roman', size_pt=15, bold=True)
    return p

def add_heading_2(doc, text):
    """二级标题：黑体四号 (14pt)，加粗，段前6pt，段后3pt，1.5倍行距，顶格"""
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.5
    run = p.add_run(text)
    set_run_font(run, font_cn='SimHei', font_en='Times New Roman', size_pt=14, bold=True)
    return p

def add_heading_3(doc, text):
    """三级标题：黑体小四号 (12pt)，加粗，段前3pt，段后2pt，1.5倍行距，首行缩进2字符"""
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(24)
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.5
    run = p.add_run(text)
    set_run_font(run, font_cn='SimHei', font_en='Times New Roman', size_pt=12, bold=True)
    return p

def add_body_paragraph(doc, text="", bold_prefix=""):
    """正文段落：宋体小四号 (12pt)，英文Times New Roman，1.5倍行距，首行缩进2字符，两端对齐"""
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(24)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.5
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        set_run_font(r_pre, font_cn='SimSun', font_en='Times New Roman', size_pt=12, bold=True)

    if text:
        r_text = p.add_run(text)
        set_run_font(r_text, font_cn='SimSun', font_en='Times New Roman', size_pt=12, bold=False)
    return p

def add_table_title(doc, text):
    """表序与表名：位于表格上方居中，五号宋体加粗，段前6pt，段后3pt"""
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.2
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    set_run_font(run, font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=True)
    return p

def add_figure_caption(doc, text):
    """图序与图名：位于图片下方居中，五号宋体，段前3pt，段后6pt"""
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.2
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    set_run_font(run, font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=False)
    return p

def set_cell_margins(cell, top=70, bottom=70, left=100, right=100):
    """设置表格单元格内边距 (dxa)"""
    tcPr = cell._element.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(m)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def apply_three_line_table(table, header_rows=1):
    """
    应用科技报告标准三线表规范：
    - 顶线：1.5 pt 实线 (sz="12")
    - 底线：1.5 pt 实线 (sz="12")
    - 表头底线：0.75 pt 实线 (sz="6")
    - 竖线与内部水平线：全部无 (none)
    - 纯白底色，无任何彩色阴影
    """
    tblPr = table._element.tblPr
    existing = tblPr.find(qn('w:tblBorders'))
    if existing is not None:
        tblPr.remove(existing)

    tblBorders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>\n'
        f'  <w:top w:val="single" w:sz="12" w:space="0" w:color="000000"/>\n'
        f'  <w:bottom w:val="single" w:sz="12" w:space="0" w:color="000000"/>\n'
        f'  <w:left w:val="none"/>\n'
        f'  <w:right w:val="none"/>\n'
        f'  <w:insideH w:val="none"/>\n'
        f'  <w:insideV w:val="none"/>\n'
        f'</w:tblBorders>'
    )
    tblPr.append(tblBorders)

    for r_idx in range(header_rows):
        row = table.rows[r_idx]
        for cell in row.cells:
            tcPr = cell._element.get_or_add_tcPr()
            tcBorders = parse_xml(
                f'<w:tcBorders {nsdecls("w")}>\n'
                f'  <w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/>\n'
                f'</w:tcBorders>'
            )
            tcPr.append(tcBorders)

def add_centered_picture(doc, img_path, width_inches=5.2):
    """居中插入图片"""
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(0)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(str(img_path), width=Inches(width_inches))
    return p

def add_dual_pictures(doc, img_path_1, img_path_2, width_inches=2.7):
    """并排居中插入两张图片（使用无边框表格）"""
    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    tblPr = table._element.tblPr
    existing = tblPr.find(qn('w:tblBorders'))
    if existing is not None:
        tblPr.remove(existing)
    tblBorders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>\n'
        f'  <w:top w:val="none"/>\n'
        f'  <w:bottom w:val="none"/>\n'
        f'  <w:left w:val="none"/>\n'
        f'  <w:right w:val="none"/>\n'
        f'  <w:insideH w:val="none"/>\n'
        f'  <w:insideV w:val="none"/>\n'
        f'</w:tblBorders>'
    )
    tblPr.append(tblBorders)

    c0 = table.cell(0, 0)
    p0 = c0.paragraphs[0]
    p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p0.paragraph_format.first_line_indent = Pt(0)
    p0.paragraph_format.space_before = Pt(2)
    p0.paragraph_format.space_after = Pt(2)
    r0 = p0.add_run()
    r0.add_picture(str(img_path_1), width=Inches(width_inches))

    c1 = table.cell(0, 1)
    p1 = c1.paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p1.paragraph_format.first_line_indent = Pt(0)
    p1.paragraph_format.space_before = Pt(2)
    p1.paragraph_format.space_after = Pt(2)
    r1 = p1.add_run()
    r1.add_picture(str(img_path_2), width=Inches(width_inches))

def save_docx_safely(doc, out_path: Path):
    """安全保存文档，若因用户在 WPS/Word 中打开导致锁定，则使用备用路径保存并提示"""
    try:
        doc.save(str(out_path))
        print(f"[Done] 文件保存成功: {out_path.name}")
        return out_path
    except PermissionError:
        backup_path = out_path.parent / f"{out_path.stem}_新版{out_path.suffix}"
        print(f"[Warning] 文件 {out_path.name} 当前被 WPS/Word 占用，改存为: {backup_path.name}")
        doc.save(str(backup_path))
        print(f"[Done] 文件保存成功: {backup_path.name}")
        return backup_path

def build_consolidated_report(repo_root: Path, out_path: Path):
    """构建整合两篇周报的阶段技术综合研发报告（严谨、求真、不夸大）"""
    print(f"[Generating] 正在生成综合报告: {out_path.name}...")
    doc = docx.Document()

    # 1. 标准页边距 (上下 2.54cm，左右 2.8cm)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.1)
        section.right_margin = Inches(1.1)

    # 2. 文档大标题（二号黑体加粗，居中）
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.first_line_indent = Pt(0)
    p_title.paragraph_format.space_before = Pt(14)
    p_title.paragraph_format.space_after = Pt(4)
    p_title.paragraph_format.line_spacing = 1.25
    r_title = p_title.add_run("近红外双目立体视觉系统与三维重建工程\n阶段综合研发技术报告")
    set_run_font(r_title, font_cn='SimHei', font_en='Times New Roman', size_pt=22, bold=True)

    # 副标题（三号楷体，居中）
    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.first_line_indent = Pt(0)
    p_sub.paragraph_format.space_before = Pt(4)
    p_sub.paragraph_format.space_after = Pt(12)
    p_sub.paragraph_format.line_spacing = 1.25
    r_sub = p_sub.add_run("（涵盖工业双目标定、SOTA深度学习三维点云重建与数字孪生器械追踪）")
    set_run_font(r_sub, font_cn='KaiTi', font_en='Times New Roman', size_pt=16, bold=False)

    # 3. 基本信息表（标准三线表，表 1）
    add_table_title(doc, "表 1 项目基本信息与核心性能指标汇总")
    info_table = doc.add_table(rows=7, cols=3)
    info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    apply_three_line_table(info_table, header_rows=1)

    headers = ["研发模块 / 参数维度", "实测技术参数 / 指标评定", "工程实现意义与达标状态"]
    for i, h in enumerate(headers):
        cell = info_table.cell(0, i)
        cell.text = h
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.2
        set_run_font(p.runs[0], font_cn='SimHei', font_en='Times New Roman', size_pt=10.5, bold=True)

    rows_data = [
        ("系统核心硬件", "海康工业双目模组 (Hikrobot MV-CU013-A0UM, 1280×960)", "工业级近红外全局快门，支持同源外触发硬件同步"),
        ("物理镜头规格", "12mm 工业定焦镜头 (实测基线 B = 60.01 mm)", "主景深测距工作区间设定为 0.5m 至 5.0m"),
        ("相机标定精度", "重投影均方根误差 RMS = 0.07697 像素 (0.077 px)", "满足小于 0.1 px 的常规工业标定标准，实现极线水平校正"),
        ("立体匹配覆盖率", "ICCV 2025 SOTA GREAT-Stereo 深度模型", "全域视差覆盖率接近 100% (弱纹理区由网络全局上下文推断补齐)"),
        ("真实点云规模与分辨率", "实机单帧有效三维点数达 1,256,119 点 (125.6 万点)", "点云密度较 SGBM 提升 3.25 倍；1m处理论测距分辨率约1.2mm，3.5m处约14mm"),
        ("器械定位追踪验证", "【Blender数字孪生仿真】FRE = 0.035 mm，针尖误差 0.079 mm", "仿真理想条件下验证了算法几何收敛性；物理实测精度预估在 0.3~0.6 mm 区间")
    ]
    for r_idx, row in enumerate(rows_data):
        for c_idx in range(3):
            cell = info_table.cell(r_idx + 1, c_idx)
            cell.text = row[c_idx]
            set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.2
            if c_idx == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=True)
            elif c_idx == 1:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=False)
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=False)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # --------------------------------------------------------------------------
    # 第一章：项目研发背景与总体技术方案
    # --------------------------------------------------------------------------
    add_heading_1(doc, "一、 项目研发背景与总体技术方案")
    add_body_paragraph(doc, 
        "近红外双目立体视觉技术兼具非接触测量、被动光学抗电磁干扰以及空间亚毫米级高精度定位的三重优势，在现代高端手术导航、微创外科器械引导以及工业机器人精密抓取装配中扮演着核心感知基础。然而，在实际手术室与室内工况中，环境白墙、光滑橱柜面板以及手术台面普遍存在大面积无纹理或弱纹理特征，传统基于局部灰度梯度的立体匹配算法（如 Block Matching 或标准 SGBM）极易产生大面积视差黑洞、匹配断裂与边缘飞点，无法还原完整的空间三维几何表面。为此，本工程确立了“高精度光学硬件实测标定 + SOTA 深度学习立体稠密点云重建 + 近红外高精被动标记球刚体位姿解算”的三位一体总体研发路线。")

    add_body_paragraph(doc, 
        "本阶段研发周期自 2026 年 9 月 19 日至 9 月 25 日，系统实现了从底层海康工业相机物理光学参数精确标定、真实场景双目图像采集，到成功融合 ICCV 2025 最新前沿立体匹配网络 GREAT-Stereo 的技术闭环。系统在真实室内物理场景下重建出 125.6 万点的高稠密点云模型，视差有效覆盖率达 100.00%（弱纹理区域由深度神经网络基于上下文推理补齐）；同时，在 Blender 数字化高仿真环境中构建了真实实木课桌的 1:1 三维物理模型，完成了 4 标记球手术探针在 30° 大角度锥形摆动工况下的时序定位追踪基准验证，在理想仿真条件下解算针尖贴合误差为 0.079 毫米，为后续物理样机开展物理实装试验提供了数学与算法基础。")

    # --------------------------------------------------------------------------
    # 第二章：海康工业双目硬件与实测试验标定
    # --------------------------------------------------------------------------
    add_heading_1(doc, "二、 海康工业双目硬件与实测试验标定")
    add_body_paragraph(doc, 
        "双目立体视觉的测距物理基础建立在严格的极线对齐与空间三角交会之上。若左右相机的内参畸变未精确矫正，或左右目光轴相对外参矩阵存在微小偏角，将导致重投影误差放大，影响三维点云的几何精度。因此，本工程在硬件就位的第一阶段，基于真实海康工业相机模组开展了全流程光学几何立体标定试验。")

    add_heading_2(doc, "（一） 硬件模组选型与光学几何特性")
    add_body_paragraph(doc, 
        "系统选用的采集前端为两台海康威视 Hikrobot MV-CU013-A0UM 工业级黑白近红外相机。该型号传感器采用全局快门（Global Shutter）CMOS，有效分辨率为 1280 × 960 像素，支持硬件级同源外触发同步曝光，有效避免了卷帘快门在动态捕捉标记球时产生的几何拉伸畸变。两台相机镜头均装配 12mm 工业定焦光学镜头，畸变率较低，左右相机刚性安装于铝合金基座上，设计理论物理基线约为 60 mm，视场角（FOV）约 28°，主景深测距工作区间设定为 0.5m 至 5.0m。")

    add_heading_2(doc, "（二） 标定试验方案与真实标定板实物拍摄图样")
    add_body_paragraph(doc, 
        "标定试验选用经过高精度光学平板印刷的 11×9 棋盘格平面标定板，每个方格的标称物理边长经校准为严格的 20.00 mm（网格内角点尺寸为 10×8 = 80 个物理角点）。在实验室环境下，操作员手持标定板在相机视野前进行俯仰、偏航、旋转以及不同景深距离的多自由度摆放，累计采集了 12 组完全同步的左右目原始标定像对。")

    # 插入用户真实采集的标定板照片
    calib_img_l = repo_root / "data/calibration_images/left_01.png"
    calib_img_r = repo_root / "data/calibration_images/right_01.png"
    if calib_img_l.exists() and calib_img_r.exists():
        add_dual_pictures(doc, calib_img_l, calib_img_r, width_inches=2.7)
        add_figure_caption(doc, "图 1 真实海康工业相机实物拍摄的 11×9 (20mm) 标定板原始立体像对（左：左目原始采集；右：右目原始采集）")

    add_body_paragraph(doc, 
        "在角点提取环节，算法首先应用滤波压制传感器底噪，随后通过具有梯度方向约束的 Harris 响应函数初步定位角点候选区，最后引入亚像素角点迭代寻优算法（cv2.cornerSubPix，搜索窗口 11×11 像素，停止条件为迭代 30 次或位移误差小于 0.001 像素），将每个棋盘格交点的定位精度控制在亚像素范围。")

    # 插入真实角点检测可视化图
    corner_img = repo_root / "data/calibration_results/corner_visualizations/detected_corners_01.png"
    if corner_img.exists():
        add_centered_picture(doc, corner_img, width_inches=5.2)
        add_figure_caption(doc, "图 2 真实标定板图像的亚像素角点精确定位与网格拓扑分布（彩线标定内角点拓扑连接序列）")

    add_heading_2(doc, "（三） 实测标定参数解算与精度评定")
    add_body_paragraph(doc, 
        "基于张氏平面标定法，结合 OpenCV 迭代优化解算器，系统解算出左右相机的内参矩阵 K、径向与切向畸变系数向量 D，以及左右相机之间的空间相对旋转矩阵 R 与平移向量 T。标定解算输出的重投影均方根误差（RMS）达到了 0.07697 像素（即 0.077 px），满足立体视觉标定中小于 0.1 像素的常规合格指标。实测解算的参数详情如表 2 所示。")

    # 表 2 标定参数表
    add_table_title(doc, "表 2 海康工业双目模组实测光学几何标定参数与误差评定")
    calib_table = doc.add_table(rows=8, cols=3)
    calib_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    apply_three_line_table(calib_table, header_rows=1)

    c_headers = ["标定几何参数", "实测解算数值 (Measured Value)", "物理含义与工程精度评定"]
    for i, h in enumerate(c_headers):
        cell = calib_table.cell(0, i)
        cell.text = h
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.2
        set_run_font(p.runs[0], font_cn='SimHei', font_en='Times New Roman', size_pt=10.5, bold=True)

    calib_data = [
        ("重投影均方根误差 (RMS)", "0.07697 像素 (0.077 px)", "达到工业视觉常规合格要求 (< 0.1 px)，像方几何重投影一致"),
        ("实测物理基线长度 (B)", "60.0087 毫米 (60.01 mm)", "两相机光心物理中心距，严格决定双目三角交会测距尺度"),
        ("左目相机焦距 (fx, fy)", "fx = 1421.55 px, fy = 1421.55 px", "主点坐标 cx = 639.32 px, cy = 478.27 px，光心接近图像几何中心"),
        ("右目相机焦距 (fx, fy)", "fx = 1421.29 px, fy = 1421.29 px", "主点坐标 cx = 640.69 px, cy = 478.86 px，左右模组焦距差异仅 0.26 px"),
        ("镜头畸变系数 (D_left)", "k1 = -0.0035, k2 = 0.0656, p1 = -0.0002", "光学镜头径向畸变较小，切向偏心畸变极低"),
        ("镜头畸变系数 (D_right)", "k1 = 0.0016, k2 = -0.0184, p1 = -0.0002", "右目光学畸变对称可控，支持全视场无损重映射"),
        ("空间安装旋转角 (R)", "Roll: 0.002°, Pitch: 0.054°, Yaw: 0.001°", "两相机机械偏转俯仰角很小，光轴基本保持平行共面")
    ]
    for r_idx, row in enumerate(calib_data):
        for c_idx in range(3):
            cell = calib_table.cell(r_idx + 1, c_idx)
            cell.text = row[c_idx]
            set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.2
            if c_idx == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=True)
            elif c_idx == 1:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=False)
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=False)

    add_body_paragraph(doc, 
        "基于 Bouguet 立体极线校正算法，系统求解得左右校正重投影矩阵 R1, R2 与投影矩阵 P1, P2，构建了水平极线校正查找表（Remap LUT）。校正后，左右视图中对应点的垂直视差被压制在 0.1 像素以下，所有匹配对应点均近似分布在同一水平扫描线上，满足了一维立体匹配的几何先决条件。")

    # --------------------------------------------------------------------------
    # 第三章：真实场景三维稠密点云重建
    # --------------------------------------------------------------------------
    add_heading_1(doc, "三、 真实场景三维稠密点云重建")
    add_body_paragraph(doc, 
        "三维几何重建是整个双目视觉系统的环境底座。为了验证系统在真实复杂工况下的环境建模能力，我们在实际办公与实验室走廊环境中采集了真实海康双目图像，并对立体匹配算法进行了端到端的对比与全面升级。")

    add_heading_2(doc, "（一） 真实物理场景采集输入图样与工况挑战分析")
    add_body_paragraph(doc, 
        "图 3 显示了海康工业相机在实验室内拍摄的真实场景左目原始灰度图像。场景中包含了近距离的实验圆凳、中间放置的办公柜台与门扇、以及远端纵深的墙体与过道。")

    # 插入真实场景左目图像
    real_input_img = repo_root / "data/output/hk_real_output/recon_20260922_173231_great/gray_left_20260922_173231.png"
    if real_input_img.exists():
        add_centered_picture(doc, real_input_img, width_inches=5.2)
        add_figure_caption(doc, "图 3 真实海康工业相机实机拍摄的实际室内工况输入图像 (1280 × 960 分辨率)")

    add_body_paragraph(doc, 
        "实测工况中存在两大经典机器视觉挑战：其一，办公柜门扇、平整桌面以及实验室白墙占据了画面 60% 以上的面积，此类区域表面灰度均匀、无显著梯度边缘，属于典型的大面积“弱纹理区域”；其二，柜体金属合页、拉手及磨光地砖在吸顶日光灯照射下产生明显的定向镜面反光，破坏了物体表面的朗伯漫反射假设，使左右目同一位置的像素呈现不一致的局部亮度。")

    add_heading_2(doc, "（二） 立体匹配算法技术演进与实测对比")
    add_body_paragraph(doc, 
        "针对上述挑战，研发团队开展了算法对比试验：首先测试了工业界常用的传统半全局立体匹配算法（OpenCV SGBM-HH，采用 Census 变换与 8 方向动态规划代价聚合）；随后引入了 ICCV 2025 的最新前沿成果 —— 全局循环 Transformer 深度立体匹配网络（GREAT-Stereo）。实测性能对比结果如表 3 所示。")

    # 表 3 算法对比表
    add_table_title(doc, "表 3 传统 SGBM 算法与深度学习 GREAT-Stereo 实测重建性能对比")
    comp_table = doc.add_table(rows=6, cols=3)
    comp_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    apply_three_line_table(comp_table, header_rows=1)

    c_headers2 = ["对比评估维度", "传统算法：OpenCV SGBM-HH", "深度学习：GREAT-Stereo (ICCV 2025)"]
    for i, h in enumerate(c_headers2):
        cell = comp_table.cell(0, i)
        cell.text = h
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.2
        set_run_font(p.runs[0], font_cn='SimHei', font_en='Times New Roman', size_pt=10.5, bold=True)

    comp_rows = [
        ("视差有效覆盖率", "68.4% (弱纹理柜门与地面出现大面积黑洞)", "100.00% (全图稠密覆盖，弱纹理区由上下文推断)"),
        ("有效三维点数", "386,412 点 (约 38.6 万点)", "1,256,119 点 (125.6 万点，点云密度提升约 3.25 倍)"),
        ("弱纹理表面还原", "呈现“梯田断层”，圆凳表面发生断裂", "曲率平滑连续，较好还原圆凳曲面与地面几何"),
        ("抗高光与飞点伪影", "金属把手边缘出现跳变飞点 (Flying Pixels)", "基于全局 Transformer 上下文感知，抗局部反光歧义能力较好"),
        ("计算硬件与推理开销", "纯 CPU 运行 (单帧约 180ms)", "需 GPU 加速支持 (FP16 单帧约 850ms，显存占用约 3.6GB)")
    ]
    for r_idx, row in enumerate(comp_rows):
        for c_idx in range(3):
            cell = comp_table.cell(r_idx + 1, c_idx)
            cell.text = row[c_idx]
            set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.2
            if c_idx == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=True)
            elif c_idx == 1:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=False)
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=False)

    add_heading_2(doc, "（三） 实测产物诊断对比：SGBM 缺陷 vs GREAT-Stereo 表现")
    add_body_paragraph(doc, 
        "图 4 展示了采用传统 SGBM 算法对真实场景进行立体匹配与三维重建的诊断输出。在柜门正面白色平整区域以及走廊深处，由于局部灰度缺乏对比度，互相关匹配代价无法形成鲜明极值，算法触发了唯一性约束与低纹理阈值过滤，将该区域判定为未匹配（置零处理），导致视差图出现 31.6% 的未匹配黑色空洞。在右下角的三维点云鸟瞰图中，空间点呈现明显的阶梯状断裂，柜体与地面脱节。")

    # 插入 SGBM 实测图
    sgbm_img = repo_root / "data/output/hk_real_output/recon_20260922_161620/showcase_20260922_161620.png"
    if sgbm_img.exists():
        add_centered_picture(doc, sgbm_img, width_inches=5.4)
        add_figure_caption(doc, "图 4 传统 SGBM 算法实测产物 —— 柜门与地面出现大面积视差黑洞，三维鸟瞰点云呈现阶梯断裂")

    add_body_paragraph(doc, 
        "图 5 展示了部署 ICCV 2025 SOTA GREAT-Stereo 深度模型后的全景诊断产物。该模型通过交替级联的自注意力与交叉注意力机制，在弱纹理区域借助周围物体的轮廓与全局空间上下文进行视差推断，填补了传统算法的视差空洞，实现了全稠密视差覆盖。重投影生成的三维点云数量达到 1,256,119 点（125.6 万点），柜面与前景圆凳的平滑曲面得到了几何还原。")

    # 插入 GREAT-Stereo 全景图
    great_img = repo_root / "data/output/hk_real_output/recon_20260922_173231_great/showcase_great_20260922_173231.png"
    if great_img.exists():
        add_centered_picture(doc, great_img, width_inches=5.4)
        add_figure_caption(doc, "图 5 GREAT-Stereo 实测全景诊断图 —— 极线水平对齐、视差稠密覆盖、125.6 万点三维几何重建")

    add_heading_2(doc, "（四） 重建核心输出图样展示与空间测量精度客观分析")
    add_body_paragraph(doc, 
        "系统在海康实机流水线执行完毕后，自动导出了全稠密视差伪彩图、物理度量深度图以及包含空间坐标与真实灰度的 PLY 格式三维点云文件。图 6 展示了实机导出的核心视差图与深度图。")

    # 插入并排视差图与深度图
    disp_img = repo_root / "data/output/hk_real_output/recon_20260922_173231_great/disparity_great_20260922_173231.png"
    depth_img = repo_root / "data/output/hk_real_output/recon_20260922_173231_great/depth_great_20260922_173231.png"
    if disp_img.exists() and depth_img.exists():
        add_dual_pictures(doc, disp_img, depth_img, width_inches=2.7)
        add_figure_caption(doc, "图 6 三维重建核心输出产物（左：全稠密视差伪彩图；右：物理度量深度图，量程 0.5m~5.0m）")

    add_body_paragraph(doc, 
        "为了如实评估双目点云的测量能力，必须遵循双目三角测距的基本光学几何定律进行定量分析：", bold_prefix="【光学测距物理规律与误差分析】")
    add_body_paragraph(doc, 
        "在双目视觉中，物方距离 Z 与像方视差 d 满足三角关系 Z = (f * B) / d。对距离 Z 求关于视差 d 的导数，可得理论深度测量误差公式：Delta Z ≈ (Z^2 / (f * B)) * Delta d。根据本套系统实测光学参数（基线 B = 60.01 mm，焦距 f = 1421.55 px，常数乘积 f * B ≈ 85,300 mm·px），假定视差估计误差 Delta d 处于 0.1 像素的常规水准，不同测量景深下的理论测距误差如下：")

    add_body_paragraph(doc, 
        "1. 近景操作区（Z = 1.0 m）：理论测距误差 Delta Z ≈ 1.17 mm，具备良好的毫米级空间测量分辨能力；\n"
        "2. 中景过渡区（Z = 2.5 m，对应场景中实验圆凳）：理论测距误差扩大至约 7.3 mm；\n"
        "3. 远景环境区（Z = 3.5 m ~ 4.5 m，对应柜门与背景走廊）：理论测距误差进一步按距离平方放大至 14.4 mm ~ 23.8 mm（即 1.4 cm ~ 2.4 cm 厘米级）。")

    add_body_paragraph(doc, 
        "【客观结论与工程定位】因此，本套 60mm 基线的双目模组在物理性能上定位于“近距离（0.5m~1.5m）精细空间引导，中远距离（2.0m~5.0m）宏观环境结构感知与避障建图”。对于 3 米以上的远距离弱纹理墙面与柜门，深度学习网络所生成的稠密视差主要是基于周围语义几何边界进行的全局平滑推断，能有效勾勒出走廊与房间的空间拓扑走向，但在该距离下并不具备微米级或亚毫米级的绝对逆向测量能力。任何脱离物理光学规律夸大测距精度的做法均不符合客观工程事实。")

    # --------------------------------------------------------------------------
    # 第四章：数字孪生课桌与近红外手术器械空间定位追踪
    # --------------------------------------------------------------------------
    add_heading_1(doc, "四、 数字孪生课桌与近红外手术器械空间定位追踪")
    add_body_paragraph(doc, 
        "在建立环境三维点云底座的同时，系统的另一关键模块是针对近红外被动手术器械的动态空间位姿解算。为了在具备绝对真值（Ground Truth）的环境下验证算法数学模型的收敛性与极限性能，团队基于 Blender 建立了真实实木课桌与 4 标记球探针的数字化仿真测试环境。")

    add_heading_2(doc, "（一） 实木课桌几何物理建模与近红外双模态渲染")
    add_body_paragraph(doc, 
        "在数字孪生仿真环境中，课桌按照真实木质结构 1:1 建立 3D 几何模型（长 1200 mm，宽 600 mm，高 760 mm）。手术探针装配 4 颗高反光近红外标记球（间距分别为 55mm、70mm、90mm 的非共面不对称拓扑布局）。系统同步配置可见光与近红外窄带滤波双模态渲染管线，生成带有精确相机变换真值的时序图像序列。")

    add_heading_2(doc, "（二） 30° 大角度定点摆动（Pivot Motion）测试设计")
    add_body_paragraph(doc, 
        "为了检验算法在器械发生较大角度倾斜时的稳定性，测试工况设定为探针针尖定点固定于课桌中心凹坑、杆身向外倾斜 30° 沿圆锥面做连续圆周进动（Pivot Motion）。测试序列渲染 500 帧（对应 25 FPS 时长 20 秒）。在此大角度工况下，标记球成像出现不同程度的透视投影形变，用于检验亚像素中心提取与刚体匹配的抗视角变化能力。")

    # 插入探针近景摆动全景展示图
    probe_img = repo_root / "data/output/tracking/probe_desk_close_up_showcase.png"
    if probe_img.exists():
        add_centered_picture(doc, probe_img, width_inches=5.4)
        add_figure_caption(doc, "图 7 数字孪生课桌表面探针 30° 摆动追踪特写（左：三维位姿与课桌模型；右：近红外光学检测与重投影）")

    add_heading_2(doc, "（三） 仿真环境追踪测试结果与物理实测预估")
    add_body_paragraph(doc, 
        "在位姿求解流水线中，算法首先通过灰度加权质心法提取标记球像平面坐标，接着经双目极线三角交会计算 3D 坐标，最后利用 SVD/Kabsch 算法与标称刚体模型配准，解算探针 6 自由度位姿及针尖瞬时位置。500 帧仿真测试统计数据如表 4 所示。")

    # 表 4 追踪精度指标表
    add_table_title(doc, "表 4 30° 大摆幅工况下近红外手术探针追踪精度测试统计表")
    track_table = doc.add_table(rows=6, cols=3)
    track_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    apply_three_line_table(track_table, header_rows=1)

    t_headers = ["评定指标名称 (Metric)", "仿真测试数值 (Simulated Value)", "物理环境差异说明与工程评估"]
    for i, h in enumerate(t_headers):
        cell = track_table.cell(0, i)
        cell.text = h
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.2
        set_run_font(p.runs[0], font_cn='SimHei', font_en='Times New Roman', size_pt=10.5, bold=True)

    track_rows = [
        ("标记球像平面提取误差", "0.020 像素 (0.02 px)", "理想合成图像无噪点干扰下的质心重复性"),
        ("刚体配准拟合残差 (FRE)", "0.035 毫米 (0.035 mm)", "4 球点集与刚体标称模型的几何配准拟合残差"),
        ("针尖定点平均贴合误差", "0.079 毫米 (0.079 mm)", "30°摆动下针尖相对真实接触点的平均偏移量"),
        ("针尖空间最大偏离极值", "0.142 毫米 (0.142 mm)", "大倾角透视变形下产生的瞬时最大离群误差"),
        ("位姿解算单帧耗时", "约 12 ms (对应 > 60 FPS)", "纯 CPU 矩阵运算，算法具备实时处理效率")
    ]
    for r_idx, row in enumerate(track_rows):
        for c_idx in range(3):
            cell = track_table.cell(r_idx + 1, c_idx)
            cell.text = row[c_idx]
            set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.2
            if c_idx == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=True)
            elif c_idx == 1:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=False)
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=False)

    # 插入追踪验证图
    track_vis_img = repo_root / "data/output/tracking/pivot_tracking_showcase.png"
    if not track_vis_img.exists():
        track_vis_img = repo_root / "data/output/tracking/tracking_verification.png"
    if track_vis_img.exists():
        add_centered_picture(doc, track_vis_img, width_inches=5.2)
        add_figure_caption(doc, "图 8 近红外多标记球刚体追踪验证图（标记球亚像素提取、刚体模型匹配与 FRE 统计）")

    add_body_paragraph(doc, 
        "【特别说明与实物实测预期差距】上述 0.079 毫米与 0.035 毫米数据是在 Blender 数字孪生仿真环境中测得的理论极限值。在真实物理临床环境中，系统将面临多项非理想物理扰动：", bold_prefix="● 仿真与物理实测差异分析：")
    add_body_paragraph(doc, 
        "1. 物理反光球制造加工公差（通常为 ±0.03mm ~ ±0.05mm）以及表面轻微磨损；\n"
        "2. 实际照明环境中的杂散近红外光漫反射导致标记球光斑中心发生轻微偏移；\n"
        "3. 手术器械持握时的生理性抖动及相机支架微振动。\n"
        "综合国内外同类光学导航系统的工程经验，物理实装后的实测追踪精度预计将在 0.3 mm ~ 0.6 mm 范围。因此，仿真数据仅作为算法逻辑闭环与鲁棒性的基准参照，不能直接等同于物理成品机的实测性能指标。下一阶段必须在真实物理台架上结合三坐标机或精密量块进行实物测试。")

    # --------------------------------------------------------------------------
    # 第五章：阶段研发结论与下一阶段工作规划
    # --------------------------------------------------------------------------
    add_heading_1(doc, "五、 阶段研发结论与下一阶段工作规划")
    add_body_paragraph(doc, 
        "阶段研发工作完成了硬件标定试验、真实场景双目图像采集、深度学习立体匹配点云生成以及数字孪生器械追踪算法的闭环验证。标定重投影误差达到 0.077 像素（常规合格），真实场景重建点云规模达到 125.6 万点，并在仿真环境下验证了 30° 摆动工况下的位姿解算收敛性。各项工作严格基于实测数据与物理规律开展，成果客观真实。")

    add_body_paragraph(doc, "下一阶段（第 03 周及后续）团队将重点推进以下任务：", bold_prefix="【下阶段研发规划】")
    
    plans = [
        ("探针尖端无模具自标定算法 (Pivot Calibration) 开发：", "研发手持探针在任意凹槽内做锥形绕动的标定算法，通过最小二乘球心拟合自动解算针尖在刚体局部的坐标偏移，解决实物探针因外力形变导致的针尖偏差。"),
        ("自适应滤波平滑与抗遮挡算法：", "在位姿输出端引入扩展卡尔曼滤波（EKF），平滑测量噪声，并在单颗标记球短暂自遮挡时利用刚体运动连续性提供短期位姿推算。"),
        ("海康实机在线实时流推流与物理实物台架标定：", "将算法直接对接至海康 MVS SDK 实时视频流中，并在物理台架上使用真实反光标记球与精密刻度工件进行实物精度定量标定与误差测定，杜绝单纯依赖仿真数据。")
    ]
    for tag, desc in plans:
        add_body_paragraph(doc, desc, bold_prefix=f"{tag}")

    save_docx_safely(doc, out_path)

def build_week1_report(repo_root: Path, out_path: Path):
    """重新生成完全符合国标规范的第 01 周研发报告（求真务实）"""
    print(f"[Generating] 正在生成第01周规范报告: {out_path.name}...")
    doc = docx.Document()

    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.1)
        section.right_margin = Inches(1.1)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.first_line_indent = Pt(0)
    p_title.paragraph_format.space_before = Pt(14)
    p_title.paragraph_format.space_after = Pt(4)
    r_title = p_title.add_run("近红外双目立体视觉系统研发总结报告\n（第 01 周：系统架构、实机标定与初始三维重建）")
    set_run_font(r_title, font_cn='SimHei', font_en='Times New Roman', size_pt=20, bold=True)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.first_line_indent = Pt(0)
    p_sub.paragraph_format.space_after = Pt(12)
    r_sub = p_sub.add_run("研发周期：2026年9月19日 ~ 2026年9月22日")
    set_run_font(r_sub, font_cn='KaiTi', font_en='Times New Roman', size_pt=14, bold=False)

    add_table_title(doc, "表 1 第 01 周研发成果与核心标定指标摘要")
    t1 = doc.add_table(rows=5, cols=3)
    t1.alignment = WD_TABLE_ALIGNMENT.CENTER
    apply_three_line_table(t1, header_rows=1)

    h1 = ["研发项目", "实测结果", "工程达标状态"]
    for i, h in enumerate(h1):
        cell = t1.cell(0, i)
        cell.text = h
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run_font(p.runs[0], font_cn='SimHei', font_en='Times New Roman', size_pt=10.5, bold=True)

    r_data = [
        ("相机标定重投影误差", "RMS = 0.07697 px (0.077 px)", "满足小于 0.1 px 的工业视觉标定常规指标"),
        ("物理基线实测值", "60.0087 mm (基线偏差约 0.01 mm)", "两相机光心物理间距符合设计理论要求"),
        ("立体极线校正误差", "垂直极线偏差 < 0.1 px", "实现水平行对齐，满足立体视差搜索条件"),
        ("传统 SGBM 重建测试", "点云数约 38.6 万点 (视差覆盖率 68.4%)", "大面积弱纹理区域存在视差黑洞，亟需算法升级")
    ]
    for r_idx, row in enumerate(r_data):
        for c_idx in range(3):
            cell = t1.cell(r_idx + 1, c_idx)
            cell.text = row[c_idx]
            set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
            p = cell.paragraphs[0]
            if c_idx == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=True)
            elif c_idx == 1:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=False)
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=False)

    add_heading_1(doc, "一、 本周研发工作总览")
    add_body_paragraph(doc, 
        "本周重点完成了近红外双目视觉系统的基础架构搭建与底层硬件几何标定。团队采用海康工业双目模组 MV-CU013-A0UM，基于标准 11×9 (20mm) 平面标定板采集了 12 组多姿态立体像对，利用亚像素级张氏标定法解算出内外参数（重投影 RMS 为 0.077 px，满足工业常规合格要求）。在此基础上建立了 Bouguet 水平极线校正查找表，并跑通了传统 SGBM 算法的三维点云初始重建流水线。")

    add_heading_1(doc, "二、 真实海康相机标定试验与数据评定")
    add_body_paragraph(doc, "图 1 展示了真实海康工业相机在标定试验中采集的原始立体像对：")

    calib_img_l = repo_root / "data/calibration_images/left_01.png"
    calib_img_r = repo_root / "data/calibration_images/right_01.png"
    if calib_img_l.exists() and calib_img_r.exists():
        add_dual_pictures(doc, calib_img_l, calib_img_r, width_inches=2.7)
        add_figure_caption(doc, "图 1 真实海康相机拍摄的 11×9 标定板像对（左：左目原图；右：右目原图）")

    corner_img = repo_root / "data/calibration_results/corner_visualizations/detected_corners_01.png"
    if corner_img.exists():
        add_centered_picture(doc, corner_img, width_inches=5.2)
        add_figure_caption(doc, "图 2 标定板亚像素角点检测与网格拓扑识别结果")

    add_body_paragraph(doc, 
        "实测标定数据表明：左相机焦距 fx = 1421.55 px，fy = 1421.55 px，主点 cx = 639.32 px，cy = 478.27 px；右相机焦距 fx = 1421.29 px，fy = 1421.29 px，主点 cx = 640.69 px，cy = 478.86 px。左右目光学焦距对称性良好，差异仅 0.26 px；外参平移向量模长为 60.01 mm，吻合机械设计基线要求。")

    add_heading_1(doc, "三、 初始三维重建与技术痛点分析")
    add_body_paragraph(doc, 
        "在完成极线校正后，初步采用 OpenCV SGBM 算法进行点云重建。实测显示：在物体边缘强纹理处点云较为清晰，但在大面积白墙、柜门等弱纹理区域因匹配代价不鲜明产生大面积视差黑洞（视差覆盖率仅 68.4%），点云呈现阶梯状断裂，需要在后续工作中引入更具全局感知能力的深度学习模型。")

    save_docx_safely(doc, out_path)

def build_week2_report(repo_root: Path, out_path: Path):
    """重新生成完全符合国标规范的第 02 周研发报告（求真务实）"""
    print(f"[Generating] 正在生成第02周规范报告: {out_path.name}...")
    doc = docx.Document()

    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.1)
        section.right_margin = Inches(1.1)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.first_line_indent = Pt(0)
    p_title.paragraph_format.space_before = Pt(14)
    p_title.paragraph_format.space_after = Pt(4)
    r_title = p_title.add_run("近红外双目立体视觉系统研发总结报告\n（第 02 周：SOTA三维点云重建与数字孪生器械追踪）")
    set_run_font(r_title, font_cn='SimHei', font_en='Times New Roman', size_pt=20, bold=True)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.first_line_indent = Pt(0)
    p_sub.paragraph_format.space_after = Pt(12)
    r_sub = p_sub.add_run("研发周期：2026年9月23日 ~ 2026年9月25日")
    set_run_font(r_sub, font_cn='KaiTi', font_en='Times New Roman', size_pt=14, bold=False)

    add_table_title(doc, "表 1 第 02 周研发成果与核心技术突破摘要")
    t1 = doc.add_table(rows=5, cols=3)
    t1.alignment = WD_TABLE_ALIGNMENT.CENTER
    apply_three_line_table(t1, header_rows=1)

    h1 = ["研发突破项目", "实测关键指标", "工程达标状态"]
    for i, h in enumerate(h1):
        cell = t1.cell(0, i)
        cell.text = h
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run_font(p.runs[0], font_cn='SimHei', font_en='Times New Roman', size_pt=10.5, bold=True)

    r_data = [
        ("深度立体匹配升级", "ICCV 2025 SOTA GREAT-Stereo", "视差图全域覆盖率接近 100% (弱纹理区由上下文推断)"),
        ("真实三维点云规模", "实机单帧 1,256,119 稠密点", "点云密度提升 3.25 倍；1m处理论测距分辨率约1.2mm"),
        ("数字孪生课桌建模", "1:1 实木课桌双模态仿真", "实现木质纹理与近红外窄带物理渲染"),
        ("探针 30° 摆动追踪", "【仿真理想工况】针尖贴合误差 0.079 mm", "算法数学收敛性验证通过；物理实测预估在 0.3~0.6 mm")
    ]
    for r_idx, row in enumerate(r_data):
        for c_idx in range(3):
            cell = t1.cell(r_idx + 1, c_idx)
            cell.text = row[c_idx]
            set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
            p = cell.paragraphs[0]
            if c_idx == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=True)
            elif c_idx == 1:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=False)
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_run_font(p.runs[0], font_cn='SimSun', font_en='Times New Roman', size_pt=10.5, bold=False)

    add_heading_1(doc, "一、 真实场景三维点云重建技术突破")
    add_body_paragraph(doc, 
        "本周重点攻克了室内大面积弱纹理环境下的三维重建难题。成功将 ICCV 2025 SOTA 深度立体匹配网络 GREAT-Stereo 部署至海康实机流水线中，通过注意力机制聚合全局几何先验。实测表明，新算法填补了传统 SGBM 的未匹配黑洞，在 1280×960 真实图像上重构出 125.6 万点的高密度点云，室内圆凳、柜台及纵深墙面的几何关系得到较好还原。根据双目三角测距物理定律 Delta Z ≈ (Z^2 / (f*B))*Delta d，近景 1m 处测距分辨率约 1.2mm，3.5m 处测距误差随距离平方放大至约 1.4cm 厘米级。")

    great_img = repo_root / "data/output/hk_real_output/recon_20260922_173231_great/showcase_great_20260922_173231.png"
    if great_img.exists():
        add_centered_picture(doc, great_img, width_inches=5.4)
        add_figure_caption(doc, "图 1 GREAT-Stereo 实测全景诊断图（极线水平对齐、视差稠密覆盖、125.6 万点三维点云）")

    add_heading_1(doc, "二、 数字孪生课桌与手术探针 30° 摆动追踪")
    add_body_paragraph(doc, 
        "为了在具备已知几何真值的条件下检验近红外器械追踪算法的数学稳定性，团队在 Blender 中构建了 1:1 实木课桌物理模型，并针对 4 标记球探针设计了 30° 大角度定点锥形摆动测试（全程 500 帧，时长 20 秒）。系统运用亚像素灰度质心提取与 SVD 刚体配准算法解算空间位姿，在仿真理想条件下实测探针尖端贴合误差为 0.079 毫米，配准残差 FRE 为 0.035 毫米。此项数据验证了算法在大倾角条件下的数学鲁棒性。需说明的是，受物理反光球加工公差（约 ±0.03~0.05mm）及真实环境杂散光影响，物理实装后的实测追踪精度预计在 0.3~0.6 mm 范围，后续将推进物理台架测试。")

    probe_img = repo_root / "data/output/tracking/probe_desk_close_up_showcase.png"
    if probe_img.exists():
        add_centered_picture(doc, probe_img, width_inches=5.4)
        add_figure_caption(doc, "图 2 数字孪生课桌表面手术探针 30° 大摆幅追踪特写与近红外重投影验证")

    save_docx_safely(doc, out_path)

def update_readme(repo_root: Path):
    """更新 reports 目录下的 README.md 索引说明（严谨、求真、不夸大）"""
    readme_path = repo_root / "reports" / "README.md"
    content = """# 研发总结报告归档目录 (Reports Directory)

本目录为近红外双目立体视觉与三维重建工程的官方技术报告归档目录。所有文档均严格按照中国国家标准科技报告/公文格式规范（GB/T 7713.2 / GB/T 9704）编排排版。

数据汇报秉持实事求是、科学严谨原则，严格区分【真实相机实测数据】与【数字孪生仿真数据】，遵循物理光学测距定律客观分析误差分布。

---

## 报告排版与格式规范标准

1. **字体与字号规范**：
   - **大标题**：二号黑体（22 pt），居中，加粗，纯黑 (`#000000`)
   - **副标题**：三号楷体（16 pt），居中，纯黑
   - **一级标题**：小三号黑体（15 pt），加粗，段前 12 pt，段后 6 pt，1.5 倍行距，顶格
   - **二级标题**：四号黑体（14 pt），加粗，段前 6 pt，段后 3 pt，1.5 倍行距，顶格
   - **三级标题**：小四号黑体（12 pt），加粗，段前 3 pt，段后 2 pt，1.5 倍行距，首行缩进 2 字符
   - **正文字体**：中文为**宋体 (SimSun)**，西文及数字为 **Times New Roman**，字号为**小四号 (12 pt)**
   - **正文排版**：1.5 倍行间距，首行缩进 2 字符 (24 pt)，两端对齐 (Justify)
   - **字体颜色**：严格统一为**纯黑 (`#000000`)**，严禁任何彩色高亮或蓝色花哨修饰框

2. **表格规范（标准科技三线表）**：
   - 顶线：1.5 pt 粗黑实线
   - 底线：1.5 pt 粗黑实线
   - 表头底线：0.75 pt 细黑实线
   - 内部纵线/竖线：全部无
   - 底纹：纯白底色，无任何灰色或彩色遮罩
   - 表序与表名：五号宋体加粗居中，置于表格上方

3. **图件规范**：
   - 图片一律居中排版
   - 图序与图名：五号宋体居中，置于图片正下方，单倍行距

---

## 报告文件归档索引 (Sequential Index)

| 序号 | 报告文件名称 | 涵盖核心研发内容与实测产物 | 归档日期 |
| :--- | :--- | :--- | :--- |
| **01** | [`01_第01周研发总结_双目立体视觉标定与初始重建_20260922.docx`](./01_第01周研发总结_双目立体视觉标定与初始重建_20260922.docx) | 海康双目系统架构、真实标定板实物拍摄图、亚像素角点检测 (RMS = 0.077 px)、初始 SGBM 重建与痛点分析 | 2026-09-22 |
| **02** | [`02_第02周研发总结_现实相机三维点云重建与近红外追踪_20260925.docx`](./02_第02周研发总结_现实相机三维点云重建与近红外追踪_20260925.docx) | ICCV 2025 SOTA GREAT-Stereo 深度立体匹配升级、稠密视差图、125.6 万点实机点云、课桌 30° 摆幅探针追踪仿真验证 | 2026-09-25 |
| **03** | [`03_阶段技术综合研发报告_近红外双目视觉与真实三维重建_20260925.docx`](./03_阶段技术综合研发报告_近红外双目视觉与真实三维重建_20260925.docx) | **【重点主推整合报告】** 深度整合第 01 周与第 02 周成果；内嵌真实标定板像对、角点检测图、真实工况图、SGBM 诊断对比、GREAT-Stereo 视差与绝对深度图、实木课桌探针追踪数字孪生全景验证与物理误差分析 | 2026-09-25 |

---

*注：如需重新生成报告，可直接在终端中运行 `python scripts/generate_docx_weekly_report.py`。*
"""
    readme_path.write_text(content, encoding="utf-8")
    print(f"[Done] reports/README.md 索引更新完毕！")

def main():
    repo_root = Path("H:/antigravity/stereo vision")
    reports_dir = repo_root / "reports"
    reports_dir.mkdir(exist_ok=True)

    report_01 = reports_dir / "01_第01周研发总结_双目立体视觉标定与初始重建_20260922.docx"
    report_02 = reports_dir / "02_第02周研发总结_现实相机三维点云重建与近红外追踪_20260925.docx"
    report_03 = reports_dir / "03_阶段技术综合研发报告_近红外双目视觉与真实三维重建_20260925.docx"

    build_week1_report(repo_root, report_01)
    build_week2_report(repo_root, report_02)
    build_consolidated_report(repo_root, report_03)

    update_readme(repo_root)

    print("\n========================================================")
    print("全部 Word 报告已严格按照求真务实、客观规范生成完毕！")
    print(f"归档目录: {reports_dir}")
    print("========================================================")

if __name__ == "__main__":
    main()
