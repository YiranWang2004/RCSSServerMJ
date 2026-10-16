"""Regressions for the explicit native-physics profile and 7v7 field."""
from unittest import TestCase
from types import SimpleNamespace
import mujoco
import numpy as np
from rcsssmj.games.soccer.sim.soccer_sim import SoccerSimulation
from rcsssmj.games.soccer.soccer_fields import create_soccer_field
from rcsssmj.games.soccer.soccer_rules import create_soccer_rule_book


class BHuman7v7Test(TestCase):
    def test_native_profile_and_field_marker_dimensions(self):
        sim = SoccerSimulation(create_soccer_field('fifa7vs7'), create_soccer_rule_book('ssim'), bhuman_physics=True)
        self.assertTrue(sim.init())
        self.assertAlmostEqual(sim.timestep, .02)
        self.assertAlmostEqual(sim.mj_model.opt.timestep, .002)
        self.assertEqual(sim.mj_model.opt.integrator, mujoco.mjtIntegrator.mjINT_EULER)
        self.assertEqual(sim.mj_model.opt.iterations, 50)
        self.assertAlmostEqual(sim.mj_model.opt.tolerance, 1e-6)
        self.assertEqual(sim.rules.max_team_size, 7)
        # The rulebook dimensions store full widths. Markers must coincide
        # with the actual goal/penalty area edges used by the referee.
        np.testing.assert_allclose(sim.mj_data.site('l_luga-vismarker').xpos, [-23.5, 3.65, 0])
        np.testing.assert_allclose(sim.mj_data.site('l_lupa-vismarker').xpos, [-18.5, 8.25, 0])

    def test_fourteen_native_models_can_join_and_step(self):
        sim = SoccerSimulation(create_soccer_field('fifa7vs7'), create_soccer_rule_book('ssim'), bhuman_physics=True)
        self.assertTrue(sim.init())
        players = sim.add_players([SimpleNamespace(model_name='K1BHuman', team_name=team, player_no=n)
                                   for team in ['Blue', 'Red'] for n in range(1, 8)])
        self.assertEqual(len(players), 14)
        self.assertTrue(all(player is not None for player in players))
        self.assertEqual(len(sim._simrobot_motors.indices), 14 * 22)
        # Initial frames already contain legal in-field positions, before
        # any client has sent a beam or started its behavior engine.
        for player in players:
            x, y, _ = player.xpos
            self.assertLess(x, 0) if player.agent_id.team_id == 0 else self.assertGreater(x, 0)
            self.assertLess(abs(y), 18)
            self.assertGreater(np.hypot(x, y), sim.field.center_circle_radius)
        np.testing.assert_allclose(players[0].xpos[:2], [-25, 0])
        np.testing.assert_allclose(players[7].xpos[:2], [25, 0])
        self.assertTrue(all(player.torso_geom_id >= 0 for player in players))
        for _ in range(5):
            sim.step([])
        self.assertTrue(np.all(np.isfinite(sim.mj_data.qpos)))
        sim.generate_perceptions()
        self.assertTrue(all(len(player.perceptions) > 6 for player in players))
