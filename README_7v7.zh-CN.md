# B-Human K1/T1 的 7v7 仿真服务器

本分支 `feature/bhuman-7v7` 基于本仓库 `ssim` 分支，推送到
`https://github.com/YiranWang2004/RCSSServerMJ` 的独立分支。搭配
`../BHumanCodeRelease` 中的 `feature/rcssservermj-7v7` 分支。使用本仓库的 55×36 米
`fifa7vs7` 场地、`ssim` 裁判规则和每队最多 7 人限制。

## 环境与启动

本机已有 `robocup_sim` conda 环境，包含 Python 3.13、MuJoCo 3.5.0、NumPy、GLFW。
启动脚本会明确加载本仓库的源码，因此不受其他服务器仓库的 editable 安装影响。

```bash
conda activate robocup_sim
cd /home/robotics/ZJUDancer/rcssservermj
scripts/start_bhuman_7v7.sh --host 127.0.0.1 --aport 60000 --mport 60001 --render
```

没有窗口时将 `--render` 换成 `--no-render`。在新机器上，准备 Python ≥3.10 的环境后
执行 `python -m pip install -r requirements.txt`。没有系统图形桌面时使用 `--no-render`。
脚本相当于：

```bash
PYTHONPATH=src python -m rcsssmj --field fifa7vs7 --rules ssim --sync --bhuman-physics
```

另开终端启动两队：

```bash
cd /home/robotics/ZJUDancer/BHumanCodeRelease
python3 scripts/start_7v7.py
```

默认两队各 7 人。设置 `--players 3` 可改为 3v3；范围为 1～7，减少人数时仍使用
7v7 大场地，1 号始终是守门员。服务器限制最大人数，客户端连接数量决定实际人数，
无需修改服务器模型或源码。客户端首次编译、单人启动和定位模式见配套仓库的
[README_7v7.zh-CN.md](../BHumanCodeRelease/README_7v7.zh-CN.md)。

## 窗口操作

按键在**释放时**触发，先选中仿真窗口。

| 操作 | 功能 |
|---|---|
| `K` | 左队开球；默认左队为 `BHumanBlue` |
| `J` | 右队开球；默认右队为 `BHumanRed` |
| `B` | 裁判抛球，恢复比赛 |
| `H` | 显示或隐藏信息菜单 |
| `Tab` | 在固定视角和跟随视角间切换 |
| 鼠标左键拖动 | 旋转视角；按住 Shift 切换旋转方向 |
| 鼠标右键拖动 | 平移视角；按住 Shift 切换平移方向 |
| 鼠标滚轮 | 缩放视角 |
| 终端 `Ctrl+C` | 关闭当前服务器或客户端启动器 |

无界面时客户端启动器支持 `--kickoff left`、`--kickoff right`，在全部客户端就绪后
向 monitor 端口发送开球命令。默认不自动开球。

## 与原版 SimRobot 对齐的独立模型

新增模型名为 **`K1BHuman`**，文件为
[src/rcsssmj/resources/robots/K1BHuman/robot.xml](src/rcsssmj/resources/robots/K1BHuman/robot.xml)。
客户端发送 `(init K1BHuman 队名 球员号)`。该模型直接生成到己方半场；
配套 B-Human 在进球后使用服务器允许的 beam 瞬间回到场内，不执行走回场流程。
B-Human 默认读取 Server 特权位置/姿态，`--localization measured` 才启用自主定位。原有 `K1` 模型及已有的本地修改保留。

模型由 B-Human Code Release 2026 的 `Config/Scenes/Includes/K1/K1.rsi3`
及其引用的外观文件生成，保留 22 个关节的轴、限位、参考角、转子惯量、刚体质量与
完整惯性张量、碰撞几何和视觉网格。总质量为 19.666 kg，初始躯干高度为 0.537 m。
相机在头部的位置为 `(0.0601, 0.0351, 0.0928)m`，采用原版 105°×94° 的矩形视锥。
模型额外保留服务器所需的传感器、球员标记和裁判躯干几何名称。

重新生成：

```bash
python3 tools/import_bhuman_k1.py ../BHumanCodeRelease
```

转换器通过 Git 读取服务器已提交的 K1 文件获取协议名称，不读取用户未提交的 K1
物理修改。B-Human 输入文件的 SHA256 记录在模型目录中的 `SIMROBOT_SOURCE.sha256`。
源许可见 `LICENSE.BHuman`；协议辅助部分的许可见同目录 `LICENSE`。

`--bhuman-physics` 使用原版 Euler / Newton 求解设置、2 ms 物理步长，每 10 个物理步
交换一次客户端数据，即 20 ms 网络周期。仅带 `simrobot_servo_*` 元数据的模型启用
原版 ServoMotor 控制：目标角限位、每 2 ms 系数 0.22 的速度低通、PD、动态力矩限幅，
再施加 XML 固定硬件上限。滤波状态在其他球员加入导致模型重编译时保留。

本分支还增加 `(HJ ... (tau Nm))` 实际关节力矩，以及关节指令末尾可选的 `maxTorque`：

```text
(lle1 target_deg velocity_deg_per_sec kp kd feedforward_Nm maxTorque_Nm)
```

原六参数指令仍可使用。没有新模型元数据时，沿用原有电机实现；不加
`--bhuman-physics` 时，全场仍采用原有 5 ms 物理步长。

