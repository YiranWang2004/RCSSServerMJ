"""Tests for illegal defense detection in SoccerReferee."""

import unittest
from unittest.mock import MagicMock

from rcsssmj.games.soccer.sim.soccer_referee import (
    _ILLEGAL_DEFENSE_DEBOUNCE_STEPS,
    _ILLEGAL_DEFENSE_MAX_PLAYERS,
    SoccerReferee,
)
from rcsssmj.sim.agent_id import AgentID
from rcsssmj.utils.geometry import AABB2D

# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------


def _make_agent(team_id: int, player_no: int, x: float, y: float) -> MagicMock:
    agent = MagicMock()
    agent.agent_id = AgentID(team_id, player_no)
    agent.xpos = [x, y, 0.0]
    return agent


def _make_game(
    left_agents: list[MagicMock],
    right_agents: list[MagicMock],
    sim_time: float = 0.0,
    field_half_x: float = 10.0,
    field_half_y: float = 7.0,
    goalie_depth: float = 2.0,
    goalie_half_y: float = 1.5,
) -> MagicMock:
    game = MagicMock()

    # field
    left_goalie_area = AABB2D(-field_half_x, -field_half_x + goalie_depth, -goalie_half_y, goalie_half_y)
    right_goalie_area = AABB2D(field_half_x - goalie_depth, field_half_x, -goalie_half_y, goalie_half_y)
    game.field.left_goalie_area = left_goalie_area
    game.field.right_goalie_area = right_goalie_area
    game.field.field_dim = (field_half_x * 2, field_half_y * 2)
    game.field.field_border = 1.0
    game.field.field_area = AABB2D(-field_half_x, field_half_x, -field_half_y, field_half_y)

    # players as Mapping[int, SoccerAgent]
    game.left_players = {a.agent_id.player_no: a for a in left_agents}
    game.right_players = {a.agent_id.player_no: a for a in right_agents}

    # game state
    game.game_state.sim_time = sim_time
    game.game_state.play_time = 0.0
    game.game_state.play_mode = MagicMock()
    game.game_state.agent_na_touch_ball = None
    game.game_state.team_na_score = None

    # ball (outside field to avoid triggering other rules)
    game.ball.xpos = [0.0, 0.0, 0.0]
    game.ball.active_contact = None
    game.ball.last_contact = None
    game.ball.contact_change = None

    # rules
    game.rules.get_end_time_for.return_value = 999.0
    game.rules.kick_off_time = -1
    game.rules.throw_in_time = -1
    game.rules.corner_kick_time = -1
    game.rules.free_kick_time = -1
    game.rules.direct_free_kick_time = -1
    game.rules.goal_kick_time = -1
    game.rules.goal_pause_time = -1

    return game


