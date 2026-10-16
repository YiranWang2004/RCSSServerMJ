"""Opt-in SimRobot 2026 ServoMotor control for imported B-Human models."""

from typing import Any

import numpy as np


class SimRobotMotors:
    """Apply filtered PD and summed torque saturation before each physics step.

    Only actuators with simrobot_servo_* model metadata participate. Ordinary
    server models retain their existing MuJoCo position/velocity actuators.
    """

    def __init__(self) -> None:
        self.indices: dict[str, int] = {}
        self.commands = np.empty((0, 6), dtype=np.float64)
        self.filtered_velocity = np.empty(0, dtype=np.float64)
        self.qpos_indices = np.empty(0, dtype=int)
        self.dof_indices = np.empty(0, dtype=int)
        self.actuator_indices = np.empty(0, dtype=int)
        self.joint_indices = np.empty(0, dtype=int)
        self.alpha = np.empty(0, dtype=np.float64)
        self.limits = np.empty((0, 2), dtype=np.float64)

    def bind(self, model: Any, data: Any) -> None:
        old_states = {name: (self.commands[index].copy(), self.filtered_velocity[index]) for name, index in self.indices.items()}
        entries = []
        for index in range(model.nnumeric):
            numeric = model.numeric(index)
            prefix, marker, actuator = numeric.name.partition('simrobot_servo_')
            if not marker:
                continue
            alpha, reference_step, kp, kd, max_torque = numeric.data
            if not np.all(np.isfinite(numeric.data)) or not 0 <= alpha <= 1 or reference_step <= 0 or min(kp, kd, max_torque) < 0:
                raise ValueError(f'Invalid SimRobot motor metadata: {numeric.name}')
            name = prefix + actuator
            motor = model.actuator(name + '_tau')
            joint_id = int(model.actuator_trnid[motor.id, 0])
            qpos_index = int(model.jnt_qposadr[joint_id])
            dof_index = int(model.jnt_dofadr[joint_id])
            command, velocity = old_states.get(name, (np.array([data.qpos[qpos_index], 0., kp, kd, 0., max_torque]), 0.))
            # Preserve the filter's time constant if the host physics step
            # differs from the source SimRobot scene's reference step.
            weight = 1. - (1. - alpha) ** (model.opt.timestep / reference_step)
            entries.append((name, qpos_index, dof_index, motor.id, joint_id, command, velocity, weight))
            for suffix in ('_pos', '_vel'):
                actuator_id = model.actuator(name + suffix).id
                model.actuator_gainprm[actuator_id, :] = 0
                model.actuator_biasprm[actuator_id, :] = 0
                data.ctrl[actuator_id] = 0
        self.indices = {entry[0]: index for index, entry in enumerate(entries)}
        self.qpos_indices = np.array([entry[1] for entry in entries], dtype=int)
        self.dof_indices = np.array([entry[2] for entry in entries], dtype=int)
        self.actuator_indices = np.array([entry[3] for entry in entries], dtype=int)
        self.joint_indices = np.array([entry[4] for entry in entries], dtype=int)
        self.commands = np.array([entry[5] for entry in entries], dtype=np.float64).reshape(-1, 6)
        self.filtered_velocity = np.array([entry[6] for entry in entries], dtype=np.float64)
        self.alpha = np.array([entry[7] for entry in entries], dtype=np.float64)
        self.limits = model.jnt_range[self.joint_indices].copy()

    def command(self, name: str, q: float, dq: float, kp: float, kd: float, tau: float, max_torque: float | None) -> bool:
        index = self.indices.get(name)
        if index is None:
            return False
        limit = self.commands[index, 5] if max_torque is None else max_torque
        values = np.array([q, dq, kp, kd, tau, limit], dtype=np.float64)
        if not np.all(np.isfinite(values)) or min(kp, kd, limit) < 0:
            raise ValueError(f'Invalid SimRobot motor command: {name}')
        # ServoMotor::setValue clips the requested angle to Deflection limits.
        values[0] = np.clip(q, *self.limits[index])
        self.commands[index] = values
        return True

    def apply(self, data: Any) -> None:
        if not self.indices:
            return
        self.filtered_velocity += self.alpha * (data.qvel[self.dof_indices] - self.filtered_velocity)
        q, dq, kp, kd, tau, limit = self.commands.T
        torque = kp * (q - data.qpos[self.qpos_indices]) + kd * (dq - self.filtered_velocity) + tau
        data.ctrl[self.actuator_indices] = np.clip(torque, -limit, limit)
