import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

# Set font
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'DejaVu Sans', 'WenQuanYi Zen Hei']
plt.rcParams['axes.unicode_minus'] = False

def create_fig1_bottlenecks():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5), dpi=300)
    
    # Subplot 1: Occlusion
    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, 10)
    ax1.axis('off')
    ax1.set_title('(a) 桁架几何遮挡与视线盲区示意', fontsize=12, fontweight='bold', pad=10)
    
    # Camera
    cam = patches.Polygon([[1, 8.5], [2, 9.2], [2, 7.8]], closed=True, color='#2b5c8f')
    ax1.add_patch(cam)
    ax1.text(1.5, 9.4, '全局单相机\n(Eye-to-Hand)', ha='center', fontsize=10, fontweight='bold')
    
    # Sight lines
    ax1.plot([2, 5.5], [8.5, 7.5], 'r--', alpha=0.7)
    ax1.plot([2, 5.5], [8.5, 4.0], 'r--', alpha=0.7)
    ax1.fill([2, 5.5, 5.5], [8.5, 7.5, 4.0], color='orange', alpha=0.15)
    ax1.text(3.5, 6.8, '视野范围 (FOV)', fontsize=9, color='darkorange', rotation=-15)
    
    # Foreground obstacle (Angle steel)
    obst = patches.Rectangle((5.5, 4.5), 1.0, 3.2, color='#7f8c8d', ec='black', lw=1.5)
    ax1.add_patch(obst)
    ax1.text(6.0, 6.1, '前排角钢\n(遮挡物)', ha='center', va='center', color='white', fontsize=10, fontweight='bold')
    
    # Occlusion shadow
    ax1.fill([6.5, 9.5, 9.5, 6.5], [7.7, 7.5, 3.5, 4.5], color='red', alpha=0.25)
    ax1.text(8.0, 5.8, '严重遮挡盲区\n(目标漏检区)', ha='center', va='center', color='#c0392b', fontsize=10, fontweight='bold')
    
    # Hidden target
    target = patches.Circle((8.5, 5.2), 0.4, color='#e74c3c', ec='black')
    ax1.add_patch(target)
    ax1.text(8.5, 4.4, '目标螺栓孔\n(处于盲区中)', ha='center', fontsize=9, color='#c0392b')
    
    # Subplot 2: Distance vs Resolution & Error
    dist = np.linspace(0.2, 2.5, 100)
    # spatial resolution (mm/pixel)
    fx = 640 # typical focal length
    resol = (dist * 1000) / fx
    error = 0.3 + 1.2 * (dist ** 1.8)
    
    color = '#2980b9'
    ax2.set_xlabel('观测距离 Z (m)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('空间分辨率 (mm/pixel)', color=color, fontsize=11, fontweight='bold')
    line1 = ax2.plot(dist, resol, color=color, lw=2.5, label='空间分辨力 (mm/pixel)')
    ax2.tick_params(axis='y', labelcolor=color)
    ax2.grid(True, linestyle='--', alpha=0.5)
    
    ax2_right = ax2.twinx()
    color = '#c0392b'
    ax2_right.set_ylabel('三维测量残差 (mm)', color=color, fontsize=11, fontweight='bold')
    line2 = ax2_right.plot(dist, error, color=color, lw=2.5, linestyle='-.', label='3D测量残差 (mm)')
    ax2_right.tick_params(axis='y', labelcolor=color)
    
    # Annotate zones
    ax2.axvspan(0.15, 0.4, color='green', alpha=0.15)
    ax2.text(0.28, 3.2, '局部手眼相机\n有效精测区\n(<0.5mm)', ha='center', fontsize=9, color='darkgreen', fontweight='bold')
    
    ax2.axvspan(1.5, 2.5, color='blue', alpha=0.1)
    ax2.text(2.0, 1.5, '全局环境相机\n宏观避障区\n(精度受限)', ha='center', fontsize=9, color='navy', fontweight='bold')
    
    ax2.set_title('(b) 观测距离与成像分辨率/测量误差关系', fontsize=12, fontweight='bold', pad=10)
    
    plt.tight_layout()
    path = '/home/liu/projects/git-demo-admittance/fig3_1_bottlenecks.png'
    plt.savefig(path, bbox_inches='tight')
    plt.close()
    print('Generated:', path)

def create_fig2_architecture():
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 7)
    ax.axis('off')
    
    # Boxes definition
    def draw_box(x, y, w, h, title, subtitle, color, bg_color):
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1", fc=bg_color, ec=color, lw=2)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h*0.68, title, ha='center', va='center', fontsize=11, fontweight='bold', color=color)
        ax.text(x + w/2, y + h*0.32, subtitle, ha='center', va='center', fontsize=9, color='#2c3e50')
        return (x, y, w, h)

    # 1. Global Camera Branch (Top)
    draw_box(0.5, 4.8, 2.8, 1.6, '全局相机 (Eye-to-Hand)', '高位外伸支架 Intel D455\n大视场俯视环境全景', '#2980b9', '#ebf5fb')
    draw_box(4.0, 4.8, 3.2, 1.6, '全局障碍感知与建图', '直通与体素滤波去噪\n外参标定与八叉树概率栅格', '#16a085', '#e8f8f5')
    draw_box(8.0, 4.8, 2.5, 1.6, 'OctoMap 体素地图', '输出障碍物空间占据网格\n输入第4章避障路径规划', '#27ae60', '#eafaf1')
    
    # 2. Local Camera Branch (Bottom)
    draw_box(0.5, 1.2, 2.8, 1.6, '局部相机 (Eye-in-Hand)', '机械臂腕部集成 Intel D455\n随动近距高分辨率成像', '#8e44ad', '#f4ecf7')
    draw_box(4.0, 1.2, 3.2, 1.6, '局部螺栓精定位模块', 'YOLO/模板ROI目标检测\nRANSAC平面拟合与空间圆心解算', '#d35400', '#fef5e7')
    draw_box(8.0, 1.2, 2.5, 1.6, '螺栓6D精确位姿', '输出空间坐标与法向量\n输入第5章导纳装配', '#c0392b', '#fdedec')
    
    # 3. Middle Coordinator
    mid_rect = patches.FancyBboxPatch((4.2, 3.2), 2.8, 1.0, boxstyle="round,pad=0.1", fc='#fef9e7', ec='#f39c12', lw=2)
    ax.add_patch(mid_rect)
    ax.text(5.6, 3.8, '双视觉协同调度中枢 (ROS 2)', ha='center', va='center', fontsize=10, fontweight='bold', color='#b9770e')
    ax.text(5.6, 3.45, '手眼标定统一基座标系 | 时间同步与分阶段状态机', ha='center', va='center', fontsize=8, color='#7d6608')
    
    # Connective arrows
    arrow_style = dict(arrowstyle="->,head_length=0.6,head_width=0.4", lw=2.2, color='#34495e')
    ax.annotate('', xy=(4.0, 5.6), xytext=(3.3, 5.6), arrowprops=arrow_style)
    ax.annotate('', xy=(8.0, 5.6), xytext=(7.2, 5.6), arrowprops=arrow_style)
    
    ax.annotate('', xy=(4.0, 2.0), xytext=(3.3, 2.0), arrowprops=arrow_style)
    ax.annotate('', xy=(8.0, 2.0), xytext=(7.2, 2.0), arrowprops=arrow_style)
    
    # Cross arrows to coordinator
    ax.annotate('', xy=(5.6, 4.8), xytext=(5.6, 4.2), arrowprops=dict(arrowstyle="<->", lw=1.5, color='#f39c12', linestyle='--'))
    ax.annotate('', xy=(5.6, 3.2), xytext=(5.6, 2.8), arrowprops=dict(arrowstyle="<->", lw=1.5, color='#f39c12', linestyle='--'))
    
    plt.tight_layout()
    path = '/home/liu/projects/git-demo-admittance/fig3_2_architecture.png'
    plt.savefig(path, bbox_inches='tight')
    plt.close()
    print('Generated:', path)

