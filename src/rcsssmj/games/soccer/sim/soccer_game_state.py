from rcsssmj.games.soccer.game_phase import GamePhase
from rcsssmj.games.soccer.play_mode import PlayMode
from rcsssmj.games.teams import TeamSide


class GameState:
    """A game state."""

    def __init__(
        self,
        phase: GamePhase = GamePhase.FIRST_HALF,
        play_time: float = 0.0,
        *,
        sim_time: float = 0.0,
    ) -> None:
        """Construct a new game state.

        Parameter
        ---------
        phase: GamePhase, default=GamePhase.FIRST_HALF
            The initial game phase (first half, second half, etc.).

        play_time: float, default=0.0
            The initial play time in seconds.

        sim_time: float
            The initial simulation time in seconds.
        """

        self._phase: GamePhase = phase
        """The current soccer game phase (first half, second half, etc.)."""

        self._sim_time: float = sim_time
        """The current simulation time in seconds."""

        self._play_time_ms: int = int(play_time * 1000)
        """The current play time in milliseconds (to circumvent accumulation errors)."""

        self._play_time: float = play_time
        """The current play time in seconds."""

        self._play_mode: PlayMode = PlayMode.BEFORE_KICK_OFF
        """The current play mode."""

        self._play_mode_history: dict[PlayMode, float] = {pm: 0.0 for pm in PlayMode}
        """The play mode time history."""

        self._left_team_name: str | None = None
        """The name of the left team or ``None`` in case no team connected, yet."""

        self._right_team_name: str | None = None
        """The name of the right team or ``None`` in case no second team connected, yet."""

        self.left_team_score: int = 0
        """The current score of the left team."""

        self.right_team_score: int = 0
        """The current score of the right team."""

    def reset(
        self,
        phase: GamePhase = GamePhase.FIRST_HALF,
        play_time: float = 0.0,
    ) -> None:
        """Reinitialize game state.

        Parameter
        ---------
        phase: GamePhase, default=GamePhase.FIRST_HALF
            The initial game phase (first half, second half, etc.).

        play_time: float, default=0.0
            The initial play time in seconds.
        """

        self._phase = phase
        self._sim_time = 0.0
        self._play_time_ms = int(play_time * 1000)
        self._play_time = play_time
        self._play_mode = PlayMode.BEFORE_KICK_OFF
        self._play_mode_history = {pm: 0.0 for pm in PlayMode}

        self._left_team_name = None
        self._right_team_name = None

        self.left_team_score = 0
        self.right_team_score = 0

        self.agent_na_touch_ball = None
        self.team_na_score = None

    @property
    def phase(self) -> GamePhase:
        """The current game phase (first half, second half, etc.)."""

        return self._phase

    def switch_phase(self, phase: GamePhase, play_time: float) -> None:
        """Switch the current game phase and set the corresponding play time.

        Parameter
        ---------
        phase: GamePhase
            The new game phase.

        play_time: float
            The initial play time for the given game phase.
        """

        self._phase = phase
        self._play_time_ms = int(play_time * 1000)
        self._play_time = play_time

        # reset play mode and clear play mode history
        self._play_mode = PlayMode.BEFORE_KICK_OFF
        self._play_mode_history = {pm: 0.0 for pm in PlayMode}

        # reset "not-allowed" flags
        self.agent_na_touch_ball = None
        self.team_na_score = None

    @property
    def sim_time(self) -> float:
        """The current simulation time."""

        return self._sim_time

    @property
    def play_time(self) -> float:
        """The current play time."""

        return self._play_time

    @property
    def play_mode(self) -> PlayMode:
        """The current play mode."""

        return self._play_mode

    @property
    def left_team_name(self) -> str | None:
        """The name of the left team or ``None`` in case no team connected, yet."""

        return self._left_team_name

    @property
    def right_team_name(self) -> str | None:
        """The name of the right team or ``None`` in case no second team connected, yet."""

        return self._right_team_name

    def get_team_name(self, side: TeamSide) -> str | None:
        """Return the team name for the given team side."""

        if side == TeamSide.UNKNOWN:
            return None

        return self._left_team_name if side == TeamSide.LEFT else self._right_team_name

    def get_team_score(self, side: TeamSide) -> int:
        """Return the team score for the given team side."""

        if side == TeamSide.UNKNOWN:
            return 0

        return self.left_team_score if side == TeamSide.LEFT else self.right_team_score

    @property
    def is_draw(self) -> bool:
        """Check if scores are equal."""

        return self.left_team_score == self.right_team_score

    def get_play_mode_time(self, play_mode: PlayMode | None = None) -> float:
        """Return the play time given play mode has last been activated.

        Parameter
        ---------
        play_mode: PlayMode | None, default=None
            The play mode for which to return the last activation time, or None to use the currently active play mode.
        """

        return self._play_mode_history[self._play_mode if play_mode is None else play_mode]

    def get_play_mode_age(self, play_mode: PlayMode | None = None) -> float:
        """Return the play time that has passed since the play mode has been set.

        Parameter
        ---------
        play_mode: PlayMode | None, default=None
            The play mode for which to return the age, or None to use the currently active play mode.
        """

        return self._play_time - self._play_mode_history[self._play_mode if play_mode is None else play_mode]

    def update_team_names(self, team_name: str) -> None:
        """Update the available team names of the game."""

        if self._left_team_name is None:
            self._left_team_name = team_name
        elif self._left_team_name != team_name and self._right_team_name is None:
            self._right_team_name = team_name
        else:
            # no third team allowed!
            pass

    def get_team_side(self, team_name: str) -> TeamSide:
        """Return the team side for the given team name."""

        if self._left_team_name == team_name:
            return TeamSide.LEFT

        if self._right_team_name == team_name:
            return TeamSide.RIGHT

        return TeamSide.UNKNOWN

    def set_play_mode(self, play_mode: PlayMode) -> None:
        """Set the play mode of the game state.

        Parameter
        ---------
        play_mode: PlayMode
            The new play mode to set.
        """

        self._play_mode = play_mode
        self._play_mode_history[play_mode] = self._play_time

    def set_play_mode_for_team(self, team_side: TeamSide, play_mode_left: PlayMode, play_mode_right: PlayMode) -> None:
        """Set the play mode of the game state based on the given team side.

        Parameter
        ---------
        team_side: TeamSide
            The team side.

        play_mode_left: PlayMode
            The play mode for the left team side.

        play_mode_right: PlayMode
            The play mode for the right team side.
        """

        if team_side == TeamSide.LEFT:
            self.set_play_mode(play_mode_left)

        elif team_side == TeamSide.RIGHT:
            self.set_play_mode(play_mode_right)

    def set_score(self, team_side: TeamSide, score: int) -> None:
        """Set the score for the given team.

        Parameter
        ---------
        team_side: TeamSide
            The team for which to set the score.

        score: int
            The team score.
        """

        if team_side == TeamSide.LEFT:
            self.left_team_score = score

        elif team_side == TeamSide.RIGHT:
            self.right_team_score = score

    def update(self, sim_time: float, *, progress_play_time: bool = True) -> None:
        """Update the game state with the given simulation time.

        Parameter
        ---------
        sim_time: float
            The current simulation time.

        progress_play_time: bool = True
            Flag if the play time should be progressed based on simulation time.
        """

        dt = sim_time - self._sim_time
        self._sim_time = sim_time

        if progress_play_time:
            self._play_time_ms += int(0.5 + dt * 1000)
            self._play_time = self._play_time_ms / 1000.0

    def goal(self, team_side: TeamSide) -> None:
        """Count a goal for the given team and set the play mode accordingly.

        Parameter
        ---------
        team_side: TeamSide
            The team side for which to give the goal.
        """

        if team_side == TeamSide.LEFT:
            self.left_team_score += 1
            self.set_play_mode(PlayMode.GOAL_LEFT)

        elif team_side == TeamSide.RIGHT:
            self.right_team_score += 1
            self.set_play_mode(PlayMode.GOAL_RIGHT)

        self.agent_na_touch_ball = None
        self.team_na_score = None
