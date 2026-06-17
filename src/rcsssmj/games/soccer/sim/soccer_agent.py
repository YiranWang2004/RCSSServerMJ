from typing import Any, Final

import mujoco

from rcsssmj.games.soccer.sim.soccer_sim_interfaces import PSoccerSimActionInterface
from rcsssmj.sim.agent_id import AgentID
from rcsssmj.sim.sim_agent import TypedSimAgent
from rcsssmj.utils.mjutils import quat_from_axis_angle


class SoccerAgent(TypedSimAgent[PSoccerSimActionInterface]):
    """A soccer agent object in simulation."""

    def __init__(
        self,
        agent_id: AgentID,
        team_name: str,
        robot_spec: Any,
        ai: PSoccerSimActionInterface,
    ) -> None:
        """Construct a new soccer agent.

        Parameter
        ---------
        agent_id: AgentID
            The unique identifier of the agent.

        team_name: str
            The name of the team the agent belongs to.

        robot_spec: Any
            The robot model specification used for representing the agent in the simulation.

        ai: PSoccerSimActionInterface
            The soccer specific action interface reference.
        """

        super().__init__(agent_id, team_name, robot_spec)

        self.ai: Final[PSoccerSimActionInterface] = ai
        """The action interface."""

        self.torso_geom_id: int = -1
        """The cached id of the torso geometry."""

        self.torso_body_id: int = -1
        """The cached id of the torso body."""

        self.camera_site_id: int = -1
        """The cached id of the camera site."""

        self.hand_geom_ids: dict[str, int] = {}
        """Dictionary mapping hand and forearm geometry names to their ids."""

    def bind(self, mj_model: Any, mj_data: Any) -> None:
        """Bind the agent to the physics simulation.

        Parameter
        ---------
        mj_model: Any
            The mujoco simulation model.
        mj_data: Any
            The mujoco simulation data.
        """
        super().bind(mj_model, mj_data)

        self.torso_geom_id = mujoco.mj_name2id(mj_model, mujoco.mjtObj.mjOBJ_GEOM, self.agent_id.prefix + 'torso')
        self.camera_site_id = mujoco.mj_name2id(mj_model, mujoco.mjtObj.mjOBJ_SITE, self.agent_id.prefix + 'camera')
        self.torso_body_id = mujoco.mj_name2id(mj_model, mujoco.mjtObj.mjOBJ_BODY, self.root_body_name)

        self.hand_geom_ids = {}
        for i in range(mj_model.ngeom):
            geom_name = mujoco.mj_id2name(mj_model, mujoco.mjtObj.mjOBJ_GEOM, i)
            if geom_name and geom_name.startswith(self.agent_id.prefix):
                if 'hand' in geom_name or 'forearm' in geom_name:
                    self.hand_geom_ids[geom_name] = i

    def _get_action_interface(self) -> PSoccerSimActionInterface:
        return self.ai

    def drop(self) -> None:
        """Drop the agent at its current location and reset all joints."""

        base_height: float = self.spec.body(self.root_body_name).pos[2]

        self.place_at((self.xpos[0], self.xpos[1], base_height))
        self.init_joints()

    def drop_at(
        self,
        x: float = 0.0,
        y: float = 0.0,
        theta: float = 0.0,
    ) -> None:
        """Drop the agent at the specified location and reset all joints.

        Parameter
        ---------
        x: float, default=0.0
            The x-position at which to drop the agent.

        y: float, default=0.0
            The y-position at which to drop the agent.

        theta: float, default=0.0
            The horizontal orientation with which to drop the agent.
        """

        base_height: float = self.spec.body(self.root_body_name).pos[2]

        quat = quat_from_axis_angle((0, 0, 1), theta)

        self.place_at((x, y, base_height), quat)
        self.init_joints()