**模型参数对齐不代表整个仿真完全相同。** 球和地面接触参数按下节对齐，
场地尺寸、裁判和视觉依然来自本服务器。
客户端按 20 ms 接收反馈，内部十个 Motion 子帧使用同一份传感器采样，无法等同于
SimRobot 每 2 ms 更新完整传感器的闭环。测量定位使用这里的理想视觉测量，不是实机图像。
另外修正了原服务器球门区、罚球区标记将完整宽度误作半宽的问题，使视觉标记与裁判区域一致。

## fifa7vs7 的球与地面物理

`fifa7vs7` 在加载世界后，统一覆盖为 SimRobot T1 的球和地面接触参数。
该配置按场地选择，与机器人型号、球队和 `--bhuman-physics` 无关，双方共同使用；
普通 `fifa` 场地继续使用原有世界参数。55×36 m 比赛尺寸、现有场地边界与裁判规则保留。

| 参数 | fifa7vs7 当前值 |
|---|---:|
| 球半径 | 0.11 m |
| 球质量 | 0.43 kg |
| 球各主轴转动惯量 | 0.0020812 kg·m² |
| 球滑动／扭转／滚动摩擦 | 0.5 / 0.007 / 0.007 |
| 球 `condim` / `priority` | 6 / 1 |
| 球和地面 `solref` | 0.02 / 1 |
| 球和地面 `solimp` | 0.9 / 0.95 / 0.001 / 0.5 / 2 |
| 地面滑动／扭转／滚动摩擦 | 1 / 0 / 0 |
| 地面 `condim` / `priority` | 3 / 0 |
| 重力加速度 | −9.80665 m/s² |
| 空气密度／黏度 | 0 / 0 |

参数依据 B-Human `Config/Scenes/Includes/BallFifa5.rsi3`、`Field2026HSLL.rsi3`
以及 SimRobot 的 `Geometry.cpp`、`SphereMass.cpp`。按约定修正原五号球
`SphereMass radius="0.011"` 的笔误，使用 **0.11 m**：
`I = (2/5) × 0.43 × 0.11² = 0.0020812 kg·m²`。
MuJoCo 根据球的碰撞半径和质量计算此惯量，不复刻错误的小半径惯量。

地面保留服务器的平面几何，以对齐平地接触；不复制原版小场地外围挡墙。
测试使用独立的、厚度 0.2 m 的 SimRobot T1 地板箱体参考模型，验证滑动、纯滚动、
自旋和落球过程。混合 K1BHuman、T1BHuman 和普通 T1 加入重编译后，也检查球的
质量、惯量及实际球地接触参数，防止被其他模型覆盖。

完整的 2 ms / 20 ms 求解和网络周期仍由 `--bhuman-physics` 开启；只选择场地而
不加该选项时，原来的 5 ms / 20 ms 调度保留，球地材料参数仍采用上表。
修改源码后需要**重启服务器和双方客户端**。本次不会热改正在进行的比赛。
B-Human 对应场地的 `ballSpecification.cfg` 球质量同步为 0.43 kg，其他客户端如有
硬编码球质量也应与上表一致；`staticFriction` 是客户端预测减速度，不等同于这里的接触摩擦。

## 独立的原生 T1BHuman

服务端也提供 **`T1BHuman`**：
[src/rcsssmj/resources/robots/T1BHuman/robot.xml](src/rcsssmj/resources/robots/T1BHuman/robot.xml)。
与现用 `T1` 分开保存，不修改原模型。按上文启动服务器，再在 B-Human 仓库中执行：

```bash
python3 scripts/start_7v7.py --robot T1
# 或左 T1、右 K1
python3 scripts/start_7v7.py --robot-a T1 --robot-b K1
```

源文件为 `Config/Scenes/Includes/T1/T1.rsi3` 及其引用的外观文件，包含 23 个关节、
31.73435 kg 总质量、完整惯量和原版电机限制，初始高度 0.670 m。相机为
640×480、79.2°×63.6°，头部位置 `(0.0429, -0.0139, 0.1214)m`；IMU 位于
躯干坐标 `(-0.0625, 0, 0)m`。参考角、视觉和碰撞几何均从源文件转换。
T1BHuman 也直接生成到己方场内，配套客户端默认使用特权位置并跳过入场和回场步行。

```bash
python3 tools/import_bhuman_t1.py ../BHumanCodeRelease
```

转换器与 K1 共用几何转换实现，重生成 K1 的输出保持一致。T1 额外记录
`simrobot_delay_*` 元数据，实现原版 **14 ms 目标角延迟**：每个物理步采样目标，
到期后用于 PD，增益和力矩上限不延迟。与速度滤波相同，未执行的目标队列在其他机器人
加入时保留；机器人退出重连后重新初始化。普通 T1 没有该元数据，继续沿用原有控制。
K1BHuman 没有新增延迟；混合比赛中每个模型分别应用自己的控制参数。

## 验证

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

当前共 37 项测试，覆盖 14 个模型加入及物理步进、K1/T1 原生参数、关节力矩、滤波、
T1 的 14 ms 目标延迟和力矩上限、重编译与重连、
原模型协议兼容及原有非法防守规则，以及球地材料、修正后的惯量与参考轨迹一致性。客户端的联调记录见配套 README。

This product includes software developed by B-Human (http://www.b-human.de).
