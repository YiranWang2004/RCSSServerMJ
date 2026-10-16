from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

import mujoco
import numpy as np

from rcsssmj.games.soccer.server.soccer_action_parser import SoccerActionParser
from rcsssmj.games.soccer.sim.soccer_sim import SoccerSimulation
from rcsssmj.games.soccer.soccer_fields import create_soccer_field
from rcsssmj.resources.spec_provider import ModelSpecProvider
from rcsssmj.sim.simrobot_motors import SimRobotMotors


class SimRobotMotorsTest(TestCase):
    def setUp(self):
        self.model = ModelSpecProvider().load_robot_spec('K1BHuman').compile()
        # Direct comparison with the source's 2 ms recurrence, independently
        # of the host server's chosen physics step.
        self.model.opt.timestep = .002
        self.data = mujoco.MjData(self.model)
        self.motors = SimRobotMotors()
        self.motors.bind(self.model, self.data)
        self.joint = self.model.joint('Left_Hip_Pitch')

    def test_filter_and_pd_follow_native_servo_recurrence(self):
        self.motors.command( 'lle1', 0, 0, 0, 1, 0, 50)
        self.data.qvel[self.joint.dofadr[0]] = 10
        self.motors.apply(self.data)
        self.assertAlmostEqual(self.data.ctrl[self.model.actuator('lle1_tau').id], -2.2)
        self.motors.apply(self.data)
        self.assertAlmostEqual(self.data.ctrl[self.model.actuator('lle1_tau').id], -3.916)
        # The MuJoCo pos/vel actuators must not apply unfiltered PD on top.
        self.assertTrue(np.all(self.model.actuator_gainprm[self.model.actuator('lle1_pos').id] == 0))
        self.assertTrue(np.all(self.model.actuator_biasprm[self.model.actuator('lle1_vel').id] == 0))

    def test_dynamic_limit_and_fixed_source_hardware_limit_both_apply(self):
        self.data.qpos[self.joint.qposadr[0]] = 0
        self.motors.command( 'lle1', 100, 0, 100, 0, 20, 7)
        self.motors.apply(self.data)
        mujoco.mj_forward(self.model, self.data)
        self.assertAlmostEqual(self.data.qfrc_actuator[self.joint.dofadr[0]], 7)
        self.assertAlmostEqual(self.motors.commands[self.motors.indices['lle1'], 0], self.joint.range[1])
        # Native low stiffness mapping uses 36 Nm on this joint; XML has 30.
        yaw_joint = self.model.joint('Left_Hip_Yaw')
        self.motors.command( 'lle3', 0, 0, 0, 0, 100, 36)
        self.motors.apply(self.data)
        mujoco.mj_forward(self.model, self.data)
        self.assertEqual(self.data.ctrl[self.model.actuator('lle3_tau').id], 36)
        self.assertAlmostEqual(self.data.qfrc_actuator[yaw_joint.dofadr[0]], 30)
        np.testing.assert_allclose(self.model.actuator('lle3_tau').ctrlrange, [-30, 30])
        self.motors.command( 'lle3', 0, 0, 0, 0, 100, 0)
        self.motors.apply(self.data)
        mujoco.mj_forward(self.model, self.data)
        self.assertEqual(self.data.qfrc_actuator[yaw_joint.dofadr[0]], 0)

    def test_filter_state_survives_model_recompile_and_removed_players_are_forgotten(self):
        sim = SoccerSimulation(create_soccer_field('fifa7vs7'))
        self.assertTrue(sim.init())
        parameters = SimpleNamespace(model_name='K1BHuman', team_name='Red', player_no=1)
        player, = sim.add_players([parameters])
        motor = player.agent_id.prefix + 'lle1'
        sim.ctrl_motor(motor, .3, 0, 80, 4, 0, 40)
        index = sim._simrobot_motors.indices[motor]
        sim._simrobot_motors.filtered_velocity[index] = 2.5
        other, = sim.add_players([SimpleNamespace(model_name='K1', team_name='Blue', player_no=1)])
        index = sim._simrobot_motors.indices[motor]
        self.assertEqual(sim._simrobot_motors.filtered_velocity[index], 2.5)
        self.assertEqual(sim._simrobot_motors.commands[index, 5], 40)
        sim.remove_players([player])
        self.assertFalse(sim._simrobot_motors.indices)
        replacement, = sim.add_players([parameters])
        index = sim._simrobot_motors.indices[motor]
        self.assertEqual(sim._simrobot_motors.filtered_velocity[index], 0)
        self.assertEqual(sim._simrobot_motors.commands[index, 5], 50)

    def test_legacy_motor_parser_and_control_remain_compatible(self):
        parser = SoccerActionParser()
        old, = parser.parse_action(b'(lle1 10 20 80 4 2)', 'r-0-1-')
        interface = Mock()
        old.perform(interface)
        interface.ctrl_motor.assert_called_once_with('r-0-1-lle1', np.deg2rad(10), np.deg2rad(20), 80, 4, 2)
        new, = parser.parse_action(b'(lle1 10 20 80 4 2 36)', 'r-0-1-')
        interface.reset_mock()
        new.perform(interface)
        interface.ctrl_motor.assert_called_once_with('r-0-1-lle1', np.deg2rad(10), np.deg2rad(20), 80, 4, 2, 36)
        model = ModelSpecProvider().load_robot_spec('K1').compile()
        legacy = SimRobotMotors()
        legacy.bind(model, mujoco.MjData(model))
        self.assertFalse(legacy.indices)
        self.assertNotEqual(model.actuator_gainprm[model.actuator('lle1_pos').id, 0], 0)

    def test_host_step_uses_same_filter_time_constant(self):
        self.model.opt.timestep = .005
        self.motors.bind(self.model, self.data)
        index = self.motors.indices['lle1']
        expected = 1 - .78 ** 2.5
        self.assertAlmostEqual(self.motors.alpha[index], expected)
        self.motors.command( 'lle1', 0, 0, 0, 1, 0, 50)
        self.data.qvel[self.joint.dofadr[0]] = 10
        for _ in range(4):
            self.motors.apply(self.data)
        # Four server physics steps and ten native steps cover the same 20 ms.
        self.assertAlmostEqual(self.motors.filtered_velocity[index], 10 * (1 - .78 ** 10))

    def test_old_model_physics_and_motor_commands_are_unchanged(self):
        sim = SoccerSimulation(create_soccer_field('fifa7vs7'))
        sim.init()
        player, = sim.add_players([SimpleNamespace(model_name='K1', team_name='Legacy', player_no=1)])
        name = player.agent_id.prefix + 'lle1'
        sim.ctrl_motor(name, .2, .3, 80, 4, 2)
        self.assertEqual(sim.mj_model.actuator(name + '_pos').gainprm[0], 80)
        self.assertEqual(sim.mj_model.actuator(name + '_vel').biasprm[2], -4)
        self.assertEqual(sim.mj_data.actuator(name + '_tau').ctrl[0], 2)
        reference = mujoco.MjData(sim.mj_model)
        mujoco.mj_copyData(reference, sim.mj_model, sim.mj_data)
        mujoco.mj_step(sim.mj_model, reference, sim.n_substeps)
        sim.step([])
        np.testing.assert_array_equal(sim.mj_data.qpos, reference.qpos)
        np.testing.assert_array_equal(sim.mj_data.qvel, reference.qvel)
        self.assertEqual(sim.timestep, .02)
        self.assertEqual(sim.mj_model.opt.timestep, .005)

    def test_nonfinite_and_negative_limits_are_rejected(self):
        for limit in [float('nan'), float('inf'), -1]:
            with self.assertRaises(ValueError):
                self.motors.command( 'lle1', 0, 0, 80, 4, 0, limit)
