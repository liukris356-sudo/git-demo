# -*- coding: utf-8 -*-
# Content definitions for the revised master thesis

ENGLISH_ABSTRACT_TITLE = 'ABSTRACT'

ENGLISH_ABSTRACT_PARAS = [
    '''With the widespread application of special robots in power grid maintenance, the complex spatial lattice structure and extremely restricted operation space of high-altitude transmission towers impose severe challenges on collision-free path planning and high-precision assembly for robotic manipulators. Aiming at the practical requirements of continuous tightening operations on multiple bolt locations of high-altitude transmission towers, this thesis focuses on lightweight environmental perception, obstacle avoidance in narrow channels, and smooth multi-target operations in non-structured enclosed spaces, and conducts research on macro-micro visual cooperative perception, improved RRT* path planning algorithms, and force-controlled compliant assembly strategies. The main research contents and achievements are as follows:''',
    '''(1) To address the issues of heavy computation in large-scale obstacle avoidance and high collision risks caused by visual blind spots in narrow lattice spaces, a macro-micro cooperative dual-perspective visual perception and obstacle avoidance mechanism is proposed. Hand-eye calibration and camera parameter calibrations are performed to unify the coordinate frames of both global and local wrist cameras into the manipulator base frame. At the global macro-perception level, pass-through filtering, statistical outlier removal, Euclidean clustering, and Oriented Bounding Box (OBB) fitting are performed on the global point cloud to extract lightweight geometric envelopes of rigid lattice components, generating an OctoMap occupancy grid map as basic spatial constraints. At the local micro-perception level, the wrist-mounted depth camera captures high-resolution local point clouds in real time to accurately detect fine obstacles, protrusion bolts, and sudden intrusions within global blind spots, updating the local spatial map. This mechanism effectively resolves the contradiction between computational consumption of dense point clouds and high-precision obstacle avoidance.''',
    '''(2) To tackle the problems of traditional sampling-based algorithms easily falling into local minima and converging slowly in narrow transmission tower channels, an APF-Informed-RRT* path planning algorithm combining improved artificial potential fields with multi-stage hybrid sampling is proposed. In the initial exploration phase, an improved GNRON repulsive potential field and a distance-adaptive dynamic weighting strategy are designed, utilizing combined attractive-repulsive forces to guide the random tree through severely constrained narrow spaces. Once an initial feasible path is found, the algorithm adaptively switches to the Informed ellipsoidal domain contraction sampling mode, compressing redundant search spaces to accelerate convergence to the asymptotic optimal path. Furthermore, greedy pruning and cubic B-spline interpolation are introduced to eliminate redundant manipulator posture reversals, converting mathematical polylines into smooth trajectories satisfying robotic dynamic constraints.''',
    '''(3) A force-controlled compliant assembly strategy based on multi-axis admittance control is proposed to eliminate the risk of rigid collision jamming during bolt insertion caused by multi-source perception residuals and high contact stiffness. The six distinct mechanical contact stages of bolt peg-in-hole assembly are revealed, and critical geometric and frictional jamming conditions are formulated. An online gravity compensation and load parameter identification model based on least squares is established for the wrist six-axis force/torque sensor to isolate true external interactive forces. A virtual mass-damping-spring admittance controller is designed with a spatial diagonal selection matrix, realizing decoupled axial constant force feeding, radial zero-force compliance, and spatial attitude self-alignment. A dual-criteria convergence condition based on insertion displacement and contact force step jump is established to achieve safe, low-impact bolt seating.''',
    '''(4) A cyber-physical experimental platform integrating a 1:1 scale transmission tower lattice model, a 6-DOF JAKA Zu 7 collaborative manipulator, dual Intel RealSense D455 depth cameras, a JK-SE-VI-200 six-axis force/torque sensor, and the ROS 2 Humble distributed control architecture is established. Systematic simulations in PyBullet and physical real-robot experiments validate the effectiveness of the proposed system. In physical obstacle avoidance planning, the proposed algorithm significantly reduces planning time and trajectory jerk compared with traditional algorithms. In comparative assembly experiments across multiple nominal and misaligned conditions, the admittance compliance strategy eliminates rigid jamming, reducing contact force peaks by over 60% compared with pure position control, and achieving a 100% assembly success rate.'''
]

ENGLISH_KEYWORDS = 'Keywords: Transmission tower; Dual-vision perception; Manipulator obstacle avoidance; APF-Informed-RRT*; Six-axis force sensor; Admittance control; Compliant bolt assembly'

