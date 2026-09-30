# -*- coding: utf-8 -*-

with open('/home/liu/projects/git-demo-admittance/build_full_thesis_final.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace the chapter title finding logic
old_func_ch2 = """def update_chapter2(doc):
    print("Step 3: Updating Chapter 2...")
    # Set Chapter 2 title
    for i, p in enumerate(doc.paragraphs):
        if p.style.name == '章标题' and any('2.1' in doc.paragraphs[min(i+k, len(doc.paragraphs)-1)].text for k in [1, 2, 3, 4]):
            p.text = '第二章  硬件系统选型与实验台架搭建'
            break"""

new_func_ch2 = """def update_chapter2(doc, p_ch2_title):
    print("Step 3: Updating Chapter 2...")
    p_ch2_title.text = '第二章  硬件系统选型与实验台架搭建'"""

code = code.replace(old_func_ch2, new_func_ch2)

# Also update update_chapter1 call and where 1.5 is inserted
old_func_ch1_ins = """    p_ch2_start = None
    for p in doc.paragraphs:
        if '2.1' in p.text and '引言' in p.text:
            p_ch2_start = p
            break
            
    if p_ch2_start is not None:
        has_1_5 = any('1.5' in p.text and '论文组织结构' in p.text for p in doc.paragraphs)
        if not has_1_5:
            add_heading_before(p_ch2_start, doc, tc.CH1_SECTION5_TITLE, level=2)
            for para_text in tc.CH1_SECTION5_PARAS:
                add_body_before(p_ch2_start, para_text, indent=True)
            p_sep = p_ch2_start.insert_paragraph_before()
            p_sep.paragraph_format.space_before = Pt(6)"""

new_func_ch1_ins = """    if p_ch2_title is not None:
        has_1_5 = any('1.5' in p.text and '论文组织结构' in p.text for p in doc.paragraphs)
        if not has_1_5:
            add_heading_before(p_ch2_title, doc, tc.CH1_SECTION5_TITLE, level=2)
            for para_text in tc.CH1_SECTION5_PARAS:
                add_body_before(p_ch2_title, para_text, indent=True)
            p_sep = p_ch2_title.insert_paragraph_before()
            p_sep.paragraph_format.space_before = Pt(14)"""

code = code.replace(old_func_ch1_ins, new_func_ch1_ins)
code = code.replace("def update_chapter1(doc):", "def update_chapter1(doc, p_ch2_title):")

# Update update_chapter4
old_ch4_head = """def update_chapter4(doc):
    print("Step 5: Updating Chapter 4...")
    for p in doc.paragraphs:
        if '基于APF-Informed-RRT*' in p.text and p.style.name == '章标题':
            p.text = '第四章  输电铁塔狭窄空间避障路径规划算法'
            break"""

new_ch4_head = """def update_chapter4(doc, p_ch4_title, p_ch5_title):
    print("Step 5: Updating Chapter 4...")
    p_ch4_title.text = '第四章  输电铁塔狭窄空间避障路径规划算法'"""

code = code.replace(old_ch4_head, new_ch4_head)

old_ch4_sum = """    p_ch5_start = None
    for p in doc.paragraphs:
        if '螺栓柔顺装配力控策略' in p.text and p.style.name == '章标题':
            p_ch5_start = p
            break
            
    if p_ch5_start is not None:
        has_ch4_sum = any('4.5' in p.text and '本章小结' in p.text for p in doc.paragraphs)
        if not has_ch4_sum:
            add_heading_before(p_ch5_start, doc, tc.CH4_SUMMARY_TITLE, level=2)
            for para_text in tc.CH4_SUMMARY_PARAS:
                add_body_before(p_ch5_start, para_text, indent=True)
            p_sep = p_ch5_start.insert_paragraph_before()
            p_sep.paragraph_format.space_before = Pt(6)"""

new_ch4_sum = """    if p_ch5_title is not None:
        has_ch4_sum = any('4.5' in p.text and '本章小结' in p.text for p in doc.paragraphs)
        if not has_ch4_sum:
            add_heading_before(p_ch5_title, doc, tc.CH4_SUMMARY_TITLE, level=2)
            for para_text in tc.CH4_SUMMARY_PARAS:
                add_body_before(p_ch5_title, para_text, indent=True)
            p_sep = p_ch5_title.insert_paragraph_before()
            p_sep.paragraph_format.space_before = Pt(14)"""

code = code.replace(old_ch4_sum, new_ch4_sum)

# Update update_chapter5
old_ch5_head = """def update_chapter5(doc):
    print("Step 6: Updating Chapter 5...")
    for p in doc.paragraphs:
        if '螺栓柔顺装配力控策略' in p.text and p.style.name == '章标题':
            p.text = '第五章  螺栓柔顺装配力控策略'
            break"""

new_ch5_head = """def update_chapter5(doc, p_ch5_title):
    print("Step 6: Updating Chapter 5...")
    p_ch5_title.text = '第五章  螺栓柔顺装配力控策略'"""

code = code.replace(old_ch5_head, new_ch5_head)

# Update update_chapter3
old_ch3_head = """def update_chapter3(doc):
    print("Step 4: Updating Chapter 3...")
    for p in doc.paragraphs:
        if '障碍物与螺栓位姿双视觉识别方法' in p.text and p.style.name == '章标题':
            p.text = '第三章  障碍物与螺栓位姿双视觉识别方法'
            break"""

new_ch3_head = """def update_chapter3(doc, p_ch3_title):
    print("Step 4: Updating Chapter 3...")
    p_ch3_title.text = '第三章  障碍物与螺栓位姿双视觉识别方法'"""

code = code.replace(old_ch3_head, new_ch3_head)

# Update main function
old_main = """    print(f"Loading document: {base_file}...")
    doc = Document(base_file)
    
    update_abstract(doc)
    update_chapter1(doc)
    update_chapter2(doc)
    update_chapter3(doc)
    update_chapter4(doc)
    update_chapter5(doc)
    update_chapter6_and_7(doc)"""

new_main = """    print(f"Loading document: {base_file}...")
    doc = Document(base_file)
    
    def get_title_para(intro_prefix):
        idx = None
        for i, p in enumerate(doc.paragraphs):
            if p.text.strip().startswith(intro_prefix):
                idx = i
                break
        if idx is not None:
            for i in range(idx - 1, -1, -1):
                if doc.paragraphs[i].style.name == '章标题':
                    return doc.paragraphs[i]
        return None

    p_ch1_title = get_title_para('1.1')
    p_ch2_title = get_title_para('2.1')
    p_ch3_title = get_title_para('3.1')
    p_ch4_title = get_title_para('4.1')
    p_ch5_title = get_title_para('5.1')

    if p_ch1_title is not None:
        p_ch1_title.text = '第一章  绪论'
        
    update_abstract(doc)
    update_chapter1(doc, p_ch2_title)
    update_chapter2(doc, p_ch2_title)
    update_chapter3(doc, p_ch3_title)
    update_chapter4(doc, p_ch4_title, p_ch5_title)
    update_chapter5(doc, p_ch5_title)
    update_chapter6_and_7(doc)"""

code = code.replace(old_main, new_main)

with open('/home/liu/projects/git-demo-admittance/build_full_thesis_final.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Updated build_full_thesis_final.py successfully.")
