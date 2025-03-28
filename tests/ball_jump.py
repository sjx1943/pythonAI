import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle, RegularPolygon

# 设置参数
gravity = 0.5  # 重力加速度
bounce = 0.8  # 弹性系数(0-1)
hexagon_radius = 5  # 六边形半径
ball_radius = 0.3  # 小球半径

# 初始化小球位置和速度
ball_pos = np.array([0.0, 0.0])  # 初始位置(中心)
ball_vel = np.array([2.0, 3.0])  # 初始速度

# 创建图形
fig, ax = plt.subplots(figsize=(8, 8))
ax.set_xlim(-hexagon_radius * 1.2, hexagon_radius * 1.2)
ax.set_ylim(-hexagon_radius * 1.2, hexagon_radius * 1.2)
ax.set_aspect('equal')
ax.axis('off')  # 隐藏坐标轴

# 创建六边形
hexagon = RegularPolygon((0, 0), numVertices=6, radius=hexagon_radius,
                         orientation=np.pi / 6, fc='none', ec='black', lw=2)
ax.add_patch(hexagon)

# 创建小球
ball = Circle(ball_pos, ball_radius, fc='red', ec='black')
ax.add_patch(ball)


# 计算点到六边形边的距离
def distance_to_hexagon(point):
    angles = np.linspace(0, 2 * np.pi, 7)[:-1] + np.pi / 6
    closest_dist = float('inf')
    for angle in angles:
        # 六边形边的法向量
        normal = np.array([np.cos(angle), np.sin(angle)])
        dist = hexagon_radius - np.dot(point, normal)
        if dist < closest_dist:
            closest_dist = dist
    return closest_dist


# 动画更新函数
def update(frame):
    global ball_pos, ball_vel

    # 应用重力
    ball_vel[1] -= gravity * 0.1

    # 临时更新位置
    new_pos = ball_pos + ball_vel * 0.1

    # 检查是否碰撞六边形边界
    dist = distance_to_hexagon(new_pos)
    if dist < ball_radius:
        # 计算碰撞点的法向量
        angle = np.arctan2(new_pos[1], new_pos[0])
        sector = np.floor((angle + np.pi / 6) / (np.pi / 3)) % 6
        normal_angle = sector * np.pi / 3 + np.pi / 6
        normal = np.array([np.cos(normal_angle), np.sin(normal_angle)])

        # 计算反弹后的速度
        vel_parallel = np.dot(ball_vel, normal) * normal
        vel_perpendicular = ball_vel - vel_parallel
        ball_vel = vel_perpendicular - vel_parallel * bounce

        # 调整位置防止穿透
        correction = (ball_radius - dist) * normal
        new_pos += correction

    # 更新位置
    ball_pos = new_pos
    ball.center = ball_pos

    return ball,


# 创建动画
ani = FuncAnimation(fig, update, frames=200, interval=50, blit=True)

# 保存为GIF
ani.save('hexagon_bounce.gif', writer='pillow', fps=20, dpi=80)

plt.close()
print("六边形内弹跳小球动画已保存为 hexagon_bounce.gif")

