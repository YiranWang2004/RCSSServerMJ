# PiPlus 机器人关节顺序说明

## XML文件中的可控制关节 (共20个)

PiPlus robot.xml 中定义的 actuator 顺序如下 (手腕关节已注释):

```
索引  关节名称                    中文名称        部位
----  -------------------------  -------------  --------
0     l_hip_pitch_joint          左髋俯仰        左腿
1     l_hip_roll_joint           左髋侧摆        左腿
2     l_thigh_joint              左大腿旋转      左腿
3     l_calf_joint               左小腿          左腿
4     l_ankle_pitch_joint        左踝俯仰        左腿
5     l_ankle_roll_joint         左踝侧摆        左腿
6     r_hip_pitch_joint          右髋俯仰        右腿
7     r_hip_roll_joint           右髋侧摆        右腿
8     r_thigh_joint              右大腿旋转      右腿
9     r_calf_joint               右小腿          右腿
10    r_ankle_pitch_joint        右踝俯仰        右腿
11    r_ankle_roll_joint         右踝侧摆        右腿
12    l_shoulder_pitch_joint     左肩俯仰        左臂
13    l_shoulder_roll_joint      左肩侧摆        左臂
14    l_upper_arm_joint          左上臂旋转      左臂
15    l_elbow_joint              左肘            左臂
16    r_shoulder_pitch_joint     右肩俯仰        右臂
17    r_shoulder_roll_joint      右肩侧摆        右臂
18    r_upper_arm_joint          右上臂旋转      右臂
19    r_elbow_joint              右肘            右臂
```

## 重要说明

### 1. 手腕关节已在XML中注释
```xml
<!-- <motor name="l_wrist_joint" joint="l_wrist_joint" ... /> -->
<!-- <motor name="r_wrist_joint" joint="r_wrist_joint" ... /> -->
```

### 2. rlDofs = 20 完全匹配
XML中只定义了20个actuator,正好对应AMP策略的rlDofs=20。
**所有20个关节都被控制,无需排除任何关节。**

### 3. 关节分组
```
0-5:   左腿 (6个关节)
6-11:  右腿 (6个关节)
12-15: 左臂 (4个关节,不含手腕)
16-19: 右臂 (4个关节,不含手腕)
```

## 观测空间构建

### 单帧观测 (69维)

| 顺序 | 内容 | 维数 | 来源 |
|------|------|------|------|
| 1 | 基座角速度 | 3 | IMU gyroscope |
| 2 | 投影重力 | 3 | IMU orientation |
| 3 | 指令速度 | 3 | 目标速度命令 |
| 4 | 关节位置 | 20 | 所有20个关节 |
| 5 | 关节速度 | 20 | 所有20个关节 |
| 6 | 上次动作 | 20 | 上一步网络输出 |

### Frame Stack (345维)
- 5帧历史观测
- 69 × 5 = 345
- FIFO顺序: [最旧帧, ..., 最新帧]

## 动作输出

### 网络输出 (20维)
对应20个关节的目标位置增量:
```
[0-5]:   左腿 (6个)
[6-11]:  右腿 (6个)
[12-15]: 左臂 (4个)
[16-19]: 右臂 (4个)
```

### 直接映射到20个关节
```python
for idx in range(20):
    target = nominal + action[idx] * 0.25
    robot.set_motor_target_position(
        robot.ROBOT_MOTORS[idx],
        np.rad2deg(target),
        kp=25,
        kd=0.6
    )
```

## 与robot.py的对应关系

`robot.py` 中 `PiPlus.ROBOT_MOTORS` 的顺序与XML完全一致:

```python
ROBOT_MOTORS = (
    "l_hip_pitch_joint",      # 0  - 左腿
    "l_hip_roll_joint",       # 1
    "l_thigh_joint",          # 2
    "l_calf_joint",           # 3
    "l_ankle_pitch_joint",    # 4
    "l_ankle_roll_joint",     # 5
    "r_hip_pitch_joint",      # 6  - 右腿
    "r_hip_roll_joint",       # 7
    "r_thigh_joint",          # 8
    "r_calf_joint",           # 9
    "r_ankle_pitch_joint",    # 10
    "r_ankle_roll_joint",     # 11
    "l_shoulder_pitch_joint", # 12 - 左臂
    "l_shoulder_roll_joint",  # 13
    "l_upper_arm_joint",      # 14
    "l_elbow_joint",          # 15
    "r_shoulder_pitch_joint", # 16 - 右臂
    "r_shoulder_roll_joint",  # 17
    "r_upper_arm_joint",      # 18
    "r_elbow_joint",          # 19
)
```

## 代码实现要点

### 1. 简化的实现
由于XML只有20个motor,代码非常简洁:
- 直接读取所有20个关节状态
- 网络输出20维动作
- 直接应用到所有20个关节
- **无需任何关节排除逻辑**

### 2. 观测空间构建
```python
# 获取所有20个关节状态
all_joint_positions = np.array(list(robot.motor_positions.values()))  # 20个
all_joint_speeds = np.array(list(robot.motor_speeds.values()))        # 20个

# 直接使用,无需过滤
q = np.deg2rad(all_joint_positions)
dq = np.deg2rad(all_joint_speeds)
```

### 3. 动作应用
```python
# 网络输出20维
nn_action = run_network(obs=final_obs_input, model=self.model)  # shape: (20,)

# 直接应用到所有20个关节
for idx in range(20):
    target = nominal[idx] + nn_action[idx] * 0.25
    robot.set_motor_target_position(robot.ROBOT_MOTORS[idx], ...)
```

## 总结

✅ XML中只有20个actuator (手腕已注释)
✅ rlDofs = 20 完全匹配
✅ 所有20个关节都被控制
✅ 代码实现简洁,无需排除逻辑
✅ 观测空间: 69维单帧 × 5帧 = 345维
✅ 动作空间: 20维,直接对应20个关节

