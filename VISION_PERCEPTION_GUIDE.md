# 视觉感知接口详细开发文档

## 目录

1. [概述](#概述)
2. [视觉感知接口实现源码位置](#视觉感知接口实现源码位置)
3. [信息获取格式详解](#信息获取格式详解)
4. [极坐标系统详解](#极坐标系统详解)
5. [视野范围与遮挡处理](#视野范围与遮挡处理)
6. [解析示例代码](#解析示例代码)
7. [常见问题解答](#常见问题解答)

---

## 概述

RCSSServerMJ 的视觉感知系统是一个基于理想相机模型的视觉传感器管道，能够检测场景中的物体（球、地标、其他机器人）并以极坐标形式返回检测结果。

**关键特性**：
- 基于相机坐标系的极坐标检测
- 视野范围：水平 ±60°，垂直 ±60°
- 默认每 2 个仿真周期生成一次视觉感知
- **不考虑物体遮挡**（透视模式）
- 无数量上限（视野内所有物体都会被检测）

---

## 视觉感知接口实现源码位置

### 核心源码文件

1. **感知数据结构定义**
   - 文件：`src/rcsssmj/sim/perceptions.py`
   - 关键类：
     - `VisionPerception` (第 401-429 行)：视觉感知容器
     - `ObjectDetection` (第 311-353 行)：单点物体检测
     - `AgentDetection` (第 356-398 行)：机器人检测（包含多个身体部位）

2. **视觉感知生成逻辑**
   - 文件：`src/rcsssmj/sim/simulation.py`
   - 关键方法：`generate_perceptions()` (第 309-446 行)
   - 视觉生成核心代码：第 405-443 行

3. **感知编码器**
   - 文件：`src/rcsssmj/server/perception_encoder.py`
   - 将感知对象编码为 S-expression 格式的字节流

4. **协议文档**
   - 文件：`doc/source/user/agent_protocol.rst`
   - 第 380-486 行：视觉感知协议详细说明

---

## 信息获取格式详解

### S-Expression 格式

视觉感知以 S-expression（符号表达式）格式发送：

```lisp
(See <detections>)
```

### 物体检测格式

#### 1. 简单物体（球、地标）

```lisp
(<name> (pol <distance> <azimuth> <elevation>))
```

**参数说明**：
- `name`：物体名称（如 `ball`, `F1L`, `G2R`）
- `distance`：距离（米）
- `azimuth`：方位角/水平角（度，-180° 到 +180°）
- `elevation`：仰角/垂直角（度，-90° 到 +90°）

**示例**：
```lisp
(ball (pol 5.2 -15.3 -2.1))  # 球在距离5.2米，左侧15.3°，下方2.1°
(F1L (pol 10.5 45.0 0.0))    # 左前旗杆
(G1R (pol 8.3 30.0 -5.0))    # 右球门柱
```

#### 2. 机器人检测

```lisp
(P (team <team_name>) (id <player_no>) <body_detections>)
```

**参数说明**：
- `team`：队伍名称
- `id`：球衣号码
- `body_detections`：身体部位检测列表（每个部位都是一个 `ObjectDetection`）

**示例**：
```lisp
(P (team TeamA) (id 2)
   (head-vismarker (pol 3.5 10.0 15.0))
   (lfoot-vismarker (pol 3.6 9.5 -20.0))
   (rfoot-vismarker (pol 3.7 10.5 -18.0)))
```

### 完整消息示例

```lisp
(See (ball (pol 8.51 -0.21 -0.17))
     (G2R (pol 17.55 -3.33 4.31))
     (G1R (pol 17.52 3.27 4.07))
     (F1R (pol 18.52 18.94 1.54))
     (P (team teamRed) (id 1)
        (head-vismarker (pol 16.98 -0.21 3.19))
        (lfoot-vismarker (pol 16.95 -0.51 1.32)))
     (P (team teamBlue) (id 3)
        (head-vismarker (pol 0.18 -33.55 -20.16))))
```

---

## 极坐标系统详解

### 坐标系原点

**极坐标系的原点是机器人头部的相机位置**，而不是脚底或躯干中心。

**源码证据**（`simulation.py` 第 407-412 行）：
```python
# fetch camera sensor site
camera_site = self._mj_data.site(agent.agent_id.prefix + 'camera')

if camera_site is not None:
    # fetch pose of camera site of robot model
    camera_pos = camera_site.xpos.astype(np.float64)
    camera_rot = camera_site.xmat.astype(np.float64).reshape((3, 3))
```

**T1 机器人相机位置**（`resources/robots/T1/robot.xml` 第 97 行）：
```xml
<site name="camera" pos="0.05 0 0.12"/>
```
相机位于头部（H2 body）内，相对头部坐标系偏移 (0.05, 0, 0.12) 米。

### 坐标系定义

**相机坐标系**（右手坐标系）：
- **X 轴**：指向前方（机器人面朝方向）
- **Y 轴**：指向左侧
- **Z 轴**：指向上方

**极坐标转换公式**（`simulation.py` 第 417-421 行）：
```python
# transform local positions into polar coordinates
azimuths = trunc2_vec(np.degrees(np.atan2(local_obj_pos[1], local_obj_pos[0])))
distances = np.linalg.norm(local_obj_pos, axis=0)
elevations = trunc2_vec(np.degrees(np.asin(local_obj_pos[2] / distances)))
distances = trunc2_vec(distances)
```

**角度定义**：
- **方位角（azimuth）**：
  - 0°：正前方（+X 轴）
  - +90°：左侧（+Y 轴）
  - -90°：右侧（-Y 轴）
  - ±180°：正后方（-X 轴）

- **仰角（elevation）**：
  - 0°：水平方向
  - +90°：正上方（+Z 轴）
  - -90°：正下方（-Z 轴）

### 与机器人朝向的关系

**视觉检测完全依赖于机器人当前的朝向**。

**实现细节**（`simulation.py` 第 414-415 行）：
```python
# transform detectable obj positions to camera frame
local_obj_pos = np.matmul(camera_rot.T, obj_pos - camera_pos[:, np.newaxis])
```

这意味着：
1. 物体的极坐标是相对于**相机当前姿态**计算的
2. 如果机器人转头或转身，同一物体的极坐标会改变
3. 方位角 0° 始终指向相机的前方（X 轴方向）

---

## 视野范围与遮挡处理

### 视野范围限制

**硬编码的视野范围**（`simulation.py` 第 426-428 行）：
```python
# check object coordinates for horizontal and vertical view range
half_horizontal_range = 60
half_vertical_range = 60
obj_visibility = (azimuths >= -half_horizontal_range) & (azimuths <= half_horizontal_range) & (elevations >= -half_vertical_range) & (elevations <= half_vertical_range)
```

**视野范围**：
- 水平视野：**±60°**（总共 120°）
- 垂直视野：**±60°**（总共 120°）

**超出视野的物体不会出现在检测结果中**。

### 遮挡处理

**重要结论：当前实现不考虑物体遮挡！**

**源码分析**（`simulation.py` 第 430-441 行）：
```python
# extract simple world object detections
obj_detections: list[PObjectDetection] = [ObjectDetection(obj_markers[i][1], azimuths[i], elevations[i], distances[i]) for i in range(n_world_markers) if obj_visibility[i]]

# extract player object detections
idx = n_world_markers
for player in agents:
    n_player_markers = len(player.markers)
    player_detections = [ObjectDetection(obj_markers[i][1], azimuths[i], elevations[i], distances[i]) for i in range(idx, idx + n_player_markers) if obj_visibility[i]]
    if player_detections:
        obj_detections.append(AgentDetection('P', player.team_name, player.agent_id.player_no, player_detections))

    idx += n_player_markers
```

**关键点**：
1. 所有物体的可见性仅通过 `obj_visibility` 判断（视野角度范围）
2. **没有射线投射或深度测试**
3. **没有遮挡剔除逻辑**
4. 即使物体 A 在物体 B 后面，只要都在视野内，两者都会被检测到

**这是一个"透视"视觉系统**：
- ✅ 优点：简化实现，降低计算成本，适合快速训练
- ❌ 缺点：不符合真实物理，可能导致不现实的行为

### 检测数量上限

**没有硬编码的数量上限**。

**源码证据**：
- 第 343-346 行：收集所有可见标记
- 第 431-441 行：遍历所有标记并添加到检测列表

**实际限制**：
- 理论上限 = 场景中所有可见标记的数量
- 包括：
  - 世界标记（球、旗杆、球门柱等）
  - 所有机器人的身体部位标记

**T1 机器人的可见标记**（`simulation.py` 第 198 行）：
```python
self._world_markers = [(site.name, site.name[:-10]) for site in self._mj_spec.sites if site.name.endswith('-vismarker')]
```
每个机器人有多个 `-vismarker` 标记（头部、脚部等）。

---

## 解析示例代码

### 示例 1：基础解析器（来自 `nn_client.py`）

```python
import re

def parse_sensor_string(s: str) -> dict:
    """
    解析传感器数据字符串（包括视觉感知）
    """
    result = {}
    # 顶层分组: (TAG ...content...)
    top_level_pattern = re.compile(r'\((\w+)((?:\s*\([^()]*\))*)\)')

    for tag, inner in top_level_pattern.findall(s):
        # 查找内部键值对: (key val1 val2 ...)
        items = re.findall(r'\(\s*(\w+)((?:\s+[^()]+)+)\)', inner)
        group = {}
        for key, vals in items:
            tokens = vals.strip().split()
            parsed_vals = []
            for t in tokens:
                try:
                    parsed_vals.append(float(t))
                except ValueError:
                    parsed_vals.append(t)
            # 单值 vs. 列表
            group[key] = parsed_vals[0] if len(parsed_vals) == 1 else parsed_vals

        # 合并到结果中，处理重复标签
        if tag in result:
            if isinstance(result[tag], list):
                result[tag].append(group)
            else:
                result[tag] = [result[tag], group]
        else:
            result[tag] = group

    return result
```

**使用示例**：
```python
perception_msg_str = "(See (ball (pol 5.2 -15.3 -2.1))(F1L (pol 10.5 45.0 0.0)))"
data = parse_sensor_string(perception_msg_str)
# data['See'] 包含解析后的视觉数据
```

### 示例 2：详细视觉解析器（来自 `AGENT_DEVELOPMENT_GUIDE.md`）

```python
import re
import numpy as np

class PerceptionParser:
    @staticmethod
    def parse_vision(perception_str: str) -> dict:
        """解析视觉感知"""
        vision = {'ball': None, 'landmarks': [], 'players': []}

        see_match = re.search(r'\(See (.+?)\)(?=\(|$)', perception_str)
        if not see_match:
            return vision

        see_content = see_match.group(1)

        # 解析球
        ball_match = re.search(r'\(ball \(pol ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\)', see_content)
        if ball_match:
            vision['ball'] = {
                'distance': float(ball_match.group(1)),
                'azimuth': float(ball_match.group(2)),  # 水平角
                'elevation': float(ball_match.group(3))  # 垂直角
            }

        # 解析地标（旗杆、球门柱）
        landmark_pattern = r'\(([FG]\w+) \(pol ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\)'
        for match in re.finditer(landmark_pattern, see_content):
            vision['landmarks'].append({
                'name': match.group(1),
                'distance': float(match.group(2)),
                'azimuth': float(match.group(3)),
                'elevation': float(match.group(4))
            })

        # 解析其他机器人
        player_pattern = r'\(P \(team (\w+)\)\(id (\d+)\)((?:\([^)]+\))+)\)'
        for match in re.finditer(player_pattern, see_content):
            team_name = match.group(1)
            player_id = int(match.group(2))
            body_parts_str = match.group(3)

            # 解析身体部位
            body_parts = []
            part_pattern = r'\(([^)]+) \(pol ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\)'
            for part_match in re.finditer(part_pattern, body_parts_str):
                body_parts.append({
                    'name': part_match.group(1),
                    'distance': float(part_match.group(2)),
                    'azimuth': float(part_match.group(3)),
                    'elevation': float(part_match.group(4))
                })

            vision['players'].append({
                'team': team_name,
                'id': player_id,
                'body_parts': body_parts
            })

        return vision
```

### 示例 3：极坐标转笛卡尔坐标

```python
def polar_to_cartesian(dist, azimuth_deg, elevation_deg):
    """
    将极坐标转换为相机坐标系下的笛卡尔坐标

    参数:
        dist: 距离（米）
        azimuth_deg: 方位角（度）
        elevation_deg: 仰角（度）

    返回:
        np.array([x, y, z]) - 相机坐标系下的位置
    """
    azimuth_rad = np.radians(azimuth_deg)
    elevation_rad = np.radians(elevation_deg)

    # 极坐标转笛卡尔坐标
    x = dist * np.cos(elevation_rad) * np.cos(azimuth_rad)
    y = dist * np.cos(elevation_rad) * np.sin(azimuth_rad)
    z = dist * np.sin(elevation_rad)

    return np.array([x, y, z])
```

### 示例 4：转换到全局坐标系

```python
from scipy.spatial.transform import Rotation as R

def local_to_global(local_pos, camera_pos, camera_quat):
    """
    将相机坐标系下的位置转换为全局坐标系

    参数:
        local_pos: 相机坐标系下的位置 [x, y, z]
        camera_pos: 相机在全局坐标系中的位置 [x, y, z]
        camera_quat: 相机姿态四元数 [qw, qx, qy, qz] (MuJoCo 格式)

    返回:
        全局坐标系下的位置
    """
    # MuJoCo 四元数格式 [qw, qx, qy, qz] -> scipy 格式 [qx, qy, qz, qw]
    rot = R.from_quat([
        camera_quat[1],  # qx
        camera_quat[2],  # qy
        camera_quat[3],  # qz
        camera_quat[0],  # qw
    ])

    # 旋转局部坐标到全局坐标
    global_offset = rot.apply(local_pos)

    # 加上相机位置
    return camera_pos + global_offset
```

---

## 常见问题解答

### Q1: 视觉感知的更新频率是多少？

**A**: 默认每 2 个仿真周期更新一次（`vision_interval=1` 表示每隔 1 个周期）。

源码位置：`simulation.py` 第 40-63 行
```python
def __init__(self, *, vision_interval: int = 1):
    self.vision_interval: Final[int] = vision_interval
```

可以通过修改 `vision_interval` 参数调整更新频率。

### Q2: 如何判断检测到的是队友还是对手？

**A**: 通过 `team` 字段与自己的队名比较：

```python
my_team = "TeamA"
for player in vision['players']:
    if player['team'] == my_team:
        print(f"队友 {player['id']}")
    else:
        print(f"对手 {player['id']}")
```

### Q3: 为什么看不到球？

**可能原因**：
1. 球不在视野范围内（±60°）
2. 球在机器人后方
3. 当前周期不生成视觉感知（每 2 周期一次）

**解决方案**：
- 转动头部关节（`he1`, `he2`）扩大搜索范围
- 转动身体朝向球的方向

### Q4: 如何获取队友的全局位置？

**步骤**：
1. 解析视觉感知，获取队友的极坐标
2. 转换为相机坐标系下的笛卡尔坐标
3. 使用自己的位置和姿态，转换为全局坐标

**完整示例**：
```python
# 1. 解析视觉感知
vision = parse_vision(perception_str)
teammate = vision['players'][0]  # 假设第一个是队友
head_marker = teammate['body_parts'][0]  # 头部标记

# 2. 极坐标转笛卡尔坐标
local_pos = polar_to_cartesian(
    head_marker['distance'],
    head_marker['azimuth'],
    head_marker['elevation']
)

# 3. 转换到全局坐标
# 需要从感知中获取自己的位置和姿态
my_pos = perception['position']  # (pos (n torso_pos) (p x y z))
my_quat = perception['orientation']  # (quat (n torso) (q qw qx qy qz))

teammate_global_pos = local_to_global(local_pos, my_pos, my_quat)
```

### Q5: 视觉感知有噪声吗？

**A**: 当前实现**没有噪声模型**，但数值被截断：
- 距离和角度：截断到 2 位小数（`trunc2_vec`）
- 源码位置：`simulation.py` 第 418-421 行

未来可能在第 423 行添加噪声：
```python
# TODO: Apply sensor noise
```

### Q6: 如何实现基于视觉的协作？

**策略**：
1. **位置共享**：每个机器人维护队友位置的世界模型
2. **角色分配**：根据相对位置分配角色（如最近的追球）
3. **传球决策**：计算队友位置，选择最佳传球目标

**示例**：
```python
class WorldModel:
    def __init__(self):
        self.teammates = {}  # {player_id: global_pos}

    def update_teammates(self, vision, my_pos, my_quat):
        for player in vision['players']:
            if player['team'] == self.my_team:
                # 计算队友全局位置
                if player['body_parts']:
                    marker = player['body_parts'][0]
                    local_pos = polar_to_cartesian(
                        marker['distance'],
                        marker['azimuth'],
                        marker['elevation']
                    )
                    global_pos = local_to_global(local_pos, my_pos, my_quat)
                    self.teammates[player['id']] = global_pos
```

### Q7: 机器人身体部位标记有哪些？

**A**: 取决于机器人模型的 XML 定义。

**T1 机器人示例**（`resources/robots/T1/robot.xml`）：
- `head-vismarker`：头部标记
- `lfoot-vismarker`：左脚标记
- `rfoot-vismarker`：右脚标记
- 其他可能的标记（需查看完整 XML）

查找方法：
```bash
grep "vismarker" src/rcsssmj/resources/robots/T1/robot.xml
```

### Q8: 如何调试视觉感知？

**方法 1：打印原始消息**
```python
perception_msg_str = perception_msg.decode()
print(perception_msg_str)
```

**方法 2：可视化检测结果**
```python
import matplotlib.pyplot as plt

def visualize_vision(vision):
    fig, ax = plt.subplots(subplot_kw={'projection': 'polar'})

    # 绘制球
    if vision['ball']:
        azimuth_rad = np.radians(vision['ball']['azimuth'])
        ax.plot(azimuth_rad, vision['ball']['distance'], 'ro', markersize=10, label='Ball')

    # 绘制地标
    for landmark in vision['landmarks']:
        azimuth_rad = np.radians(landmark['azimuth'])
        ax.plot(azimuth_rad, landmark['distance'], 'bs', markersize=5)

    # 绘制机器人
    for player in vision['players']:
        for part in player['body_parts']:
            azimuth_rad = np.radians(part['azimuth'])
            color = 'g' if player['team'] == my_team else 'r'
            ax.plot(azimuth_rad, part['distance'], color+'x', markersize=8)

    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 20)
    plt.legend()
    plt.show()
```

---

## 总结

RCSSServerMJ 的视觉感知系统提供了一个简化但功能完整的视觉接口：

**优点**：
- ✅ 简单易用的极坐标格式
- ✅ 无数量限制，视野内所有物体都可见
- ✅ 不考虑遮挡，降低计算复杂度
- ✅ 适合快速原型开发和强化学习训练

**限制**：
- ❌ 不符合真实物理（透视视觉）
- ❌ 固定视野范围（±60°）
- ❌ 无噪声模型（当前版本）
- ❌ 每 2 周期更新一次（可能导致延迟）

**适用场景**：
- 机器人足球仿真
- 多智能体协作研究
- 强化学习策略训练
- 视觉导航算法开发

**不适用场景**：
- 需要真实遮挡效果的场景
- 需要高频视觉更新的任务
- 需要传感器噪声建模的研究

---

**文档版本**: 1.0
**最后更新**: 2026-03-02
**基于代码版本**: rcssservermj (当前 master 分支)