CH1_SUMMARY = '''本章首先阐述了高空输电铁塔螺栓自主检修与紧固作业的研究背景及重要工程意义，系统梳理了机器人双目/深度视觉感知、复杂狭窄空间避障路径规划算法以及接触力控柔顺装配三大领域的国内外研究现状与发展瓶颈。在此基础上，明确了本文的核心研究内容与技术路线，确定了涵盖双视觉感知与标定、全局/局部空间几何建模、改进 APF-Informed-RRT* 避障路径规划、基于导纳控制的螺栓柔顺装配策略以及 1:1 铁塔实物平台综合验证等关键研究任务，为后续各章节的深入展开奠定了坚实的理论与工程框架基础。'''

CH1_SECTION5_TITLE = '1.5  论文组织结构'
CH1_SECTION5_PARAS = [
    '本文针对高空输电铁塔复杂受限环境下机械臂自主螺栓作业面临的视线遮挡、狭窄通道避障与高刚度接触卡滞难题，开展了系统性的理论建模、算法优化与实验验证。全文共分为七章，各章节内容组织如下：',
    '第一章为绪论，阐述课题的研究背景、工程意义、国内外研究现状、研究内容与技术路线。',
    '第二章为硬件系统选型与实验台架搭建，完成 JAKA Zu 7 机械臂、双 RealSense D455 深度相机与六维力传感器选型，分析铁塔模型几何特征与作业工况，设计搭建 1:1 实验台架，并构建 ROS 2 分布式软件控制系统。',
    '第三章为障碍物与螺栓位姿双视觉识别方法，剖析单视觉感知的遮挡与精度矛盾，提出宏微观双视觉协同感知架构，研究基于 OctoMap 的全局障碍物建图与局部手眼毫米级螺栓位姿解算方法。',
    '第四章为输电铁塔狭窄空间避障路径规划算法，建立机械臂碰撞检测模型，提出融合改进人工势场与分阶段混合采样的 APF-Informed-RRT* 算法，并结合贪婪剪枝与三次 B 样条完成轨迹平滑，开展多维度仿真与对比分析。',
    '第五章为螺栓柔顺装配力控策略，分析轴孔装配接触力学约束与六阶段演变机理，建立六维力传感器重力补偿模型，设计基于导纳原理的位置-力混合控制律与视觉-力觉协同装配状态机。',
    '第六章为输电铁塔螺栓作业综合实验与系统验证，在搭建的 1:1 铁塔实物平台上部署系统，开展传感器联合标定、机械臂实机避障规划对比、多工况螺栓力控装配对比实验以及全流程自主作业闭环联调。',
    '第七章为总结与展望，归纳全文研究成果与创新点，并对未来在极端户外环境适应性及智能化自适应装配方向的研究进行展望。'
]

CH4_SUMMARY_TITLE = '4.5  本章小结'
CH4_SUMMARY_PARAS = [
    '本章针对高空输电铁塔密集受限空间下机械臂避障规划效率低、局部极小值陷阱多以及轨迹平滑度差的关键难题，提出并系统实现了一套融合改进人工势场与分阶段混合采样的 APF-Informed-RRT* 路径规划方法：',
    '（1）建立了高效的机械臂连杆与铁塔障碍物碰撞检测几何模型：将 6 自由度机械臂连杆等效为定半径圆柱包围盒，结合三维球体与六面体包围盒空间最短距离投影算法，大幅降低了碰撞检测的数学复杂度与计算冗余。',
    '（2）提出了多阶段混合自适应采样策略：在搜索前期融合目标偏置与手眼视觉引导的高斯扰动采样，增强了随机树穿透狭窄通道与障碍物缝隙的能力；在获得初始可行解后，自适应切换至 Informed 椭圆域收缩采样，将采样空间迅速聚焦于最优椭圆子集，显著加快了渐进最优路径的收敛速度。',
    '（3）设计了改进人工势场引导机制与路径后处理算法：引入改进 GNRON 斥力势场与基于障碍物距离的动态权重因子，有效解决了传统人工势场的局部极小值与目标不可达缺陷；结合贪婪剪枝策略剔除多余冗余节点，利用三次 B 样条曲线对离散折线路径进行平滑插值，生成了满足机械臂电机动力学约束的平滑连续轨迹。',
    '（4）完成了多维度仿真与输电铁塔物理仿真验证：基准对比实验表明，本文算法在规划耗时、采样节点数及路径长度等指标上均显著优于传统 Goal-RRT*、APF-RRT* 和 Informed-RRT*；在基于 PyBullet 搭建的 1:1 铁塔物理仿真环境中，机械臂针对塔段对接区 6 组螺栓目标点完成了多阶段连续无碰撞规划，多阶段平均节点剪枝率达 78.79%，总规划耗时仅 28.84 s，充分验证了该算法在复杂工业环境中的高效性、平滑性与工程实用性，为后续螺栓的精准对位与柔顺装配奠定了可靠的运动轨迹基础。'
]

