import docx
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import qn

def set_run_font(run, ascii_font='Times New Roman', eastasia_font='宋体', size_pt=12, bold=False, italic=False):
    run.font.name = ascii_font
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    rPr = run.element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), eastasia_font)

def add_mixed_paragraph(doc, segments, indent=True, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=0, space_after=0):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    if indent:
        p.paragraph_format.first_line_indent = Pt(24)
    else:
        p.paragraph_format.first_line_indent = Pt(0)
        
    for seg in segments:
        seg_type = seg[0]
        if seg_type == 'text':
            text = seg[1]
            bold = seg[2] if len(seg) > 2 else False
            italic = seg[3] if len(seg) > 3 else False
            eastasia = seg[4] if len(seg) > 4 else '宋体'
            size = seg[5] if len(seg) > 5 else 12
            run = p.add_run(text)
            set_run_font(run, 'Times New Roman', eastasia, size, bold, italic)
        elif seg_type == 'math':
            math_xml = f'<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">{seg[1]}</m:oMath>'
            p._p.append(parse_xml(math_xml))
    return p

def update_chapter5():
    doc = Document()
    for s in doc.sections:
        s.top_margin = Inches(1.0)
        s.bottom_margin = Inches(1.0)
        s.left_margin = Inches(1.18)
        s.right_margin = Inches(1.18)

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

    # --- CHAPTER 5 CONTENT ---
    add_h1("第5章  螺栓柔顺装配力控策略")
    
    add_body("在输电铁塔高空与狭窄桁架环境下，机械臂执行螺栓装配任务面临着构件制造公差、视觉测量残差以及结构弹性形变等多重不确定性扰动。若仅依赖传统的刚性位置控制，极易导致螺栓与螺孔在接触瞬间产生极大的破坏性接触力，诱发卡滞、咬死甚至损坏机械臂。为此，本章在上游视觉粗定位与无碰撞路径规划的基础上，重点研究螺栓与安装孔接触交互阶段的力控装配策略。首先深入分析铁塔螺栓装配过程中的接触力学约束与传统位置控制的本质瓶颈；进而建立机械臂末端六维力传感器的数据处理与重力/零偏在线补偿模型，设计基于导纳原理的位置-力混合控制律；最后，构建“视觉引导预定位—力觉引导柔顺插入”的分阶段自主装配闭环流程，确保在存在位姿偏差工况下螺栓的高可靠、低冲击顺畅装配。")

    add_h2("5.1  铁塔螺栓装配的力控需求分析")
    
    add_h3("5.1.1  螺栓装配的接触力约束")
    add_body("输电铁塔节点板与角钢主材之间的螺栓紧固作业在力学机理上属于典型的空间三维刚性轴孔装配（Peg-in-Hole）问题。如图 5-1 所示，在机械臂末端执行器的驱动下，装配件（螺栓）从初始接触到完全装配到位，需经历端面点接触寻孔（a）、平面滑移对心（b）、孔口倾斜两点接触（c）、深入孔内两点卡滞危险期（d）、同轴垂直平稳插入（e）以及完全贴合到位（f）六个典型的力学演化阶段：")

    # Image insertion
    img_path = '/home/liu/.gemini/antigravity/brain/459352ac-3327-40c2-bb29-4319774ed722/.user_uploaded/media_1790058152907.png'
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(6)
    p_img.paragraph_format.space_after = Pt(2)
    p_img.paragraph_format.first_line_indent = Pt(0)
    p_img.add_run().add_picture(img_path, width=Inches(5.6))

    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_before = Pt(2)
    p_cap.paragraph_format.space_after = Pt(8)
    p_cap.paragraph_format.first_line_indent = Pt(0)
    r_cap = p_cap.add_run("图 5-1 螺栓装配各阶段接触状态演变与受力模型")
    set_run_font(r_cap, 'Times New Roman', '黑体', 10.5, True)

    # Detailed stage descriptions with inline math
    add_mixed_paragraph(doc, [
        ('text', '（a）初始表面点接触阶段（状态 '),
        ('math', '<m:sSub><m:e><m:r><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:t>1</m:t></m:r></m:sub></m:sSub>'),
        ('text', '）：在全局与局部视觉粗定位引导下，机械臂将螺栓运送至基体件（铁塔节点板或角钢）表面。由于视觉标定与测量残差的存在，螺栓端部并未直接对准孔心，而是以微小的倾斜姿态与基体上表面发生单点接触。此时螺栓受到重力 '),
        ('math', '<m:r><m:t>G</m:t></m:r>'),
        ('text', '、基体表面法向支撑力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>N</m:t></m:r></m:e><m:sub><m:r><m:t>1</m:t></m:r></m:sub></m:sSub>'),
        ('text', '、表面摩擦力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>f</m:t></m:r></m:e><m:sub><m:r><m:t>1</m:t></m:r></m:sub></m:sSub>'),
        ('text', ' 以及机械臂末端的主动驱动力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>F</m:t></m:r></m:e><m:sub><m:sSub><m:e><m:r><m:t>A</m:t></m:r></m:e><m:sub><m:r><m:t>1</m:t></m:r></m:sub></m:sSub></m:sub></m:sSub>'),
        ('text', ' 的共同作用；机械臂需根据接触产生的偏心反力矩施加自适应顺应力矩 '),
        ('math', '<m:sSub><m:e><m:r><m:t>Q</m:t></m:r></m:e><m:sub><m:r><m:t>1</m:t></m:r></m:sub></m:sSub>'),
        ('text', '，使螺栓向孔口方向微调并滑动。')
    ], indent=True, space_before=4)

    add_mixed_paragraph(doc, [
        ('text', '（b）平面滑移对心阶段（状态 '),
        ('math', '<m:sSub><m:e><m:r><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:t>j</m:t></m:r></m:sub></m:sSub>'),
        ('text', '）：螺栓在机械臂末端下压与横向驱动力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>F</m:t></m:r></m:e><m:sub><m:sSub><m:e><m:r><m:t>A</m:t></m:r></m:e><m:sub><m:r><m:t>j</m:t></m:r></m:sub></m:sSub></m:sub></m:sSub>'),
        ('text', ' 作用下，克服滑动摩擦阻力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>f</m:t></m:r></m:e><m:sub><m:r><m:t>j</m:t></m:r></m:sub></m:sSub>'),
        ('text', ' 沿基体表面向预制孔中心匀速滑动。该阶段垂直支撑力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>N</m:t></m:r></m:e><m:sub><m:r><m:t>j</m:t></m:r></m:sub></m:sSub>'),
        ('text', ' 与轴向下压力维持动态平衡，力控系统需严格抑制轴向力在安全接触阈值内（10 ~ 20 N），既保证螺栓不脱离基体表面，又避免压力过大刮伤工件表面涂层。')
    ], indent=True, space_before=4)

    add_mixed_paragraph(doc, [
        ('text', '（c）孔口落入与倒角两点接触阶段（状态 '),
        ('math', '<m:sSub><m:e><m:r><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:t>k</m:t></m:r></m:sub></m:sSub>'),
        ('text', '）：螺栓下端滑至孔口倒角边缘处受阻力突变开始“掉入”孔口。由于轴线尚未与孔轴线重合，螺栓头部与孔壁两侧发生倾斜接触，形成初始的两点接触约束。此时，孔壁两侧对螺栓产生法向反力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>N</m:t></m:r></m:e><m:sub><m:sSub><m:e><m:r><m:t>k</m:t></m:r></m:e><m:sub><m:r><m:t>1</m:t></m:r></m:sub></m:sSub></m:sub></m:sSub>'),
        ('text', '、'),
        ('math', '<m:sSub><m:e><m:r><m:t>N</m:t></m:r></m:e><m:sub><m:sSub><m:e><m:r><m:t>k</m:t></m:r></m:e><m:sub><m:r><m:t>2</m:t></m:r></m:sub></m:sSub></m:sub></m:sSub>'),
        ('text', ' 及切向摩擦阻力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>f</m:t></m:r></m:e><m:sub><m:sSub><m:e><m:r><m:t>k</m:t></m:r></m:e><m:sub><m:r><m:t>1</m:t></m:r></m:sub></m:sSub></m:sub></m:sSub>'),
        ('text', '、'),
        ('math', '<m:sSub><m:e><m:r><m:t>f</m:t></m:r></m:e><m:sub><m:sSub><m:e><m:r><m:t>k</m:t></m:r></m:e><m:sub><m:r><m:t>2</m:t></m:r></m:sub></m:sSub></m:sub></m:sSub>'),
        ('text', '，若下压力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>F</m:t></m:r></m:e><m:sub><m:sSub><m:e><m:r><m:t>A</m:t></m:r></m:e><m:sub><m:r><m:t>k</m:t></m:r></m:sub></m:sSub></m:sub></m:sSub>'),
        ('text', ' 过大将极易在孔口边缘诱发“几何楔紧（Wedging）”。因此，机械臂必须依靠六维力传感器感知到的力矩突变，启动主动自适应调姿力矩 '),
        ('math', '<m:sSub><m:e><m:r><m:t>Q</m:t></m:r></m:e><m:sub><m:r><m:t>k</m:t></m:r></m:sub></m:sSub>'),
        ('text', '，驱动螺栓绕接触点旋转“摆正”，消除轴线夹角。')
    ], indent=True, space_before=4)

    add_mixed_paragraph(doc, [
        ('text', '（d）深孔两点接触与自适应纠偏阶段（状态 '),
        ('math', '<m:sSub><m:e><m:r><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:t>m</m:t></m:r></m:sub></m:sSub>'),
        ('text', '）：螺栓部分杆身深入预制孔内，此时螺栓下端外壁与孔口对侧内壁同时紧贴，处于典型的深孔两点接触状态。该阶段是装配过程中最危险的“卡滞（Jamming）”高发期：孔壁两侧产生的法向力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>N</m:t></m:r></m:e><m:sub><m:r><m:t>m</m:t></m:r></m:sub></m:sSub>'),
        ('text', ' 和纵向摩擦力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>f</m:t></m:r></m:e><m:sub><m:r><m:t>m</m:t></m:r></m:sub></m:sSub>'),
        ('text', ' 构成了强烈的阻力偶矩，阻碍螺栓继续下潜。此时常规位置控制若强行推进必将导致螺栓咬死；系统必须通过导纳控制算法，利用测得的翻转弯矩实时微调机械臂末端横向位置与空间偏角，迫使螺栓与孔壁法线方向严格重合。根据接触几何与摩擦极限条件：')
    ], indent=True, space_before=4)

    # Eq 5-1: lc / (2r)
    eq1 = """
    <m:oMath>
      <m:r><m:t>μ</m:t></m:r>
      <m:r><m:t> ≥ </m:t></m:r>
      <m:f>
        <m:num>
          <m:sSub>
            <m:e><m:r><m:t>l</m:t></m:r></m:e>
            <m:sub><m:r><m:t>c</m:t></m:r></m:sub>
          </m:sSub>
        </m:num>
        <m:den>
          <m:r><m:t>2</m:t></m:r>
          <m:r><m:t>r</m:t></m:r>
        </m:den>
      </m:f>
      <m:r><m:t>                        (5-1)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq1)

    add_body("式中，μ 为材料静摩擦系数，lc 为接触深度，r 为螺栓公称半径。若满足该自锁条件，纯轴向推力将无法克服接触阻力，反而诱发机械卡死。")

    add_mixed_paragraph(doc, [
        ('text', '（e）同轴垂直平稳插入阶段（状态 '),
        ('math', '<m:sSub><m:e><m:r><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:t>l</m:t></m:r></m:sub></m:sSub>'),
        ('text', '）：随着轴线偏角的彻底消除（'),
        ('math', '<m:r><m:t>Δ</m:t></m:r><m:r><m:t>θ</m:t></m:r><m:r><m:t> ≈ 0</m:t></m:r>'),
        ('text', '），螺栓与预制孔恢复同轴共线状态，原有的两点刚性卡滞退化为均匀的柱面滑动摩擦接触。此时横向干涉力与翻转力矩均衰减至零附近，机械臂只需施加恒定的轴向推进推力 '),
        ('math', '<m:r><m:t>G</m:t></m:r><m:d><m:e><m:sSub><m:e><m:r><m:t>F</m:t></m:r></m:e><m:sub><m:sSub><m:e><m:r><m:t>A</m:t></m:r></m:e><m:sub><m:r><m:t>l</m:t></m:r></m:sub></m:sSub></m:sub></m:sSub></m:e></m:d>'),
        ('text', ' 克服平稳滑动阻力，驱动螺栓快速、平稳地向孔底深处匀速滑入。')
    ], indent=True, space_before=4)

    add_mixed_paragraph(doc, [
        ('text', '（f）底部贴合与装配完成阶段（状态 '),
        ('math', '<m:sSub><m:e><m:r><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:t>N</m:t></m:r></m:sub></m:sSub>'),
        ('text', '）：当螺栓头部法兰面与基体件表面完全密合时，由于基体件孔底具有极高的法向刚度，垂直支撑反力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>N</m:t></m:r></m:e><m:sub><m:r><m:t>N</m:t></m:r></m:sub></m:sSub>'),
        ('text', ' 发生阶跃式剧增。控制器实时捕获到该轴向力突变并判断其超过设定的装配终止阈值（如 '),
        ('math', '<m:sSub><m:e><m:r><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>stop</m:t></m:r></m:sub></m:sSub><m:r><m:t> ≥ 45 N</m:t></m:r>'),
        ('text', '），立即切断轴向下压伺服指令并锁定当前位姿，宣告全流程柔顺装配顺利完成。')
    ], indent=True, space_before=4)

    # Rest of Chapter 5
    add_h3("5.1.2  传统位置控制的局限性")
    add_body("工业机器人常规采用高刚度的比例-微分（PD）关节位置伺服控制。尽管 JAKA Zu 7 协作机械臂本体具备 ±0.02 mm 的优异重复定位精度，但在复杂的输电铁塔实际工况下，纯位置控制无法独立完成装配，其核心局限性体现在以下三个方面：")
    add_body("1. 多源感知残差的不可消除性：视觉系统的测量精度受光照波动、桁架表面反光、手眼标定误差等物理因素限制，局部相机位姿解算误差通常在 0.5 ~ 2 mm 与 0.5° ~ 1.5° 范围内；同时，大型铁塔桁架因风载扰动与自重产生的微米/毫米级弹性漂移不可忽略。这种毫米级综合几何误差在间隙配合仅有 0.5 ~ 1.0 mm 的螺栓孔装配中是致命的。")
    add_body("2. 环境接触刚度极高导致的“刚碰刚”力暴溃：螺栓、节点板与角钢主材均为高强度结构钢材，材料接触等效刚度系数通常高达 Ke ≈ 10⁵ ~ 10⁷ N/m。根据胡克定律：")
    
    eq2 = """
    <m:oMath>
      <m:r><m:t>F</m:t></m:r>
      <m:r><m:t> = </m:t></m:r>
      <m:sSub><m:e><m:r><m:t>K</m:t></m:r></m:e><m:sub><m:r><m:t>e</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> · Δ</m:t></m:r>
      <m:r><m:t>x</m:t></m:r>
      <m:r><m:t>                        (5-2)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq2)
    add_body("当机械臂依据存在微小偏差的规划轨迹强制下压时，仅 0.1 mm 的微小干涉位移就会在数毫秒内激发出数百牛顿的巨大冲击反力。")
    add_body("3. 闭环自适应纠偏能力的缺失：纯位置控制对末端受力状态完全“失明”，无法根据外界反作用力的方向去主动“感知并寻找孔心”，不仅极易导致工件表面拉伤、螺纹滑丝变形，甚至会引发机械臂关节过流急停，严重破坏系统连续作业的自主性。因此，必须引入末端主动柔顺力控制算法。")

    add_h2("5.2  基于导纳控制的柔顺装配策略")
    add_h3("5.2.1  末端力信息处理与重力补偿")
    add_body("安装于机械臂第 6 关节法兰处的 JK-SE-VI-200 六维力传感器采集到的原始力/力矩信号 Fraw ∈ ℝ⁶ 并非纯粹的外界接触力，而是由真实接触交互力 Fext、末端执行器自重引起的重力分量 Fg 以及传感器内部零点漂移与噪声 Fbias 共同叠加而成：")
    
    eq3 = """
    <m:oMath>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>raw</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> = </m:t></m:r>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>ext</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> + </m:t></m:r>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>g</m:t></m:r></m:sub></m:sSub>
      <m:d><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>q</m:t></m:r></m:e></m:d>
      <m:r><m:t> + </m:t></m:r>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>bias</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t>                        (5-3)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq3)

    add_body("为了在动态运动中精准剥离出真实的外部接触力 Fext，必须执行滤波处理与精准的重力/负载辨识补偿。")
    add_body("1. 高频信号数字滤波：机械臂关节电机运行与减速机啮合会产生高频机械振动噪声。在 ROS 2 控制节点中，设计二阶巴特沃斯低通滤波器（Butterworth Low-pass Filter）对六维力传感器数据流进行平滑去噪，截止频率根据系统控制周期设定为 20 ~ 30 Hz，在有效滤除高频抖动的同时最大程度避免相位超前滞后。")
    add_body("2. 末端负载重力与质心辨识模型：设末端执行器（含局部相机与装配工具）的总质量为 m，其质心在传感器坐标系 {S} 下的相对坐标为 rc = [xc, yc, zc]ᵀ，传感器初始静态零偏为 f₀ = [f₀x, f₀y, f₀z]ᵀ 与 m₀ = [m₀x, m₀y, m₀z]ᵀ。根据正运动学计算当前机械臂基座坐标系到传感器坐标系的姿态旋转矩阵 Rbˢ(q)，重力加速度矢量在传感器坐标系下的投影为：")

    eq4 = """
    <m:oMath>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>g</m:t></m:r></m:e><m:sub><m:r><m:t>s</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> = </m:t></m:r>
      <m:sSubSup><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>R</m:t></m:r></m:e><m:sub><m:r><m:t>b</m:t></m:r></m:sub><m:sup><m:r><m:t>s</m:t></m:r></m:sup></m:sSubSup>
      <m:sSup><m:e><m:d><m:dPr><m:begChr m:val="["/><m:endChr m:val="]"/></m:dPr><m:e><m:r><m:t>0, 0, -g</m:t></m:r></m:e></m:d></m:e><m:sup><m:r><m:t>T</m:t></m:r></m:sup></m:sSup>
      <m:r><m:t>                        (5-4)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq4)

    add_body("在无外界接触力（Fext = 0）状态下，传感器测得的力与力矩模型满足：")

    eq5 = """
    <m:oMath>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>sensor</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> = </m:t></m:r>
      <m:d><m:dPr><m:begChr m:val="["/><m:endChr m:val="]"/></m:dPr><m:e><m:m><m:mr><m:e><m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>f</m:t></m:r></m:e><m:sub><m:r><m:t>s</m:t></m:r></m:sub></m:sSub></m:e></m:mr><m:mr><m:e><m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>m</m:t></m:r></m:e><m:sub><m:r><m:t>s</m:t></m:r></m:sub></m:sSub></m:e></m:mr></m:m></m:e></m:d>
      <m:r><m:t> = </m:t></m:r>
      <m:d><m:dPr><m:begChr m:val="["/><m:endChr m:val="]"/></m:dPr><m:e><m:m><m:mr><m:e><m:r><m:t>m</m:t></m:r><m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>g</m:t></m:r></m:e><m:sub><m:r><m:t>s</m:t></m:r></m:sub></m:sSub><m:r><m:t> + </m:t></m:r><m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>f</m:t></m:r></m:e><m:sub><m:r><m:t>0</m:t></m:r></m:sub></m:sSub></m:e></m:mr><m:mr><m:e><m:r><m:t>m </m:t></m:r><m:d><m:e><m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>r</m:t></m:r></m:e><m:sub><m:r><m:t>c</m:t></m:r></m:sub></m:sSub><m:r><m:t> × </m:t></m:r><m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>g</m:t></m:r></m:e><m:sub><m:r><m:t>s</m:t></m:r></m:sub></m:sSub></m:e></m:d><m:r><m:t> + </m:t></m:r><m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>m</m:t></m:r></m:e><m:sub><m:r><m:t>0</m:t></m:r></m:sub></m:sSub></m:e></m:mr></m:m></m:e></m:d>
      <m:r><m:t>                        (5-5)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq5)

    add_body("3. 基于最小二乘法的参数辨识与补偿：控制机械臂在无干涉作业空间内旋转姿态，遍历 N 个具有充分激励的非共面构型（N ≥ 24），记录对应的关节角 qᵢ 与传感器读数，构建超定线性方程组 Y = W · Θ。利用最小二乘法求解待辨识参数矢量 Θ = [m, xc, yc, zc, f₀x, ..., m₀z]ᵀ。完成辨识后，在装配控制循环中实时计算重力分量并予以剔除，即可获得纯净真实的外部交互力：")

    eq6 = """
    <m:oMath>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>ext</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> = </m:t></m:r>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>filtered</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> - </m:t></m:r>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>g</m:t></m:r></m:sub></m:sSub>
      <m:d><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>q</m:t></m:r></m:e></m:d>
      <m:r><m:t> - </m:t></m:r>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>bias</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t>                        (5-6)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq6)

    add_h3("5.2.2  位置-力混合控制律设计")
    add_body("为了使高刚度机械臂呈现出理想的人工弹性阻尼柔顺特性，本文采用基于位置的导纳控制（Admittance Control）架构。该架构由“外环导纳动力学解算 + 内环高精度位置伺服”复合而成，具备极强的抗外界扰动能力与系统稳定性。")
    add_body("1. 目标虚拟导纳动力学模型：在笛卡尔末端坐标系下，构建由目标惯量矩阵 Md、目标阻尼矩阵 Bd 及目标刚度矩阵 Kd 定义的虚拟二阶质量-阻尼-弹簧动力学方程：")

    eq7 = """
    <m:oMath>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>M</m:t></m:r></m:e><m:sub><m:r><m:t>d</m:t></m:r></m:sub></m:sSub>
      <m:d><m:e><m:sSubSup><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>x</m:t></m:r></m:e><m:sub><m:r><m:t>c</m:t></m:r></m:sub><m:sup><m:r><m:t>¨</m:t></m:r></m:sup></m:sSubSup><m:r><m:t> - </m:t></m:r><m:sSubSup><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>x</m:t></m:r></m:e><m:sub><m:r><m:t>d</m:t></m:r></m:sub><m:sup><m:r><m:t>¨</m:t></m:r></m:sup></m:sSubSup></m:e></m:d>
      <m:r><m:t> + </m:t></m:r>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>B</m:t></m:r></m:e><m:sub><m:r><m:t>d</m:t></m:r></m:sub></m:sSub>
      <m:d><m:e><m:sSubSup><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>x</m:t></m:r></m:e><m:sub><m:r><m:t>c</m:t></m:r></m:sub><m:sup><m:r><m:t>˙</m:t></m:r></m:sup></m:sSubSup><m:r><m:t> - </m:t></m:r><m:sSubSup><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>x</m:t></m:r></m:e><m:sub><m:r><m:t>d</m:t></m:r></m:sub><m:sup><m:r><m:t>˙</m:t></m:r></m:sup></m:sSubSup></m:e></m:d>
      <m:r><m:t> + </m:t></m:r>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>K</m:t></m:r></m:e><m:sub><m:r><m:t>d</m:t></m:r></m:sub></m:sSub>
      <m:d><m:e><m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>x</m:t></m:r></m:e><m:sub><m:r><m:t>c</m:t></m:r></m:sub></m:sSub><m:r><m:t> - </m:t></m:r><m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>x</m:t></m:r></m:e><m:sub><m:r><m:t>d</m:t></m:r></m:sub></m:sSub></m:e></m:d>
      <m:r><m:t> = </m:t></m:r>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>ext</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> - </m:t></m:r>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:t>d</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t>                        (5-7)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq7)

    add_body("式中，xd, ẋd, ẍd ∈ ℝ⁶ 为离线规划的期望末端位姿、速度与加速度；xc, ẋc, ẍc ∈ ℝ⁶ 为经导纳模型动态修正后的机器人参考指令；Fd ∈ ℝ⁶ 为期望目标接触力矢量（插入轴设定恒定目标推力，其余自由度设定为 0）。")
    add_body("2. 空间多自由度解耦与选择矩阵设计：针对螺栓轴孔装配的几何各向异性，引入对角选择矩阵 S = diag(s₁, s₂, ..., s₆)，实现平移纠偏、角度调平与进给压紧的完全解耦：")
    add_body("（1）轴向进给自由度（Z轴）：设定为恒力跟踪模式。令刚度矩阵对应项 Kdz = 0，系统退化为一阶纯阻尼系统，以抑制机械臂与孔底接触时的瞬态冲击，实现以稳定推力 Fdz 匀速下潜插入：", indent=True)

    eq8 = """
    <m:oMath>
      <m:sSub><m:e><m:r><m:t>B</m:t></m:r></m:e><m:sub><m:r><m:t>dz</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> Δ</m:t></m:r>
      <m:sSup><m:e><m:r><m:t>z</m:t></m:r></m:e><m:sup><m:r><m:t>˙</m:t></m:r></m:sup></m:sSup>
      <m:r><m:t> = </m:t></m:r>
      <m:sSub><m:e><m:r><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:t>ext,z</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> - </m:t></m:r>
      <m:sSub><m:e><m:r><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:t>dz</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t>                        (5-8)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq8)

    add_body("（2）横向对心自由度（X, Y轴）：设定为零力顺应模式。期望力 Fdx = Fdy = 0，令虚拟刚度极小而阻尼适中，只要孔口接触产生侧向阻力，导纳算法立刻驱动末端沿反方向发生自适应滑移，自动消除径向对心偏差：", indent=True)

    eq9 = """
    <m:oMath>
      <m:sSub><m:e><m:r><m:t>M</m:t></m:r></m:e><m:sub><m:r><m:t>dx</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> Δ</m:t></m:r>
      <m:sSup><m:e><m:r><m:t>x</m:t></m:r></m:e><m:sup><m:r><m:t>¨</m:t></m:r></m:sup></m:sSup>
      <m:r><m:t> + </m:t></m:r>
      <m:sSub><m:e><m:r><m:t>B</m:t></m:r></m:e><m:sub><m:r><m:t>dx</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> Δ</m:t></m:r>
      <m:sSup><m:e><m:r><m:t>x</m:t></m:r></m:e><m:sup><m:r><m:t>˙</m:t></m:r></m:sup></m:sSup>
      <m:r><m:t> + </m:t></m:r>
      <m:sSub><m:e><m:r><m:t>K</m:t></m:r></m:e><m:sub><m:r><m:t>dx</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> Δ</m:t></m:r>
      <m:r><m:t>x = </m:t></m:r>
      <m:sSub><m:e><m:r><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:t>ext,x</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t>                        (5-9)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq9)

    add_body("（3）空间对准姿态自由度（Roll, Pitch方向）：期望倾覆力矩 Mdx = Mdy = 0，将检测到的接触弯矩实时转化为末端小角度旋转位移修正量 Δθx, Δθy，迫使螺栓轴线向孔壁法线方向自适应“摆正调平”，彻底杜绝两点卡滞隐患。")
    add_body("3. 离散化求解与关节伺服指令生成：在 ROS 2 控制周期 Δt（10 ms，即 100 Hz）内数值解算位移修正增量 Δxₖ。结合正运动学与逆雅可比矩阵 J†(q)，将笛卡尔修正量转化为机械臂关节位置流，通过 JAKA SDK 实时伺服接口下发至底层驱动器执行：")

    eq10 = """
    <m:oMath>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>q</m:t></m:r></m:e><m:sub><m:r><m:t>k+1</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> = </m:t></m:r>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>q</m:t></m:r></m:e><m:sub><m:r><m:t>k</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> + </m:t></m:r>
      <m:sSup><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>J</m:t></m:r></m:e><m:sup><m:r><m:t>†</m:t></m:r></m:sup></m:sSup>
      <m:d><m:e><m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>q</m:t></m:r></m:e><m:sub><m:r><m:t>k</m:t></m:r></m:sub></m:sSub></m:e></m:d>
      <m:r><m:t> · Δ</m:t></m:r>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>x</m:t></m:r></m:e><m:sub><m:r><m:t>k</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t>                        (5-10)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq10)

    add_h2("5.3  视觉引导的力控装配流程")
    add_body("为了克服传统单一传感模式鲁棒性差的弊端，充分发挥“双视觉宏观与微观感知”与“高频力觉触觉顺应”的各自优势，系统设计了分阶段分层递进的螺栓自主装配控制流。")
    
    add_h3("5.3.1  视觉预定位阶段")
    add_body("视觉预定位的核心任务是消除大范围空间不确定性，为后续力控接触提供高精度的初始位姿条件，防止盲探盲插造成的刚性硬冲：")
    add_body("1. 全局粗定位与末端逼近：全局相机（Eye-to-Hand）在全景视野下识别出目标节点板所在的大致三维区域，调用第 4 章的改进 APF-Informed-RRT* 算法规划出一条绕过铁塔外侧横构件与脚钉的无碰撞平滑路径，驱动机械臂将末端局部相机运送至目标节点板正前方约 150 ~ 250 mm 的最优观测视场内。")
    add_body("2. 局部高精度特征提取与法向量解算：末端局部 RealSense D455 深度相机启动近距高分辨率采集，基于点云轮廓提取算法拟合出螺栓预制孔的中心三维坐标 Phole = [xh, yh, zh]ᵀ 及其表面法向量 nhole。")
    add_body("3. 预装配安全悬停位姿构建：根据孔位姿态，构建工具坐标系下的预装配对齐点：")

    eq11 = """
    <m:oMath>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>pre</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> = </m:t></m:r>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>hole</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> + </m:t></m:r>
      <m:sSub><m:e><m:r><m:t>d</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>safe</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t> · </m:t></m:r>
      <m:sSub><m:e><m:r><m:rPr><m:b/></m:rPr><m:t>n</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>hole</m:t></m:r></m:sub></m:sSub>
      <m:r><m:t>                        (5-11)</m:t></m:r>
    </m:oMath>
    """
    add_equation(eq11)

    add_body("安全距离 dsafe 通常取 5 ~ 10 mm。机械臂执行直线运动平稳行进至该预装配点，使螺栓尖端正对螺孔，并使其轴线与螺孔法向量基本共线，完成非接触式视觉预定位。")

    add_h3("5.3.2  力控柔顺插入阶段")
    add_body("当视觉引导螺栓到达预装配位姿后，由于剩余亚毫米级与亚度级微观偏差的存在，系统切换至以六维力闭环为主导的接触装配控制状态机：")
    add_body("1. 轻载慢速下潜与初始接触判定：机械臂沿螺孔法向量方向以极慢的速度（vapproach = 1 ~ 2 mm/s）匀速向下探寻。同时，ROS 2 控制节点以 100 Hz 频率实时监视六维力传感器读数。设置初始接触判定门限 Fthreshold = 3 N。若 |Fext,z| < Fthreshold，机械臂保持位置控制继续探寻；一旦 |Fext,z| ≥ Fthreshold，系统立即触发“接触事件”信号，机械臂停止纯位置前进，无缝切换至多维导纳柔顺控制器。")
    add_body("2. 导纳自适应搜孔与倾斜纠偏：在导纳控制器作用下，轴向施加恒定推进力 Fdz = 15 N。若此时螺栓尖端仅触碰在孔边缘倒角处，接触产生的水平分力 Fx, Fy 与倾覆力矩 Mx, My 经由导纳方程瞬时转化为末端径向微调位移 Δx, Δy 和自适应调姿偏角 Δθx, Δθy。机械臂像人手一样展现出柔顺触觉，自动“滑入”孔心并消除两点卡滞夹角。")
    add_body("3. 稳态深孔插入与终止收敛判据：当螺栓顺利落入孔中后，随着装配深度的增加，机械臂保持平稳的恒定推力继续下潜。系统设置双重装配到位判定条件：（1）位移判据：机械臂末端沿轴向推进的累积位移达到预设孔深（dinsert ≥ Lbolt - ε）；（2）突变力判据：当螺栓头部法兰面与铁塔节点板完全贴合时，由于孔底为绝对刚体，轴向阻力急剧跳变并瞬间超过安全阈值 Fstop = 45 N。满足任一收敛条件后，控制器立即撤销轴向推力，锁定当前位置并输出装配成功状态码，完成全流程柔顺装配。")

    add_h2("5.4  本章小结")
    add_body("本章针对输电铁塔螺栓自主装配中因多源感知残差与高接触刚度极易诱发碰撞卡滞的难题，提出了一套融合视觉引导与六维力控的自主柔顺装配策略：")
    add_body("（1）阐明了铁塔螺栓装配的力学机理与控制瓶颈：系统分析了轴孔装配中两点接触产生卡滞（Jamming）的几何与摩擦力学条件，论证了传统刚性位置控制在应对微小位置/姿态偏差时的缺陷，指出了引入多维力觉柔顺主动纠偏的必要性；")
    add_body("（2）建立了精确的力信息预处理与重力补偿模型：针对 JAKA 机械臂末端 JK-SE-VI-200 六维力传感器，设计了二阶低通滤波算法以抑制机械高频抖动；通过构建末端工具重力与质心辨识模型，采用最小二乘法精确剥离了工具自重与传感器零点漂移，获得了纯净的外部真实交互力；")
    add_body("（3）设计了基于导纳原理的位置-力混合控制律：采用虚拟质量-阻尼-弹簧导纳模型，引入对角选择矩阵实现了轴向恒力推移、横向零力顺应滑移以及空间力矩自动摆平的完全解耦控制，使机械臂表现出仿生柔顺顺应特性；")
    add_body("（4）构建了“视觉引导预定位+力控柔顺插入”的闭环装配流程：设计了从全局宏观调姿、局部手眼毫米级微观粗对齐，到力觉接触判定、导纳自适应纠偏下潜及双重收敛终止判据的状态机协同机制，从机制上彻底根除了螺栓装配的自锁卡滞隐患，为第 6 章的实物对比装配实验提供了成熟的控制算法闭环。")

    out1 = '/home/liu/projects/git-demo-admittance/第5章_螺栓柔顺装配力控策略.docx'
    out2 = '/home/liu/下载/第5章_螺栓柔顺装配力控策略.docx'
    doc.save(out1)
    doc.save(out2)
    print('Updated Chapter 5 docx at:', out1)
    print('Copied to:', out2)

if __name__ == '__main__':
    update_chapter5()
