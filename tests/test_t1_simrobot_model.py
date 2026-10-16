"""Native T1 dynamics, delayed servos, protocol and mixed-model regressions."""
from types import SimpleNamespace
from unittest import TestCase
import mujoco
import numpy as np
from rcsssmj.resources.spec_provider import ModelSpecProvider
from rcsssmj.games.soccer.sim.soccer_sim import SoccerSimulation
from rcsssmj.games.soccer.soccer_fields import create_soccer_field
from rcsssmj.sim.simrobot_motors import SimRobotMotors


class T1SimRobotModelTest(TestCase):
    def setUp(self):
        self.model = ModelSpecProvider().load_robot_spec('T1BHuman').compile()

    def test_native_mass_dynamics_camera_and_geometry(self):
        m = self.model
        self.assertAlmostEqual(sum(m.body_mass), 31.73435)
        self.assertEqual((m.njnt, m.nu, m.nsensor), (24, 69, 50))
        for name, limit, armature in [
            ('Left_Hip_Pitch', 90, .0523908), ('Left_Hip_Roll', 105, .0478125),
            ('Left_Knee_Pitch', 110, .0636012), ('Left_Ankle_Pitch', 57, .0679104),
            ('Left_Ankle_Roll', 57, .0679104), ('Waist', 40, .0478125)]:
            j = m.joint(name)
            np.testing.assert_allclose(m.jnt_actfrcrange[j.id], [-limit, limit])
            self.assertAlmostEqual(m.dof_armature[j.dofadr[0]], armature)
            self.assertEqual(m.dof_damping[j.dofadr[0]], 0)
            self.assertEqual(m.dof_frictionloss[j.dofadr[0]], 0)
        np.testing.assert_allclose(m.joint('Left_Hip_Pitch').range, np.radians([-172, 128]))
        np.testing.assert_allclose(m.site('camera').pos, [.0429, -.0139, .1214])
        np.testing.assert_allclose(m.site('camera').user[:2], [39.6, 31.8])
        np.testing.assert_allclose(m.site('imu').pos, [-.0625, 0, 0])
        self.assertAlmostEqual(m.body('Shank_Left').mass[0], 1.82)
        self.assertGreater(max(m.body('Shank_Left').inertia), .061)
        self.assertGreater(m.geom('left_forearm').id, 0)
        # Legacy models remain independent and retain their old dynamics.
        old = ModelSpecProvider().load_robot_spec('T1').compile()
        self.assertAlmostEqual(sum(old.body_mass), 31.614357)
        np.testing.assert_allclose(old.jnt_actfrcrange[old.joint('Left_Hip_Roll').id], [-30, 30])

    def test_target_delay_is_14ms_while_gains_and_limits_are_immediate(self):
        m = self.model
        m.opt.timestep = .002
        d = mujoco.MjData(m)
        motors = SimRobotMotors()
        motors.bind(m, d)
        self.assertEqual(len(motors.delays), 23)
        self.assertAlmostEqual(motors.delays['lle1'], .014)
        motors.command('lle1', .3, 0, 80, 0, 0, 90)
        actuator = m.actuator('lle1_tau').id
        for tick in range(7):
            d.time = tick * .002
            motors.apply(d)
            self.assertEqual(d.ctrl[actuator], 0)
        d.time = .014
        motors.apply(d)
        self.assertAlmostEqual(d.ctrl[actuator], 24)
        # A new limit applies immediately even though targets are delayed.
        motors.command('lle1', .5, 0, 40, 0, 0, 7)
        d.time = .016
        motors.apply(d)
        self.assertAlmostEqual(d.ctrl[actuator], 7)

    def test_delay_history_and_filter_survive_recompile_then_clear_on_rejoin(self):
        sim = SoccerSimulation(create_soccer_field('fifa7vs7'), bhuman_physics=True)
        self.assertTrue(sim.init())
        params = SimpleNamespace(model_name='T1BHuman', team_name='T1', player_no=2)
        player, = sim.add_players([params])
        name = player.agent_id.prefix + 'lle1'
        sim.ctrl_motor(name, .3, 0, 80, 0, 0, 90)
        sim._simrobot_motors.apply(sim.mj_data)
        history = list(sim._simrobot_motors.target_history[name])
        sim.add_players([SimpleNamespace(model_name='K1BHuman', team_name='K1', player_no=1)])
        self.assertEqual(list(sim._simrobot_motors.target_history[name]), history)
        self.assertEqual(len(sim._simrobot_motors.indices), 45)
        self.assertEqual(len(sim._simrobot_motors.delays), 23)
        sim.remove_players([player])
        self.assertNotIn(name, sim._simrobot_motors.target_history)
        replacement, = sim.add_players([params])
        self.assertEqual(len(sim._simrobot_motors.target_history[name]), 0)
        replacement.drop_at(-18, 6, 0)
        for joint in replacement.spec.joints:
            if joint.type == mujoco.mjtJoint.mjJNT_HINGE:
                np.testing.assert_allclose(sim.mj_data.joint(joint.name).qpos, joint.ref)
        self.assertAlmostEqual(replacement.xpos[2], .670)
        self.assertTrue(np.all(np.isfinite(sim.mj_data.qpos)))