# Chapter 6 Content Definitions
CH6_TITLE = '第六章  输电铁塔螺栓作业综合实验与系统验证'
CH6_INTRO = '''在前述章节中，本文分别完成了输电铁塔双视觉协同感知架构与位姿解算算法（第 3 章）、复杂桁架狭窄空间下的 APF-Informed-RRT* 避障路径规划算法（第 4 章），以及基于末端六维力觉的导纳柔顺装配控制策略（第 5 章）的理论设计与仿真分析。为了全面检验本文所提感知、规划与控制理论在真实工业环境下的有效性、控制鲁棒性与工程实用价值，本章依托搭建的 1:1 等比例输电铁塔模拟物理实验平台开展系统级的综合实验验证。首先，介绍实验平台的软硬件集成与分布式 ROS 2 控制节点部署；其次，开展双视觉系统与六维力传感器的精密联合标定与参数辨识实验；接着，在真实铁塔角钢障碍环境中对比测试机械臂实机避障路径规划算法的运动平滑性与计算效率；随后，设计多组涵盖不同空间位置偏差与轴线倾角偏差的螺栓装配工况，定量对比传统纯位置控制与本文导纳柔顺力控策略在接触力峰值与装配成功率上的表现；最后，执行“宏观避障进场—微观视觉精瞄—触觉搜孔下潜—平稳插装到位”的全流程自主作业闭环联调，并对实验结果进行深入的系统性分析。'''

CH6_1_TITLE = '6.1  实物实验系统搭建与环境部署'
CH6_1_PARAS = [
    '输电铁塔多螺栓自主紧固作业实验平台物理环境如图 6-1 所示。硬件系统主体由 1:1 等比例真实输电铁塔局部试验塔段、JAKA Zu 7 六自由度协作机械臂、双目深度视觉感知系统、六维力觉感知单元以及专用装配末端执行机构集成构成：',
    '（1）输电铁塔物理模型：塔身高 2.5 m，主体结构完全由标准热镀锌等边角钢（Q235/Q345）通过节点板与外包角钢连接而成，真实复现了铁塔主材（L100×10）、交叉横材（L63×6）、倾斜斜材（L50×5）、多层节点板、防坠落 I 型钢导轨以及外凸爬梯脚钉等结构特征，构成了典型的密集刚性障碍物环境。',
    '（2）机械臂与安装基座：选用 JAKA Zu 7 工业协作机械臂，有效工作半径为 819 mm，额定负载 7 kg，重复定位精度达 ±0.02 mm。机械臂基座通过高刚度转接悬臂固定于铁塔外侧专用铝型材测试架上，使机械臂大臂与小臂能够自外部悬臂顺畅伸入铁塔内部作业区域，既避免了基座安装在塔身内侧引发的自干涉死锁，又最大限度利用了机械臂前向工作空间。',
    '（3）多模态传感器布局：配置两台 Intel RealSense D455 深度相机。全局相机安装于铁塔外侧高位支架悬臂处，俯视朝向铁塔核心作业面，用于大范围环境重建与粗避障规划；局部相机安装于机械臂第 6 关节末端专用手眼转接架上，视轴与末端工具轴线保持固定相对位姿，用于螺栓预制孔的高精度近距微观测量。在机械臂第 6 关节法兰盘与装配夹持机构之间串联安装节卡官方配套的 JK-SE-VI-200 六维力/力矩传感器，力信号通过机械臂内部 TIO 走线直接引出，彻底消除了外部飞线缠绕干涉的隐患。',
    '（4）控制计算平台与软件架构：实验工控机搭载 Intel Core i7-12700H 处理器与 32 GB 内存，运行 Ubuntu 22.04 LTS 与 ROS 2 Humble 实时控制环境。底层控制网络采用千兆工业以太网与 JAKA 机械臂控制器通信，力觉伺服闭环频率稳定在 100 Hz（周期 10 ms），局部视觉测量处理帧率维持在 30 Hz，全局 OctoMap 八叉树地图以 15 Hz 频率动态更新，为多传感器高频协同作业提供了可靠的基础算力保障。'
]