def create_fig3_pose_estimation():
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(12, 4.0), dpi=300)
    
    # (1) 2D Detection
    ax1.set_title('(a) 2D检测与ROI提取', fontsize=11, fontweight='bold')
    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, 10)
    ax1.axis('off')
    plate = patches.Rectangle((1, 1), 8, 8, color='#bdc3c7', ec='#34495e', lw=2)
    ax1.add_patch(plate)
    ax1.text(2.0, 8.2, '铁塔节点板表面', fontsize=9, color='#2c3e50')
    hole1 = patches.Circle((3.5, 4.5), 1.2, color='#2c3e50', ec='black')
    ax1.add_patch(hole1)
    # Bounding Box
    bbox = patches.Rectangle((1.8, 2.8), 3.4, 3.4, fill=False, ec='#e74c3c', lw=2.5, linestyle='--')
    ax1.add_patch(bbox)
    ax1.text(3.5, 6.5, 'YOLO检测框 (ROI)', ha='center', fontsize=9, color='#e74c3c', fontweight='bold')
    ax1.plot([3.5], [4.5], 'r+', ms=12, mew=2)
    ax1.text(3.5, 3.9, '(u0, v0)', ha='center', fontsize=9, color='white')
    
    # (2) 3D Point Cloud & Plane fitting
    ax2.set_title('(b) RANSAC基面与点云拟合', fontsize=11, fontweight='bold')
    ax2.set_xlim(0, 10)
    ax2.set_ylim(0, 10)
    ax2.axis('off')
    # 3D tilted plane
    plane = patches.Polygon([[1.5, 2.0], [7.5, 3.0], [9.0, 8.5], [3.0, 7.5]], color='#d5dbdb', ec='#7f8c8d', lw=1.5)
    ax2.add_patch(plane)
    # Scatter points
    np.random.seed(42)
    px = np.random.uniform(2.5, 7.5, 80)
    py = np.random.uniform(3.5, 7.5, 80)
    ax2.scatter(px, py, s=12, color='#2980b9', alpha=0.7)
    # Normal vector
    ax2.annotate('', xy=(5.5, 8.0), xytext=(5.0, 5.0),
                 arrowprops=dict(arrowstyle="->,head_width=0.4", lw=2.5, color='#c0392b'))
    ax2.text(5.7, 7.8, '法向量 n', fontsize=10, fontweight='bold', color='#c0392b')
    ax2.text(5.0, 4.3, '拟合基面 Π\nAx+By+Cz+D=0', ha='center', fontsize=9, color='#2c3e50')
    
    # (3) 6D Pose coordinate frame
    ax3.set_title('(c) 空间六自由度坐标系解算', fontsize=11, fontweight='bold')
    ax3.set_xlim(0, 10)
    ax3.set_ylim(0, 10)
    ax3.axis('off')
    
    # Circle
    circle_3d = patches.Circle((5, 4.5), 2.2, color='#34495e', ec='#16a085', lw=2)
    ax3.add_patch(circle_3d)
    ax3.plot([5], [4.5], 'yo', ms=8)
    ax3.text(5.0, 3.8, '空间圆心 Ph(xh,yh,zh)', ha='center', fontsize=9, color='white', fontweight='bold')
    
    # 3 axes
    # Z (normal)
    ax3.annotate('', xy=(5.0, 7.8), xytext=(5.0, 4.5),
                 arrowprops=dict(arrowstyle="->", lw=2.5, color='#3498db'))
    ax3.text(5.2, 7.6, 'Z轴 (法向轴线)', fontsize=9, color='#3498db', fontweight='bold')
    # X (tangent)
    ax3.annotate('', xy=(7.8, 5.3), xytext=(5.0, 4.5),
                 arrowprops=dict(arrowstyle="->", lw=2.5, color='#e74c3c'))
    ax3.text(8.0, 5.2, 'X轴', fontsize=9, color='#e74c3c', fontweight='bold')
    # Y
    ax3.annotate('', xy=(3.0, 6.0), xytext=(5.0, 4.5),
                 arrowprops=dict(arrowstyle="->", lw=2.5, color='#2ecc71'))
    ax3.text(2.6, 6.1, 'Y轴', fontsize=9, color='#2ecc71', fontweight='bold')
    
    ax3.text(5.0, 1.2, '经手眼标定矩阵变换:\nTb^bolt = Tb^flange · Tflange^cam · Tcam^bolt', ha='center', fontsize=9, color='#2c3e50', fontweight='bold')
    
    plt.tight_layout()
    path = '/home/liu/projects/git-demo-admittance/fig3_3_pose_pipeline.png'
    plt.savefig(path, bbox_inches='tight')
    plt.close()
    print('Generated:', path)

if __name__ == '__main__':
    create_fig1_bottlenecks()
    create_fig2_architecture()
    create_fig3_pose_estimation()
