from types import SimpleNamespace
from unittest import TestCase

import mujoco
import numpy as np

from rcsssmj.games.soccer.sim.soccer_sim import SoccerSimulation
from rcsssmj.games.soccer.soccer_fields import create_soccer_field
from rcsssmj.resources.spec_provider import ModelSpecProvider


class K1SimRobotModelTest(TestCase):
    def test_bhuman_model_can_disconnect_and_rejoin_with_same_number(self):
        sim = SoccerSimulation(create_soccer_field('fifa7vs7'))
        self.assertTrue(sim.init())
        parameters = SimpleNamespace(model_name='K1BHuman', team_name='Red', player_no=1)
        player, = sim.add_players([parameters])
        sim.remove_players([player])
        replacement, = sim.add_players([parameters])
        self.assertIsNotNone(replacement)
        self.assertTrue(np.all(np.isfinite(sim._mj_data.sensordata)))

    def test_dynamics_match_simrobot_and_legacy_model_remains_loadable(self):
        model = ModelSpecProvider().load_robot_spec('K1BHuman').compile()
        legacy = ModelSpecProvider().load_robot_spec('K1').compile()
        self.assertAlmostEqual(sum(model.body_mass), 19.666)
        self.assertGreater(sum(legacy.body_mass), 19.)  # Existing local K1 physics is independent.
        self.assertEqual(model.njnt, 23)  # free base + 22 motor hinges
        self.assertEqual(model.nu, 66)
        self.assertEqual(model.nsensor, 48)
        np.testing.assert_allclose(model.body('Left_Hip_Pitch').pos, [0, .096, -.077])
        np.testing.assert_allclose(model.body('Left_Hip_Roll').pos, [.012, 0, -.026])
        np.testing.assert_allclose(model.body('Left_Hip_Yaw').pos, [0, 0, 0])
        np.testing.assert_allclose(model.body('Left_Shank').pos, [-.014, 0, -.1655])
        np.testing.assert_allclose(model.body('Head_1').pos, [.0056, 0, .2479])
        self.assertAlmostEqual(model.body('left_foot_link').mass[0], .494)
        joint = model.joint('Left_Ankle_Roll')
        np.testing.assert_allclose(model.jnt_actfrcrange[joint.id], [-30, 30])
        self.assertAlmostEqual(model.dof_armature[joint.dofadr[0]], .0565056)
        self.assertAlmostEqual(model.dof_damping[joint.dofadr[0]], 0.)
        np.testing.assert_allclose(model.site('camera').pos, [.0601, .0351, .0928])
        np.testing.assert_allclose(legacy.site('camera').pos, [.06, 0, .08])
        foot_boxes = [i for i in range(model.ngeom)
                      if model.geom_bodyid[i] == model.body('left_foot_link').id
                      and model.geom_type[i] == mujoco.mjtGeom.mjGEOM_BOX]
        self.assertEqual(len(foot_boxes), 1)
        np.testing.assert_allclose(model.geom_size[foot_boxes[0]], [.092, .035, .015])
        np.testing.assert_allclose(model.geom_pos[foot_boxes[0]], [.027, 0, -.023])

    def test_beam_restores_simrobot_reference_pose_only_for_bhuman(self):
        sim = SoccerSimulation(create_soccer_field('fifa7vs7'))
        self.assertTrue(sim.init())
        home, guest = sim.add_players([
            SimpleNamespace(model_name=model_name, team_name=team, player_no=1)
            for model_name, team in (('K1', 'Blue'), ('K1BHuman', 'Red'))])
        home.drop_at(-3, 0, 0)
        guest.drop_at(3, 0, 0)
        for spec_joint in guest.spec.joints:
            if spec_joint.type == mujoco.mjtJoint.mjJNT_HINGE:
                np.testing.assert_allclose(sim.mj_data.joint(spec_joint.name).qpos, spec_joint.ref)
        self.assertAlmostEqual(guest.xpos[2], .537)
        self.assertAlmostEqual(home.xpos[2], 1.)
        np.testing.assert_allclose(sim.mj_data.joint(guest.agent_id.prefix + 'Left_Shoulder_Roll').qpos, -83 * np.pi / 180)
        for spec_joint in home.spec.joints:
            if spec_joint.type == mujoco.mjtJoint.mjJNT_HINGE:
                np.testing.assert_allclose(sim.mj_data.joint(spec_joint.name).qpos, 0)

    def test_self_contacts_excluded_but_robots_still_collide_after_attach(self):
        sim = SoccerSimulation(create_soccer_field('fifa7vs7'))
        self.assertTrue(sim.init())
        players = sim.add_players([SimpleNamespace(model_name=model_name, team_name=team, player_no=1)
                                   for model_name, team in (('K1', 'Blue'), ('K1BHuman', 'Red'))])
        self.assertTrue(all(player is not None for player in players))
        model, data = sim._mj_model, sim._mj_data
        data.ctrl[:] = 0
        # Overlap both robot roots in midair. Cross-robot contacts must remain
        # enabled while each robot's own geometries cannot self-collide.
        for player in players:
            root = model.joint(player.agent_id.prefix + 'root')
            data.qpos[root.qposadr[0]:root.qposadr[0] + 3] = [0, 0, 2]
        mujoco.mj_forward(model, data)
        cross_contacts = 0
        for contact in data.contact:
            bodies = [model.body(model.geom_bodyid[index]).name for index in contact.geom]
            owners = [next((player.agent_id.prefix for player in players if name.startswith(player.agent_id.prefix)), None) for name in bodies]
            if all(owner is not None for owner in owners):
                if owners[0] == players[1].agent_id.prefix:
                    self.assertNotEqual(owners[0], owners[1], 'SimRobot disables self-collisions')
            if all(owner is not None for owner in owners) and owners[0] != owners[1]:
                cross_contacts += 1
        self.assertGreater(cross_contacts, 0)

    def test_adding_second_model_preserves_controls_and_camera_fov(self):
        sim = SoccerSimulation(create_soccer_field('fifa7vs7'))
        self.assertTrue(sim.init())
        home, = sim.add_players([SimpleNamespace(model_name='K1', team_name='Blue', player_no=1)])
        self.assertTrue(np.all(sim._mj_data.ctrl == 0))
        sim._mj_data.ctrl[:] = .125
        guest, = sim.add_players([SimpleNamespace(model_name='K1BHuman', team_name='Red', player_no=1)])
        for index in range(sim._mj_model.nu):
            name = sim._mj_model.actuator(index).name
            self.assertEqual(sim._mj_data.ctrl[index], .125 if name.startswith(home.agent_id.prefix) else 0)
        guest_camera = guest.spec.site(guest.agent_id.prefix + 'camera')
        np.testing.assert_allclose(list(guest_camera.userdata)[:2], [52.5, 47])
