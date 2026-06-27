from typing import Final

from rcsssmj.games.soccer.play_mode import PlayMode
from rcsssmj.games.soccer.sim.soccer_referee import Foul
from rcsssmj.games.soccer.soccer_fields import SoccerField
from rcsssmj.games.soccer.soccer_rules import SoccerRules
from rcsssmj.sim.agent_id import AgentID
from rcsssmj.sim.state_info import SimStateInformation


class SoccerEnvironmentInformation(SimStateInformation):
    """Soccer environment state information."""

    def __init__(self, field: SoccerField, rules: SoccerRules, ball_radius: float):
        """Construct a new soccer environment state information.

        Parameter
        ---------
        field: SoccerField
            The soccer field specification.

        rules: SoccerRules
            The active soccer rule book.

        ball_radius: float
            The ball radius.
        """

        super().__init__('soccer-env')

        self.field: Final[SoccerField] = field
        """The soccer field specification."""

        self.rules: Final[SoccerRules] = rules
        """The active soccer rule book."""

        self.ball_radius: Final[float] = ball_radius
        """The ball radius."""

    def to_sexp(self, full: bool) -> str:
        if not full:
            return ''
        ge = f'((ge 1 0)(FieldLength {self.field.field_dim[0]})(FieldWidth {self.field.field_dim[1]})(FieldHeight {self.field.field_dim[2]})(GoalWidth {self.field.goal_dim[0]})(GoalDepth {self.field.goal_dim[1]})(GoalHeight {self.field.goal_dim[2]})(BorderSize {self.field.line_width})(FreeKickDistance 0)(BallRadius {self.ball_radius})(RuleGoalPauseTime {self.rules.goal_pause_time})(RuleHalfTime {self.rules.half_time})(play_modes {" ".join([pm.value for pm in PlayMode])})(CenterCircleRadius {self.field.center_circle_radius})(CorderAreaRadius {self.field.corner_area_radius})(GoalieAreaLength {self.field.goalie_area_dim[0]})(GoalieAreaWidth {self.field.goalie_area_dim[1]})(PenaltySpotDistance {self.field.penalty_spot_distance})'
        if self.field.penalty_area_dim is not None:
            ge += f'(PenaltyAreaLength {self.field.penalty_area_dim[0]})(PenaltyAreaWidth {self.field.penalty_area_dim[1]})'
        ge += ')'
        return ge


class SoccerGameInformation(SimStateInformation):
    """Soccer game state information."""

    def __init__(
        self,
        rules: SoccerRules,
        left_team: str,
        right_team: str,
        left_score: int,
        right_score: int,
        play_time: float,
        play_mode: PlayMode,
        fouls: dict[AgentID, list[Foul]],
    ):
        """Construct a new soccer game state information.

        Parameter
        ---------
        rules: SoccerRules
            The active soccer rule book.

        left_team: str
            The name of the left team.

        right_team: str
            The name of the right team.

        left_score: int
            The score of the left team.

        right_score: int
            The score of the right team.

        play_time: float
            The current play time.

        play_mode: PlayMode
            The current play mode.

        fouls: dict[AgentID, list[Foul]]
            The fouls given in this cycle.
        """

        super().__init__('soccer-game')

        self.rules: Final[SoccerRules] = rules
        """The active soccer rule book."""

        self.left_team: Final[str] = left_team
        """The name of the left team."""

        self.right_team: Final[str] = right_team
        """The name of the right team."""

        self.left_score: Final[int] = left_score
        """The score of the left team."""

        self.right_score: Final[int] = right_score
        """The score of the right team."""

        self.play_time: Final[float] = play_time
        """The current play time."""

        self.play_mode: Final[PlayMode] = play_mode
        """The current play mode."""

        self.fouls: Final[dict[AgentID, list[Foul]]] = fouls
        """The current play mode."""

    def to_sexp(self, full: bool) -> str:
        gi = [f'((gs 1 0)(time {self.play_time})(half {2 if self.play_time > self.rules.half_time else 1})(score_left {self.left_score})(score_right {self.right_score})(play_mode {[pm for pm in PlayMode].index(self.play_mode)})']
        if full:
            gi.append(f'(team_left {self.left_team})(team_right {self.right_team})')
        for agent, fouls in self.fouls.items():
            for foul in fouls:
                gi.append(f'(foul {foul} {agent.team_id} {agent.player_no})')
        gi.append(')')
        return ''.join(gi)
