# -*- coding: utf-8 -*-
"""
生成《珞石XB7机器人六维笛卡尔导纳柔顺装配系统技术交接与迭代指南》
专注交付六维力控导纳装配算法、底层实现、实测数据、配置参数、操作SOP及避坑指南。
"""

import os
import docx
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import qn, nsdecls

def build_docx():
    doc = Document()

    # 1. 页面设置：标准 A4，四周边距 1 英寸
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.different_first_page_header_footer = False

    # 2. 颜色定义
    COLOR_PRIMARY = RGBColor(27, 54, 93)      # 科技深蓝 #1B365D
    COLOR_SECONDARY = RGBColor(46, 91, 136)   # 中深蓝 #2E5B88
    COLOR_ACCENT = RGBColor(194, 65, 12)      # 强调橙 #C2410C
    COLOR_TEXT = RGBColor(30, 41, 59)         # 正文深灰 #1E293B
    COLOR_MUTED = RGBColor(100, 116, 139)     # 辅助灰 #64748B
    HEX_PRIMARY = "1B365D"
    HEX_LIGHT_BG = "F1F5F9"
    HEX_WARN_BG = "FEF3C7"
    HEX_BORDER = "CBD5E1"

    # 3. 基础正文样式
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Times New Roman'
    normal_style.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = COLOR_TEXT
    normal_style.paragraph_format.line_spacing = 1.35
    normal_style.paragraph_format.space_after = Pt(4)

    # 4. 排版辅助函数
    def add_title(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(text)
        run.font.name = 'Times New Roman'
        run.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
        run.font.size = Pt(22)
        run.font.bold = True
        run.font.color.rgb = COLOR_PRIMARY
        return p

    def add_subtitle(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(18)
        run = p.add_run(text)
        run.font.name = 'Times New Roman'
        run.element.rPr.rFonts.set(qn('w:eastAsia'), '楷体')
        run.font.size = Pt(13)
        run.font.color.rgb = COLOR_MUTED
        return p

    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Times New Roman'
        run.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
        run.font.size = Pt(15)
        run.font.bold = True
        run.font.color.rgb = COLOR_PRIMARY
        return p

    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(13)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Times New Roman'
        run.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
        run.font.size = Pt(12.5)
        run.font.bold = True
        run.font.color.rgb = COLOR_SECONDARY
        return p

    def add_h3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Times New Roman'
        run.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = COLOR_TEXT
        return p

    def add_p(text, bold_prefix=None):
        p = doc.add_paragraph()
        if bold_prefix:
            run_b = p.add_run(bold_prefix)
            run_b.font.name = 'Times New Roman'
            run_b.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
            run_b.font.bold = True
            run_b.font.color.rgb = COLOR_TEXT
        run = p.add_run(text)
        run.font.name = 'Times New Roman'
        run.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        run.font.size = Pt(11)
        run.font.color.rgb = COLOR_TEXT
        return p

    def add_bullet(text, bold_prefix=None):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.3
        if bold_prefix:
            run_b = p.add_run(bold_prefix)
            run_b.font.name = 'Times New Roman'
            run_b.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
            run_b.font.bold = True
            run_b.font.color.rgb = COLOR_TEXT
        run = p.add_run(text)
        run.font.name = 'Times New Roman'
        run.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        run.font.size = Pt(10.5)
        return p

    def add_callout(text, title="【重要注意】", warn=False):
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        bg_hex = HEX_WARN_BG if warn else HEX_LIGHT_BG
        border_hex = "D97706" if warn else HEX_PRIMARY
        
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg_hex}"/>')
        borders = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'  <w:top w:val="none"/>'
            f'  <w:left w:val="single" w:sz="24" w:space="0" w:color="{border_hex}"/>'
            f'  <w:bottom w:val="none"/>'
            f'  <w:right w:val="none"/>'
            f'</w:tcBorders>'
        )
        tcPr.append(shd)
        tcPr.append(borders)

        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(5)
        p.paragraph_format.space_after = Pt(5)
        p.paragraph_format.line_spacing = 1.3
        run_t = p.add_run(title + " ")
        run_t.font.name = 'Times New Roman'
        run_t.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
        run_t.font.bold = True
        run_t.font.color.rgb = RGBColor(180, 83, 9) if warn else COLOR_PRIMARY
        
        run_c = p.add_run(text)
        run_c.font.name = 'Times New Roman'
        run_c.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        run_c.font.size = Pt(10)
        doc.add_paragraph()

    def add_code_block(code_text):
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F8FAFC"/>')
        borders = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'  <w:top w:val="single" w:sz="4" w:color="CBD5E1"/>'
            f'  <w:left w:val="single" w:sz="16" w:color="475569"/>'
            f'  <w:bottom w:val="single" w:sz="4" w:color="CBD5E1"/>'
            f'  <w:right w:val="single" w:sz="4" w:color="CBD5E1"/>'
            f'</w:tcBorders>'
        )
        tcPr.append(shd)
        tcPr.append(borders)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        run = p.add_run(code_text)
        run.font.name = 'Consolas'
        run.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        run.font.size = Pt(9.5)
        run.font.color.rgb = RGBColor(15, 23, 42)
        doc.add_paragraph()

    def style_table(table, col_widths=None):
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, row in enumerate(table.rows):
            trPr = row._tr.get_or_add_trPr()
            trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
            if i == 0:
                trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
            
            for j, cell in enumerate(row.cells):
                if col_widths and j < len(col_widths):
                    cell.width = Inches(col_widths[j])
                tcPr = cell._tc.get_or_add_tcPr()
                borders = parse_xml(
                    f'<w:tcBorders {nsdecls("w")}>'
                    f'  <w:top w:val="single" w:sz="4" w:color="CBD5E1"/>'
                    f'  <w:left w:val="none"/>'
                    f'  <w:bottom w:val="single" w:sz="4" w:color="CBD5E1"/>'
                    f'  <w:right w:val="none"/>'
                    f'</w:tcBorders>'
                )
                tcPr.append(borders)
                if i == 0:
                    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{HEX_PRIMARY}"/>')
                    tcPr.append(shd)
                    for p in cell.paragraphs:
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        p.paragraph_format.space_before = Pt(5)
                        p.paragraph_format.space_after = Pt(5)
                        for r in p.runs:
                            r.font.bold = True
                            r.font.color.rgb = RGBColor(255, 255, 255)
                            r.font.size = Pt(10)
                else:
                    if i % 2 == 1:
                        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F8FAFC"/>')
                        tcPr.append(shd)
                    for p in cell.paragraphs:
                        p.paragraph_format.space_before = Pt(4)
                        p.paragraph_format.space_after = Pt(4)
                        p.paragraph_format.line_spacing = 1.2
                        for r in p.runs:
                            r.font.size = Pt(9.5)

    # ========================== 文档生成内容 ==========================

    add_title("珞石 XB7 机械臂六维力控导纳装配系统")
    add_subtitle("技术交接文档与后继开发迭代指南 (基于 TA67L 六维力传感器的实时闭环控制)")

    # 封面概览元数据表
    meta_table = doc.add_table(rows=5, cols=2)
    meta_table.rows[0].cells[0].paragraphs[0].add_run("系统名称：XB7 机械臂 6D 笛卡尔导纳柔顺装配系统")
    meta_table.rows[0].cells[1].paragraphs[0].add_run("版本编号：v2.0-Admittance-Release")
    meta_table.rows[1].cells[0].paragraphs[0].add_run("工作空间：/home/liu/projects/git-demo-admittance")
    meta_table.rows[1].cells[1].paragraphs[0].add_run("驱动路径：/home/liu/下载/xCoreSDK-v0.7.1.ar_6")
    meta_table.rows[2].cells[0].paragraphs[0].add_run("控制架构：ROS 2 Jazzy + Rokae xCore 1000Hz 实时接口")
    meta_table.rows[2].cells[1].paragraphs[0].add_run("传感单元：坤维科技 TA67L 压电六维力传感器")
    meta_table.rows[3].cells[0].paragraphs[0].add_run("通讯网络：控制器 192.168.2.160 / 上位机 192.168.2.100")
    meta_table.rows[3].cells[1].paragraphs[0].add_run("核心算法：阶段感知六维空间导纳 + 正常力包络学习")
    meta_table.rows[4].cells[0].paragraphs[0].add_run("文档密级：核心工程研发交接资料")
    meta_table.rows[4].cells[1].paragraphs[0].add_run("编写日期：2026 年 9 月")
    style_table(meta_table, [3.2, 3.2])
    doc.add_paragraph()

    # ------------------ 第 1 章 ------------------
    add_h1("一、 系统工程定位与装配难点解析")
    add_p(
        "在 3C 消费电子行业（如智能手机主板、精密接插件）的自动化装配作业中，主板与中框卡槽的配合公差极小（通常在 0.05mm~0.2mm 之间），装配工序具有极高的空间约束性。"
    )
    add_p(
        "传统工业机械臂纯位置控制方案在此类精密装配中存在致命痛点："
    )
    add_bullet(
        "由于来料尺寸微差、工装夹具磨损以及吸盘/夹爪抓取误差，零件在进入卡槽时不可避免地存在 0.1~0.5mm 的侧向偏移或 0.5°~2° 的姿态倾角。",
        bold_prefix="1. 定位误差不可消除："
    )
    add_bullet(
        "机械臂本体刚度极高，一旦发生干涉，位置闭环仍强制按规划轨迹推进，导致侧向接触力迅速飙升至 60N~90N 以上，极易刮伤零件外壳、压断金手指引脚，甚至触发机械臂关节伺服力矩过载硬急停。",
        bold_prefix="2. 刚性干涉引发过载报废："
    )
    add_bullet(
        "不同于简单轴孔直插，精密主板装配通常需要经历“斜插进入 -> 贴合逼近 -> 旋转下压入座”的多姿态复合过程，单纯的被动柔顺器（如弹簧浮动头）无法满足复杂的空间控力需求。",
        bold_prefix="3. 复合装配轨迹的姿态自适应："
    )
    add_p(
        "本项目依托珞石 (Rokae) XB7 六轴工业机械臂，末端串联集成坤维 TA67L 高精度六维力传感器，构建了一套在工件坐标系下的阶段感知六维笛卡尔导纳控制闭环系统（6D Cartesian Admittance Control）。系统将标定示教轨迹作为“中心吸引子”，实时根据接触力传感器测得的超额接触力/力矩，动态修正末端执行器的 6 自由度空间位姿，实现“以力导位、顺应卡槽、微米自对心、平稳入座”。"
    )

    # ------------------ 第 2 章 ------------------
    add_h1("二、 软硬件运行环境与系统拓扑")
    add_h2("2.1 硬件设备与传感器接线配置")
    
    hw_table = doc.add_table(rows=6, cols=3)
    hw_headers = ["设备组件", "型号规格与关键指标", "物理接线与通讯协议"]
    for j, h in enumerate(hw_headers):
        hw_table.rows[0].cells[j].paragraphs[0].add_run(h)
    
    hw_data = [
        ("工业机器人本体", "Rokae XB7s-R707-3J 六轴工业臂", "额定负载 7kg，工作半径 707mm，法兰接口 ISO 9409-1-50-4-M6"),
        ("机器人控制器", "Rokae xCore 控制柜，系统版本 3.2.2", "双网口，LAN1 直连上位工控机，静态 IP: 192.168.2.160"),
        ("六维力传感器", "坤维科技 (Kunwei) TA67L 压电/应变式", "量程: Fxyz ±200N, Mxyz ±5N·m；通讯: RS-485 (Modbus-RTU)"),
        ("通讯转接器", "工业级 USB 转 RS-485 隔离转换器 (CH340/CH341)", "固定串口映射: /dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"),
        ("上位机计算平台", "高性能工控机 / 笔记本 Linux x86_64", "静态 IP: 192.168.2.100 (掩码 255.255.255.0)，与控制器百兆直连")
    ]
    for row_idx, data in enumerate(hw_data, start=1):
        for col_idx, val in enumerate(data):
            hw_table.rows[row_idx].cells[col_idx].paragraphs[0].add_run(val)
    style_table(hw_table, [1.5, 2.3, 2.6])
    doc.add_paragraph()

    add_h2("2.2 核心软件框架与依赖环境")
    add_bullet("操作系统：Ubuntu 24.04 LTS (x86_64)")
    add_bullet("机器人操作系统：ROS 2 Jazzy Jalisco")
    add_bullet("机械臂底层驱动库：Rokae xCoreSDK v0.7.1.ar_6（C++17 封装，本地路径 `/home/liu/下载/xCoreSDK-v0.7.1.ar_6`）")
    add_bullet("数学运算库：Eigen 3.4+（用于 6D 空间旋转向量、四元数变换与矩阵求逆，配置 `EIGEN_DONT_ALIGN_STATICALLY`）")
    add_bullet("坐标系定义：装配末端夹爪工具坐标系命名为 `g_tool_1`，装配底座参考坐标系命名为 `g_wobj_0`，两者已在示教器（RobotAssist）中标定保存。")

    add_h2("2.3 代码工作空间目录拓扑与编译指南")
    add_p(
        "本项目完整的 ROS 2 工作空间根目录绝对路径为："
    )
    add_code_block("/home/liu/projects/git-demo-admittance")
    add_p("工作空间内部核心功能包、配置文件、数据归档以及关键入口脚本的目录拓扑与职责划分如下表所示：")

    ws_table = doc.add_table(rows=8, cols=3)
    ws_headers = ["功能模块 / 目录相对路径", "类型与主要内容", "职责定位与工程说明"]
    for j, h in enumerate(ws_headers):
        ws_table.rows[0].cells[j].paragraphs[0].add_run(h)
    
    ws_data = [
        ("ar_admittance_control/", "ROS 2 C++ 核心功能包", "六维空间笛卡尔导纳控制算法核心实现包，包含实时控制主循环、阶段感知正常力包络、轨迹减速器看门狗及参数加载模块。"),
        ("force_sensor_ta67l/", "ROS 2 Python/C++ 驱动包", "坤维 TA67L 六维力传感器驱动与可视化看板，提供串口 Modbus-RTU 采集、实时低通滤波、多子图波形监控看板及 CSV 导出。"),
        ("xb7_point_control/", "ROS 2 Python 控制包", "机械臂点位示教、坐标系读取、笛卡尔运动规划与关节状态查询模块。"),
        ("launch/", "系统启动脚本目录", "包含六维导纳装配系统主启动文件 xb7_assembly_cartesian_6d_admittance.launch.py 及传感器看板启动文件 monitor.launch.py。"),
        ("xb7_records/", "标定点位与示教轨迹库", "存放装配关键点位与插补轨迹 CSV，包含核心装配轨迹 xb7_assembly_new_full_20260929.csv 与反向退出轨迹。"),
        ("~/force_sensor_logs/\n(/home/liu/force_sensor_logs/)", "实验数据记录归档目录", "由六维力监控看板自动保存的实测六维受力 CSV 原始数据集（如 ta67l_20260929_164459_final.csv）。"),
        ("xb7_admittance.sh", "系统主控 Shell 脚本", "一键式交互脚本，集成 status（健康检查）、shadow（安全只读仿真）与 run（实机上电装配）三大运行模式。")
    ]
    for row_idx, data in enumerate(ws_data, start=1):
        for col_idx, val in enumerate(data):
            ws_table.rows[row_idx].cells[col_idx].paragraphs[0].add_run(val)
    style_table(ws_table, [2.0, 1.8, 2.6])
    doc.add_paragraph()

    add_p("工作空间完整构建与环境变量激活命令（后继开发者接手编译规范）：")
    add_code_block(
        "# 1. 切换至工作空间根目录\n"
        "cd /home/liu/projects/git-demo-admittance\n\n"
        "# 2. 激活底层 ROS 2 Jazzy 环境\n"
        "source /opt/ros/jazzy/setup.bash\n\n"
        "# 3. 执行全量编译（使用软链接模式便于 Python 调试，开启 Release 优化）\n"
        "colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=Release\n\n"
        "# 4. 激活当前工作空间环境（必须在每个新终端中执行）\n"
        "source install/setup.bash"
    )

    # ------------------ 第 3 章 ------------------
    add_h1("三、 核心示教基准点位与装配阶段分解")
    add_p(
        "力控导纳算法必须基于一条高质量的名义示教轨迹（Nominal Trajectory）展开。当前系统加载的核心点位数据来自文件：`xb7_records/xb7_assembly_new_full_20260929.csv`。"
    )
    add_p(
        "整个装配过程被分解为四个关键位姿，各点位在工件参考系 `g_wobj_0` 下的物理坐标及分段速度如下表所示："
    )

    pts_table = doc.add_table(rows=5, cols=4)
    pts_headers = ["阶段点名", "工件参考系下 TCP (X, Y, Z / mm)", "姿态欧拉角 (Rx, Ry, Rz / deg)", "规划插补速度与工艺作用"]
    for j, h in enumerate(pts_headers):
        pts_table.rows[0].cells[j].paragraphs[0].add_run(h)
    
    pts_content = [
        ("P_SAFE_NEW\n(起始安全点)", "X: 587.755\nY: 2.022\nZ: +2.291", "Rx: -179.97\nRy: -16.27\nRz: -178.65", "起点准备位；工件悬空处于卡槽上方安全区，准备开始斜插靠近。"),
        ("pxiecha2\n(斜插过渡点)", "X: 615.689\nY: 2.652\nZ: -5.198", "Rx: -179.88\nRy: -9.61\nRz: -178.65", "速度 0.6 mm/s；零件前端倾斜插入中框限位槽内，完成粗对齐。"),
        ("pbijing1\n(贴合逼近点)", "X: 616.096\nY: 2.683\nZ: -6.965", "Rx: -179.86\nRy: -7.66\nRz: -178.65", "速度 0.2 mm/s；零件完全接触弹片与内壁，阻力开始建立，导纳纠偏核心段。"),
        ("pfinal4\n(最终压合点)", "X: 615.966\nY: 2.891\nZ: -7.598", "Rx: 179.87\nRy: -6.15\nRz: -178.90", "速度 0.1 mm/s；微速下压使卡扣完全闭锁落座，法向压力达到 35N。")
    ]
    for row_idx, data in enumerate(pts_content, start=1):
        for col_idx, val in enumerate(data):
            pts_table.rows[row_idx].cells[col_idx].paragraphs[0].add_run(val)
    style_table(pts_table, [1.5, 1.8, 1.5, 1.6])
    doc.add_paragraph()

    add_callout(
        "反向释放与退出轨迹（Reverse Trajectory）：当装配完成需要拔出检查，或装配测试需要回退时，必须严格执行与进给互为倒序的轨迹：pfinal4 -> pbijing1 -> pxiecha2 -> P_SAFE_NEW。严禁在入座状态下直接执行关节 MoveAbsJ 直线拉升，否则会因倾斜角度强行卡折工装定位销！对应反向文件为 xb7_assembly_new_reverse_full_20260929.csv。",
        title="【轨迹倒序工艺要点】"
    )

    # ------------------ 第 4 章 ------------------
    add_h1("四、 六维空间笛卡尔导纳控制算法深度剖析")
    add_p(
        "导纳控制的核心思想是将机械臂末端虚拟化为一个具有特定“质量-阻尼-刚度”特性的二阶机械阻抗系统。当外界接触力超出设定的正常阈值时，算法自适应计算出顺应位移并叠加到名义位姿上。"
    )

    add_h2("4.1 导纳控制核心微分方程与参数配置")
    add_p("六维笛卡尔导纳动力学方程定义为：")
    add_code_block("M * e_ddot + D * e_dot + K * e = W_excess")
    add_p("其中六维状态向量定义为：`[X, Y, Z, Rx, Ry, Rz]`，平移单位为米 (m)，转动单位为弧度 (rad)；力单位为牛顿 (N)，力矩单位为牛·米 (N·m)。各物理参数在 `xb7_assembly_cartesian_6d_admittance.yaml` 中的调定取值如下：")

    param_table = doc.add_table(rows=7, cols=3)
    param_headers = ["动力学参数", "调定数值 (X, Y, Z, Rx, Ry, Rz)", "工程设计依据与调谐准则"]
    for j, h in enumerate(param_headers):
        param_table.rows[0].cells[j].paragraphs[0].add_run(h)
    
    param_data = [
        ("虚拟质量矩阵 (M)", "平移: [5.0, 5.0, 5.0] kg\n旋转: [0.05, 0.05, 0.05] kg·m²", "平抑力传感器采样毛刺与加速度冲击，质量过小易抖动，过大会增加响应惯性。"),
        ("虚拟阻尼矩阵 (D)", "平移: [150.0, 150.0, 140.0] N·s/m\n旋转: [2.0, 2.0, 1.5] N·m·s/rad", "吸收冲击能量，决定纠偏速度。当前阻尼比接近过阻尼状态，确保运动无超调振荡。"),
        ("虚拟刚度矩阵 (K)", "平移: [800.0, 5000.0, 3000.0] N/m\n旋转: [15.0, 15.0, 10.0] N·m/rad", "X 轴设定较小刚度 (800 N/m) 允许大范围顺应纠偏；Y/Z 轴设定高刚度保证垂直插装精度。"),
        ("力传感器死区阈值", "平移: [0.5, 0.5, 0.5] N\n旋转: [0.03, 0.03, 0.03] N·m", "忽略静止零漂和线缆抖动噪声，死区内的微小力不引起机械臂响应。"),
        ("低通滤波截止频率", "filter_cutoff_hz: 10.0 Hz", "一阶巴特沃斯数字低通滤波，滤除 25Hz 采样信号中的高频电磁杂波。"),
        ("最大偏移安全限幅", "平移: [±3.5mm, ±1.5mm, ±1.5mm]\n旋转: [±1.0°, ±1.0°, ±0.1°]", "硬限幅看门狗，防止传感器断线或撞机时机械臂大范围发散失控。")
    ]
    for row_idx, data in enumerate(param_data, start=1):
        for col_idx, val in enumerate(data):
            param_table.rows[row_idx].cells[col_idx].paragraphs[0].add_run(val)
    style_table(param_table, [1.8, 2.3, 2.3])
    doc.add_paragraph()

    add_h2("4.2 阶段感知“正常力包络”(Normal Force Envelope) 机制")
    add_p(
        "在实际装配中，即使是完美装配，零件在摩擦和弹片挤压下也会产生正常的反力。传统的固定阈值力控无法区分“正常装配阻力”与“异常卡死碰撞”。"
    )
    add_p(
        "本系统创新实现了阶段感知力包络机制：通过无误差标准装配学习出 14 个进度节点（Progress 0.0 ~ 1.0）上各轴正常的力中心值 `center(s)` 与允许半宽 `half_width(s)`。"
    )
    add_bullet("当实际测量力在 `[center - half_width, center + half_width]` 内部时，`W_excess = 0`，导纳不介入，机械臂坚决推进。")
    add_bullet("当实际测量力超出包络上限（发生卡滞）或低于包络下限时，差值部分被定义为“超差力”：`W_excess = W_meas - Envelope`。导纳控制器仅对超差力做出卸力响应。")
    add_bullet("向零扩展特性：算法会自动将各轴包络向零扩展，确保悬空或未接触时的微弱力绝不会被误判为反向接触力。")

    add_h2("4.3 轨迹减速器 (Trajectory Governor) 协同调度")
    add_p(
        "为了避免机械臂在发生严重卡阻时因名义轨迹持续前进而把工件“强行挤碎”，系统设计了轨迹减速看门狗："
    )
    add_bullet("触发门限：当法向接触力超过 3.0 N 时，主轨迹推进速率自动以 4.0/s 的斜率急剧减速，乃至完全暂停主进给。")
    add_bullet("恢复机制：主轨迹暂停期间，导纳控制循环持续以 1000Hz 运行纠偏，当接触力卸除降至 1.5 N 以下并维持 0.2 秒后，主轨迹重新平滑加速恢复推进。")

    # ------------------ 第 5 章 ------------------
    add_h1("五、 实测装配实验对比与数据分析")
    add_p(
        "为了严密检验导纳系统的自对心与纠偏能力，我们在上位机中注入了横向误差（在名义轨迹的 X 轴人为叠加 +0.2mm 与 +0.5mm 偏差），并与原示教无误差基准数据进行了对比测试。"
    )

    # 插入实测对比曲线图
    chart_path = "/home/liu/projects/git-demo-admittance/force_comparison_curve.png"
    if os.path.exists(chart_path):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_img = p_img.add_run()
        run_img.add_picture(chart_path, width=Inches(6.2))
        p_caption = doc.add_paragraph()
        p_caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_cap = p_caption.add_run("图 1：XB7 机械臂六维导纳控制装配力学实测曲线对比图 (原示教基准 vs X=+0.2mm 导纳实测)")
        run_cap.font.name = 'Times New Roman'
        run_cap.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
        run_cap.font.size = Pt(9.5)
        run_cap.font.bold = True
        run_cap.font.color.rgb = COLOR_SECONDARY
        doc.add_paragraph()

    add_p("基于实机传感器采集日志（`ta67l_20260929_164459_final.csv` 与 `ta67l_20260929_175200x=+0.5.csv`）的量化对比指标如下：")

    exp_table = doc.add_table(rows=6, cols=4)
    exp_headers = ["力学评价指标", "原示教基准组 (0 误差)", "导纳控制组 (注入 X=+0.2mm)", "对比分析与控制结论"]
    for j, h in enumerate(exp_headers):
        exp_table.rows[0].cells[j].paragraphs[0].add_run(h)
    
    exp_data = [
        ("总受力模长 ||F|| 峰值", "41.5 N", "39.9 N", "未出现破坏性冲击力，全程受控于 45N 硬安全阈值之内。"),
        ("X 轴侧向纠偏力 (Fx)", "峰值 12.3 N", "峰值 4.5 N (平稳对心)", "注入 +0.2mm 侧向偏差后，Fx 无任何硬碰撞突变，自适应平滑卸载。"),
        ("最终落座压紧力 (Fz)", "-26.5 N", "-25.9 N", "压紧力绝对偏差仅 0.6 N，两组实验在最终到位时完全吻合。"),
        ("空间合力矩 ||M|| 峰值", "0.85 N·m", "0.80 N·m", "扭矩保持在极低水平，说明零件始终保持平行位姿，未出现倾斜扭曲卡死。"),
        ("装配完成成功率", "100%", "100%", "导纳算法成功吸收了 0.2mm 的装配定位误差，实现完全无损装配。")
    ]
    for row_idx, data in enumerate(exp_data, start=1):
        for col_idx, val in enumerate(data):
            exp_table.rows[row_idx].cells[col_idx].paragraphs[0].add_run(val)
    style_table(exp_table, [1.5, 1.4, 1.5, 2.0])
    doc.add_paragraph()

    # ------------------ 第 6 章 ------------------
    add_h1("六、 用户自研六维力传感器实时监视与录制页面 (monitor.py) 深度解析与实操指南")
    add_p(
        "为了在装配现场提供高可读性、低延迟的受力监控，并方便快速采集与归档实测力学曲线，系统配套开发了基于 ROS 2、Python Tkinter 与 Matplotlib 的专用交互式六维力监控与数据录制看板（对应源码：force_sensor_ta67l/src/force_sensor_ta67l/monitor.py，启动脚本：force_sensor_ta67l/launch/monitor.launch.py）。"
    )
    add_p(
        "在导纳参数调优、异常受力排查、安全边界验证以及对标实验中，该页面是最关键的实验数据记录与可视化分析工具。"
    )

    add_h2("6.1 界面三级子图结构与物理量读数解析")
    add_p("监视窗口默认以 1200x1000 像素高清呈现，主视图由上至下划分为三层联动子图，共享水平时间轴（默认展示过去 10.0 秒内的滑动时间窗）：")
    
    add_bullet(
        "实时展示传感器三向平移受力 Fx (蓝色)、Fy (橙色)、Fz (绿色)。坐标单位为牛顿 (N)。装配过程中的主要下压力表现为 Fz 负向增长，侧向自对心调整表现为 Fx/Fy 的瞬态波动与平抑。",
        bold_prefix="1. 顶层子图【力曲线 Force (N)】："
    )
    add_bullet(
        "实时展示传感器三向空间力矩 Mx (蓝色)、My (橙色)、Mz (绿色)。坐标单位为牛·米 (N·m)。若零件发生角度倾斜卡滞，该子图会灵敏反应出扭曲力矩的突增。",
        bold_prefix="2. 中间子图【力矩曲线 Torque (Nm)】："
    )
    add_bullet(
        "采用阶梯图 (Step Plot，紫色高亮线 #7b2cbf) 直观展示当前空间受力最显著的主导方向。Y 轴标定为 7 个状态档位：[-Z, -Y, -X, 无, +X, +Y, +Z]。当任意单轴受力绝对值超过设定阈值（默认 dominant_threshold_n = 0.10 N）时，算法自动提取幅值最大的轴向并在图上标定，现场工程师无需费力比对各曲线即可一眼看出机械臂正承受哪个方向的外力推压。",
        bold_prefix="3. 底层子图【主导受力轴判定 Dominant Axis】： "
    )
    add_bullet(
        "界面底部上方以醒目字体实时刷新显示：当前滤波后的六维数值（格式为 Fx=+0.012 N, Fy=-0.035 N, Fz=-0.120 N, Mx=... My=... Mz=...），以及当前在传感器坐标系下的主导力方向文本（例如：主导力（传感器坐标系）：+Z (-0.500 N) 或 无明显主导力）。",
        bold_prefix="4. 实时数值与主导力文字指示区："
    )
    add_bullet(
        "实时提示当前数据缓存状态，例如：“未记录：实时曲线不会自动保存”、“正在记录｜缓存样本：1250｜尚未保存”或“记录已停止｜缓存样本：1250｜尚未保存”。",
        bold_prefix="5. 录制状态看门狗提示条："
    )

    add_h2("6.2 界面交互控制按钮全功能与实操说明")
    add_p("窗口最底部横向集成了 5 个交互式操作按钮，采用 Tkinter/Matplotlib 原生事件响应机制，各功能定义与使用方法如下表：")

    btn_table = doc.add_table(rows=6, cols=3)
    btn_headers = ["控制按钮名称", "系统内部执行动作", "工程使用场景与操作时机"]
    for j, h in enumerate(btn_headers):
        btn_table.rows[0].cells[j].paragraphs[0].add_run(h)
    
    btn_data = [
        ("【开始/继续记录】", "触发 node.start_recording()，将 ROS 2 话题接收到的每一帧原始力数据压入内存数组 (array('d')) 缓存。", "在机械臂准备启动装配或开始下压前点击。支持中途断点续录。"),
        ("【停止记录】", "触发 node.stop_recording()，停止向内存压栈，但完整保留已录制的数据样本，提示栏显示已缓冲样本数与未保存标记。", "装配完成落座或实验终止后立即点击，锁定当前测试循环的数据片段。"),
        ("【保存CSV……】", "弹出图形化文件保存对话框 (asksaveasfilename)，默认推荐路径为 ~/force_sensor_logs/，并自动生成时间戳文件名。点击确定后将内存数据高速序列化为标准 CSV 文件。", "完成单次实验后点击保存。建议在文件名末尾添加本次工况备注（如 ta67l_20260929_175200x=+0.5.csv），便于离线批处理分析。"),
        ("【清空记录】", "触发 node.clear_recording()。若当前有未保存数据，会自动弹出二次确认对话框 (messagebox.askyesno) 防止误丢失，确认后重置内存缓存并清空脏标记。", "开始下一次全新装配实验前点击，清空上一次的历史样本。"),
        ("【暂停显示】\n(切换为【恢复显示】)", "仅冻结 Matplotlib 画布的动画刷新循环，记录最后时刻的视图快照；后台 ROS 2 订阅及 CSV 录制完全不受影响，持续在后台全速运行。", "当装配出现异响或突变峰值时点击暂停，可从容缩放/拖动查看突变瞬间波形，确认后点击恢复继续监视。")
    ]
    for row_idx, data in enumerate(btn_data, start=1):
        for col_idx, val in enumerate(data):
            btn_table.rows[row_idx].cells[col_idx].paragraphs[0].add_run(val)
    style_table(btn_table, [1.5, 2.3, 2.6])
    doc.add_paragraph()

    add_h2("6.3 双流数据处理架构：低通滤波显示与原始硬件采样录制分离")
    add_p(
        "在工业力控数据采集中，直接渲染 25Hz/1000Hz 原始高频数据会导致屏幕剧烈抖动频闪，给操作员带来视觉疲劳；但若对存储数据也执行强滤波，则会抹平瞬态碰撞冲击的峰值，丢失宝贵的真实物理特征。"
    )
    add_p("为此，监视程序采用了先进的“显示与录制双流正交解耦架构”：")
    add_bullet(
        "采用一阶数字低通滤波（默认截止频率 display_cutoff_hz = 8.0 Hz），并按 display_sample_rate_hz (25Hz) 重抽样后推入长度受限的双端队列 (deque) 进行滑动渲染，保证了画面平滑稳定且不失真。",
        bold_prefix="1. 屏幕显示渲染流 (Display Stream)："
    )
    add_bullet(
        "直接从 ROS 2 原始话题回调提取完整精度的浮点数据，完全不经过任何软件滤波，按真实硬件采样频率实时追加至底层高紧凑连续内存数组 (array('d'))，确保了落盘 CSV 数据的绝对保真度。",
        bold_prefix="2. 硬盘 CSV 录制流 (Recording Stream)："
    )
    add_p("保存生成的 CSV 文件包含 9 列标准物理量：")
    add_code_block("wall_time_s, ros_stamp_s, elapsed_s, fx_n, fy_n, fz_n, mx_nm, my_nm, mz_nm")

    add_h2("6.4 启动命令与常用参数微调")
    add_p("监视程序支持通过 ROS 2 Launch 传入自定义参数以适应不同工况：")
    add_code_block(
        "ros2 launch force_sensor_ta67l monitor.launch.py \\\n"
        "  port:=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 \\\n"
        "  serial_mode:=modbus \\\n"
        "  tare_on_start:=true \\\n"
        "  window_seconds:=15.0 \\\n"
        "  display_cutoff_hz:=8.0 \\\n"
        "  dominant_threshold_n:=0.10 \\\n"
        "  output_dir:=~/force_sensor_logs"
    )
    add_bullet("tare_on_start (默认 true)：节点启动时自动向传感器发送去皮清零指令，消除静置重力和零漂。")
    add_bullet("window_seconds (默认 10.0)：时间轴滑动窗口宽度，装配节拍较慢时可设为 15.0 或 20.0 秒。")
    add_bullet("dominant_threshold_n (默认 0.10 N)：主导方向判别的最小力阈值，低于此值显示为“无明显主导力”。")

    add_h2("6.5 典型装配实验联调闭环工作流 (标准化操作指引)")
    add_bullet("步骤 1【启动并清零】：在工控机终端 1 启动 monitor.launch.py，观察界面加载并等待“当前值”稳定归零（Fx, Fy, Fz 接近 ±0.01N）。")
    add_bullet("步骤 2【开始记录】：在界面上点击【开始/继续记录】，底部状态栏更新为“正在记录｜缓存样本：...”；")
    add_bullet("步骤 3【触发装配】：在终端 2 启动机械臂导纳程序（./xb7_admittance.sh shadow 或 run），工件开始按规划进给；")
    add_bullet("步骤 4【实时观察】：观察顶层 Fz 下压力曲线与中间扭矩曲线，同时用底层主导力判断卡槽侧壁挤压方向；")
    add_bullet("步骤 5【锁定并导出】：装配完成后立即点击【停止记录】，随后点击【保存CSV……】，命名保存为当前批次文件；")
    add_bullet("步骤 6【清空重置】：点击【清空记录】，确认对话框后重置，进入下一工件循环。")

    # ------------------ 第 7 章 ------------------
    add_h1("七、 操作运行 SOP 与调试标准化流程")

    add_h2("7.1 步骤一：力传感器上电、零点去皮与实时监控页面启动")
    add_p("在工控机终端 1 执行以下指令，启动 TA67L 串口采集节点、零点去皮（Tare）以及实时曲线可视化看板：")
    add_code_block(
        "source /opt/ros/jazzy/setup.bash\n"
        "cd /home/liu/projects/git-demo-admittance\n"
        "source install/setup.bash\n\n"
        "# 启动传感器驱动与监控页面，确保 tare_on_start 为 true\n"
        "ros2 launch force_sensor_ta67l monitor.launch.py \\\n"
        "  port:=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0 \\\n"
        "  serial_mode:=modbus \\\n"
        "  tare_on_start:=true"
    )
    add_p("启动成功后将弹出六维力实时监控窗口（详见第六章）。观察当前读数是否归零，并保持该终端在后台运行。")

    add_h2("7.2 步骤二：系统健康状态检查 (status)")
    add_p("在终端 2 运行状态检查脚本，确认机器人通讯与传感器频率：")
    add_code_block("./xb7_admittance.sh status")
    add_p("输出必须显示：`[OK] 成功 ping 通机械臂控制器: 192.168.2.160`，且 `/ta67l/wrench_raw` 话题稳定在 25 Hz 左右。")

    add_h2("7.3 步骤三：只读安全影子模式 (SHADOW 校验)")
    add_p("在正式上电让机械臂动作之前，必须先跑一次 SHADOW 模式：")
    add_bullet("在传感器监视页面点击【开始/继续记录】；")
    add_bullet("在终端 2 运行：`./xb7_admittance.sh shadow`；")
    add_bullet("特性：机械臂不上电、不动作，控制循环模拟轨迹推进。用手轻推传感器各轴，观察终端打印的 `OffsetXYZ` 是否与施力方向相反（避让逻辑），同时在监视页面核验受力方向阶梯图；")
    add_bullet("测试完毕在监视页面点击【停止记录】。")

    add_h2("7.4 步骤四：实机上电闭环装配 (ACTIVE 运行)")
    add_p("确认 SHADOW 校验无误后，佩戴手套，手持示教器急停按键，执行实机导纳装配：")
    add_bullet("在传感器监视页面点击【清空记录】，然后点击【开始/继续记录】；")
    add_bullet("在终端 2 运行：`./xb7_admittance.sh run`；")
    add_bullet("终端会要求输入安全口令确认：`ARM_XB7_ACTIVE`，回车后机械臂自动上电，切入实时控制模式，完整执行 6D 导纳柔顺装配；")
    add_bullet("装配到位停机后，立即在监控页面点击【停止记录】，并点击【保存CSV……】归档本次实验曲线。")

    # ------------------ 第 8 章 ------------------
    add_h1("八、 接手必读：技术内幕与工程避坑指南")
    add_p("本章汇集了在本项目开发调试过程中踩过的真实工程“深坑”，后继开发者在接手维护或进行二次开发时务必严格遵循：")

    add_h2("8.1 避坑点 1：传感器物理安装方向与工具 TCP 的旋转矩阵对齐")
    add_p(
        "TA67L 六维力传感器安装在机械臂第 6 轴法兰盘与夹爪之间。传感器自身的坐标系轴向（标注在外壳上）并不必然与夹爪 TCP 坐标系完全平行。"
    )
    add_callout(
        "灾难性后果：若在配置文件中 sensor_to_tool 旋转变换未标定或方向反相，当装配遇到侧向阻力时，导纳算法会错误地认为受力方向相反，进而驱动机械臂反向加大下压或侧推，形成严重的“正反馈发散震荡”，极速顶断夹具！\n"
        "排查守则：每次更换夹爪或拆卸传感器后，必须在 SHADOW 模式下用手轻推夹爪 +X，确认计算出的修正偏移量 dx 必定为负值（产生避让位移），并在传感器监视页面观察阶梯图是否显示为 +X。",
        title="【核心安全警示】",
        warn=True
    )

    add_h2("8.2 避坑点 2：25Hz 传感器采样与 1000Hz 实时控制循环的匹配延时")
    add_p(
        "坤维 TA67L 采用 RS-485 Modbus 轮询，受限于串口波特率（115200bps）与传感器内部 MCU 处理周期，其实际最大稳定发布频率为 25Hz（周期 40ms）。"
    )
    add_bullet("而 Rokae xCoreSDK 实时运动控制线程 `RtMotionControlIndustrial` 的内部调度周期必须为 1ms (1000Hz)。")
    add_bullet("设计对策：在 C++ 节点中设计了双缓冲线程安全锁与一阶低通插值器，每次拿到 25Hz 的最新力值后平滑插值到 1000Hz；同时看门狗超时时间 `wrench_timeout_s` 严禁设置过小（必须大于 0.15s，当前设为 0.20s），防止由于串口传输单次重发抖动误触发安全急停。")

    add_h2("8.3 避坑点 3：Rokae 机械臂断开与重新上电的 1.5~2.0 秒伺服抱闸时延")
    add_bullet("物理机理：在调用 `safeShutdown()` 断开机械臂时，控制器会将工作模式切回 `manual`，同时切断伺服动力电，机械刹车抱闸吸合（咔哒声），网络 TCP 套接字进入 TIME_WAIT。")
    add_bullet("踩坑教训：如果编写自动化批处理脚本，在断开后立即以 0 毫秒延时发起新的连接或上电指令，控制器将返回 `servo not ready` 或拒绝连接。")
    add_bullet("工程铁律：任何两次机械臂连接或模式切换之间，必须在脚本中预留至少 1.5 ~ 2.0 秒的缓冲时间 (`sleep 2`)。")

    add_h2("8.4 避坑点 4：到位的双重终止保护条件 (Position + Force)")
    add_bullet("装配到位判断采用“双重门限”原则：一是轨迹时间达到末端（Z 向物理深度到达），二是 Z 向下压接触力达到预定压紧力（当前设定 -25.0 N）。")
    add_bullet("工程防护：即使未到最大行程，如果持续接触力超过 `hard_force_n: 45.0 N`，系统看门狗会在 1ms 内直接切断动力电源紧急下电，确保 PCB 板绝不会被压碎。")

    # ------------------ 第 9 章 ------------------
    add_h1("九、 后继开发者的进阶迭代建议")
    add_p("本系统已打通了完整的感知-决策-执行实时闭环链路，后继研发人员可在此坚实基础上，沿着以下几个方向开展进阶研发：")
    add_bullet(
        "目前 TA67L 走串口 Modbus 限制在 25Hz，制约了高频接触碰撞的瞬态响应速度。建议下一阶段将传感器升级为 EtherCAT 总线型六维力传感器，直接接入上位机实时网口，实现 500Hz~1000Hz 同频采样，使导纳控制响应更加迅速凌厉。",
        bold_prefix="1. 传感器总线升级 (EtherCAT 代替 RS-485)："
    )
    add_bullet(
        "当装配轨迹在空中发生大角度姿态旋转（如倾斜 > 15°）时，夹爪自重在传感器各轴的分量会随重力矢量发生变化，产生虚假接触力。建议后续开发者在导纳计算前，加入基于欧拉角姿态的夹爪重力与偏心力矩实时补偿模型（Gravity Compensation）。",
        bold_prefix="2. 动态重力与末端负载自适应补偿："
    )
    add_bullet(
        "目前阻尼矩阵 D 为常数。可进一步探索变阻尼控制策略：在装配起始阶段采用大阻尼（快速消除初始位置偏差且不超调），进入狭窄深槽贴合后动态降低阻尼（提高柔顺依从性），在接触力陡增时增大阻尼（抑制反弹）。",
        bold_prefix="3. 变阻尼与可变刚度自适应学习算法："
    )

    output_path = "/home/liu/projects/git-demo-admittance/XB7机械臂六维力控导纳装配系统技术交接与迭代指南.docx"
    doc.save(output_path)
    print(f"技术交接文档已成功生成并保存至: {output_path}")

if __name__ == "__main__":
    build_docx()
