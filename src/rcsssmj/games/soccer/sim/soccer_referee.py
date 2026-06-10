import logging
from itertools import chain
from math import pi, sqrt
from typing import TYPE_CHECKING, cast

from rcsssmj.games.soccer.play_mode import PlayMode
from rcsssmj.games.soccer.sim.soccer_agent import SoccerAgent
from rcsssmj.games.soccer.sim.soccer_game import PSoccerGame
from rcsssmj.games.teams import TeamSide

if TYPE_CHECKING:
    from rcsssmj.sim.agent_id import AgentID

logger = logging.getLogger(__name__)


class SoccerReferee:
    """A referee, applying soccer game rules."""

    def __init__(self, game: PSoccerGame | None = None) -> None:
        """Create a new soccer referee.

        Parameter
        ---------
        game: PSoccerGame | None, default=None
            The soccer game instance to referee. If ``None``, the game instance must be injected from externally before calling any method of the referee.
        """

        # MYPY-HACK: The game instance may initially be `None` but will be automatically injected in this case by the simulation (cast is used to silence mypy while preventing repetitive `None` checks)
        self.game: PSoccerGame = cast('PSoccerGame', game)
        """The soccer game instance to referee."""

        self._did_act: bool = False
        """Flag if the referee has already taken a decision in this referee cycle."""

        self._last_sim_time: float = 0.0
        """The simulation time of the last referee cycle."""

        self._ground_time: dict[AgentID, float] = {}
        """Time each agent has been on the ground."""

        self._not_standing_time: dict[AgentID, float] = {}
        """Time each agent has been not standing."""

        self._standing_time: dict[AgentID, float] = {}
        """Time each agent has been standing."""

    def reset(self) -> None:
        """Reinitialize the referee."""

        # init referee state
        self._did_act = False
        self._last_sim_time = 0.0
        self._ground_time.clear()
        self._not_standing_time.clear()
        self._standing_time.clear()

    def is_beaming_allowed(self) -> bool:
        """Check if an agent is allowed to beam in the current game state."""

        return self.game.game_state.play_mode in (PlayMode.BEFORE_KICK_OFF, PlayMode.GOAL_LEFT, PlayMode.GOAL_RIGHT)

    def kick_off(self, team_side: TeamSide | int) -> None:
        """Instruct kickoff for the given team.

        Parameter
        ---------
        team_side: TeamSide | int
            The team side for which to give the kick off.
        """

        if not isinstance(team_side, TeamSide):
            team_side = TeamSide.from_id(team_side)

        self._did_act = True

        self.game.game_state.set_play_mode_for_team(team_side, PlayMode.KICK_OFF_LEFT, PlayMode.KICK_OFF_RIGHT)
        self.game.game_state.agent_na_touch_ball = None
        self.game.game_state.team_na_score = team_side

        self.game.ball.drop_at(0, 0)

    def play_on(self) -> None:
        """Instruct the normal progressing of the game."""

        self._did_act = True
        self.game.game_state.set_play_mode(PlayMode.PLAY_ON)

    def throw_in(self, team_side: TeamSide) -> None:
        """Instruct a throw in for the given team.

        Parameter
        ---------
        team_side: TeamSide
            The team side for which to give the throw in.
        """

        self._did_act = True

        self.game.game_state.set_play_mode_for_team(team_side, PlayMode.THROW_IN_LEFT, PlayMode.THROW_IN_RIGHT)
        self.game.game_state.agent_na_touch_ball = None
        self.game.game_state.team_na_score = None

        y = self.game.field.field_area.min_y if self.game.ball.xpos[1] < 0 else self.game.field.field_area.max_y
        self.game.ball.drop_at(self.game.ball.xpos[0], y)

    def corner_kick(self, team_side: TeamSide) -> None:
        """Instruct corner kick for the given team.

        Parameter
        ---------
        team_side: TeamSide
            The team side for which to give the corner kick.
        """

        self._did_act = True

        self.game.game_state.set_play_mode_for_team(team_side, PlayMode.CORNER_KICK_LEFT, PlayMode.CORNER_KICK_RIGHT)
        self.game.game_state.agent_na_touch_ball = None
        self.game.game_state.team_na_score = None

        x = self.game.field.field_area.max_x if team_side == TeamSide.LEFT else self.game.field.field_area.min_x
        y = self.game.field.field_area.min_y if self.game.ball.xpos[1] < 0 else self.game.field.field_area.max_y
        self.game.ball.drop_at(x, y)

    def goal_kick(self, team_side: TeamSide) -> None:
        """Instruct goal kick for the given team.

        Parameter
        ---------
        team_side: TeamSide
            The team side for which to give the goal kick.
        """

        self._did_act = True

        self.game.game_state.set_play_mode_for_team(team_side, PlayMode.GOAL_KICK_LEFT, PlayMode.GOAL_KICK_RIGHT)
        self.game.game_state.agent_na_touch_ball = None
        self.game.game_state.team_na_score = None

        drop_pos = self.game.field.left_goalie_area.center() if team_side == TeamSide.LEFT else self.game.field.right_goalie_area.center()
        self.game.ball.drop_at(drop_pos[0], drop_pos[1])

    def offsite(self, team_side: TeamSide) -> None:
        """Offsite state for the given team.

        Parameter
        ---------
        team_side: TeamSide
            The team side for which to give the offside.
        """

        self._did_act = True
        self.game.game_state.set_play_mode_for_team(team_side, PlayMode.OFFSIDE_LEFT, PlayMode.OFFSIDE_RIGHT)

    def game_over(self) -> None:
        """Instruct the end of the game."""

        self._did_act = True

        self.game.game_state.set_play_mode(PlayMode.GAME_OVER)
        self.game.game_state.agent_na_touch_ball = None
        self.game.game_state.team_na_score = None

        self.game.ball.reset_contacts()

    def goal(self, team_side: TeamSide) -> None:
        """Count a goal for the given team and set the play mode accordingly.

        Parameter
        ---------
        team_side: TeamSide
            The team side for which to give the goal.
        """

        self._did_act = True

        self.game.game_state.goal(team_side)

    def free_kick(self, team_side: TeamSide) -> None:
        """Instruct an indirect free kick for the given team.

        Parameter
        ---------
        team_side: TeamSide
            The team side for which to give the free kick.
        """

        self._did_act = True

        self.game.game_state.set_play_mode_for_team(team_side, PlayMode.FREE_KICK_LEFT, PlayMode.FREE_KICK_RIGHT)
        self.game.game_state.agent_na_touch_ball = None
        self.game.game_state.team_na_score = team_side

        self.game.ball.drop()

    def direct_free_kick(self, team_side: TeamSide) -> None:
        """Instruct a direct free kick for the given team.

        Parameter
        ---------
        team_side: TeamSide
            The team side for which to give the direct free kick.
        """

        self._did_act = True

        self.game.game_state.set_play_mode_for_team(team_side, PlayMode.DIRECT_FREE_KICK_LEFT, PlayMode.DIRECT_FREE_KICK_RIGHT)
        self.game.game_state.agent_na_touch_ball = None
        self.game.game_state.team_na_score = None

        self.game.ball.drop()

    def penalty_kick(self, team_side: TeamSide) -> None:
        """Instruct a penalty kick for the given team.

        Parameter
        ---------
        team_side: TeamSide
            The team side for which to give the penalty kick.
        """

        self._did_act = True

        self.game.game_state.set_play_mode_for_team(team_side, PlayMode.PENALTY_KICK_LEFT, PlayMode.PENALTY_KICK_RIGHT)
        self.game.game_state.agent_na_touch_ball = None
        self.game.game_state.team_na_score = None

        penalty_spot_x = self.game.field.field_area.max_x - self.game.field.penalty_spot_distance
        self.game.ball.drop_at(-penalty_spot_x if team_side == TeamSide.LEFT else penalty_spot_x)

    def penalty_shoot(self, team_side: TeamSide) -> None:
        """Instruct a penalty shoot for the given team.

        Parameter
        ---------
        team_side: TeamSide
            The team side for which to give the penalty shoot.
        """

        self._did_act = True
        self.game.game_state.set_play_mode_for_team(team_side, PlayMode.PENALTY_SHOOT_LEFT, PlayMode.PENALTY_SHOOT_RIGHT)
        # TODO: place ball for penalty-shoot

    def drop_ball(self, pos: tuple[float, float] | None = None) -> None:
        """Drop the ball at the specified position and instruct the normal progressing of the game.

        Parameter
        ---------
        pos: tuple[float, float] | None, default=None
            The position at which to drop the ball or none, to drop it at its current location.
        """

        self._did_act = True
        if pos is not None:
            self.game.ball.drop_at(pos[0], pos[1])
        else:
            self.game.ball.drop()
        # TODO: cause relocation of all agents nearby the ball (within a radius defined here)

        self.game.game_state.set_play_mode(PlayMode.PLAY_ON)

    def referee(self) -> None:
        """Referee the current game situation."""

        # update game state times
        self.game.game_state.update(self.game.sim_time, progress_play_time=self.game.game_state.play_mode not in (PlayMode.BEFORE_KICK_OFF, PlayMode.GAME_OVER))

        # check game over
        if self.game.game_state.play_time >= self.game.rules.get_end_time_for(self.game.game_state.phase):
            self.game_over()
            return

        # check for rule violations
        self._check_fouls()

        # automatically progress play mode based on timeouts, object locations and action triggers
        self._check_timeouts()
        self._check_location_triggers()
        self._check_contact_triggers()

        # penalize misplaced players (according to play mode restrictions)
        self._penalize_misplaced_players()

        # reset decision flag
        self._did_act = False

    def _check_fouls(self) -> None:
        """Check fouls / violations of game rules."""

        active_ball_contact = self.game.ball.active_contact
        last_ball_contact = self.game.ball.last_contact
        last_ball_contact_change = self.game.ball.contact_change
        agent_na_touch_ball = self.game.game_state.agent_na_touch_ball
        sim_time = self.game.game_state.sim_time

        # check no score rule
        if self.game.game_state.team_na_score is not None and active_ball_contact is not None and last_ball_contact is not None:
            self.game.game_state.team_na_score = None

        # check double-touch rule
        if agent_na_touch_ball is not None and active_ball_contact is not None and last_ball_contact is not None:
            if agent_na_touch_ball == last_ball_contact and agent_na_touch_ball == active_ball_contact:
                if last_ball_contact_change is not None and sim_time - last_ball_contact_change > 1:
                    self.free_kick(TeamSide.get_opposing_side(agent_na_touch_ball.team_id))
                    return
            else:
                self.game.game_state.agent_na_touch_ball = None

        # check for incapable fouls
        self._check_incapable_fouls()

    def _check_incapable_fouls(self) -> None:
        """Check for incapable fouls (players laying on the ground for too long)."""

        sim_time = self.game.game_state.sim_time
        dt = sim_time - self._last_sim_time
        self._last_sim_time = sim_time

        if self.game.game_state.play_mode == PlayMode.BEFORE_KICK_OFF:
            return

        ground_z_val = 0.15
        middle_z_val = 0.25
        field_width = self.game.field.field_dim[1]

        out_of_bounds_y = (field_width / 2.0) + 0.1
        goalie_ground_max = self.game.rules.goalie_ground_max_time
        goalie_not_standing_max = self.game.rules.goalie_not_standing_max_time
        ground_max = self.game.rules.ground_max_time
        not_standing_max = self.game.rules.not_standing_max_time

        for agent in chain(self.game.left_players.values(), self.game.right_players.values()):
            a_id = agent.agent_id

            if a_id not in self._ground_time:
                self._ground_time[a_id] = 0.0
                self._not_standing_time[a_id] = 0.0
                self._standing_time[a_id] = 0.0

            # Only check if agent is inside the field (+ 0.1 margin)
            if abs(agent.xpos[1]) > out_of_bounds_y:
                self._ground_time[a_id] = 0.0
                self._not_standing_time[a_id] = 0.0
                self._standing_time[a_id] = 0.0
                continue

            z_pos = agent.xpos[2]

            if z_pos < middle_z_val:
                self._not_standing_time[a_id] += dt
                self._standing_time[a_id] = 0.0

            if z_pos < ground_z_val:
                self._ground_time[a_id] += dt

            if z_pos >= middle_z_val:
                self._standing_time[a_id] += dt
                self._ground_time[a_id] = 0.0

            if self._standing_time[a_id] > 0.5:
                self._not_standing_time[a_id] = 0.0

            if a_id.player_no == 1:
                if self._ground_time[a_id] > goalie_ground_max:
                    self._penalize(agent)
                    self._ground_time[a_id] = 0.0
                elif self._not_standing_time[a_id] > goalie_not_standing_max:
                    self._penalize(agent)
                    self._not_standing_time[a_id] = 0.0
            elif self._ground_time[a_id] > ground_max:
                self._penalize(agent)
                self._ground_time[a_id] = 0.0
            elif self._not_standing_time[a_id] > not_standing_max:
                self._penalize(agent)
                self._not_standing_time[a_id] = 0.0

    def _check_timeouts(self) -> None:
        """Check timeouts (kick-off time, throw-in time, etc.) for the current play mode."""

        if self._did_act:
            # the referee has already taken a decision in this simulation cycle
            return

        pm = self.game.game_state.play_mode

        if pm == PlayMode.PLAY_ON:
            # shortcut, as remaining rules only apply to other states than play-on
            return

        def check_timeout(timeout: int, *play_modes: PlayMode) -> bool:
            """Helper function for checking a play mode specific timeout."""
            return timeout >= 0 and pm in play_modes and self.game.game_state.get_play_mode_age() > timeout

        # check kick-off, throw-in, corner-kick and free-kick times
        if (
            check_timeout(self.game.rules.kick_off_time, PlayMode.KICK_OFF_LEFT, PlayMode.KICK_OFF_RIGHT)
            or check_timeout(self.game.rules.throw_in_time, PlayMode.THROW_IN_LEFT, PlayMode.THROW_IN_RIGHT)
            or check_timeout(self.game.rules.corner_kick_time, PlayMode.CORNER_KICK_LEFT, PlayMode.CORNER_KICK_RIGHT)
            or check_timeout(self.game.rules.free_kick_time, PlayMode.FREE_KICK_LEFT, PlayMode.FREE_KICK_RIGHT)
            or check_timeout(self.game.rules.direct_free_kick_time, PlayMode.DIRECT_FREE_KICK_LEFT, PlayMode.DIRECT_FREE_KICK_RIGHT)
        ):
            self.play_on()
            return

        # check goal-kick times
        if check_timeout(self.game.rules.goal_kick_time, PlayMode.GOAL_KICK_LEFT):
            # drop ball at a corner of the left goalie area
            self.drop_ball((self.game.field.left_goalie_area.max_x, self.game.field.left_goalie_area.max_y))
            return

        if check_timeout(self.game.rules.goal_kick_time, PlayMode.GOAL_KICK_RIGHT):
            self.drop_ball((self.game.field.right_goalie_area.min_x, self.game.field.right_goalie_area.max_y))
            return

        # check goal pause time
        if pm == PlayMode.GOAL_LEFT and self.game.game_state.get_play_mode_age() > self.game.rules.goal_pause_time:
            self.kick_off(TeamSide.RIGHT)
            return

        if pm == PlayMode.GOAL_RIGHT and self.game.game_state.get_play_mode_age() > self.game.rules.goal_pause_time:
            self.kick_off(TeamSide.LEFT)
            return

    def _check_location_triggers(self) -> None:
        """Check location triggers (ball leaving the field in play-on, leaving the goalie-area in goal-kick, etc.) for the current play mode."""

        if self._did_act:
            # the referee has already taken a decision in this simulation cycle
            return

        pm = self.game.game_state.play_mode

        if pm in (PlayMode.GOAL_LEFT, PlayMode.GOAL_RIGHT):
            # no location triggers in goal states
            return

        # check left goal
        if self.game.field.left_goal_box.contains(self.game.ball.xpos[0], self.game.ball.xpos[1], self.game.ball.xpos[2]):
            if pm == PlayMode.GOAL_KICK_LEFT:
                # drop ball at a corner of the left goalie area
                self.drop_ball((self.game.field.left_goalie_area.max_x, self.game.field.left_goalie_area.max_y))
            elif self.game.game_state.team_na_score == TeamSide.RIGHT:
                self.goal_kick(TeamSide.LEFT)
            else:
                self.goal(TeamSide.RIGHT)
            return

        # check right goal
        if self.game.field.right_goal_box.contains(self.game.ball.xpos[0], self.game.ball.xpos[1], self.game.ball.xpos[2]):
            if pm == PlayMode.GOAL_KICK_RIGHT:
                # drop ball at a corner of the left goalie area
                self.drop_ball((self.game.field.right_goalie_area.min_x, self.game.field.right_goalie_area.max_y))
            elif self.game.game_state.team_na_score == TeamSide.LEFT:
                self.goal_kick(TeamSide.RIGHT)
            else:
                self.goal(TeamSide.LEFT)
            return

        # check if the ball left the field
        if not self.game.field.field_area.contains(self.game.ball.xpos[0], self.game.ball.xpos[1]):
            agent_contact = self.game.ball.get_most_recent_contact()
            last_team_contact = TeamSide.UNKNOWN if agent_contact is None else TeamSide.from_id(agent_contact.team_id)

            if self.game.ball.xpos[0] < self.game.field.field_area.min_x:
                # corner-kick right / goal-kick left
                if last_team_contact == TeamSide.LEFT:
                    self.corner_kick(TeamSide.RIGHT)
                else:
                    self.goal_kick(TeamSide.LEFT)

            elif self.game.ball.xpos[0] > self.game.field.field_area.max_x:
                # corner-kick left / goal-kick right
                if last_team_contact == TeamSide.RIGHT:
                    self.corner_kick(TeamSide.LEFT)
                else:
                    self.goal_kick(TeamSide.RIGHT)

            # elif self.game.ball.xpos[1] < -self.game.field.field_area.min_y or self.game.ball.xpos[1] > self.game.field.field_area.max_y:
            else:
                # throw-in
                self.throw_in(TeamSide.get_opposing_side(last_team_contact))

            return

        # check if ball left the goalie area on goal-kick
        if (pm == PlayMode.GOAL_KICK_LEFT and not self.game.field.left_goalie_area.contains(self.game.ball.xpos[0], self.game.ball.xpos[1])) or (
            pm == PlayMode.GOAL_KICK_RIGHT and not self.game.field.right_goalie_area.contains(self.game.ball.xpos[0], self.game.ball.xpos[1])
        ):
            self.play_on()
            return

    def _check_contact_triggers(self) -> None:
        """Check contact action triggers (touching the ball in kick-off, throw-in, etc.) for the current play mode."""

        if self._did_act:
            # the referee has already taken a decision in this simulation cycle
            return

        if self.game.ball.active_contact is None:
            # no action trigger
            return

        pm = self.game.game_state.play_mode

        if pm == PlayMode.PLAY_ON:
            # shortcut, as remaining rules only apply to other states than play-on
            return

        # kick-off, throw-in, corner-kick and free kicks
        if pm in (
            PlayMode.KICK_OFF_LEFT,
            PlayMode.KICK_OFF_RIGHT,
            PlayMode.THROW_IN_LEFT,
            PlayMode.THROW_IN_RIGHT,
            PlayMode.CORNER_KICK_LEFT,
            PlayMode.CORNER_KICK_RIGHT,
            PlayMode.FREE_KICK_LEFT,
            PlayMode.FREE_KICK_RIGHT,
            PlayMode.DIRECT_FREE_KICK_LEFT,
            PlayMode.DIRECT_FREE_KICK_RIGHT,
        ):
            if len(self.game.get_players(self.game.ball.active_contact.team_id)) > 1:
                self.game.game_state.agent_na_touch_ball = self.game.ball.active_contact

            self.play_on()
            return

    def _penalize_misplaced_players(self) -> None:
        """Check if players are within areas they are not allowed in and, in case, penalize them accordingly."""

        pm = self.game.game_state.play_mode

        if pm == PlayMode.KICK_OFF_LEFT:
            self._check_placement_for_kick_off_left()

        elif pm == PlayMode.KICK_OFF_RIGHT:
            self._check_placement_for_kick_off_right()

        elif pm == PlayMode.GOAL_KICK_LEFT:
            self._check_placement_for_goal_kick_left()

        elif pm == PlayMode.GOAL_KICK_RIGHT:
            self._check_placement_for_goal_kick_right()

        elif pm in (PlayMode.THROW_IN_LEFT, PlayMode.CORNER_KICK_LEFT, PlayMode.FREE_KICK_LEFT, PlayMode.DIRECT_FREE_KICK_LEFT):
            self._check_placement_for_free_kick_left()

        elif pm in (PlayMode.THROW_IN_RIGHT, PlayMode.CORNER_KICK_RIGHT, PlayMode.FREE_KICK_RIGHT, PlayMode.DIRECT_FREE_KICK_RIGHT):
            self._check_placement_for_free_kick_right()

    def _check_placement_for_kick_off_left(self) -> None:
        """Penalize all players of the left team that are on the right side and all players of the right team that are on the left side or within the middle circle."""

        cc_radius = self.game.field.center_circle_radius
        kickoff_agent = None
        kickoff_agent_dist = cc_radius
        for agent in self.game.left_players.values():
            if agent.xpos[0] > 0:
                # agent is in opponent half --> check if it is the closest agent to the center
                dist_to_center = sqrt(agent.xpos[0] ** 2 + agent.xpos[1] ** 2)
                if dist_to_center > kickoff_agent_dist:
                    # not kickoff agent or outside the center circle --> penalize
                    self._penalize(agent)
                else:
                    # closer to center as the kickoff agent --> penalize previously considered kickoff agent
                    if kickoff_agent is not None:
                        self._penalize(kickoff_agent)

                    kickoff_agent = agent
                    kickoff_agent_dist = dist_to_center

        for agent in self.game.right_players.values():
            if agent.xpos[0] < 0 or sqrt(agent.xpos[0] ** 2 + agent.xpos[1] ** 2) < cc_radius:
                self._penalize(agent)

    def _check_placement_for_kick_off_right(self) -> None:
        """Penalize all players of the left team that are on the right side or within the middle circle and all players of the right team that are on the left side."""

        cc_radius = self.game.field.center_circle_radius
        for agent in self.game.left_players.values():
            if agent.xpos[0] > 0 or sqrt(agent.xpos[0] ** 2 + agent.xpos[1] ** 2) < cc_radius:
                self._penalize(agent)

        kickoff_agent = None
        kickoff_agent_dist = cc_radius
        for agent in self.game.right_players.values():
            if agent.xpos[0] < 0:
                # agent is in opponent half --> check if it is the closest agent to the center
                dist_to_center = sqrt(agent.xpos[0] ** 2 + agent.xpos[1] ** 2)
                if dist_to_center > kickoff_agent_dist:
                    # not kickoff agent or outside the center circle --> penalize
                    self._penalize(agent)
                else:
                    # closer to center as the kickoff agent --> penalize previously considered kickoff agent
                    if kickoff_agent is not None:
                        self._penalize(kickoff_agent)

                    kickoff_agent = agent
                    kickoff_agent_dist = dist_to_center

    def _check_placement_for_goal_kick_left(self) -> None:
        """Penalize all players of the right team that are within the left goalie area."""

        area = self.game.field.left_goalie_area

        for agent in self.game.right_players.values():
            if area.contains(agent.xpos[0], agent.xpos[1]):
                self._penalize(agent)

    def _check_placement_for_goal_kick_right(self) -> None:
        """Penalize all players of the left team that are within the right goalie area."""

        area = self.game.field.right_goalie_area

        for agent in self.game.left_players.values():
            if area.contains(agent.xpos[0], agent.xpos[1]):
                self._penalize(agent)

    def _check_placement_for_free_kick_left(self) -> None:
        """Penalize all players of the right team that are within the center circle radius to the ball."""

        ball_x = self.game.ball.xpos[0]
        ball_y = self.game.ball.xpos[1]
        cc_radius = self.game.field.center_circle_radius

        for agent in self.game.right_players.values():
            if sqrt((agent.xpos[0] - ball_x) ** 2 + (agent.xpos[1] - ball_y) ** 2) < cc_radius:
                self._penalize(agent)

    def _check_placement_for_free_kick_right(self) -> None:
        """Penalize all players of the left team that are within the center circle radius to the ball."""

        ball_x = self.game.ball.xpos[0]
        ball_y = self.game.ball.xpos[1]
        cc_radius = self.game.field.center_circle_radius

        for agent in self.game.left_players.values():
            if sqrt((agent.xpos[0] - ball_x) ** 2 + (agent.xpos[1] - ball_y) ** 2) < cc_radius:
                self._penalize(agent)

    def _penalize(self, player: SoccerAgent) -> None:
        """Penalize the given player."""

        # choose upper / lower field border based on ball position
        y_side = -1 if self.game.ball.xpos[1] > 0 else 1

        x = 0.0
        y = y_side * ((self.game.field.field_dim[1] / 2) + self.game.field.field_border)

        # Extract other player locations once to avoid nested looping
        other_players = [(a.xpos[0], a.xpos[1]) for a in chain(self.game.left_players.values(), self.game.right_players.values()) if a != player]

        # check for free space in 2m steps
        x_step = -2.0 if player.agent_id.team_id == TeamSide.LEFT.value else 2.0
        is_occupied = True
        while is_occupied:
            x += x_step

            # check location for collisions
            for ax, ay in other_players:
                # use distance squared to avoid calculating sqrt each time
                if (ax - x) ** 2 + (ay - y) ** 2 < 1.0:
                    # other player is occupying the location already
                    break
            else:
                is_occupied = False

        player.drop_at(x, y, -pi * y_side / 2)


