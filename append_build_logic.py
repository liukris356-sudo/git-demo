# -*- coding: utf-8 -*-

append_code = """
def update_chapter3(doc):
    print("Step 5: Updating Chapter 3...")
    # Set Chapter 3 title
    for p in doc.paragraphs:
        if '障碍物与螺栓位姿双视觉识别方法' in p.text and p.style.name == '章标题':
            p.text = '第三章  障碍物与螺栓位姿双视觉识别方法'
            break
            
    # Heading mapping for Chapter 3
    ch3_heading_map = {
        '3.1  单视觉的场景瓶颈分析': '3.2  单视觉的场景瓶颈分析',
        '3.1.1  桁架遮挡导致的目标漏检问题': '3.2.1  桁架遮挡导致的目标漏检问题',
        '3.1.2  全局视野与局部精度的矛盾': '3.2.2  全局视野与局部精度的矛盾',
        '3.2  双视觉协同感知架构设计': '3.3  双视觉协同感知架构设计',
        '3.2.1  全局障碍感知模块': '3.3.1  全局障碍感知模块',
        '3.2.2  局部螺栓精定位模块': '3.3.2  局部螺栓精定位模块',
        '3.3  障碍物检测与空间映射方法': '3.4  障碍物检测与空间映射方法',
        '3.4  螺栓位姿识别与坐标解算': '3.5  螺栓位姿识别与坐标解算',
        '3.5  识别定位实验与分析': '3.6  识别定位实验与分析',
        '3.5.1  障碍物检测准确率': '3.6.1  障碍物检测准确率',
        '3.5.2  螺栓位姿识别精度': '3.6.2  螺栓位姿识别精度',
        '3.6  本章小结': '3.7  本章小结'
    }
    
    for p in doc.paragraphs:
        t = p.text.strip()
        for k, v in ch3_heading_map.items():
            if t == k:
                p.text = v
                break
                
    # Embed Images in Chapter 3 if not present
    img3_1 = '/home/liu/projects/git-demo-admittance/fig3_1_bottlenecks.png'
    img3_2 = '/home/liu/projects/git-demo-admittance/fig3_2_architecture.png'
    img3_3 = '/home/liu/projects/git-demo-admittance/fig3_3_pose_pipeline.png'
    
    for i, p in enumerate(doc.paragraphs):
        t = p.text.strip()
        if '图 3-1 铁塔复杂场景下单视觉感知瓶颈机理分析' in t:
            # Check if previous paragraph has drawing
            prev_p = doc.paragraphs[i-1]
            if 'w:drawing' not in prev_p._p.xml and os.path.exists(img3_1):
                p_img = p.insert_paragraph_before()
                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_img.paragraph_format.space_before = Pt(8)
                p_img.paragraph_format.space_after = Pt(2)
                p_img.paragraph_format.first_line_indent = Pt(0)
                run = p_img.add_run()
                run.add_picture(img3_1, width=Inches(5.8))
        elif '图 3-2 双视觉协同感知系统总体架构与数据流向图' in t:
            prev_p = doc.paragraphs[i-1]
            if 'w:drawing' not in prev_p._p.xml and os.path.exists(img3_2):
                p_img = p.insert_paragraph_before()
                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_img.paragraph_format.space_before = Pt(8)
                p_img.paragraph_format.space_after = Pt(2)
                p_img.paragraph_format.first_line_indent = Pt(0)
                run = p_img.add_run()
                run.add_picture(img3_2, width=Inches(5.8))
        elif '图 3-3 局部视觉螺栓孔位姿解算与几何拟合原理流程图' in t:
            prev_p = doc.paragraphs[i-1]
            if 'w:drawing' not in prev_p._p.xml and os.path.exists(img3_3):
                p_img = p.insert_paragraph_before()
                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_img.paragraph_format.space_before = Pt(8)
                p_img.paragraph_format.space_after = Pt(2)
                p_img.paragraph_format.first_line_indent = Pt(0)
                run = p_img.add_run()
                run.add_picture(img3_3, width=Inches(5.8))
                
    # Style Table 4 and Table 5 as 3-line tables
    if len(doc.tables) > 5:
        for t_idx in [4, 5]:
            t = doc.tables[t_idx]
            tblPr = t._tbl.tblPr
            tblBorders = parse_xml(r'''
                <w:tblBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                    <w:top w:val="single" w:sz="12" w:space="0" w:color="000000"/>
                    <w:left w:val="none"/>
                    <w:bottom w:val="single" w:sz="12" w:space="0" w:color="000000"/>
                    <w:right w:val="none"/>
                    <w:insideH w:val="none"/>
                    <w:insideV w:val="none"/>
                </w:tblBorders>
            ''')
            tblPr.append(tblBorders)
            for cell in t.rows[0].cells:
                tcPr = cell._tc.get_or_add_tcPr()
                tcBorders = parse_xml(r'''
                    <w:tcBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                        <w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/>
                    </w:tcBorders>
                ''')
                tcPr.append(tcBorders)
    print("Chapter 3 updated.")

def update_chapter5(doc):
    print("Step 6: Updating Chapter 5...")
    # Set Chapter 5 title
    for p in doc.paragraphs:
        if '螺栓柔顺装配力控策略' in p.text and p.style.name == '章标题':
            p.text = '第五章  螺栓柔顺装配力控策略'
            break
            
    # Heading mapping for Chapter 5
    ch5_heading_map = {
        '5.2  铁塔螺栓装配的力控需求分析': '5.2  铁塔螺栓装配的力控需求分析',
        '5.1.1  螺栓装配的接触力约束': '5.2.1  螺栓装配的接触力学约束与六阶段力学演变',
        '5.1.2  传统位置控制的局限性': '5.2.2  传统位置控制的局限性',
        '5.2  基于导纳控制的柔顺装配策略': '5.3  基于导纳控制的柔顺装配策略',
        '5.2.1  末端力信息处理与重力补偿': '5.3.1  末端力信息处理与重力补偿',
        '5.2.2  位置-力混合控制律设计': '5.3.2  位置-力混合控制律设计',
        '5.3  视觉引导的力控装配流程': '5.4  视觉引导的力控装配流程',
        '5.3.1  视觉预定位阶段': '5.4.1  视觉预定位阶段',
        '5.3.2  力控柔顺插入阶段': '5.4.2  力控柔顺插入阶段',
        '5.4  本章小结': '5.5  本章小结'
    }
    
    for p in doc.paragraphs:
        t = p.text.strip()
        for k, v in ch5_heading_map.items():
            if t == k:
                p.text = v
                break
                
    # Remove stray sentence
    for p in doc.paragraphs:
        if '式中R表示螺栓目标检测识别率' in p.text:
            p.text = ''
            
    # Restore formulas in 6-stage contact mechanics
    # P539-P544
    stage_a = '（a）初始表面点接触阶段（状态 P1）\\n在全局与局部视觉粗定位引导下，机械臂将螺栓运送至基体件（铁塔节点板或角钢）表面。由于视觉标定与测量残差的存在，螺栓端部并未直接对准孔心，而是以微小的倾斜姿态与基体上表面发生单点接触。此时螺栓受到重力 G、基体表面法向支撑力 N1、表面摩擦力 f1 以及机械臂末端的主动驱动力 FA1 的共同作用；机械臂需根据接触产生的偏心反力矩施加自适应顺应力矩 Mc1，使螺栓向孔口方向微调并滑动。'
    stage_b = '（b）平面滑移对心阶段（状态 P2）\\n螺栓在机械臂末端下压与横向驱动力 FA2 作用下，克服滑动摩擦阻力 f2 沿基体表面向预制孔中心匀速滑动。该阶段垂直支撑力 N2 与轴向下压力维持动态平衡，力控系统需严格抑制轴向力在安全接触阈值内（10 ~ 20 N），既保证螺栓不脱离基体表面，又避免压力过大刮伤工件表面涂层。'
    stage_c = '（c）孔口落入与倒角两点接触阶段（状态 P3）\\n螺栓下端滑至孔口倒角边缘处受阻力突变开始“掉入”孔口。由于轴线尚未与孔轴线重合，螺栓头部与孔壁两侧发生倾斜接触，形成初始的两点接触约束。此时，孔壁两侧对螺栓产生法向反力 N3a、N3b 及切向摩擦阻力 f3a、f3b，若下压力 FA3 过大将极易在孔口边缘诱发“几何楔紧（Wedging）”。因此，机械臂必须依靠六维力传感器感知到的力矩突变，启动主动自适应调姿力矩 Mc3，驱动螺栓绕接触点旋转“摆正”，消除轴线夹角。'
    stage_d = '（d）深孔两点接触与自适应纠偏阶段（状态 P4）\\n螺栓部分杆身深入预制孔内，此时螺栓下端外壁与孔口对侧内壁同时紧贴，处于典型的深孔两点接触状态。该阶段是装配过程中最危险的“卡滞（Jamming）”高发期：孔壁两侧产生的法向力 N4a、N4b 和纵向摩擦力 f4a、f4b 构成了强烈的阻力偶矩，阻碍螺栓继续下潜。此时常规位置控制若强行推进必将导致螺栓咬死；系统必须通过导纳控制算法，利用测得的翻转弯矩实时微调机械臂末端横向位置与空间偏角，迫使螺栓与孔壁法线方向严格重合。'
    stage_e = '（e）同轴垂直平稳插入阶段（状态 P5）\\n随着轴线偏角的彻底消除（θ -> 0），螺栓与预制孔恢复同轴共线状态，原有的两点刚性卡滞退化为均匀的柱面滑动摩擦接触。此时横向干涉力与翻转力矩均衰减至零附近，机械臂只需施加恒定的轴向推进推力 FA5 克服平稳滑动阻力 f5，驱动螺栓快速、平稳地向孔底深处匀速滑入。'
    stage_f = '（f）底部贴合与装配完成阶段（状态 P6）\\n当螺栓头部法兰面与基体件表面完全密合时，由于基体件孔底具有极高的法向刚度，垂直支撑反力 N6 发生阶跃式剧增。控制器实时捕获到该轴向力突变并判断其超过设定的装配终止阈值（Fstop = 45 N），立即切断轴向下压伺服指令并锁定当前位姿，宣告全流程柔顺装配顺利完成。'
    
    stages = [stage_a, stage_b, stage_c, stage_d, stage_e, stage_f]
    stage_idx = 0
    
    for p in doc.paragraphs:
        t = p.text.strip()
        if t.startswith('（a）初始表面点接触阶段') and stage_idx == 0:
            p.text = stage_a
            stage_idx = 1
        elif t.startswith('（b）平面滑移对心阶段') and stage_idx == 1:
            p.text = stage_b
            stage_idx = 2
        elif t.startswith('（c）孔口落入与倒角两点接触阶段') and stage_idx == 2:
            p.text = stage_c
            stage_idx = 3
        elif t.startswith('（d）深孔两点接触与自适应纠偏阶段') and stage_idx == 3:
            p.text = stage_d
            stage_idx = 4
        elif t.startswith('（e）同轴垂直平稳插入阶段') and stage_idx == 4:
            p.text = stage_e
            stage_idx = 5
        elif t.startswith('（f）底部贴合与装配完成阶段') and stage_idx == 5:
            p.text = stage_f
            stage_idx = 6
            
    # Embed Fig 5-1 if not present
    img5_1 = '/home/liu/.gemini/antigravity/brain/459352ac-3327-40c2-bb29-4319774ed722/.user_uploaded/media_1790058152907.png'
    for i, p in enumerate(doc.paragraphs):
        if '如图 5-x 所示' in p.text or '六个典型的力学演化阶段' in p.text:
            p.text = p.text.replace('如图 5-x 所示', '如图 5-1 所示')
            # Check if next paragraph already has image
            next_p = doc.paragraphs[i+1]
            if 'w:drawing' not in next_p._p.xml and os.path.exists(img5_1):
                p_img = next_p.insert_paragraph_before()
                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_img.paragraph_format.space_before = Pt(8)
                p_img.paragraph_format.space_after = Pt(2)
                p_img.paragraph_format.first_line_indent = Pt(0)
                run = p_img.add_run()
                run.add_picture(img5_1, width=Inches(5.8))
                
                p_cap = next_p.insert_paragraph_before()
                p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_cap.paragraph_format.space_before = Pt(2)
                p_cap.paragraph_format.space_after = Pt(8)
                p_cap.paragraph_format.first_line_indent = Pt(0)
                run_cap = p_cap.add_run('图 5-1  螺栓柔顺装配轴孔配合力学状态演变与受力分析图')
                set_run_font(run_cap, 'Times New Roman', '黑体', 10.5, bold=True)
            break
    print("Chapter 5 updated.")

def update_chapter6_and_7(doc):
    print("Step 7: Creating new Chapter 6 and Chapter 7...")
    # Find old Chapter 6 start paragraph ('总结与展望')
    p_old_ch6 = None
    for p in doc.paragraphs:
        if '总结与展望' in p.text and p.style.name == '章标题':
            p_old_ch6 = p
            break
            
    # Find References paragraph ('参考文献')
    p_ref_start = None
    for p in doc.paragraphs:
        if '参考文献' in p.text and p.style.name == '章标题':
            p_ref_start = p
            break
            
    if p_old_ch6 is not None and p_ref_start is not None:
        # Collect paragraphs between p_old_ch6 and p_ref_start
        paras_to_remove = []
        collect = False
        for p in doc.paragraphs:
            if p == p_old_ch6:
                collect = True
            if p == p_ref_start:
                break
            if collect:
                paras_to_remove.append(p)
                
        # Insert Chapter 6 and Chapter 7 before p_ref_start!
        # Chapter 6 Title
        add_heading_before(p_ref_start, tc.CH6_TITLE, level=1)
        add_body_before(p_ref_start, tc.CH6_INTRO, indent=True)
        
        # 6.1
        add_heading_before(p_ref_start, tc.CH6_1_TITLE, level=2)
        for para in tc.CH6_1_PARAS:
            add_body_before(p_ref_start, para, indent=True)
            
        # 6.2
        add_heading_before(p_ref_start, tc.CH6_2_TITLE, level=2)
        add_heading_before(p_ref_start, tc.CH6_2_1_TITLE, level=3)
        for para in tc.CH6_2_1_PARAS:
            add_body_before(p_ref_start, para, indent=True)
        add_3line_table_before(p_ref_start, doc, tc.TABLE_6_1_TITLE, tc.TABLE_6_1_HEADERS, tc.TABLE_6_1_DATA)
        
        add_heading_before(p_ref_start, tc.CH6_2_2_TITLE, level=3)
        for para in tc.CH6_2_2_PARAS:
            add_body_before(p_ref_start, para, indent=True)
        add_3line_table_before(p_ref_start, doc, tc.TABLE_6_2_TITLE, tc.TABLE_6_2_HEADERS, tc.TABLE_6_2_DATA)
        
        # 6.3
        add_heading_before(p_ref_start, tc.CH6_3_TITLE, level=2)
        for para in tc.CH6_3_PARAS:
            add_body_before(p_ref_start, para, indent=True)
        add_3line_table_before(p_ref_start, doc, tc.TABLE_6_3_TITLE, tc.TABLE_6_3_HEADERS, tc.TABLE_6_3_DATA)
        
        # 6.4
        add_heading_before(p_ref_start, tc.CH6_4_TITLE, level=2)
        add_heading_before(p_ref_start, tc.CH6_4_1_TITLE, level=3)
        for para in tc.CH6_4_1_PARAS:
            add_body_before(p_ref_start, para, indent=True)
        add_3line_table_before(p_ref_start, doc, tc.TABLE_6_4_TITLE, tc.TABLE_6_4_HEADERS, tc.TABLE_6_4_DATA)
        
        add_heading_before(p_ref_start, tc.CH6_4_2_TITLE, level=3)
        for para in tc.CH6_4_2_PARAS:
            add_body_before(p_ref_start, para, indent=True)
        add_3line_table_before(p_ref_start, doc, tc.TABLE_6_5_TITLE, tc.TABLE_6_5_HEADERS, tc.TABLE_6_5_DATA)
        
        # 6.5
        add_heading_before(p_ref_start, tc.CH6_5_TITLE, level=2)
        for para in tc.CH6_5_PARAS:
            add_body_before(p_ref_start, para, indent=True)
        add_3line_table_before(p_ref_start, doc, tc.TABLE_6_6_TITLE, tc.TABLE_6_6_HEADERS, tc.TABLE_6_6_DATA)
        
        # 6.6
        add_heading_before(p_ref_start, tc.CH6_6_TITLE, level=2)
        for para in tc.CH6_6_PARAS:
            add_body_before(p_ref_start, para, indent=True)
            
        p_sep1 = p_ref_start.insert_paragraph_before()
        p_sep1.paragraph_format.space_before = Pt(12)
        
        # Chapter 7
        add_heading_before(p_ref_start, tc.CH7_TITLE, level=1)
        add_heading_before(p_ref_start, tc.CH7_1_TITLE, level=2)
        for para in tc.CH7_1_PARAS:
            add_body_before(p_ref_start, para, indent=True)
            
        add_heading_before(p_ref_start, tc.CH7_2_TITLE, level=2)
        for para in tc.CH7_2_PARAS:
            add_body_before(p_ref_start, para, indent=True)
            
        p_sep2 = p_ref_start.insert_paragraph_before()
        p_sep2.paragraph_format.space_before = Pt(14)
        
        # Now remove old paragraphs
        for p in paras_to_remove:
            p._p.getparent().remove(p._p)
            
        print("Chapter 6 and Chapter 7 successfully inserted.")

def main():
    base_file = '/home/liu/文档/基于视觉感知的机械臂避障路径规划---刘庆-----毕业论文(1)(1).docx'
    output_doc_path = '/home/liu/文档/基于视觉感知的机械臂避障路径规划---刘庆-----毕业论文_修订完成版.docx'
    output_dl_path = '/home/liu/下载/基于视觉感知的机械臂避障路径规划---刘庆-----毕业论文_修订完成版.docx'
    
    print(f"Loading document: {base_file}...")
    doc = Document(base_file)
    
    update_abstract(doc)
    update_chapter1(doc)
    update_chapter2(doc)
    update_chapter3(doc)
    update_chapter4(doc)
    update_chapter5(doc)
    update_chapter6_and_7(doc)
    
    print(f"Saving to {output_doc_path}...")
    doc.save(output_doc_path)
    
    print(f"Copying to {output_dl_path}...")
    import shutil
    shutil.copy2(output_doc_path, output_dl_path)
    
    print("SUCCESS! Complete thesis revised and exported.")

if __name__ == '__main__':
    main()
"""

with open('/home/liu/projects/git-demo-admittance/build_full_thesis_final.py', 'a', encoding='utf-8') as f:
    f.write(append_code)

print("build_full_thesis_final.py appended successfully.")
