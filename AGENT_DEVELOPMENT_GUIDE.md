# RCSSServerMJ Agent 开发完整教程

本教程将指导你从零开始开发一个完整的足球仿真 Agent，实现环境感知、速度规划、上层策略等功能。

---

## 目录

1. [平台接口概览](#1-平台接口概览)
2. [通信协议详解](#2-通信协议详解)
3. [Agent 开发步骤](#3-agent-开发步骤)
4. [完整示例代码](#4-完整示例代码)
5. [进阶开发指南](#5-进阶开发指南)

---

## 1. 平台接口概览

### 1.1 感知接口（Perception）

服务器每个仿真周期会向 Agent 发送以下感知数据（S-expression 格式）：

| 感知类型 | 格式 | 说明 |
|---------|------|------|
| **时间** | `(time (now <t>))` | 当前仿真时间（秒） |
| **比赛状态** | `(GS (t <play_time>)(pm <play_mode>)(tl <team_left>)(tr <team_right>)(sl <score_left>)(sr <score_right>))` | 比赛时间、play mode、队名、比分 |
| **关节状态** | `(HJ (n <joint_name>)(ax <angle_deg>)(vx <velocity_deg_s>))*` | 所有关节的角度（度）和角速度（度/秒） |
| **陀螺仪** | `(GYR (n torso)(rt <rx> <ry> <rz>))` | 躯干角速度（度/秒） |
| **加速度计** | `(ACC (n torso)(a <ax> <ay> <az>))` | 躯干线加速度（m/s²） |
| **姿态** | `(quat (n torso)(q <qw> <qx> <qy> <qz>))` | 躯干姿态四元数 |
| **位置** | `(pos (n torso_pos)(p <x> <y> <z>))` | 躯干绝对位置（米，ground-truth） |
| **触觉** | `(TCH n <sensor_name> val <0/1>)` | 接触传感器状态 |
| **视觉** | `(See (<obj> (pol <dist> <h_angle> <v_angle>))*)` | 视野内物体的极坐标检测 |

#### 视觉感知详解

视觉感知以极坐标形式给出，视野范围：水平 ±60°，垂直 ±60°

```
(See
  (ball (pol 5.2 -15.3 -2.1))                    # 球：距离5.2m，水平角-15.3°，仰角-2.1°
  (F1L (pol 10.5 45.0 0.0))                      # 左前旗杆
  (G1L (pol 8.3 30.0 -5.0))                      # 左球门柱
  (P (team TeamA)(id 2)                          # 队友2号
     (head (pol 3.5 10.0 15.0))                  # 头部检测
     (lfoot-vismarker (pol 3.6 9.5 -20.0)))      # 左脚标记
)
```

**可检测物体**：
- `ball` — 足球
- `F1L`, `F2L`, `F1R`, `F2R` — 四角旗杆
- `G1L`, `G2L`, `G1R`, `G2R` — 球门柱
- `P` — 其他球员（包含队名、球衣号、身体部位）

### 1.2 动作接口（Action）

Agent 可以发送以下动作命令：

| 动作类型 | 格式 | 说明 |
|---------|------|------|
| **关节控制** | `(<joint_name> <q_deg> <dq_deg> <kp> <kd> <tau>)` | PD位置控制 + 额外力矩 |
| **传送** | `(beam <x> <y> <theta>)` | 传送到指定位置（仅特定 play mode 有效） |
| **语音** | `(say <message>)` | 广播消息（尚未实现） |

#### 关节控制详解

```
(lle1 -23.5 0.0 25.0 0.6 0.0)
```

参数说明：
- `lle1` — 关节名称（左腿髋关节俯仰）
- `-23.5` — 目标角度 q（度）
- `0.0` — 目标角速度 dq（度/秒）
- `25.0` — 比例增益 kp
- `0.6` — 微分增益 kd
- `0.0` — 额外力矩 tau（N·m）

**控制公式**：
```
applied_torque = kp * (q - q_current) + kd * (dq - dq_current) + tau
```

**T1 机器人关节列表**（23个）：
```python
JOINTS = [
    'he1', 'he2',                    # 头部：偏航、俯仰
    'lae1', 'lae2', 'lae3', 'lae4',  # 左臂：肩俯仰、肩侧摆、肘俯仰、肘偏航
    'rae1', 'rae2', 'rae3', 'rae4',  # 右臂
    'te1',                           # 腰部偏航
    'lle1', 'lle2', 'lle3', 'lle4', 'lle5', 'lle6',  # 左腿：髋俯仰、髋侧摆、髋偏航、膝、踝俯仰、踝侧摆
    'rle1', 'rle2', 'rle3', 'rle4', 'rle5', 'rle6',  # 右腿
]
```

### 1.3 Play Mode（比赛模式）

| Play Mode | 说明 | 可用动作 |
|-----------|------|---------|
| `BeforeKickOff` | 开球前 | beam, 关节控制 |
| `KickOff_Left` / `KickOff_Right` | 开球（某队专属球权） | 关节控制 |
| `PlayOn` | 正常比赛 | 关节控制 |
| `Goal_Left` / `Goal_Right` | 进球后暂停 | 无 |
| `KickIn_Left` / `KickIn_Right` | 界外球 | 关节控制 |
| `corner_kick_left` / `corner_kick_right` | 角球 | 关节控制 |
| `goal_kick_left` / `goal_kick_right` | 球门球 | 关节控制 |
| `GameOver` | 比赛结束 | 无 |

---

## 2. 通信协议详解

### 2.1 连接流程

```
1. Agent 连接到服务器 TCP 端口（默认 60000）
2. Agent 发送初始化消息：(init <model> <team> <player_no>)
3. 服务器分配 Agent ID，开始发送感知数据
4. Agent 每次收到感知后，发送动作消息
5. 循环步骤 4 直到断开连接
```

### 2.2 消息格式

所有消息采用**长度前缀 + 内容**的格式：

```
[4 bytes: message_length (big-endian)] + [message_content (UTF-8)]
```

**Python 实现**：

```python
# 发送消息
def send_message(sock, msg: str):
    msg_bytes = msg.encode('utf-8')
    length_prefix = len(msg_bytes).to_bytes(4, byteorder='big')
    sock.send(length_prefix + msg_bytes)

# 接收消息
def receive_message(sock) -> str:
    # 读取长度前缀
    length_bytes = sock.recv(4)
    msg_length = int.from_bytes(length_bytes, byteorder='big')

    # 读取消息内容
    msg_bytes = sock.recv(msg_length)
    return msg_bytes.decode('utf-8')
```

### 2.3 初始化消息

```python
init_msg = f"(init T1 MyTeam 1)"  # 模型名、队名、球衣号
send_message(sock, init_msg)
```

### 2.4 动作消息

多个动作可以拼接在一起发送：

```python
action_msg = "(lle1 -20.0 0.0 25.0 0.6 0.0)(lle2 5.0 0.0 25.0 0.6 0.0)(beam 5.0 2.0 0.0)"
send_message(sock, action_msg)
```

---

## 3. Agent 开发步骤

### 3.1 架构设计

一个完整的 Agent 应包含以下模块：

```
┌─────────────────────────────────────────┐
│           Agent Architecture            │
├─────────────────────────────────────────┤
│  1. Communication Layer (通信层)        │
│     - TCP socket 管理                   │
│     - 消息收发                          │
├─────────────────────────────────────────┤
│  2. Perception Parser (感知解析层)      │
│     - S-expression 解析                 │
│     - 数据结构化                        │
├─────────────────────────────────────────┤
│  3. World Model (世界模型层)            │
│     - 自身状态估计                      │
│     - 球位置估计                        │
│     - 队友/对手位置估计                 │
├─────────────────────────────────────────┤
│  4. Decision Making (决策层)            │
│     - 角色分配（守门员/后卫/前锋）      │
│     - 行为选择（追球/传球/射门）        │
├─────────────────────────────────────────┤
│  5. Motion Control (运动控制层)         │
│     - 行走控制                          │
│     - 踢球动作                          │
│     - 起身动作                          │
├─────────────────────────────────────────┤
│  6. Low-level Controller (底层控制器)   │
│     - 关节 PD 控制                      │
│     - 动作插值                          │
└─────────────────────────────────────────┘
```

### 3.2 开发步骤

#### 步骤 1：建立通信连接

```python
import socket

class SoccerAgent:
    def __init__(self, host, port, team, player_no, model='T1'):
        self.host = host
        self.port = port
        self.team = team
        self.player_no = player_no
        self.model = model

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def connect(self):
        self.sock.connect((self.host, self.port))
        init_msg = f"(init {self.model} {self.team} {self.player_no})"
        self.send_message(init_msg)
```

#### 步骤 2：解析感知数据

```python
import re
import numpy as np

class PerceptionParser:
    @staticmethod
    def parse(perception_str: str) -> dict:
        """解析 S-expression 格式的感知数据"""
        data = {}

        # 解析时间
        time_match = re.search(r'\(time \(now ([\d.]+)\)\)', perception_str)
        if time_match:
            data['time'] = float(time_match.group(1))

        # 解析比赛状态
        gs_match = re.search(r'\(GS \(t ([\d.]+)\)\(pm (\w+)\)', perception_str)
        if gs_match:
            data['play_time'] = float(gs_match.group(1))
            data['play_mode'] = gs_match.group(2)

        # 解析关节状态
        joint_pattern = r'\(HJ \(n (\w+)\)\(ax ([-\d.]+)\)\(vx ([-\d.]+)\)\)'
        joints = {}
        for match in re.finditer(joint_pattern, perception_str):
            name = match.group(1)
            joints[name] = {
                'angle': float(match.group(2)),
                'velocity': float(match.group(3))
            }
        data['joints'] = joints

        # 解析陀螺仪
        gyr_match = re.search(r'\(GYR \(n \w+\)\(rt ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\)', perception_str)
        if gyr_match:
            data['gyro'] = np.array([float(gyr_match.group(i)) for i in range(1, 4)])

        # 解析姿态
        quat_match = re.search(r'\(quat \(n \w+\)\(q ([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\)', perception_str)
        if quat_match:
            data['orientation'] = np.array([float(quat_match.group(i)) for i in range(1, 5)])

        # 解析位置
        pos_match = re.search(r'\(pos \(n \w+\)\(p ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\)', perception_str)
        if pos_match:
            data['position'] = np.array([float(pos_match.group(i)) for i in range(1, 4)])

        # 解析视觉
        data['vision'] = PerceptionParser.parse_vision(perception_str)

        return data

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
                'h_angle': float(ball_match.group(2)),
                'v_angle': float(ball_match.group(3))
            }

        # 解析地标（旗杆、球门柱）
        landmark_pattern = r'\(([FG]\w+) \(pol ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\)'
        for match in re.finditer(landmark_pattern, see_content):
            vision['landmarks'].append({
                'name': match.group(1),
                'distance': float(match.group(2)),
                'h_angle': float(match.group(3)),
                'v_angle': float(match.group(4))
            })

        return vision
```

#### 步骤 3：构建世界模型

```python
from scipy.spatial.transform import Rotation as R

class WorldModel:
    def __init__(self):
        self.my_pos = np.zeros(3)
        self.my_orientation = np.array([1, 0, 0, 0])  # qw, qx, qy, qz
        self.ball_pos = None
        self.ball_relative = None

    def update(self, perception: dict):
        """更新世界模型"""
        # 更新自身位置
        if 'position' in perception:
            self.my_pos = perception['position']

        # 更新自身姿态
        if 'orientation' in perception:
            self.my_orientation = perception['orientation']

        # 更新球的相对位置
        if perception['vision']['ball']:
            ball_data = perception['vision']['ball']
            self.ball_relative = self.polar_to_cartesian(
                ball_data['distance'],
                ball_data['h_angle'],
                ball_data['v_angle']
            )

            # 转换到全局坐标系
            self.ball_pos = self.local_to_global(self.ball_relative)

    def polar_to_cartesian(self, dist, h_angle, v_angle):
        """极坐标转笛卡尔坐标（相机坐标系）"""
        h_rad = np.radians(h_angle)
        v_rad = np.radians(v_angle)

        x = dist * np.cos(v_rad) * np.cos(h_rad)
        y = dist * np.cos(v_rad) * np.sin(h_rad)
        z = dist * np.sin(v_rad)

        return np.array([x, y, z])

    def local_to_global(self, local_pos):
        """局部坐标转全局坐标"""
        # 使用姿态四元数旋转
        rot = R.from_quat([
            self.my_orientation[1],  # qx
            self.my_orientation[2],  # qy
            self.my_orientation[3],  # qz
            self.my_orientation[0],  # qw
        ])
        global_offset = rot.apply(local_pos)
        return self.my_pos + global_offset
```

#### 步骤 4：决策层设计

```python
class DecisionMaker:
    def __init__(self, player_no):
        self.player_no = player_no
        self.role = 'goalkeeper' if player_no == 1 else 'field_player'

    def decide(self, world_model: WorldModel, perception: dict) -> str:
        """决策行为"""
        play_mode = perception.get('play_mode', 'BeforeKickOff')

        # 开球前传送到初始位置
        if play_mode == 'BeforeKickOff':
            return 'beam_to_start'

        # 比赛中
        if play_mode == 'PlayOn':
            if world_model.ball_relative is not None:
                ball_dist = np.linalg.norm(world_model.ball_relative[:2])

                if ball_dist < 0.5:  # 球在脚下
                    return 'kick_ball'
                elif ball_dist < 5.0:  # 球在附近
                    return 'chase_ball'
                else:
                    return 'position'
            else:
                return 'search_ball'

        return 'stand'
```

#### 步骤 5：运动控制层

```python
class MotionController:
    def __init__(self):
        self.joint_names = [
            'he1', 'he2', 'lae1', 'lae2', 'lae3', 'lae4',
            'rae1', 'rae2', 'rae3', 'rae4', 'te1',
            'lle1', 'lle2', 'lle3', 'lle4', 'lle5', 'lle6',
            'rle1', 'rle2', 'rle3', 'rle4', 'rle5', 'rle6'
        ]
        self.kp = 25.0
        self.kd = 0.6

    def walk_forward(self, speed=0.5) -> str:
        """前进行走（需要神经网络策略）"""
        # 这里简化为站立姿态
        return self.stand()

    def turn_to_ball(self, ball_angle) -> str:
        """转向球"""
        # 调整腰部关节
        te1_angle = np.clip(ball_angle * 0.5, -30, 30)
        return f"(te1 {te1_angle} 0.0 {self.kp} {self.kd} 0.0)"

    def stand(self) -> str:
        """站立姿态"""
        actions = []
        standing_pose = {
            'he1': 0, 'he2': 0,
            'lae1': 0, 'lae2': 20, 'lae3': 0, 'lae4': -10,
            'rae1': 0, 'rae2': -20, 'rae3': 0, 'rae4': 10,
            'te1': 0,
            'lle1': -10, 'lle2': 0, 'lle3': 0, 'lle4': 20, 'lle5': -10, 'lle6': 0,
            'rle1': -10, 'rle2': 0, 'rle3': 0, 'rle4': 20, 'rle5': -10, 'rle6': 0,
        }

        for joint, angle in standing_pose.items():
            actions.append(f"({joint} {angle} 0.0 {self.kp} {self.kd} 0.0)")

        return ''.join(actions)

    def beam(self, x, y, theta) -> str:
        """传送"""
        return f"(beam {x} {y} {theta})"
```

#### 步骤 6：整合主循环

```python
class SoccerAgent:
    def __init__(self, host, port, team, player_no, model='T1'):
        # ... (前面的初始化代码)
        self.parser = PerceptionParser()
        self.world_model = WorldModel()
        self.decision_maker = DecisionMaker(player_no)
        self.motion_controller = MotionController()

    def run(self):
        """主循环"""
        self.connect()

        while True:
            try:
                # 1. 接收感知
                perception_str = self.receive_message()

                # 2. 解析感知
                perception = self.parser.parse(perception_str)

                # 3. 更新世界模型
                self.world_model.update(perception)

                # 4. 决策
                behavior = self.decision_maker.decide(self.world_model, perception)

                # 5. 生成动作
                action_msg = self.generate_action(behavior)

                # 6. 发送动作
                self.send_message(action_msg)

            except Exception as e:
                print(f"Error: {e}")
                break

        self.sock.close()

    def generate_action(self, behavior: str) -> str:
        """根据行为生成动作消息"""
        if behavior == 'beam_to_start':
            positions = {1: (5, 0, 0), 2: (3, 2, 0), 3: (3, -2, 0)}
            pos = positions.get(self.player_no, (0, 0, 0))
            return self.motion_controller.beam(*pos)

        elif behavior == 'chase_ball':
            if self.world_model.ball_relative is not None:
                ball_angle = np.degrees(np.arctan2(
                    self.world_model.ball_relative[1],
                    self.world_model.ball_relative[0]
                ))
                return self.motion_controller.turn_to_ball(ball_angle) + \
                       self.motion_controller.walk_forward()
            return self.motion_controller.stand()

        else:
            return self.motion_controller.stand()
```

---

## 4. 完整示例代码

完整的可运行示例见 `example/client/mujoco_client.py` 和 `example/nn_client/nn_client.py`。

**启动服务器**：
```bash
rcssservermj -b hl_adult -f hl_adult_2020
```

**运行 Agent**：
```bash
python my_agent.py -s 127.0.0.1 -p 60000 -t MyTeam -n 1 -r T1
```

---

## 5. 进阶开发指南

### 5.1 使用神经网络策略

参考 `example/nn_client/nn_client.py`，使用 PyTorch 加载预训练的行走策略：

```python
import torch
import torch.nn as nn

class WalkingPolicy(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(78, 512)  # 输入：关节状态+陀螺仪+目标速度+重力
        self.fc2 = nn.Linear(512, 256)
        self.fc3 = nn.Linear(256, 128)
        self.fc4 = nn.Linear(128, 23)  # 输出：23个关节目标角度

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        x = torch.relu(self.fc3(x))
        return self.fc4(x)

# 加载模型
policy = WalkingPolicy()
policy.load_state_dict(torch.load('locomotion_nn.pth'))
policy.eval()

# 使用模型
observation = np.concatenate([joint_states, gyro, goal_velocity, gravity])
with torch.no_grad():
    action = policy(torch.tensor(observation, dtype=torch.float32)).numpy()
```

### 5.2 多 Agent 协作

使用 `(say <message>)` 动作（待实现）或通过外部通信（如 Redis、ROS）实现队内通信。

### 5.3 训练强化学习策略

1. 使用 `--sync --no-realtime` 模式启动服务器（训练模式）
2. 收集感知-动作数据
3. 使用 PPO/SAC 等算法训练策略网络
4. 保存模型并在比赛中加载

### 5.4 调试技巧

- 使用 `print(perception_str)` 查看原始感知数据
- 在服务器端查看 `console.log` 日志
- 使用 MuJoCo 可视化窗口观察机器人行为
- 降低仿真速度：`rcssservermj --no-realtime`

### 5.5 性能优化

- 使用 `numpy` 向量化计算
- 缓存不变的计算结果（如关节名称列表）
- 使用 C++ 扩展加速关键路径
- 多线程处理感知和决策

---

## 附录

### A. 常用坐标系

- **全局坐标系**：X 轴指向右球门，Y 轴指向左侧，Z 轴向上
- **机器人坐标系**：X 轴向前，Y 轴向左，Z 轴向上
- **相机坐标系**：X 轴向前，Y 轴向左，Z 轴向上

### B. 参考资源

- 官方文档：https://robocup-sim.gitlab.io/rcssservermj/
- 示例代码：`example/client/` 和 `example/nn_client/`
- MuJoCo 文档：https://mujoco.readthedocs.io/

### C. 常见问题

**Q: 机器人一连接就倒地？**
A: 检查 PD 增益是否合理（推荐 kp=25, kd=0.6），确保发送了站立姿态的关节角度。

**Q: 看不到球？**
A: 球可能在视野外（±60°），或者被其他物体遮挡。使用头部关节转动扩大视野。

**Q: 如何实现踢球动作？**
A: 需要设计腿部关节的摆动轨迹，或使用强化学习训练踢球策略。

**Q: 如何加速训练？**
A: 使用 `--sync --no-realtime` 模式，并行运行多个仿真实例。

---

**祝开发顺利！如有问题请提交 Issue：https://gitlab.com/robocup-sim/rcssservermj/-/issues**
