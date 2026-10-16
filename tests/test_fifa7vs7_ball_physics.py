"""Compiled contacts and dynamics against a corrected SimRobot T1 ball/floor.

The independent reference below uses BallFifa5.rsi3, Field2026HSLL.rsi3,
Geometry.cpp and SphereMass.cpp, correcting only the inertial radius to .11 m.
It retains a floor box, whereas the server uses its existing flat plane.
"""
from types import SimpleNamespace
from unittest import TestCase

import mujoco
import numpy as np

from rcsssmj.games.soccer.sim.soccer_sim import SoccerSimulation
from rcsssmj.games.soccer.soccer_fields import create_soccer_field


REFERENCE = '''
<mujoco>
  <compiler inertiafromgeom="false"/>
  <option timestep=".002" gravity="0 0 -9.80665" integrator="Euler"
          solver="Newton" iterations="50" tolerance="1e-6"/>
  <worldbody>
    <geom name="floor" type="box" pos="0 0 -.1" size="13 9 .1"
          friction="1 0 0" condim="3"/>
    <body name="ball" pos="0 0 .11">
      <freejoint name="ball-root"/>
      <inertial pos="0 0 0" mass=".43"
                diaginertia=".0020812 .0020812 .0020812"/>
      <geom name="ball" type="sphere" size=".11" priority="1"
            friction=".5 .007 .007" condim="6"/>
    </body>
  </worldbody>
</mujoco>
'''


class FIFA7vs7BallPhysicsTest(TestCase):
    def simulation(self, field='fifa7vs7', bhuman_physics=True):
        sim = SoccerSimulation(create_soccer_field(field), bhuman_physics=bhuman_physics)
        self.assertTrue(sim.init())
        self.addCleanup(sim.shutdown)
        return sim

    def test_correct_inertia_and_effective_contact_survive_mixed_robot_joins(self):
        sim = self.simulation()
        sim.add_players([
            SimpleNamespace(model_name=model, team_name=team, player_no=number)
            for model, team, number in [('K1BHuman', 'Native', 1), ('T1BHuman', 'Native', 2), ('T1', 'Other', 1)]
        ])
        model = sim.mj_model
        self.assertAlmostEqual(model.body('ball').mass[0], .43)
        np.testing.assert_allclose(model.body('ball').inertia, [.0020812] * 3)
        np.testing.assert_allclose(model.geom('ball').size, [.11, 0, 0])
        self.assertEqual(sim.field.field_dim[:2], (55, 36))
        sim.request_place_ball((0, 0, .109), (0, 0, 0))
        mujoco.mj_forward(model, sim.mj_data)
        contacts = [contact for contact in sim.mj_data.contact
                    if set(contact.geom) == {model.geom('ball').id, model.geom('pitch').id}]
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0].dim, 6)
        np.testing.assert_allclose(contacts[0].friction, [.5, .5, .007, .007, .007])
        np.testing.assert_allclose(contacts[0].solref, [.02, 1])

    def test_surface_profile_is_selected_by_field_without_changing_frame_scheduling(self):
        for native in (False, True):
            with self.subTest(bhuman_physics=native):
                sim = self.simulation(bhuman_physics=native)
                self.assertAlmostEqual(sim.mj_model.body('ball').mass[0], .43)
                np.testing.assert_allclose(sim.mj_model.geom('pitch').friction, [1, 0, 0])
                np.testing.assert_allclose(sim.mj_model.opt.gravity, [0, 0, -9.80665])
                self.assertEqual(sim.mj_model.opt.density, 0)
                self.assertEqual(sim.mj_model.opt.viscosity, 0)
                self.assertAlmostEqual(sim.timestep, .02)
                self.assertAlmostEqual(sim.mj_model.opt.timestep, .002 if native else .005)

    def test_other_field_keeps_legacy_ball_and_ground(self):
        for native in (False, True):
            with self.subTest(bhuman_physics=native):
                sim = self.simulation('fifa', native)
                model = sim.mj_model
                self.assertAlmostEqual(model.body('ball').mass[0], .41)
                np.testing.assert_allclose(model.body('ball').inertia, [.0019844] * 3)
                np.testing.assert_allclose(model.geom('ball').friction, [.4, .01, .01])
                np.testing.assert_allclose(model.geom('ball').solref, [-5000, -20])
                np.testing.assert_allclose(model.geom('pitch').friction, [1, .005, .0001])
                np.testing.assert_allclose(model.opt.gravity, [0, 0, -9.81])
                self.assertEqual(model.opt.density, 0 if native else 1.2)
                self.assertEqual(model.opt.viscosity, 0 if native else .00002)

    @staticmethod
    def trajectory(model, position, velocity):
        data = mujoco.MjData(model)
        joint = model.joint('ball-root')
        qpos = int(joint.qposadr[0])
        dof = int(joint.dofadr[0])
        data.qpos[qpos:qpos + 3] = position
        data.qvel[dof:dof + 6] = velocity
        mujoco.mj_forward(model, data)
        samples = []
        for frame in range(3000):
            # Exercise only physics, without referee respawns or game clocks.
            mujoco.mj_step(model, data)
            if frame % 25 == 0:
                samples.append(np.concatenate((data.qpos[qpos:qpos + 3], data.qvel[dof:dof + 6])))
        return np.asarray(samples)

    def test_sliding_rolling_spin_and_drop_match_corrected_t1_reference(self):
        actual = self.simulation().mj_model
        reference = mujoco.MjModel.from_xml_string(REFERENCE)
        cases = [
            ('slide', [0, 0, .11], [2, 0, 0, 0, 0, 0]),
            ('roll', [0, 0, .11], [2, 0, 0, 0, 2 / .11, 0]),
            ('spin', [0, 0, .11], [1, .5, 0, 2, -1, 4]),
            ('drop', [0, 0, 1], [0, 0, 0, 0, 0, 0]),
        ]
        for name, position, velocity in cases:
            with self.subTest(case=name):
                expected = self.trajectory(reference, position, velocity)
                observed = self.trajectory(actual, position, velocity)
                np.testing.assert_allclose(observed, expected, atol=1e-6, rtol=1e-6)
