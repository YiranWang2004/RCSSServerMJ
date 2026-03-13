# PiPlus 机器人集成总结

## 修改完成清单

### 1. rcssservermj 仿真平台
✅ **无需修改** - PiPlus 机器人 XML 已存在于 `src/rcsssmj/resources/robots/PiPlus/robot.xml`

### 2. BahiaRT 队伍程序

#### 已修改文件:

1. **`mujococodebase/robot.py`**
   - 添加了 `PiPlus` 类
   - 定义了 22 个关节 (包括 2 个头部关节)
   - 关节顺序与 XML 文件一致

2. **`mujococodebase/agent.py`**
   - 添加 `robot_type` 参数
   - 支持动态选择 T1 或 PiPlus 机器人

3. **`run_player.py`**
   - 添加 `-r/--robot` 命令行参数
   - 可选值: `T1` (默认) 或 `PiPlus`

4. **`mujococodebase/skills/walk/walk_piplus.py`** (新建)
   - 实现 PiPlus 专用行走技能
   - 使用 `pi_plus_amp_1201_policy_1.onnx` 模型
   - **严格按照 AMP 策略观测空间构建**

5. **`mujococodebase/skills/skills_manager.py`**
   - 根据机器人类型自动加载对应技能
   - PiPlus 使用 `WalkPiPlus`, T1 使用 `Walk`

6. **`mujococodebase/decision_maker.py`**
   - 根据机器人类型使用正确的行走技能名称

## 观测空间详细说明

### 单帧观测 (numSingleObs = 69)

按照 AMP 策略源码的严格顺序:

| 顺序 | 内容 | 维数 | 缩放因子 |
|------|------|------|----------|
| 1 | 基座角速度 base_ang_vel | 3 | × 0.25 (robotAngleVelScale_) |
| 2 | 投影重力向量 projected_gravity | 3 | × 1.0 |
| 3 | 指令速度 [vx, vy, dyaw] | 3 | × 1.0 |
| 4 | 关节位置 q (相对于 nominal) | 20 | × 1.0 (robotLinePoseScale_) |
| 5 | 关节速度 dq | 20 | × 0.05 (robotLineVelScale_) |
| 6 | 上次动作 previous_action | 20 | × 1.0 |

**总计**: 3 + 3 + 3 + 20 + 20 + 20 = **69 维**

### Frame Stack (frameStack = 5)

- 历史缓冲区维护最近 5 帧观测
- FIFO 顺序: 最旧帧在前,最新帧在后
- 网络输入维数: 69 × 5 = **345 维**

### 关键点

1. **rlDofs = 20**: 只控制 20 个关节,排除 2 个头部关节
   - 头部关节在行走时保持在 nominal position (0)

2. **关节顺序**:
   ```
   PiPlus 全部 22 关节:
   [0] head_yaw          (不控制)
   [1] head_pitch        (不控制)
   [2] l_hip_pitch       (控制)
   [3] l_hip_roll        (控制)
   ...
   [21] r_wrist_joint    (控制)
   ```

3. **动作输出**:
   - 网络输出 20 维动作
   - 缩放因子: × 0.25 (actionScale_)
   - 应用到 nominal position: `target = nominal + action × 0.25`

## 使用方法

### 启动 PiPlus 机器人

```bash
cd BahiaRT-MujOCo-base
python run_player.py -r PiPlus -t TeamName -n 1
```

### 启动 T1 机器人 (默认)

```bash
python run_player.py -t TeamName -n 1
```

### 完整参数示例

```bash
python run_player.py \
  --robot PiPlus \
  --team MyTeam \
  --number 1 \
  --host 127.0.0.1 \
  --port 60000 \
  --field fifa
```

## 参数调优建议

如果机器人行为不理想,可以调整以下参数 (在 `walk_piplus.py` 中):

### 1. 观测空间缩放因子 (第 30-32 行)
```python
self.robot_angle_vel_scale = 0.25  # 基座角速度缩放
self.robot_line_pose_scale = 1.0   # 关节位置缩放
self.robot_line_vel_scale = 0.05   # 关节速度缩放
```

### 2. 动作缩放因子 (第 35 行)
```python
self.action_scale = 0.25  # 动作输出缩放
```

### 3. PD 控制参数 (第 146-147, 151-156 行)
```python
kp=25   # 比例增益
kd=0.6  # 微分增益
```

## 验证步骤

1. **检查 ONNX 模型**:
   ```bash
   python inspect_onnx.py
   ```
   确认:
   - 输入维数 = 345 (69 × 5)
   - 输出维数 = 20

2. **启动仿真服务器**

3. **启动 PiPlus 机器人**:
   ```bash
   cd BahiaRT-MujOCo-base
   python run_player.py -r PiPlus -t Test -n 1
   ```

4. **观察机器人行为**:
   - 机器人应该能够站立
   - 能够响应球的位置移动
   - 行走动作应该流畅

## 故障排查

### 问题: 机器人倒地
- 检查 PD 参数是否过小
- 检查动作缩放因子是否合适
- 确认观测空间缩放因子与训练环境一致

### 问题: 机器人不动
- 确认 ONNX 模型路径正确
- 检查网络输入维数是否为 345
- 查看控制台是否有错误信息

### 问题: 动作抖动
- 降低 kp 增益
- 增加 kd 增益
- 检查观测空间是否正确 clip

## 技术细节

### Frame Stack 实现

```python
# 初始化历史缓冲区 (5 帧 × 69 维)
self.hist_obs = np.zeros((5, 69))

# 每步更新:
# 1. 构建当前帧观测 (69 维)
single_obs = np.concatenate([...])

# 2. 更新历史缓冲区 (FIFO)
self.hist_obs = np.roll(self.hist_obs, -1, axis=0)
self.hist_obs[-1] = single_obs

# 3. 展平为网络输入 (345 维)
final_obs_input = self.hist_obs.flatten()
```

### 关节映射

```python
# 从 robot.motor_positions 获取全部 22 个关节
all_joint_positions = np.array(list(robot.motor_positions.values()))

# 提取控制关节 (跳过前 2 个头部关节)
controlled_joint_positions = all_joint_positions[2:]  # 20 个

# 发送控制命令时:
# - 头部关节 [0:2]: 保持 0
# - 控制关节 [2:22]: 使用网络输出
```

## 文件结构

```
BahiaRT-MujOCo-base/
├── mujococodebase/
│   ├── robot.py                    # 添加了 PiPlus 类
│   ├── agent.py                    # 添加了 robot_type 参数
│   ├── decision_maker.py           # 根据机器人类型选择技能
│   └── skills/
│       ├── skills_manager.py       # 根据机器人类型加载技能
│       └── walk/
│           ├── walk.py             # T1 行走技能
│           └── walk_piplus.py      # PiPlus 行走技能 (新建)
├── run_player.py                   # 添加了 -r/--robot 参数
└── pi_plus_amp_1201_policy_1.onnx  # PiPlus 行走策略模型
```

## 总结

所有修改已完成,PiPlus 机器人已成功集成到 BahiaRT 队伍程序中。观测空间严格按照 AMP 策略源码构建,包括:
- 正确的观测顺序
- 正确的缩放因子
- 5 帧 frame stack
- 20 个控制关节 (排除头部)
- 总输入维数 345

现在可以使用 `python run_player.py -r PiPlus` 启动 PiPlus 机器人进行比赛!
