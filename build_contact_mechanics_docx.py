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

def create_standalone_doc():
    doc = Document()
    for s in doc.sections:
        s.top_margin = Inches(1.0)
        s.bottom_margin = Inches(1.0)
        s.left_margin = Inches(1.18)
        s.right_margin = Inches(1.18)

    # Title
    p_t = doc.add_paragraph()
    p_t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_t.paragraph_format.space_before = Pt(14)
    p_t.paragraph_format.space_after = Pt(10)
    r_t = p_t.add_run("螺栓柔顺装配各阶段接触状态演变与受力分析")
    set_run_font(r_t, 'Times New Roman', '黑体', 15, True)

    # Insert Image
    img_path = '/home/liu/.gemini/antigravity/brain/459352ac-3327-40c2-bb29-4319774ed722/.user_uploaded/media_1790058152907.png'
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(6)
    p_img.paragraph_format.space_after = Pt(2)
    p_img.paragraph_format.first_line_indent = Pt(0)
    p_img.add_run().add_picture(img_path, width=Inches(5.6))

    # Caption
    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_before = Pt(2)
    p_cap.paragraph_format.space_after = Pt(8)
    p_cap.paragraph_format.first_line_indent = Pt(0)
    r_cap = p_cap.add_run("图 5-x 螺栓装配各阶段接触状态演变与受力模型")
    set_run_font(r_cap, 'Times New Roman', '黑体', 10.5, True)

    # Intro Paragraph
    add_mixed_paragraph(doc, [
        ('text', '输电铁塔螺栓装配在力学本质上属于典型的刚性三维轴孔配合过程。如图 5-x 所示，在机械臂末端执行器的驱动下，装配件（螺栓）从初始接触到完全装配到位，需经历端面点接触寻孔（a）、平面滑移对心（b）、孔口倾斜两点接触（c）、深入孔内两点卡滞危险期（d）、同轴垂直平稳插入（e）以及完全贴合到位（f）六个典型的力学演化阶段：')
    ], indent=True)

    # Stage a
    add_mixed_paragraph(doc, [
        ('text', '（a）初始表面点接触阶段（状态 '),
        ('math', '<m:sSub><m:e><m:r><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:t>1</m:t></m:r></m:sub></m:sSub>'),
        ('text', '）\n在全局与局部视觉粗定位引导下，机械臂将螺栓运送至基体件（铁塔节点板或角钢）表面。由于视觉标定与测量残差的存在，螺栓端部并未直接对准孔心，而是以微小的倾斜姿态与基体上表面发生单点接触。此时螺栓受到重力 '),
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

    # Stage b
    add_mixed_paragraph(doc, [
        ('text', '（b）平面滑移对心阶段（状态 '),
        ('math', '<m:sSub><m:e><m:r><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:t>j</m:t></m:r></m:sub></m:sSub>'),
        ('text', '）\n螺栓在机械臂末端下压与横向驱动力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>F</m:t></m:r></m:e><m:sub><m:sSub><m:e><m:r><m:t>A</m:t></m:r></m:e><m:sub><m:r><m:t>j</m:t></m:r></m:sub></m:sSub></m:sub></m:sSub>'),
        ('text', ' 作用下，克服滑动摩擦阻力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>f</m:t></m:r></m:e><m:sub><m:r><m:t>j</m:t></m:r></m:sub></m:sSub>'),
        ('text', ' 沿基体表面向预制孔中心匀速滑动。该阶段垂直支撑力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>N</m:t></m:r></m:e><m:sub><m:r><m:t>j</m:t></m:r></m:sub></m:sSub>'),
        ('text', ' 与轴向下压力维持动态平衡，力控系统需严格抑制轴向力在安全接触阈值内（10 ~ 20 N），既保证螺栓不脱离基体表面，又避免压力过大刮伤工件表面涂层。')
    ], indent=True, space_before=4)

    # Stage c
    add_mixed_paragraph(doc, [
        ('text', '（c）孔口落入与倒角两点接触阶段（状态 '),
        ('math', '<m:sSub><m:e><m:r><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:t>k</m:t></m:r></m:sub></m:sSub>'),
        ('text', '）\n螺栓下端滑至孔口倒角边缘处受阻力突变开始“掉入”孔口。由于轴线尚未与孔轴线重合，螺栓头部与孔壁两侧发生倾斜接触，形成初始的两点接触约束。此时，孔壁两侧对螺栓产生法向反力 '),
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

    # Stage d
    add_mixed_paragraph(doc, [
        ('text', '（d）深孔两点接触与自适应纠偏阶段（状态 '),
        ('math', '<m:sSub><m:e><m:r><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:t>m</m:t></m:r></m:sub></m:sSub>'),
        ('text', '）\n螺栓部分杆身深入预制孔内，此时螺栓下端外壁与孔口对侧内壁同时紧贴，处于典型的深孔两点接触状态。该阶段是装配过程中最危险的“卡滞（Jamming）”高发期：孔壁两侧产生的法向力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>N</m:t></m:r></m:e><m:sub><m:r><m:t>m</m:t></m:r></m:sub></m:sSub>'),
        ('text', ' 和纵向摩擦力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>f</m:t></m:r></m:e><m:sub><m:r><m:t>m</m:t></m:r></m:sub></m:sSub>'),
        ('text', ' 构成了强烈的阻力偶矩，阻碍螺栓继续下潜。此时常规位置控制若强行推进必将导致螺栓咬死；系统必须通过导纳控制算法，利用测得的翻转弯矩实时微调机械臂末端横向位置与空间偏角，迫使螺栓与孔壁法线方向严格重合。')
    ], indent=True, space_before=4)

    # Stage e
    add_mixed_paragraph(doc, [
        ('text', '（e）同轴垂直平稳插入阶段（状态 '),
        ('math', '<m:sSub><m:e><m:r><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:t>l</m:t></m:r></m:sub></m:sSub>'),
        ('text', '）\n随着轴线偏角的彻底消除（'),
        ('math', '<m:r><m:t>Δ</m:t></m:r><m:r><m:t>θ</m:t></m:r><m:r><m:t> ≈ 0</m:t></m:r>'),
        ('text', '），螺栓与预制孔恢复同轴共线状态，原有的两点刚性卡滞退化为均匀的柱面滑动摩擦接触。此时横向干涉力与翻转力矩均衰减至零附近，机械臂只需施加恒定的轴向推进推力 '),
        ('math', '<m:r><m:t>G</m:t></m:r><m:d><m:e><m:sSub><m:e><m:r><m:t>F</m:t></m:r></m:e><m:sub><m:sSub><m:e><m:r><m:t>A</m:t></m:r></m:e><m:sub><m:r><m:t>l</m:t></m:r></m:sub></m:sSub></m:sub></m:sSub></m:e></m:d>'),
        ('text', ' 克服平稳滑动阻力，驱动螺栓快速、平稳地向孔底深处匀速滑入。')
    ], indent=True, space_before=4)

    # Stage f
    add_mixed_paragraph(doc, [
        ('text', '（f）底部贴合与装配完成阶段（状态 '),
        ('math', '<m:sSub><m:e><m:r><m:t>P</m:t></m:r></m:e><m:sub><m:r><m:t>N</m:t></m:r></m:sub></m:sSub>'),
        ('text', '）\n当螺栓头部法兰面与基体件表面完全密合时，由于基体件孔底具有极高的法向刚度，垂直支撑反力 '),
        ('math', '<m:sSub><m:e><m:r><m:t>N</m:t></m:r></m:e><m:sub><m:r><m:t>N</m:t></m:r></m:sub></m:sSub>'),
        ('text', ' 发生阶跃式剧增。控制器实时捕获到该轴向力突变并判断其超过设定的装配终止阈值（如 '),
        ('math', '<m:sSub><m:e><m:r><m:t>F</m:t></m:r></m:e><m:sub><m:r><m:rPr><m:nor/></m:rPr><m:t>stop</m:t></m:r></m:sub></m:sSub><m:r><m:t> ≥ 45 N</m:t></m:r>'),
        ('text', '），立即切断轴向下压伺服指令并锁定当前位姿，宣告全流程柔顺装配顺利完成。')
    ], indent=True, space_before=4)

    out1 = '/home/liu/projects/git-demo-admittance/螺栓柔顺装配力学状态演变与受力分析.docx'
    out2 = '/home/liu/下载/螺栓柔顺装配力学状态演变与受力分析.docx'
    doc.save(out1)
    doc.save(out2)
    print('Saved standalone contact mechanics docx to:', out1)
    print('Copied to:', out2)

if __name__ == '__main__':
    create_standalone_doc()