def _advance_steps(referee: SoccerReferee, game: MagicMock, n: int, dt: float = 0.02) -> None:
    """Call _check_illegal_defense() n times, incrementing sim_time by dt each step."""
    for _ in range(n):
        game.game_state.sim_time += dt
        referee._check_illegal_defense()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIllegalDefenseDetection(unittest.TestCase):
    def setUp(self):
        self.referee = SoccerReferee()

    def _make_referee_with_game(self, game: MagicMock) -> SoccerReferee:
        return SoccerReferee(game)

    # --- no violation -------------------------------------------------------

    def test_no_violation_with_two_players_in_area(self):
        """Exactly 2 left players in the left goalie area — no penalty."""
        left = [
            _make_agent(1, 1, -9.5, 0.0),
            _make_agent(1, 2, -9.0, 0.5),
        ]
        game = _make_game(left, [])
        ref = self._make_referee_with_game(game)

        _advance_steps(ref, game, _ILLEGAL_DEFENSE_DEBOUNCE_STEPS + 2)

        for agent in left:
            agent.drop_at.assert_not_called()

    def test_no_violation_with_one_player_in_area(self):
        """Only 1 left player in the area — no penalty."""
        left = [_make_agent(1, 1, -9.5, 0.0)]
        game = _make_game(left, [])
        ref = self._make_referee_with_game(game)

        _advance_steps(ref, game, _ILLEGAL_DEFENSE_DEBOUNCE_STEPS + 2)

        left[0].drop_at.assert_not_called()

    def test_no_violation_when_players_outside_area(self):
        """3 left players all outside the left goalie area — no penalty."""
        left = [
            _make_agent(1, 1, 0.0, 0.0),
            _make_agent(1, 2, 5.0, 0.0),
            _make_agent(1, 3, -5.0, 0.0),
        ]
        game = _make_game(left, [])
        ref = self._make_referee_with_game(game)

        _advance_steps(ref, game, _ILLEGAL_DEFENSE_DEBOUNCE_STEPS + 2)

        for agent in left:
            agent.drop_at.assert_not_called()

    # --- violation: debounce ------------------------------------------------

    def test_violation_not_triggered_before_debounce(self):
        """3 left players in area but fewer than DEBOUNCE_STEPS steps passed — no penalty yet."""
        left = [
            _make_agent(1, 1, -9.5, 0.0),
            _make_agent(1, 2, -9.0, 0.5),
            _make_agent(1, 3, -9.0, -0.5),
        ]
        game = _make_game(left, [])
        ref = self._make_referee_with_game(game)

        _advance_steps(ref, game, _ILLEGAL_DEFENSE_DEBOUNCE_STEPS - 1)

        for agent in left:
            agent.drop_at.assert_not_called()

    def test_violation_triggered_after_debounce(self):
        """3 left players in area for DEBOUNCE_STEPS steps — exactly one penalty."""
        left = [
            _make_agent(1, 1, -9.5, 0.0),
            _make_agent(1, 2, -9.0, 0.5),
            _make_agent(1, 3, -9.0, -0.5),
        ]
        game = _make_game(left, [])
        ref = self._make_referee_with_game(game)

        _advance_steps(ref, game, _ILLEGAL_DEFENSE_DEBOUNCE_STEPS)

        total_penalized = sum(1 for a in left if a.drop_at.called)
        assert total_penalized == 1

    def test_counter_resets_when_violation_clears(self):
        """Violation steps reset to 0 when players drop to ≤ 2 in area."""
        left = [
            _make_agent(1, 1, -9.5, 0.0),
            _make_agent(1, 2, -9.0, 0.5),
            _make_agent(1, 3, -9.0, -0.5),
        ]
        game = _make_game(left, [])
        ref = self._make_referee_with_game(game)

        _advance_steps(ref, game, _ILLEGAL_DEFENSE_DEBOUNCE_STEPS - 1)

        # third player leaves
        left[2].xpos = [0.0, 0.0, 0.0]
        _advance_steps(ref, game, 1)

        assert ref._illegal_defense_violation_steps['left'] == 0
        for agent in left:
            agent.drop_at.assert_not_called()

    # --- violation: correct agent penalized ---------------------------------

    def test_last_entrant_is_penalized(self):
        """The player that entered the area last must be the one penalized."""
        # players 1 and 2 enter at t=0, player 3 enters later
        game = _make_game([], [])
        ref = self._make_referee_with_game(game)

        p1 = _make_agent(1, 1, -9.5, 0.0)
        p2 = _make_agent(1, 2, -9.0, 0.5)
        p3 = _make_agent(1, 3, -9.0, -0.5)

        # step 1: only p1 and p2 in area
        game.game_state.sim_time = 1.0
        game.left_players = {1: p1, 2: p2, 3: p3}
        p3.xpos = [0.0, 0.0, 0.0]  # p3 outside
        ref._check_illegal_defense()

        # step 2: p3 enters the area at t=1.02
        game.game_state.sim_time = 1.02
        p3.xpos = [-9.0, -0.5, 0.0]
        ref._check_illegal_defense()

        # advance until debounce triggers
        for _ in range(_ILLEGAL_DEFENSE_DEBOUNCE_STEPS - 1):
            game.game_state.sim_time += 0.02
            ref._check_illegal_defense()

        p3.drop_at.assert_called_once()
        p1.drop_at.assert_not_called()
        p2.drop_at.assert_not_called()

    def test_first_entrant_not_penalized_when_later_entrant_present(self):
        """Player that has been in the area longest is NOT the one penalized."""
        game = _make_game([], [])
        ref = self._make_referee_with_game(game)

        p1 = _make_agent(1, 1, -9.5, 0.0)
        p2 = _make_agent(1, 2, -9.0, 0.5)
        p3 = _make_agent(1, 3, 0.0, 0.0)  # starts outside

        game.left_players = {1: p1, 2: p2, 3: p3}

        # p1 and p2 have been inside for a while
        for _ in range(3):
            game.game_state.sim_time += 0.02
            ref._check_illegal_defense()

        # p3 enters late
        game.game_state.sim_time += 0.02
        p3.xpos = [-9.0, -0.5, 0.0]
        ref._check_illegal_defense()

        # trigger debounce
        for _ in range(_ILLEGAL_DEFENSE_DEBOUNCE_STEPS):
            game.game_state.sim_time += 0.02
            ref._check_illegal_defense()

        p3.drop_at.assert_called_once()
        p1.drop_at.assert_not_called()
        p2.drop_at.assert_not_called()

    # --- right side ---------------------------------------------------------

    def test_violation_right_goalie_area(self):
        """Same logic applies symmetrically to the right goalie area."""
        right = [
            _make_agent(2, 1, 9.5, 0.0),
            _make_agent(2, 2, 9.0, 0.5),
            _make_agent(2, 3, 9.0, -0.5),
        ]
        game = _make_game([], right)
        ref = self._make_referee_with_game(game)

        _advance_steps(ref, game, _ILLEGAL_DEFENSE_DEBOUNCE_STEPS)

        total_penalized = sum(1 for a in right if a.drop_at.called)
        assert total_penalized == 1

    def test_independent_tracking_per_side(self):
        """Left and right violations are tracked independently."""
        left = [
            _make_agent(1, 1, -9.5, 0.0),
            _make_agent(1, 2, -9.0, 0.5),
            _make_agent(1, 3, -9.0, -0.5),
        ]
        right = [
            _make_agent(2, 1, 9.5, 0.0),
        ]
        game = _make_game(left, right)
        ref = self._make_referee_with_game(game)

        _advance_steps(ref, game, _ILLEGAL_DEFENSE_DEBOUNCE_STEPS)

        # exactly one left player penalized, no right player penalized
        left_penalized = sum(1 for a in left if a.drop_at.called)
        right_penalized = sum(1 for a in right if a.drop_at.called)
        assert left_penalized == 1
        assert right_penalized == 0

    # --- after penalization -------------------------------------------------

    def test_penalized_agent_removed_from_tracking(self):
        """After a penalty, the penalized agent is removed from entry-time tracking."""
        left = [
            _make_agent(1, 1, -9.5, 0.0),
            _make_agent(1, 2, -9.0, 0.5),
            _make_agent(1, 3, -9.0, -0.5),
        ]
        game = _make_game(left, [])
        ref = self._make_referee_with_game(game)

        _advance_steps(ref, game, _ILLEGAL_DEFENSE_DEBOUNCE_STEPS)

        # the penalized agent's ID should not be in entry_times anymore
        entry_times = ref._goalie_area_entry_time['left']
        penalized_agent = next(a for a in left if a.drop_at.called)
        assert penalized_agent.agent_id not in entry_times

    def test_violation_counter_resets_after_penalty(self):
        """After a penalty is applied, the violation step counter resets to 0."""
        left = [
            _make_agent(1, 1, -9.5, 0.0),
            _make_agent(1, 2, -9.0, 0.5),
            _make_agent(1, 3, -9.0, -0.5),
        ]
        game = _make_game(left, [])
        ref = self._make_referee_with_game(game)

        _advance_steps(ref, game, _ILLEGAL_DEFENSE_DEBOUNCE_STEPS)

        assert ref._illegal_defense_violation_steps['left'] == 0

    # --- constants ----------------------------------------------------------

    def test_max_players_constant(self):
        assert _ILLEGAL_DEFENSE_MAX_PLAYERS == 2

    def test_debounce_steps_constant(self):
        assert _ILLEGAL_DEFENSE_DEBOUNCE_STEPS > 0


if __name__ == '__main__':
    unittest.main()