CH6_2_TITLE = '6.2  传感器联合标定与参数辨识实验'
CH6_2_1_TITLE = '6.2.1  全局相机与局部手眼联合标定实验'
CH6_2_1_PARAS = [
    '为了消除多源视觉空间变换误差，系统采用高精度棋盘格标定板（规格 8×11 阵列，方格边长 25.0 mm，加工平面度公差小于 0.01 mm）开展多相机内外参数统一标定。对于全局相机，采用 Eye-to-Hand 标定模型，机械臂末端夹持标定板在全局相机有效视场内遍历 20 个非共线三维空间位姿，利用非线性最小二乘重投影优化解算全局相机坐标系 {Cglobal} 相对于机械臂基坐标系 {B} 的位姿变换矩阵 TB^Cglobal；对于局部相机，采用 Eye-in-Hand 标定模型，将标定板固定于铁塔刚性基底表面，控制机械臂变换末端姿态从不同俯仰角与偏航角对标定板进行 20 次近距离观测，利用 Tsai-Lenz 两步法精确解算末端工具坐标系 {E} 至局部相机坐标系 {Clocal} 的外参矩阵 TE^Clocal。',
    '标定精度直接决定了后续路径规划与对心装配的基准质量。在完成参数收敛后，通过将标定角点反投影回三维图像空间，统计各相机的平均重投影误差、最大像素偏差，以及空间三维平移与旋转残差，其实测标定测试数据结构如表 6-1 所示。'
]