class KickChallengeReferee(SoccerReferee):
    """A referee, applying soccer game rules for a kick-challenge."""

    def __init__(self, game: PSoccerGame | None = None) -> None:
        """Create a new kick challenge referee.

        Parameter
        ---------
        game: PSoccerGame | None, default=None
            The soccer game instance to referee. If ``None``, the game instance must be injected from externally before calling any method of the referee.
        """

        super().__init__(game)

        self._start_time: float = -1
        """The time at which to automatically start the game."""

    def reset(self) -> None:
        super().reset()

        self._start_time = -1

    def referee(self) -> None:
        # check if an agent is connected
        if self._start_time < 0 and len(self.game.get_players(TeamSide.LEFT)) > 0:
            self._start_time = self.game.game_state.sim_time + 2

        # automatically kick-off left 2 seconds after the first agent connected
        if self.game.game_state.play_mode == PlayMode.BEFORE_KICK_OFF and self._start_time >= 0 and self._start_time <= self.game.game_state.sim_time:
            self.kick_off(TeamSide.LEFT)

        # forward to base class
        super().referee()

        # calculate challenge score
        if self.game.game_state.play_mode != PlayMode.GAME_OVER:
            score = int((self.game.ball.xpos[0] - abs(self.game.ball.xpos[1])) * 100)
            self.game.game_state.set_score(TeamSide.LEFT, score)

    def _check_fouls(self) -> None:
        # disable no score rule
        self.game.game_state.team_na_score = None

        # check double-touch rule
        if self.game.ball.active_contact is not None and self.game.ball.active_contact == self.game.ball.last_contact:
            self.game_over()

    def _check_location_triggers(self) -> None:
        # no location triggers in challenge
        return

    def _penalize_misplaced_players(self) -> None:
        # no misplacement of agents in challenges
        return
