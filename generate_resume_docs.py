import docx
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import qn

def create_resume_document():
    doc = Document()
    
    # Page Margins
    for s in doc.sections:
        s.top_margin = Inches(0.8)
        s.bottom_margin = Inches(0.8)
        s.left_margin = Inches(0.9)
        s.right_margin = Inches(0.9)

    def set_font(run, ascii_font='Times New Roman', eastasia_font='宋体', size_pt=11, bold=False, italic=False, color=None):
        run.font.name = ascii_font
        run.font.size = Pt(size_pt)
        run.font.bold = bold
        run.font.italic = italic
        if color:
            run.font.color.rgb = color
        rPr = run.element.get_or_add_rPr()
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None:
            rFonts = OxmlElement('w:rFonts')
            rPr.append(rFonts)
        rFonts.set(qn('w:eastAsia'), eastasia_font)

    def add_title(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(12)
        run = p.add_run(text)
        set_font(run, 'Times New Roman', '黑体', 18, True, color=RGBColor(31, 78, 121))
        return p

    def add_h1(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        set_font(run, 'Times New Roman', '黑体', 14, True, color=RGBColor(31, 78, 121))
        return p

    def add_h2(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        set_font(run, 'Times New Roman', '黑体', 12, True, color=RGBColor(44, 98, 140))
        return p

    def add_body(text, bold_prefix=None, indent=True):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.line_spacing = 1.25
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        if indent:
            p.paragraph_format.first_line_indent = Pt(22)
        else:
            p.paragraph_format.first_line_indent = Pt(0)
            
        if bold_prefix:
            run_b = p.add_run(bold_prefix)
            set_font(run_b, 'Times New Roman', '黑体', 10.5, True)
        run_t = p.add_run(text)
        set_font(run_t, 'Times New Roman', '宋体', 10.5, False)
        return p

    def add_bullet(bold_prefix, text):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.line_spacing = 1.2
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Inches(0.25)
        run_b = p.add_run(bold_prefix)
        set_font(run_b, 'Times New Roman', '黑体', 10.5, True)
        run_t = p.add_run(text)
        set_font(run_t, 'Times New Roman', '宋体', 10.5, False)
        return p

    # --- DOCUMENT GENERATION ---
    add_title("机器人力控装配与测控上位机项目总结（简历实操版）")
    
    p_meta = doc.add_paragraph()
    p_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_meta = p_meta.add_run("基于代码库实际实现深度提炼 · 严格代码文件与参数指向 · 契合机器人学术与工程规范")
    set_font(r_meta, 'Times New Roman', '楷体', 10, italic=True, color=RGBColor(100, 100, 100))

    # SECTION 1
    add_h1("一、 六维力传感器上位机开发：分类归属与独立项目标题")
    add_body("在机器人软件与系统开发领域，六维力传感器驱动与可视化监控软件是非常重要的硬件在环（HIL）基础设施。它既展现了底层嵌入式协议解析能力，又展现了多线程数据可视化、数字信号滤波与工业交互系统架构能力。")
    
    add_h2("1.1 简历中的分类归属建议")
    add_bullet("分类方向一（推荐）：", "【机器人感知与软件系统】或【工业测控与上位机软件开发】。适合投递机器人软件工程师、系统集成工程师、嵌入式应用工程师。")
    add_bullet("分类方向二：", "【机器人力觉传感与驱动开发】。适合投递机器人底层控制工程师、力控算法工程师（作为力控算法的传感前置支撑项目）。")

    add_h2("1.2 独立项目标题推荐（可直接选填入简历）")
    add_bullet("标题推荐 1（工程全能型）：", "《基于 ROS 2 的高频六维力觉传感器驱动与多线程监测上位机开发》")
    add_bullet("标题推荐 2（面向精密装配）：", "《工业六维力传感器实时采集解析与力控监测上位机系统》")
    add_bullet("标题推荐 3（突出数据测控）：", "《基于 PyQt/Tkinter 与 ROS 2 的六维力觉标定、滤波与实时监控平台》")

    add_h2("1.3 该模块简历描述与实际代码指向（严格对应）")
    add_bullet("底层硬件协议解析与校验重同步引擎：", 
               "针对宇立 SRI M3815CA2 六轴力传感器，基于 Python serial 编写 RS485 连续上传（115200 baud, 8N1）高速通信驱动，精准解调 14 字节二进制数据帧（AA 55 帧头），实现 CRC8 校验与错帧自恢复机制；输出已解耦的 Fx/Fy/Fz 与 Mx/My/Mz 六维物理量。\n"
               "【对应代码指向】：src/force_sensor_yl/protocol.py（SRIFrameParser 类）、src/force_sensor_yl/driver.py（SRIForceSensor.connect 与数据流解析）")
    
    add_bullet("高频 ROS 2 驱动节点与自动去皮清零（Software Tare）：",
               "封装标准化 ROS 2 发布节点，以 500 Hz 频率异步发布 geometry_msgs/msg/WrenchStamped 消息；设计启动自检与软件清零机制，系统上电时自动连续采样 100 帧有效数据计算初始静态漂移均值并完成在线 Tare 扣除。\n"
               "【对应代码指向】：src/force_sensor_yl/node.py（ForceSensorNode 类、_tare 采样重置机制）")

    add_bullet("多线程实时监测上位机与动态主导力解算（GUI Monitor）：",
               "基于 Tkinter 与 Matplotlib 构建中文实时监测界面；设计双采样率解耦通道：显示端采用 8 Hz 低通滤波与 25 Hz 降采样避免波形高频粘连，底层保持 500 Hz 无损采集；实时计算受力矢量模长并解算空间主导受力轴（±X/±Y/±Z 动态判定）；集成无锁双向缓冲队列（deque）与毫秒级按需 CSV 数据录制与导出。\n"
               "【对应代码指向】：src/force_sensor_yl/monitor.py（ForceSensorMonitor 类、8Hz/25Hz 解耦设计、_dominant_axis 解算、CSV 记录器）")

    # SECTION 2
    add_h1("二、 小米手机主板力控柔顺装配项目：学术化简历技术要点")
    add_body("小米手机主板装配属于典型的非对称精密弱刚性薄壁构件卡扣装配（Snap-fit & Insertion）。装配间隙微米级，受装配壳体公差、夹具公差与机器人定位漂移影响，极易在进壳、卡扣斜插与垂直平整时发生单侧挤压、结构拉伤甚至断板。本项目通过六维导纳控制与阶段自适应策略实现了全自主无损伤柔顺入壳。")

    add_h2("2.1 项目核心信息（简历版）")
    add_body("面向小米手机主板精密柔顺装配系统开发", bold_prefix="项目名称：", indent=False)
    add_body("Rokae AR5-R（7-DOF 协作机械臂）、Rokae XB7（6-DOF 工业臂）、宇立 SRI M3815CA2 六维力传感器、xCoreSDK（C++）、ROS 2、Eigen、C++17", bold_prefix="硬件与软件平台：", indent=False)
    add_body("针对手机主板装配过程中微米级间隙、脆弱卡扣易折损及侧向接触自锁卡滞难题，基于 7-DOF/6-DOF 机械臂构建了 1 kHz 硬实时笛卡尔力控闭环，提出了阶段感知 6 维导纳控制律与接触力轨迹调速器（Trajectory Governor），实现了主板从斜插进壳、姿态顺应找平到恒力贴合到位的全流程平稳装配。", bold_prefix="项目摘要：", indent=False)

    add_h2("2.2 简历专业描述与学术语言匹配（Bullet Points）")
    
    add_bullet("1 kHz 笛卡尔空间硬实时闭环控制架构（Hard Real-Time Control & Redundancy）：",
               "基于 C++17 深入调用工业机器人 xCoreSDK 底层库，接管机器人伺服控制流，构建 1 kHz（1 ms 周期）笛卡尔空间实时运动闭环；针对 7-DOF 机械臂运动学冗余自运动流形（Self-motion Manifold），引入肘部角（Arm Angle）参数化几何约束，确保逆运动学（IK）映射的确定性、构型连续性与关节平滑平稳运行。\n"
               "【代码指向】：ar_admittance_control/src/ar_assembly_cartesian_6d_admittance_node.cpp（runActive 函数中 RtMotionControlCobot<7>、肘部角约束参数化、1ms 控制回调）")

    add_bullet("阶段感知 6 维笛卡尔导纳控制律（Phase-Aware 6D Admittance Control）：",
               "建立基于二阶质量-阻尼-弹簧（Mass-Damper-Spring）方程的笛卡尔空间位置基导纳控制律（PBAC），利用旋转向量指数映射将末端交互力矩严格解算为 SE(3) 空间姿态修正；针对手机主板装配工艺，将其划分为接近（Approach）、唇边接触（Lip Contact）、释放入壳（Release）、斜插进给（Insert）、找平校准（Flatten）与最终按压贴合（Seat）六大力学演变阶段，为各阶段动态配置轴向顺应掩码（Phase Masks）与力包络（Force Envelope）。\n"
               "【代码指向】：ar_assembly_cartesian_6d_admittance_node.cpp（phaseName 六阶段状态映射、Admittance6D 求解器、enabledAxes 掩码动态切换）")

    add_bullet("自适应接触轨迹调速器与脱困恢复机制（Trajectory Governor & Active Recovery）：",
               "提出基于接触力矢量的轨迹调节器（Trajectory Governor），当接触阻力或倾覆弯矩超过安全阈值（2.0 N / 0.10 Nm）时，以预设斜率动态抑制规划轨迹进给速率（Rate Ramp），并启动微幅回退释放与阻力卸载机制，有效防止主板受压破损并确保了物理交互全过程的无源性（Passivity）与系统稳定性。\n"
               "【代码指向】：ar_assembly_cartesian_6d_admittance_node.cpp（governor_force_trigger_n、trajectory_rate_ramp_per_s、recovery_clear_hold_s、recovery_resume_offset）")

    add_bullet("到位接触力闭环与极限双重安全屏障（Seat Force Regulation & Safety Watchdog）：",
               "在主板贴合到位阶段引入 Z 轴 25 N 恒定深压目标推力控制，实现卡扣稳固闭合；建立多层级软硬件安全防线：集成力传感器数据超时看门狗（50 ms）、关节软限位安全裕度校验（Soft Limit Margin）、TCP 跟踪误差超限熔断以及 35 N / 1.5 Nm 刚性硬保护急停机制。\n"
               "【代码指向】：ar_assembly_cartesian_6d_admittance_node.cpp（seat_target_force_n=25N、hard_force_n=35N、hard_torque_nm=1.5Nm、WrenchSafety 结构体）")

    add_bullet("工业臂装配点位通道对齐与反向安全抽取（XB7 Alignment & Reverse Extraction）：",
               "针对 XB7 工业机械臂，构建多点位高精度装配路径（P_SAFE -> p_ALMOST_EDGE_IN -> P_EDGE_IN -> P_Plus -> P_PRESSSS）；创新性提出工件坐标系下斜插点、平整点与按压点的 Y 轴严格几何通道对齐（Y = 2.1412 mm），消除下压干涉侧向摩擦阻力；设计严格倒序的反向安全拔出脱困指令链（reverse-release / reverse-extract）；针对大转矩工况下的关节轴故障，引入 Jerk 动力学约束与安全锁机制。\n"
               "【代码指向】：xb7_point_control/src/xb7_point_player.cpp、xb7_assembly.sh、xb7_records/SAFETY_LOCK_AXIS5_35610.txt")

    # SECTION 3
    add_h1("三、 实际工作与代码实现映射对应表（查验与背调支撑）")
    add_body("下表将你在简历中阐述的每一项能力与算法，精确对应到代码仓库中的具体文件、模块及函数，确保面试答辩与背景调查时具有 100% 真实依据：")

    # Table
    table = doc.add_table(rows=1, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    hdr_cells = table.rows[0].cells
    headers = ["简历能力维度", "理论与算法要点", "代码仓库对应文件", "核心参数 / 函数 / 实现逻辑"]
    col_widths = [Inches(1.2), Inches(1.8), Inches(1.8), Inches(2.2)]

    for i, h in enumerate(headers):
        hdr_cells[i].width = col_widths[i]
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        set_font(run, 'Times New Roman', '黑体', 9.5, True, color=RGBColor(255, 255, 255))
        # Set cell background to navy blue
        shading = parse_xml(r'<w:shd xmlns:w="http://schemas.openxmlformats.org/officeDocument/2006/math" fill="1F4E79"/>')
        hdr_cells[i]._tc.get_or_add_tcPr().append(shading)

    data = [
        ("力传感器驱动", "RS485协议解析、CRC8校验、错帧重同步", "src/force_sensor_yl/protocol.py\nsrc/force_sensor_yl/driver.py", "SRIFrameParser, AA 55帧头匹配, 14字节校验, 115200波特率"),
        ("力传感器上位机", "双速率解耦、主导力解算、无损CSV录制", "src/force_sensor_yl/monitor.py\nlaunch/monitor.launch.py", "8Hz低通+25Hz显示降采样(绘图不挤色块), 500Hz底层采集, dominant_axis受力矢量分析"),
        ("实时运动伺服", "1kHz硬实时闭环、冗余机械臂肘部角约束", "ar_admittance_control/src/ar_assembly_cartesian_6d_admittance_node.cpp", "rokae::RtMotionControlCobot<7>, 1ms周期回调, controllerPoint, elbow参数化求解"),
        ("6维导纳控制", "二阶虚拟阻抗模型、SE(3)姿态指数映射", "ar_admittance_control/include/ar_admittance_control/admittance_common.hpp", "Admittance6D::step, Mass/Damping/Stiffness解算, rotationVectorToMatrix姿态更新"),
        ("装配状态机", "分阶段阻抗调度、自适应轴掩码调度", "ar_assembly_cartesian_6d_admittance_node.cpp", "phaseName(APPROACH/LIP_CONTACT/RELEASE/INSERT/FLATTEN/SEAT), phaseMasks动态掩码"),
        ("自适应调速器", "阻力触发自适应减速、无源性保证、回退脱困", "ar_assembly_cartesian_6d_admittance_node.cpp", "governor_force_trigger_n(2.0N), trajectory_rate_ramp_per_s(4.0/s), recovery_resume_offset"),
        ("到位力控与安全", "恒力压紧闭环、多级力矩熔断与看门狗", "ar_assembly_cartesian_6d_admittance_node.cpp", "seat_target_force_n=25N, hard_force_n=35N, hard_torque_nm=1.5Nm, wrench_timeout_s=50ms"),
        ("轨迹通道对齐", "工业臂分段示教、Y轴平移对齐、反向抽取", "xb7_assembly.sh\nxb7_point_control/src/xb7_point_player.cpp", "Y=2.1412mm全局通道对齐, checkPath路径校验, reverse-release/reverse-extract反向抽取")
    ]

    for row_idx, row_data in enumerate(data):
        row_cells = table.add_row().cells
        for col_idx, cell_value in enumerate(row_data):
            row_cells[col_idx].width = col_widths[col_idx]
            p = row_cells[col_idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            run = p.add_run(cell_value)
            set_font(run, 'Times New Roman', '宋体', 9.0, False)
            if row_idx % 2 == 1:
                shading = parse_xml(r'<w:shd xmlns:w="http://schemas.openxmlformats.org/officeDocument/2006/math" fill="F2F5F8"/>')
                row_cells[col_idx]._tc.get_or_add_tcPr().append(shading)

    # SECTION 4
    add_h1("四、 面试高频追问与理论答辩话术准备")
    
    add_h2("4.1 追问：为什么手机主板装配必须做‘阶段感知’？为什么不能全过程开放六自由度导纳？")
    add_body("“手机主板装配不同于简单的圆柱轴孔。它包含柔性排线、精密卡扣和非对称边缘。在初期未进壳的接近阶段，如果直接放开多轴导纳，外部轻微风阻或惯性力会导致机械臂产生不必要的漂移，降低对准精度；在卡扣斜插阶段，我们需要沿斜下方刚性进给，但允许横向浮动顺应；而到了最终贴合下压阶段，我们需要 Z 轴恒力压紧，同时释放平面内的旋转力矩防止受力偏载折断主板。因此，必须引入‘阶段感知状态机’，根据装配几何深度与力学演化动态切换受控自由度的选择矩阵（Selection Matrix），做到该刚则刚、该柔则柔。”", bold_prefix="答辩要点：")

    add_h2("4.2 追问：你的轨迹调速器（Trajectory Governor）在数学和控制层面是怎么保证不压坏工件的？")
    add_body("“传统位置控制机械臂一旦规划好时间参数轨迹，遇到阻力仍会强行向前走，导致接触力随时间积分呈指数级暴涨。我设计的 Trajectory Governor 本质上是在名义轨迹进度 s(t) 上施加了动态阻尼：当传感器检测到接触合力超过阈值（如 2.0 N）时，控制器通过比例速率减速因子立即调低轨迹进度增长率 s_dot，使机械臂在接触点瞬间‘慢下来’甚至‘停下来’；同时，导纳外环利用接触力解算出的位移修正量将末端往离开工件的反方向推，二者协同实现主动卸力。当接触力回落至安全阈值以下并维持特定驻留时间后，系统再平滑恢复进给。”", bold_prefix="答辩要点：")

    add_h2("4.3 追问：XB7 机械臂调试中出现的 35610 Axis 5 转矩故障是什么原因？你怎么解决的？")
    add_body("“该故障是机械臂第 5 轴（腕部俯仰轴）瞬态电机转矩超限。深孔装配时，由于工件坐标系标定微小偏差，下压过程中机械臂末端与壳体侧壁存在横向干涉挤压，导致第 5 轴承受了持续增大的倾覆弯矩；此外，离散点位切换时的加速度与加加速度（Jerk）过大，激发出机械谐振。我的解决方案有两个：第一是在几何上对齐通道，将斜插点、平整点与最终按压点的工件 Y 坐标严格对齐为 2.1412 mm，消除了下压过程中的横向干涉应力；第二是在运动控制上引入 Jerk 约束，将非实时加速度/加加速度降至 20%/10%，并编写了安全故障锁定与自动脱困反向拔出脚本，彻底消除了该故障。”", bold_prefix="答辩要点：")

    output_path = "/home/liu/projects/git-demo-admittance/小米手机主板力控柔顺装配项目总结.docx"
    doc.save(output_path)
    print("Document successfully created at:", output_path)

if __name__ == '__main__':
    create_resume_document()
