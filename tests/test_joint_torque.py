from types import SimpleNamespace
from unittest import TestCase

import numpy as np

from rcsssmj.games.soccer.sim.soccer_sim import SoccerSimulation
from rcsssmj.games.soccer.soccer_fields import create_soccer_field
from rcsssmj.sim.perceptions import JointStatePerception


class JointTorqueTest(TestCase):
    def test_legacy_joint_state_format_is_unchanged_without_torque(self) -> None:
        state = JointStatePerception(['a'], [12.0], [-3.0])
        self.assertEqual(state.to_sexp(), '(HJ (n a)(ax 12.0)(vx -3.0))')

    def test_joint_torques_follow_sensor_names_after_model_recompile(self) -> None:
        sim = SoccerSimulation(create_soccer_field('fifa7vs7'))
        self.assertTrue(sim.init())
        player, = sim.add_players([SimpleNamespace(model_name='K1', team_name='TorqueTest', player_no=1)])
        self.assertIsNotNone(player)
        # Free-base DOFs precede the hinges. Unique values make a mistaken
        # sensor index / actuator index / generalized-DOF index observable.
        sim._mj_data.qfrc_actuator[:] = np.arange(sim._mj_model.nv, dtype=float) + .125
        sim.generate_perceptions()
        states = [p for p in player.perceptions if isinstance(p, JointStatePerception)]
        self.assertEqual(len(states), 1)
        state = states[0]
        self.assertEqual(len(state.joint_taus), 22)
        prefix = player.agent_id.prefix
        for name, torque in zip(state.joint_names, state.joint_taus, strict=True):
            sensor = sim._mj_model.sensor(prefix + name)
            joint = sim._mj_model.joint(int(sensor.objid[0]))
            expected = float(sim._mj_data.qfrc_actuator[int(joint.dofadr[0])])
            self.assertAlmostEqual(torque, expected)
        self.assertEqual(state.to_sexp().count('(tau '), 22)