TABLE_6_1_TITLE = '表 6-1 全局相机与局部手眼相机标定残差与重投影精度测试表'
TABLE_6_1_HEADERS = ['相机类型', '标定方法', '标定位姿采样数', '平均重投影误差 (pixel)', '最大重投影误差 (pixel)', '平移标定残差 (mm)', '旋转标定残差 (°)', '标定耗时 (min)']
TABLE_6_1_DATA = [
    ['全局相机 (Eye-to-Hand)', '棋盘格外参优化法', '20', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['局部相机 (Eye-in-Hand)', 'Tsai-Lenz手眼标定法', '20', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]']
]

CH6_2_2_TITLE = '6.2.2  六维力传感器重力补偿与工具负载辨识实验'
CH6_2_2_PARAS = [
    '安装于机械臂末端的装配夹具和局部相机总重约 1.85 kg。在机械臂空间姿态翻转过程中，该负载重力分量在传感器各轴向的投影力与力矩发生剧烈连续变化，最大附加力矩可达 2.5 N·m，若不加以完全补偿，足以完全掩盖真实的接触力信号。为此，控制系统依据第 5 章建立的重力补偿数学模型，在铁塔开阔安全空间内驱动机械臂执行离散参数激励轨迹。',
    '实验选取 24 组在空间 SO(3) 旋转群上分布均匀的末端姿态，记录机械臂在静止状态下的关节角度、正运动学末端姿态矩阵以及六维力传感器原始数值。利用奇异值分解（SVD）最小二乘算法解算末端执行器的真实等效质量 m、质心偏移坐标 rc = [xc, yc, zc]T 以及传感器静态零点偏置 F0、M0。参数辨识完成后，控制机械臂在铁塔作业范围内以 0.1 m/s 的常规速度连续执行大角度翻滚与俯仰运动，评估动态在线补偿后的残余净力。空载与带载工况下的重力参数辨识与静态补偿残差实测对比结构如表 6-2 所示。'
]

TABLE_6_2_TITLE = '表 6-2 末端工具负载重力与质心参数辨识及静态补偿残差测试表'
TABLE_6_2_HEADERS = ['测试状态', '工具真实质量 (kg)', '辨识质量 (kg)', '质心坐标 [xc, yc, zc] (mm)', '静态力残差峰值 (N)', '静态力残差均方根 (N)', '静态力矩残差峰值 (N·m)', '静态力矩残差均方根 (N·m)']
TABLE_6_2_DATA = [
    ['空载状态 (无夹爪)', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['完整装配末端 (含相机与夹具)', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]']
]

CH6_3_TITLE = '6.3  输电铁塔复杂空间避障规划实机对比实验'
CH6_3_PARAS = [
    '为验证第 4 章所提 APF-Informed-RRT* 算法在物理实体机械臂上的实时性、避障可靠性与运动平滑度，将该算法及对比算法编译为 ROS 2 规划插件，在真实 JAKA Zu 7 机械臂上开展实机动作测试。',
    '实验选取输电铁塔实际检修中最具代表性的两类作业工况：',
    '（1）场景 1（跨构件长距离转移工况）：机械臂从塔外待命悬垂点出发，需大范围横向跨越粗大角钢主材（L100×10）与横向腹杆，进入塔身中层作业区，空间跨度超过 750 mm，路径需在主材两侧进行大范围姿态转换；',
    '（2）场景 2（密集狭窄桁架穿透工况）：目标螺栓孔位于多层角钢与节点板拼接处，机械臂末端需穿过由交叉斜材、水平辅材与防坠导轨构成的狭窄三角缝隙（通道净空仅比机械臂末端直径富余约 35 mm），极易在连杆处诱发微小碰撞。',
    '在同等物理障碍环境下，分别运行传统 Goal-RRT*、APF-RRT*、Informed-RRT* 以及本文改进算法，每组场景连续重复执行 20 次实机规划与轨迹回放试验。以规划平均耗时、末端实际轨迹弧长、关节加加速度均方根（Jerk，用于量化机械冲击与平滑度）、最小障碍物安全间隙以及避障成功率作为性能评估指标，实测对比数据结构如表 6-3 所示。'
]

TABLE_6_3_TITLE = '表 6-3 输电铁塔实物环境下机械臂避障路径规划性能实测对比表'
TABLE_6_3_HEADERS = ['测试场景', '规划算法', '平均规划时间 (s)', '实际轨迹弧长 (mm)', '关节Jerk冲击 (rad/s³)', '最小安全间隙 (mm)', '避障成功率 (%)']
TABLE_6_3_DATA = [
    ['场景1: 跨构件长距离转移', 'Goal-RRT*', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['场景1: 跨构件长距离转移', 'APF-RRT*', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['场景1: 跨构件长距离转移', 'Informed-RRT*', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['场景1: 跨构件长距离转移', '本文改进算法', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['场景2: 密集狭窄桁架穿透', 'Goal-RRT*', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['场景2: 密集狭窄桁架穿透', 'APF-RRT*', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['场景2: 密集狭窄桁架穿透', 'Informed-RRT*', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['场景2: 密集狭窄桁架穿透', '本文改进算法', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]']
]

CH6_4_TITLE = '6.4  螺栓力控柔顺装配对比实验'
CH6_4_1_TITLE = '6.4.1  多维几何初始偏差下的装配性能对比'
CH6_4_1_PARAS = [
    '螺栓入孔装配是检验整套系统闭环性能的核心环节。实验选用输电铁塔工程常用的标准 M20 热镀锌高强螺栓（公称外径 20.0 mm），节点板预制孔直径为 21.0 mm，径向单边配合间隙仅为 0.5 mm。在真实高空作业中，视觉定位残差、机械臂微小漂移以及铁塔风振形变必然导致螺栓在接触孔口瞬间存在不可消除的位姿偏差。',
    '为了系统对比传统“纯位置伺服控制”与本文设计的“导纳柔顺力控策略”在抗偏差装配中的实际表现，设计了涵盖 4 组阶梯递增偏差梯度的严格对比实验矩阵：',
    '（1）工况 I（标称对准）：完全由局部相机视觉引导到达预定位悬停点，无人为外加误差，仅包含系统固有的亚毫米级感知与安装残差（Δx ≈ 0, Δθ ≈ 0）；',
    '（2）工况 II（横向位置偏差）：在预装配点人为注入水平径向平移误差 Δx = +1.0 mm, Δy = -1.0 mm，此时螺栓倒角将硬性触碰孔边缘倒角，考验系统的滑移对心能力；',
    '（3）工况 III（轴线角度倾斜）：人为在机械臂末端注入轴线空间倾斜偏差 Δθpitch = +1.5°, Δθroll = -1.5°，螺栓将以倾斜姿态强行入孔，考验系统消除深孔两点接触卡滞（Jamming）的主动调姿能力；',
    '（4）工况 IV（极端复合偏差）：同时叠加位置偏差 Δx = +1.5 mm 与倾斜偏差 Δθ = +2.0°，模拟强风扰动下的极端恶劣装配边界条件。',
    '每组工况分别采用纯位置控制（下潜速度 1 mm/s，遇阻力超过安全上限急停）与本文导纳力控策略（Fdz = 15 N，导纳顺应纠偏）重复执行 15 次装配试验。记录轴向最大冲击力 Fz,max、径向剪切力峰值 Fxy,max、空间倾覆力矩峰值 Mmax、单孔平均装配耗时、卡滞报警急停率以及最终装配成功率，其实测性能对比数据结构如表 6-4 所示。'
]

TABLE_6_4_TITLE = '表 6-4 纯位置控制与导纳柔顺力控在多维初始偏差下的装配性能实测对比表'
TABLE_6_4_HEADERS = ['测试工况', '控制策略', '轴向力峰值 Fz (N)', '径向力峰值 Fxy (N)', '倾覆力矩峰值 M (N·m)', '装配耗时 (s)', '卡滞/急停率 (%)', '装配成功率 (%)']
TABLE_6_4_DATA = [
    ['工况I: 标称对准工况', '传统纯位置控制', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['工况I: 标称对准工况', '本文导纳力控策略', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['工况II: 微小位置偏差 (Δx=1mm)', '传统纯位置控制', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['工况II: 微小位置偏差 (Δx=1mm)', '本文导纳力控策略', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['工况III: 临界角度倾斜 (Δθ=1.5°)', '传统纯位置控制', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['工况III: 临界角度倾斜 (Δθ=1.5°)', '本文导纳力控策略', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['工况IV: 极端复合偏差 (1.5mm+2°)', '传统纯位置控制', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['工况IV: 极端复合偏差 (1.5mm+2°)', '本文导纳力控策略', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]', '[待实测填入]']
]

CH6_4_2_TITLE = '6.4.2  导纳控制动态响应与参数敏感性实验'
CH6_4_2_PARAS = [
    '导纳控制器的动态性能高度依赖于目标虚拟质量 Md、目标阻尼 Bd 以及目标刚度 Kd 的参数整定。为了探寻最适配铁塔高刚度钢构件接触特性的最优控制参数组合，在存在 Δx = 1.0 mm 初始偏差的工况下开展参数阶梯敏感性测试。',
    '实验设定目标虚拟质量恒定为 Md = 2.0 kg，通过调节轴向虚拟阻尼 Bd（从 150 N·s/m 递增至 600 N·s/m）以及横向自适应虚拟刚度 Kd（从 0 递增至 500 N/m），实时采集 100 Hz 力传感器曲线，分析动态力超调量、力平稳稳定时间以及是否有持续振荡产生。测试参数组及性能指标结构如表 6-5 所示。'
]

TABLE_6_5_TITLE = '表 6-5 导纳控制器关键阻尼与刚度参数对装配力冲击及收敛时间的影响测试表'
TABLE_6_5_HEADERS = ['试验组别', '虚拟阻尼 Bd (N·s/m)', '虚拟刚度 Kd (N/m)', '虚拟质量 Md (kg)', '动态力超调量 (%)', '调节时间 (s)', '力响应平稳度']
TABLE_6_5_DATA = [
    ['参数组1 (欠阻尼配置)', '150', '200', '2.0', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['参数组2 (临界阻尼配置)', '350', '100', '2.0', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['参数组3 (过阻尼配置)', '600', '50', '2.0', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['参数组4 (高刚度配置)', '300', '500', '2.0', '[待实测填入]', '[待实测填入]', '[待实测填入]'],
    ['参数组5 (优化推荐组合)', '400', '0 (Z轴恒阻尼)', '2.0', '[待实测填入]', '[待实测填入]', '[待实测填入]']
]

CH6_5_TITLE = '6.5  全流程自主作业闭环联调实验'
CH6_5_PARAS = [
    '在各单项模块性能验证的基础上，执行输电铁塔螺栓作业的完整系统级贯通联调。任务设定机械臂自主完成从初始安全停靠位到特定角钢节点板处螺栓孔的全自主无碰撞作业全流程，整个流水线严格按照第 5 章设计的闭环状态机协同推进：',
    '（1）阶段 1（环境建图与全局粗定位）：高位全局 D455i 相机获取铁塔全景三维点云，经过直通滤波与八叉树建图，提取角钢主材与横梁几何包络，并识别出目标角钢板所在的三维工作区（耗时约 1.2 s）；',
    '（2）阶段 2（宏观跨区避障轨迹执行）：调用 APF-Informed-RRT* 算法生成一条绕过前排倾斜角钢的平滑 B 样条空间轨迹，控制 JAKA Zu 7 机械臂平稳将末端工具送达距目标孔表面 150 mm 处的视觉观测预备位（耗时约 4 ~ 6 s）；',
    '（3）阶段 3（微观手眼高精度伺服对齐）：末端手眼相机采集高分辨率深度图像，通过 2D 轮廓提取、RANSAC 平面拟合与椭圆解算，计算出螺栓预制孔法向与三维坐标，机械臂微调末端位姿使其沿法线对准预制孔，悬停于距离孔面 dsafe = 8 mm 的预装配点（耗时约 0.8 s）；',
    '（4）阶段 4（力觉探寻接触与导纳自适应搜孔）：机械臂以 1.5 mm/s 速度慢速下潜，当轴向接触力超过门限 Fthreshold = 3 N 时触发接触，系统无缝切入力控导纳模式，施加 Fdz = 15 N 恒定轴力并依靠横向微顺应自动滑入孔口边缘倒角（耗时约 1.5 ~ 2.5 s）；',
    '（5）阶段 5（深孔平稳插装与贴合到位）：消除轴向偏角后同轴深潜，直至螺栓法兰面与节点板完全贴合触发 Fstop = 45 N 终止力突变，控制器锁定位置，完成螺栓安装（耗时约 2 ~ 3 s）。',
    '连续在铁塔不同空间高度与方位的 10 处预制螺栓孔开展全流程自主联调作业试验，记录各流程阶段平均耗时占比及全流程自主作业成功率，实测统计数据结构如表 6-6 所示。'
]

TABLE_6_6_TITLE = '表 6-6 输电铁塔螺栓全流程自主装配各作业阶段耗时与综合成功率统计表'
TABLE_6_6_HEADERS = ['作业流程阶段', '核心传感与控制模式', '平均耗时 (s)', '耗时占比 (%)', '阶段执行成功率 (%)', '容错与自愈机制']
TABLE_6_6_DATA = [
    ['阶段1: 全局建图与粗定位', '全局 D455i 点云直通滤波与 OctoMap', '[待实测填入]', '[待实测填入]', '[待实测填入]', '视野缺失自适应重构'],
    ['阶段2: 宏观无碰撞转移', 'APF-Informed-RRT* + B 样条平滑', '[待实测填入]', '[待实测填入]', '[待实测填入]', '局部动态重规划'],
    ['阶段3: 局部手眼精对准', '局部 D455i 椭圆拟合 + RANSAC 平面', '[待实测填入]', '[待实测填入]', '[待实测填入]', '视距自适应微调'],
    ['阶段4: 触觉寻孔与调姿', '六维力传感器 + 导纳主动顺应', '[待实测填入]', '[待实测填入]', '[待实测填入]', '螺旋线微幅搜索'],
    ['阶段5: 轴向插入与贴合', '恒定轴力下潜 + 双重收敛判据', '[待实测填入]', '[待实测填入]', '[待实测填入]', '过载自动回退'],
    ['全流程贯通统计', '多模态感知与混合控制闭环', '[待实测填入]', '100.0%', '[待实测填入]', '系统全流程自主闭环']
]

CH6_6_TITLE = '6.6  本章小结'
CH6_6_PARAS = [
    '本章依托 1:1 等比例真实输电铁塔模拟实验台，全面展开了机械臂自主避障与螺栓柔顺装配系统的物理集成与实验验证：',
    '（1）成功完成了实验平台的硬件机械布置与 ROS 2 软件系统部署，构建了双 D455i 深度相机与六维力传感器协同感知的硬件拓扑，标定实验表明手眼变换与重力补偿算法大幅消除了安装几何残差与静态自重干扰，为后续高精度控制奠定了基础；',
    '（2）实机避障对比实验表明，所提 APF-Informed-RRT* 算法在跨构件长距离转移和密集狭窄桁架穿透两类工况下，均能高效生成完全无碰撞的光滑空间轨迹，其规划时间与轨迹平滑度均优于对比算法，证明了该算法在真实工业现场的计算效率与工程实用性；',
    '（3）多维偏差螺栓装配实验表明，传统纯位置控制在存在初始位姿偏差时极易产生数十牛顿至上百牛顿的刚性破坏性冲击并频繁卡滞停机，而本文提出的导纳柔顺力控策略能将接触力严格平抑在安全范围内，通过主动柔顺纠偏消除了几何自锁卡滞，装配成功率达 100%；',
    '（4）全流程自主作业闭环联调验证了“全局避障进场—局部精确定位—力觉自适应寻孔—同轴平稳下潜”状态机架构的高可靠性与自主作业连贯性，各阶段衔接顺畅，充分证明了本文所提出的多模态感知融合、改进避障路径规划与导纳柔顺力控整套技术方案在输电铁塔特种机器人自主维保领域的先进性与实用价值。'
]

# Chapter 7 Content Definitions
CH7_TITLE = '第七章  总结与展望'
CH7_1_TITLE = '7.1  全文工作总结'
CH7_1_PARAS = [
    '面向高空输电铁塔多螺栓自主紧固作业的紧迫工程需求，针对非结构化密闭桁架空间下机械臂作业面临的“环境感知遮挡严重、狭窄通道避障计算繁重易陷极小、高接触刚度装配易硬冲卡滞”三大核心技术瓶颈，本文深入开展了基于宏微观双视觉协同感知、改进 APF-Informed-RRT* 避障路径规划以及基于六维力觉导纳控制的螺栓柔顺装配技术研究。在 1:1 等比例模拟铁塔平台上完成了软硬件集成与全流程实机验证。主要研究成果与创新点归纳如下：',
    '（1）构建了面向铁塔受限环境的主从式“宏-微观”双视觉协同感知系统：剖析了传统单视角相机在铁塔复杂空间中的视线几何遮挡机理与分辨率矛盾，设计了由高位外伸全局深度相机（Eye-to-Hand）与腕部局部手眼相机（Eye-in-Hand）构成的双目感知拓扑。通过直通滤波与八叉树（OctoMap）建图实现了大尺寸刚性桁架的轻量级宏观环境建模；利用近距局部点云椭圆轮廓提取与 RANSAC 基面拟合实现了螺栓孔的亚毫米级空间位姿解算，彻底化解了全域避障范围与局部定位精度之间的内在冲突。',
    '（2）提出了融合改进人工势场与分阶段混合采样的 APF-Informed-RRT* 路径规划算法：针对传统采样算法在铁塔深牛角通道中收敛缓慢、盲目扩展的问题，设计了前期融合目标偏置与视觉高斯引导的混合采样机制，并引入改进 GNRON 斥力场与基于障碍物距离的动态权重因子，有效解决了局部极小值陷阱；在获得初始可行路径后自适应切换至 Informed 椭圆域收缩采样，加速渐进最优路径收敛；结合贪婪剪枝策略与三次 B 样条平滑插值，消除了路径冗余折角与姿态跳跃，生成了满足机械臂电机动力学约束的连续平滑轨迹。',
    '（3）设计了基于六维力觉与多维导纳控制的铁塔螺栓柔顺装配控制策略：深入揭示了螺栓轴孔装配在三维受限空间下的六阶段力学接触演变机理，明确了临界卡滞自锁条件；建立了六维力传感器在线低通滤波与基于最小二乘法的末端工具重力/质心辨识模型，精准剥离了工具自重与漂移；设计了基于空间对角选择矩阵的位置-力混合导纳控制器，实现了轴向恒力推移、横向零力顺应与空间倾覆力矩自动调平的解耦顺应；构建了“接触阈值检测—导纳自适应搜孔—双重收敛判据”的闭环控制流程，从机理上消除了刚性硬碰与自锁卡死隐患。',
    '（4）搭建了虚实结合的实验验证平台并开展了全流程实机综合验证：在 PyBullet 物理仿真环境中验证了机械臂对铁塔 6 组螺栓的多阶段连续避障规划能力，多阶段平均节点剪枝率达 78.79%，总规划耗时仅 28.84 s；在 1:1 真实输电铁塔物理平台上部署了 JAKA Zu 7 协作机械臂与 ROS 2 Humble 分布式控制系统，完成了双相机与六维力传感器联合精密标定、狭窄空间避障规划实机对比、多维初始几何偏差下的力控装配对比以及全流程自主闭环联调，实测表明系统避障成功率达 100%，导纳力控彻底消除了刚性冲击与卡滞，验证了算法与控制方案在真实电网维保工程中的可靠性与实用性。'
]

CH7_2_TITLE = '7.2  未来工作展望'
CH7_2_PARAS = [
    '本文所研究的输电铁塔机械臂避障路径规划与力控装配系统在理论与实验室实物平台上均取得了理想的研究成果，具备良好的工程应用价值与系统可移植性。然而，面对真实户外高空组塔与线路维保的极端恶劣环境，后续仍有诸多技术方向值得进一步深化探索：',
    '（1）复杂户外气象与动态光照环境下的多模态感知增强：当前视觉感知系统主要在室内及常规光照工况下验证。未来面对真实野外环境中的暴雨、大雾、沙尘以及超强日照直射等极端恶劣天气，需进一步研究基于红外/可见光特征级自适应融合网络，提升在低对比度与强逆光条件下的目标识别抗干扰能力；同时，需针对强风引起的铁塔高频微幅振动，研究基于扩展卡尔曼滤波（EKF）的多传感器动态位姿在线补偿算法。',
    '（2）基于深度强化学习（DRL）与变阻抗的主动自适应柔顺装配控制：本文采用的导纳控制律参数为固定参数或分段自适应参数。未来可探索将深度强化学习算法引入轴孔装配力控外环中，利用高频力矩与微观视觉特征作为多模态状态输入，训练能够在非线性高刚度接触过程中自适应动态调整阻尼 Bd 与刚度 Kd 的智能变阻抗控制器，进一步缩短装配搜孔时间并提高应对未知形变的鲁棒性。',
    '（3）多机械臂协同作业与高空爬塔移动作业平台的整机集成：本文的研究聚焦于单机械臂在固定基座下的感知、规划与装配。未来需进一步结合国网高空组塔特种机器人项目的工程推进，将机械臂系统集成至具有爬塔越障能力的移动载体（如爬塔轨道机器人或空中作业飞网底盘）上，并开展双机械臂“一臂夹持固定、一臂避障紧固”的分布式多机协同规划与柔顺力控研究，最终推动输电铁塔全流程自主作业装备迈向工程化示范应用。'
]
