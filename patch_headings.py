# -*- coding: utf-8 -*-

with open('/home/liu/projects/git-demo-admittance/build_full_thesis_final.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix Chapter 2 heading mapping
old_ch2_map = """        '2.4  软件平台架构': '2.5  软件控制系统架构设计',
        '2.4.1  ROS操作系统': '2.5.1  ROS 2 软件系统架构与通信机制',
        '2.4.2  ROS2操作系统优势': '2.5.2  多源异构传感器分布式协同与节点设计',
        '2.5  双相机安装分布': '2.4  输电铁塔模拟实验台架与机械安装设计',
        '2.5.3': '2.4.2  传感器空间拓扑与双相机分布'"""

new_ch2_map = """        '2.4  软件平台架构': '2.4  软件控制系统架构设计',
        '2.4.1  ROS操作系统': '2.4.1  ROS 2 软件系统架构与通信机制',
        '2.4.2  ROS2操作系统优势': '2.4.2  多源异构传感器分布式协同与节点设计',
        '2.5  双相机安装分布': '2.5  输电铁塔模拟实验台架与双相机安装设计',
        '2.5.3': '2.5.1  传感器空间拓扑与双相机安装分布'"""

content = content.replace(old_ch2_map, new_ch2_map)

# Fix Chapter 4 headings
old_ch4_map = """        '三维复杂空间单目标点路径规划': '4.4.2  三维复杂空间单目标点路径规划仿真',"""

new_ch4_map = """        '实验验证和结果分析': '4.4  算法仿真与对比分析',
        '二维复杂环境单目标点路径规划': '4.4.1  二维复杂环境单目标点路径规划仿真',
        '三维复杂空间单目标点路径规划': '4.4.2  三维复杂空间单目标点路径规划仿真',"""

content = content.replace(old_ch4_map, new_ch4_map)

with open('/home/liu/projects/git-demo-admittance/build_full_thesis_final.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied to build_full_thesis_final.py.")
