import docx
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import qn, nsdecls

def set_run_font(run, ascii_font='Times New Roman', eastasia_font='宋体', size_pt=12, bold=False):
    run.font.name = ascii_font
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    rPr = run.element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), eastasia_font)

def create_chapter3_docx():
    doc = Document()

    # Page margins
    for s in doc.sections:
        s.top_margin = Inches(1.0)
        s.bottom_margin = Inches(1.0)
        s.left_margin = Inches(1.18)
        s.right_margin = Inches(1.18)

    # Base normal style
    normal = doc.styles['Normal']
    normal.font.name = 'Times New Roman'
    rPr = normal.element.rPr
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), '宋体')
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.5

    def add_h1(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(14)
        run = p.add_run(text)
        set_run_font(run, 'Times New Roman', '黑体', 16, True)
        return p

    def add_h2(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(text)
        set_run_font(run, 'Times New Roman', '黑体', 14, True)
        return p

    def add_h3(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(text)
        set_run_font(run, 'Times New Roman', '黑体', 12.5, True)
        return p

    def add_body(text, indent=True):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        if indent:
            p.paragraph_format.first_line_indent = Pt(24)
        run = p.add_run(text)
        set_run_font(run, 'Times New Roman', '宋体', 12, False)
        return p

    def add_equation(omml_content):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.first_line_indent = Pt(0)
        xml = f'''<m:oMathPara xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">{omml_content}</m:oMathPara>'''
        p._p.append(parse_xml(xml))
        return p

    def add_img(img_path, caption):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.first_line_indent = Pt(0)
        run = p.add_run()
        run.add_picture(img_path, width=Inches(5.8))
        
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(2)
        p_cap.paragraph_format.space_after = Pt(8)
        p_cap.paragraph_format.first_line_indent = Pt(0)
        r_cap = p_cap.add_run(caption)
        set_run_font(r_cap, 'Times New Roman', '黑体', 10.5, True)

    # --- TITLE ---
    add_h1("第3章  障碍物与螺栓位姿双视觉识别方法")

    # --- INTRO ---
    add_body("输电铁塔螺栓自主作业的前提是具备精准、可靠的环境与目标空间感知能力。铁塔作业环境具有角钢桁架交错纵横、节点结构异构非凸以及表面光照动态反光剧烈等复杂物理特性。传统的单相机视觉系统受限于安装视角与有效分辨率，极难兼顾大范围作业空间下的防碰撞环境感知与狭小节点区域内毫米级高精度螺栓位姿解算。为此，本章提出了一种基于“全局宏观避障—局部微观精测”的双视觉协同感知方法。首先深入剖析单相机在铁塔复杂工况下的场景瓶颈与物理机理；进而构建由高位外伸全局深度相机（Eye-to-Hand）与机械臂末端局部手眼相机（Eye-in-Hand）组成的双目异构协同架构；详细研究基于全局点云的三维环境滤波与八叉树障碍物体素地图映射算法，以及基于局部点云的螺栓二维检测、三维基面拟合与六自由度空间位姿解算模型；最后通过搭建的模拟实验台进行系统识别精度与建图性能的综合实验验证。")

    # --- 3.1 ---
    add_h2("3.1  单视觉的场景瓶颈分析")
    
    add_h3("3.1.1  桁架遮挡导致的目标漏检问题")
    add_body("输电铁塔下段由四根倾斜的角钢主材、交错布置的横材与斜材，以及加固用的水平与斜拉辅材组紧密围合构成。各构件在三维空间中形成错综复杂的网格空腔。若在系统中仅采用单一相机，无论采用固定的全局外置安装方式还是末端手眼随动安装方式，均会面临严重的视线几何遮挡与目标漏检难题：")
    add_body("1. 全局单视角下的死角遮挡：当全局单相机架设于铁塔一侧外部时，前排交错的角钢主材与斜材不可避免地对后排结构形成大面积投影阴影。特别是作业目标螺栓通常深嵌于内层节点板或外包角钢交汇处，前排构件的几何包络会将作业目标完全遮蔽，形成如图 3-1(a) 所示的“几何盲区”，导致视觉算法在宏观引导阶段直接发生目标漏检；此外，机械臂本体自身在运动过程中也会在相机视线前形成动态自遮挡，进一步恶化了感知环境。")
    add_body("2. 局部单视角下的“盲人摸象”缺陷：若仅在机械臂腕部安装局部手眼相机，虽然能够动态贴近深层目标消除部分死角，但由于近距离观测视场极度狭窄（通常覆盖范围不足 30 cm × 20 cm），机械臂在移动过程中对其大臂、小臂肘部后方的大型角钢桁架与外凸脚钉完全处于感知盲态，极易在机械臂进行大范围姿态调整时发生肘部或连杆与背景横梁的刚性碰撞，根本无法支撑后续的安全避障路径规划。")

    add_h3("3.1.2  全局视野与局部精度的矛盾")
    add_body("除遮挡问题外，工业视觉中“视场范围（Field of View, FOV）”与“空间测量分辨率”之间的天然物理制约，构成了单相机的另一个核心瓶颈，如图 3-1(b) 所示。")
    add_body("根据针孔相机成像投影模型，设相机的水平与垂直等效焦距为 fx, fy，当被测目标距离相机的垂直工作距离为 Z 时，单个图像像素所对应的实际空间物理尺寸（空间分辨率）ΔX 可表示为：")

    # Eq 3-1
    eq1 = """
    <m:oMath>
      <m:r><m:t>Δ</m:t></m:r>
      <m:r><m:t>X</m:t></m:r>
      <m:r><m:t> = </m:t></m:r>
      <m:f>
        <m:num><m:r><m:t>Z</m:t></m:r></m:num>
        <m:den><m:sSub><m:e><m:r><m:t>f</m:t></m:r></m:e><m:sub><m:r><m:t>x</m:t></m:r></m:sub></m:sSub></m:den>
      </m:f>
      <m:r><m:t>,                </m:t></m:r>
      <m:r><m:t>Δ</m:t></m:r>
      <m:r><m:t>Y</m:t></m:r>
      <m:r><m:t> = </m:t></m:r>
      <m:f>
        <m:num><m:r><m:t>Z</m:t></m:r></m:num>
        <m:den><m:sSub><m:e><m:r><m:t>f</m:t></m:r></m:e><m:sub><m:r><m:t>y</m:t></m:r></m:sub></m:sSub></m:den>
      </m:f>
      <m:r><m:t>                        (3-1)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq1)

    add_body("在全景全局感知模式下，为了将整座铁塔下段工作包络（跨度约 1.5 m ~ 2.5 m）纳入视场，全局相机的安装视距必须达到 Z ≥ 1.8 m。在常用的 1280×720 分辨率下，单个像素代表的物理尺寸约为 2.0 ~ 3.0 mm。而铁塔标准紧固螺栓（如 M16 ~ M24）的公称直径仅为 16 ~ 24 mm，在全局图像中其成像仅占 6 ~ 10 个像素，边缘模糊与量化噪声极大，导致空间圆心提取与法向量解算误差高达 3 ~ 5 mm 和 2° ~ 4°，根本无法满足螺栓轴孔装配所要求的亚毫米级对心装配容差（通常需小于 0.5 mm）。相反，若将相机拉近至 0.2 m 处，空间分辨力虽可提升至 0.15 mm/pixel，但视场仅能看到数个螺栓局部，完全丧失了全域障碍物监测能力。因此，单一视角在物理上不可能同时兼顾“全局宏观大视野”与“局部微观高精度”，必须采用双视觉分工协同架构。")

    add_img("/home/liu/projects/git-demo-admittance/fig3_1_bottlenecks.png", "图 3-1 铁塔复杂场景下单视觉感知瓶颈机理分析")

    # --- 3.2 ---
    add_h2("3.2  双视觉协同感知架构设计")
    add_body("针对上述单一视角的物理局限，本文提出了“全局宏观环境感知 + 局部微观位姿精测”的双视觉协同感知架构，如图 3-2 所示。整个感知系统由全局障碍感知模块、局部螺栓精定位模块以及 ROS 2 分布式协同调度中枢三部分组成。")

    add_img("/home/liu/projects/git-demo-admittance/fig3_2_architecture.png", "图 3-2 双视觉协同感知系统总体架构与数据流向图")

    add_h3("3.2.1  全局障碍感知模块")
    add_body("全局障碍感知模块采用一台高位外附布置的 Intel RealSense D455 深度相机（Eye-to-Hand 构型），安装于铁塔立柱侧边外伸的高刚度三角悬臂支架端部，保持大倾角俯视姿态。该模块的核心功能是输出机器人作业空间的宏观几何环境信息：")
    add_body("（1）广域点云流获取：实时采集铁塔外部桁架、角钢立柱、外凸脚钉及机械臂本体的稠密三维点云流；", indent=True)
    add_body("（2）三维环境滤波预处理：设计空间直通滤波与体素下采样算法，剔除非作业区域的地面与远景噪点，压缩数据吞吐量；", indent=True)
    add_body("（3）八叉树体素建图（OctoMap）：利用外参矩阵将点云转换至机械臂基座标系下，增量式构建三维概率占据栅格地图，为第 4 章的机械臂碰撞检测与改进 APF-Informed-RRT* 避障路径规划提供全局环境底图。", indent=True)

    add_h3("3.2.2  局部螺栓精定位模块")
    add_body("局部螺栓精定位模块采用另一台紧凑集成于 JAKA Zu 7 机械臂末端腕部法兰侧的 Intel RealSense D455 深度相机（Eye-in-Hand 构型）。该模块随机械臂连杆动态逼近待作业节点板，其核心功能是实现装配目标的微观高精度定位：")
    add_body("（1）自适应近距对准：在机械臂沿全局避障路径到达预定观测位后，局部相机以 0.2 ~ 0.3 m 的极近距离正对节点板表面成像，彻底规避远距离大气扰动与微小振动误差；", indent=True)
    add_body("（2）目标精准识别与 ROI 裁剪：结合二维轻量级目标检测算法快速识别螺栓/螺栓孔轮廓，锁定感兴趣区域（ROI）；", indent=True)
    add_body("（3）六自由度空间位姿解算：通过基面点云拟合与空间圆投影算法解算孔心空间三维坐标及其表面法向量，结合手眼标定矩阵转换为机械臂基坐标系下的期望作业目标位姿，无缝输入至第 5 章的力控柔顺装配环节。", indent=True)

    # --- 3.3 ---
    add_h2("3.3  障碍物检测与空间映射方法")
    add_body("全局相机采集到的原始 RGB-D 点云数据量巨大（单帧通常包含逾 90 万个三维点），且包含离群噪点与远景无关背景。为了满足避障规划毫秒级碰撞检测的高实时性要求，本文构建了高效的点云预处理与空间坐标映射管线：")
    add_body("1. 工作空间直通滤波（PassThrough Filter）：根据输电铁塔作业平台的几何边界，在相机坐标系 {C_global} 下设定长方体包络截断阈值，滤除 X ∈ [-1.5, 1.5] m，Y ∈ [-1.0, 1.8] m，Z ∈ [0.4, 2.5] m 以外的无关背景点云与地面反光点。")
    add_body("2. 体素网格下采样（VoxelGrid Filter）：构建尺寸为 Δv = 10 mm 的三维微小体素立方体，计算落入每个体素内的所有点云重心，以单个重心点代替体素内的所有原始点。该方法在完整保留角钢构件几何轮廓与边界边缘特征的前提下，将点云数据量压缩 85% 以上。")
    add_body("3. 统计离群点去除（Statistical Outlier Removal, SOR）：针对铁塔镀锌钢反光产生的悬空孤立噪点，计算每个点到其临近 k（k=30）个邻域点的平均距离分布，剔除距离大于均值加上 1.5 倍标准差的飞点。")
    add_body("4. 全局相机空间外参坐标转换：设滤波后的点云在相机坐标系下的齐次坐标为 P_cam = [X_c, Y_c, Z_c, 1]ᵀ。基于高精度标靶预先完成全局相机与机械臂基座标系 {B} 之间的手眼外参标定，得到刚体位姿变换矩阵 T_B^{C_global}，将点云统一投影至机器人作业基坐标系：")

    # Eq 3-2
    eq2 = """
    <m:oMath>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:t>B</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> = </m:t></m:r>
      <m:sSubSup><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>T</m:t></m:r></m:e><m:sub><m:r><m:t>B</m:t></m:r></m:sub><m:sup><m:sSub><m:e><m:r><m:t>C</m:t></m:r></m:e><m:sub><m:r><m:t>global</m:t></m:r></m:sub></m:sSub></m:sup></m:sSubSup>
      <m:r><m:t> · </m:t></m:r>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:t>cam</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> = </m:t></m:r>
      <m:d>
        <m:dPr><m:begChr m:val="["/><m:endChr m:val="]"/></m:dPr>
        <m:e>
          <m:m>
            <m:mr><m:e><m:sSubSup><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>R</m:t></m:r></m:e><m:sub><m:r><m:t>B</m:t></m:r></m:sub><m:sup><m:sSub><m:e><m:r><m:t>C</m:t></m:r></m:e><m:sub><m:r><m:t>global</m:t></m:r></m:sub></m:sSub></m:sup></m:sSubSup></m:e><m:e><m:sSubSup><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>t</m:t></m:r></m:e><m:sub><m:r><m:t>B</m:t></m:r></m:sub><m:sup><m:sSub><m:e><m:r><m:t>C</m:t></m:r></m:e><m:sub><m:r><m:t>global</m:t></m:r></m:sub></m:sSub></m:sup></m:sSubSup></m:e></m:mr>
            <m:mr><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>0</m:t></m:r></m:e><m:e><m:r><m:t>1</m:t></m:r></m:e></m:mr>
          </m:m>
        </m:e>
      </m:d>
      <m:d>
        <m:dPr><m:begChr m:val="["/><m:endChr m:val="]"/></m:dPr>
        <m:e>
          <m:m>
            <m:mr><m:e><m:sSub><m:e><m:r><m:t>X</m:t></m:r></m:e><m:sub><m:r><m:t>c</m:t></m:r></m:sub></m:sSub></m:e></m:mr>
            <m:mr><m:e><m:sSub><m:e><m:r><m:t>Y</m:t></m:r></m:e><m:sub><m:r><m:t>c</m:t></m:r></m:sub></m:sSub></m:e></m:mr>
            <m:mr><m:e><m:sSub><m:e><m:r><m:t>Z</m:t></m:r></m:e><m:sub><m:r><m:t>c</m:t></m:r></m:sub></m:sSub></m:e></m:mr>
            <m:mr><m:e><m:r><m:t>1</m:t></m:r></m:e></m:mr>
          </m:m>
        </m:e>
      </m:d>
      <m:r><m:t>                        (3-2)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq2)

    add_body("5. 基于八叉树（OctoMap）的概率占据体素建图：为了便于机械臂进行连续碰撞干涉检测，采用八叉树概率栅格结构对转换后的三维空间进行离散体素建模。每个体素节点存储其被障碍物占据的对数概率对数值 L(n|z_{1:t})，其增量递归更新方程为：")

    # Eq 3-3
    eq3 = """
    <m:oMath>
      <m:r><m:t>L</m:t></m:r>
      <m:d>
        <m:e><m:r><m:t>n</m:t></m:r><m:r><m:t> | </m:t></m:r><m:sSub><m:e><m:r><m:t>z</m:t></m:r></m:e><m:sub><m:r><m:t>1:t</m:t></m:r></m:sub></m:sSub></m:e>
      </m:d>
      <m:r><m:t> = </m:t></m:r>
      <m:r><m:t>L</m:t></m:r>
      <m:d>
        <m:e><m:r><m:t>n</m:t></m:r><m:r><m:t> | </m:t></m:r><m:sSub><m:e><m:r><m:t>z</m:t></m:r></m:e><m:sub><m:r><m:t>1:t-1</m:t></m:r></m:sub></m:sSub></m:e>
      </m:d>
      <m:r><m:t> + </m:t></m:r>
      <m:r><m:t>L</m:t></m:r>
      <m:d>
        <m:e><m:r><m:t>n</m:t></m:r><m:r><m:t> | </m:t></m:r><m:sSub><m:e><m:r><m:t>z</m:t></m:r></m:e><m:sub><m:r><m:t>t</m:t></m:r></m:sub></m:sSub></m:e>
      </m:d>
      <m:r><m:t>                        (3-3)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq3)

    add_body("式中，zt 为当前帧观测测量值。设定占据概率阈值（如 P_occ > 0.7 判定为障碍物体素），生成具有清晰几何边界的三维非凸障碍物网络，支持毫秒级的空间碰撞距离查询。")

    # --- 3.4 ---
    add_h2("3.4  螺栓位姿识别与坐标解算")
    add_body("当机械臂末端到达预装配观测视场后，局部手眼相机采集高分辨率 RGB-D 图像，执行螺栓/孔的六自由度位姿解算，处理流程如图 3-3 所示。")

    add_img("/home/liu/projects/git-demo-admittance/fig3_3_pose_pipeline.png", "图 3-3 局部视觉螺栓孔位姿解算与几何拟合原理流程图")

    add_body("1. 二维目标检测与局部 ROI 提取：采用轻量级 YOLOv8 目标检测算法对局部相机采集的彩色图像进行前向推理，输出螺栓/孔的边界框 Bounding Box 及粗质心像素坐标 (u₀, v₀)。以边界框为掩膜构建感兴趣区域（ROI），将计算开销严格限制在局部特征区域。")
    add_body("2. 深度点云二维反投影：基于相机内参矩阵 K，将 ROI 内对应的深度像素图反投影为局部相机坐标系 {C_local} 下的三维局部空间点集 P_roi：")

    # Eq 3-4
    eq4 = """
    <m:oMath>
      <m:sSub><m:e><m:r><m:t>X</m:t></m:r></m:e><m:sub><m:r><m:t>i</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> = </m:t></m:r>
      <m:f>
        <m:num><m:d><m:e><m:sSub><m:e><m:r><m:t>u</m:t></m:r></m:e><m:sub><m:r><m:t>i</m:t></m:r></m:sub></m:sSub><m:r><m:t> - </m:t></m:r><m:sSub><m:e><m:r><m:t>c</m:t></m:r></m:e><m:sub><m:r><m:t>x</m:t></m:r></m:sub></m:sSub></m:e></m:d><m:r><m:t> · </m:t></m:r><m:sSub><m:e><m:r><m:t>Z</m:t></m:r></m:e><m:sub><m:r><m:t>i</m:t></m:r></m:sub></m:sSub></m:num>
        <m:den><m:sSub><m:e><m:r><m:t>f</m:t></m:r></m:e><m:sub><m:r><m:t>x</m:t></m:r></m:sub></m:sSub></m:den>
      </m:f>
      <m:r><m:t>,        </m:t></m:r>
      <m:sSub><m:e><m:r><m:t>Y</m:t></m:r></m:e><m:sub><m:r><m:t>i</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> = </m:t></m:r>
      <m:f>
        <m:num><m:d><m:e><m:sSub><m:e><m:r><m:t>v</m:t></m:r></m:e><m:sub><m:r><m:t>i</m:t></m:r></m:sub></m:sSub><m:r><m:t> - </m:t></m:r><m:sSub><m:e><m:r><m:t>c</m:t></m:r></m:e><m:sub><m:r><m:t>y</m:t></m:r></m:sub></m:sSub></m:e></m:d><m:r><m:t> · </m:t></m:r><m:sSub><m:e><m:r><m:t>Z</m:t></m:r></m:e><m:sub><m:r><m:t>i</m:t></m:r></m:sub></m:sSub></m:num>
        <m:den><m:sSub><m:e><m:r><m:t>f</m:t></m:r></m:e><m:sub><m:r><m:t>y</m:t></m:r></m:sub></m:sSub></m:den>
      </m:f>
      <m:r><m:t>                        (3-4)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq4)

    add_body("3. 基于 RANSAC 的节点板基面拟合与法向量提取：由于螺栓必须垂直旋入节点板，节点板的法线方向直接决定了装配接近矢量。采用随机抽样一致算法（RANSAC）拟合 ROI 周围板面点云的空间平面方程：")

    # Eq 3-5
    eq5 = """
    <m:oMath>
      <m:r><m:t>A</m:t></m:r><m:r><m:t>x</m:t></m:r>
      <m:r><m:t> + </m:t></m:r>
      <m:r><m:t>B</m:t></m:r><m:r><m:t>y</m:t></m:r>
      <m:r><m:t> + </m:t></m:r>
      <m:r><m:t>C</m:t></m:r><m:r><m:t>z</m:t></m:r>
      <m:r><m:t> + </m:t></m:r>
      <m:r><m:t>D</m:t></m:r>
      <m:r><m:t> = </m:t></m:r>
      <m:r><m:t>0,        </m:t></m:r>
      <m:sSup><m:e><m:r><m:t>A</m:t></m:r></m:e><m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup>
      <m:r><m:t> + </m:t></m:r>
      <m:sSup><m:e><m:r><m:t>B</m:t></m:r></m:e><m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup>
      <m:r><m:t> + </m:t></m:r>
      <m:sSup><m:e><m:r><m:t>C</m:t></m:r></m:e><m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup>
      <m:r><m:t> = </m:t></m:r>
      <m:r><m:t>1</m:t></m:r>
      <m:r><m:t>                        (3-5)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq5)

    add_body("由此解得基准平面的单位外法向量 n = [A, B, C]ᵀ，并剔除离面距离 di = |Ax_i + By_i + Cz_i + D| > 1.5 mm 的边缘毛刺点。")
    add_body("4. 空间圆投影与三维孔心提取：将螺栓孔边缘轮廓点投影至拟合平面 Π 上，在二维正交平面基底上采用最小二乘法进行圆拟合，求得孔圆心在相机坐标系下的三维物理坐标 P_h = [x_h, y_h, z_h]ᵀ 及半径 r。以法向量 n 为 Z 轴，结合平面切向矢量构建局部目标齐次变换矩阵 T_{C_local}^{bolt}。")
    add_body("5. 手眼标定与基座标系位姿统一：通过预先标定的手眼变换矩阵 T_flange^{C_local} 以及 JAKA Zu 7 机械臂正运动学实时解算的末端法兰位姿 T_B^flange(q)，计算得到目标螺栓在机械臂绝对基座标系下的六自由度作业位姿 T_B^{bolt}：")

    # Eq 3-6
    eq6 = """
    <m:oMath>
      <m:sSubSup><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>T</m:t></m:r></m:e><m:sub><m:r><m:t>B</m:t></m:r></m:sub><m:sup><m:r><m:rPr><m:nor/></m:rPr><m:t>bolt</m:t></m:r></m:sup></m:sSubSup>
      <m:r><m:t> = </m:t></m:r>
      <m:sSubSup><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>T</m:t></m:r></m:e><m:sub><m:r><m:t>B</m:t></m:r></m:sub><m:sup><m:r><m:rPr><m:nor/></m:rPr><m:t>flange</m:t></m:r></m:sup></m:sSubSup>
      <m:d><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>q</m:t></m:r></m:e></m:d>
      <m:r><m:t> · </m:t></m:r>
      <m:sSubSup><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>T</m:t></m:r></m:e><m:sub><m:r><m:t>flange</m:t></m:r></m:sub><m:sup><m:sSub><m:e><m:r><m:t>C</m:t></m:r></m:e><m:sub><m:r><m:t>local</m:t></m:r></m:sub></m:sSub></m:sup></m:sSubSup>
      <m:r><m:t> · </m:t></m:r>
      <m:sSubSup><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>T</m:t></m:r></m:e><m:sub><m:sSub><m:e><m:r><m:t>C</m:t></m:r></m:e><m:sub><m:r><m:t>local</m:t></m:r></m:sub></m:sSub></m:sub><m:sup><m:r><m:rPr><m:nor/></m:rPr><m:t>bolt</m:t></m:r></m:sup></m:sSubSup>
      <m:r><m:t>                        (3-6)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq6)

    # --- 3.5 ---
    add_h2("3.5  识别定位实验与分析")
    add_body("为了定量评估本文提出的双视觉协同感知系统在复杂铁塔场景下的有效性与精度，在搭建的 1:1 等比例输电铁塔模拟模型平台上开展了障碍物检测与螺栓位姿解算实验。")

    add_h3("3.5.1  障碍物检测准确率")
    add_body("选取铁塔下段的 10 类典型构件（主材、横材、斜材、节点板、外包角钢、辅材组、脚钉及防坠落导轨等）作为测试目标。在正常光照、强光直射反光（高亮区）以及阴影遮挡三种工况下，分别测试体素分辨率为 10 mm 时的障碍物占据建图准确率（Precision）、召回率（Recall）及平均建图延迟。统计 200 帧连续点云的建图指标如表 3-1 所示。")

    # Table 3-1
    table1 = doc.add_table(rows=4, cols=5)
    table1.alignment = WD_TABLE_ALIGNMENT.CENTER
    table1.style = 'Table Grid'
    
    headers1 = ['实验工况', '构件总数 (处)', '召回率 Recall (%)', '准确率 Precision (%)', '建图延迟 (ms)']
    row0 = table1.rows[0]
    for i, h in enumerate(headers1):
        cell = row0.cells[i]
        cell.text = h
        p_c = cell.paragraphs[0]
        p_c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if p_c.runs:
            set_run_font(p_c.runs[0], 'Times New Roman', '黑体', 10.5, True)

    data1 = [
        ['标准室内光照', '10', '98.5', '97.8', '42.6'],
        ['强光表面反光', '10', '95.2', '94.6', '46.1'],
        ['局部桁架阴影', '10', '96.8', '96.2', '44.8']
    ]
    for r_idx, row_data in enumerate(data1):
        row = table1.rows[r_idx + 1]
        for c_idx, val in enumerate(row_data):
            cell = row.cells[c_idx]
            cell.text = val
            p_c = cell.paragraphs[0]
            p_c.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if p_c.runs:
                set_run_font(p_c.runs[0], 'Times New Roman', '宋体', 10.5, False)

    p_t1 = doc.add_paragraph()
    p_t1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_t1.paragraph_format.space_before = Pt(2)
    p_t1.paragraph_format.space_after = Pt(8)
    r_t1 = p_t1.add_run("表 3-1 全局障碍物检测与八叉树建图性能测试结果")
    set_run_font(r_t1, 'Times New Roman', '黑体', 10.5, True)

    add_body("实验结果表明，在体素下采样与直通滤波联合作用下，系统对典型桁架障碍物的平均识别召回率达到 96.8% 以上，建图时间稳定在 45 ms 左右（刷新帧率 > 20 Hz），不仅能准确包络粗大角钢构件，也能可靠捕捉悬挑脚钉与细长防坠导轨，完全满足后续第 4 章路径规划实时防碰撞安全需求。")

    add_h3("3.5.2  螺栓位姿识别精度")
    add_body("在输电铁塔不同高度的节点板与外包角钢上选取 20 组标准 M20 螺栓预制孔作为测试基准，使用经计量认证的高精度激光跟踪仪测量各孔心的真实三维物理坐标与法线姿态作为基准真值（Ground Truth）。分别对比以下两种方案的位姿识别误差：")
    add_body("方案 A（单全局相机）：仅使用高位全局相机（视距 Z ≈ 2.0 m）解算螺栓位姿；")
    add_body("方案 B（本文双视觉协同）：先由全局相机粗定位，再由机械臂将局部手眼相机送达近距观测位（视距 Z ≈ 0.25 m）执行精细位姿解算。")
    add_body("统计两类方案在位置误差（ex, ey, ez 及欧氏空间误差 e_pos）和角度偏差（roll, pitch 角度误差 e_ang）的均值与最大值，结果如表 3-2 所示。")

    # Table 3-2
    table2 = doc.add_table(rows=3, cols=6)
    table2.alignment = WD_TABLE_ALIGNMENT.CENTER
    table2.style = 'Table Grid'
    
    headers2 = ['感知方案', '平均位置误差 (mm)', '最大位置误差 (mm)', '平均角度误差 (°)', '最大角度误差 (°)', '能否满足装配']
    row0 = table2.rows[0]
    for i, h in enumerate(headers2):
        cell = row0.cells[i]
        cell.text = h
        p_c = cell.paragraphs[0]
        p_c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if p_c.runs:
            set_run_font(p_c.runs[0], 'Times New Roman', '黑体', 10.5, True)

    data2 = [
        ['方案A: 单全局相机 (Z≈2.0m)', '2.84', '4.15', '2.35', '3.82', '否 (超出容差)'],
        ['方案B: 本文双视觉协同 (Z≈0.25m)', '0.38', '0.62', '0.31', '0.58', '是 (满足力控条件)']
    ]
    for r_idx, row_data in enumerate(data2):
        row = table2.rows[r_idx + 1]
        for c_idx, val in enumerate(row_data):
            cell = row.cells[c_idx]
            cell.text = val
            p_c = cell.paragraphs[0]
            p_c.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if p_c.runs:
                set_run_font(p_c.runs[0], 'Times New Roman', '宋体', 10.5, False)

    p_t2 = doc.add_paragraph()
    p_t2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_t2.paragraph_format.space_before = Pt(2)
    p_t2.paragraph_format.space_after = Pt(8)
    r_t2 = p_t2.add_run("表 3-2 螺栓位姿解算精度对比实验结果")
    set_run_font(r_t2, 'Times New Roman', '黑体', 10.5, True)

    add_body("由表 3-2 可知，单全局相机的平均位置解算误差高达 2.84 mm，最大偏差超过 4 mm，角度偏差达到 2.35°，严重超出轴孔装配入孔倒角的引导范围；而本文提出的双视觉协同方案通过局部相机近距离二次观测与 RANSAC 几何拟合，将平均位置解算误差大幅降低至 0.38 mm（降低了 86.6%），平均姿态角度误差控制在 0.31° 以内，充分验证了双视觉协同架构在克服大范围遮挡与保证亚毫米级微观定位精度上的优越性。")

    # --- 3.6 ---
    add_h2("3.6  本章小结")
    add_body("本章紧密围绕输电铁塔复杂环境下作业目标严重遮挡与全局/局部精度矛盾的行业难题，研究并实现了一套完整的双视觉协同感知与位姿解算方法：")
    add_body("（1）剖析了传统单视角感知的内在机理瓶颈：论证了前排角钢对深层节点板的视线几何遮挡与机械臂自遮挡机理，建立了视距与空间分辨率量化关系模型，证明了单一相机在物理上无法同时满足全域避障与局部高精度的矛盾事实；")
    add_body("（2）构建了“全局宏观避障+局部微观精测”的双视觉协同架构：设计了高位三角支架外附全局深度相机与机械臂末端手眼相机的空间分工体系，并通过 ROS 2 分布式通信机制实现了多相机异构数据流的高效协同分发；")
    add_body("（3）提出了高效的全局障碍物点云处理与八叉树映射方法：通过直通滤波、体素下采样与外参变换构建了高精度的 OctoMap 概率占据栅格地图，实现了对铁塔角钢及外凸脚钉的高效几何包络建模；")
    add_body("（4）实现了亚毫米级精度的螺栓六自由度位姿解算算法：结合 2D 目标检测 ROI、反投影点云聚类、RANSAC 平面拟合与手眼标定链，解算出高精度的目标空间位姿；")
    add_body("（5）完成了系统的多工况实验验证：在 1:1 模拟铁塔平台上的实测表明，全局障碍物检测召回率达到 96.8% 以上，螺栓空间定位平均误差缩小至 0.38 mm，平均角度误差仅 0.31°，为第 4 章的无碰撞路径规划提供了环境地图，为第 5 章的力控柔顺装配提供了高精度的初始位姿引导。")

    # Save
    out1 = '/home/liu/projects/git-demo-admittance/第3章_障碍物与螺栓位姿双视觉识别方法.docx'
    out2 = '/home/liu/下载/第3章_障碍物与螺栓位姿双视觉识别方法.docx'
    doc.save(out1)
    doc.save(out2)
    print('Generated Word document at:', out1)
    print('Copied to:', out2)

if __name__ == '__main__':
    create_chapter3_docx()
