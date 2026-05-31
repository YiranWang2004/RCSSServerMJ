from abc import ABC, abstractmethod
from typing import Any, Final, Sequence
import mujoco
import numpy as np

from rcsssmj.sim.agent_id import strip_agent_prefix, AgentID
from rcsssmj.sim.sim_agent import SimAgent
from rcsssmj.utils.geometry import Matrix4x4, matrix_4x4_mul, matrix_4x4_transpose, to_transformation_matrix, transformation_matrix_inverse


class SimStateInformation(ABC):
    """Base implementation for simulation state information."""

    def __init__(self, name: str):
        """Construct a new simulation state information.

        Parameter
        ---------
        name: str
            The state information name / id.
        """

        self.name: str = name
        """The state information name / id."""

    @abstractmethod
    def to_sexp(self, full: bool) -> str:
        """Return an symbolic expression representing this state information.

        Parameter
        ---------
        full: bool
            Whether to send a full state update.
        """


class GlobalTime(SimStateInformation):
    """Global time information,"""

    def __init__(self, time: float):
        """Construct a new global time information."""

        super().__init__('global-time')

        self.time: Final[float] = time
        """The current global time."""

    def to_sexp(self, full: bool) -> str:
        return f'((gt 1 0){self.time:.2f})'


class TransformNode:
    def __init__(self):
        self.children = []
        self.slt = tuple([0] * 16)

    def update(self, slt, init=False) -> bool:
        if init:
            self.slt = slt
            return True
        for i in range(16):
            d = abs(self.slt[i] - slt[i])
            if d > 0.005:
                self.slt = slt
                return True
        return False

    def reset(self):
        self.children = []


class SceneGraph(SimStateInformation):
    """Scene graph state information."""

    def __init__(self, mj_model: Any, mj_data: Any, body_children_map: dict[int, list[int]], sim_agents: Sequence[SimAgent], descriptions: dict[str, list[list[str]]]):
        """Construct a new scene graph state information."""

        super().__init__('scene-graph')

        self.mj_model: Final[Any] = mj_model
        """The current mujoco simulation model."""

        self.mj_data: Final[Any] = mj_data
        """The current mujoco simulation data array."""

        self.body_children_map: Final[dict[int, list[int]]] = body_children_map
        """The mapping from bodies to their children."""

        self.sim_agents: Sequence[SimAgent] = sim_agents
        """The current simulation agents."""

        self.descriptions: dict[str, list[list[str]]] = descriptions
        """The descriptions to add for the given body names."""

    def _get_sim_agent(self, id: AgentID) -> SimAgent | None:
        """Get a SimAgent for a given prefixed name."""
        for agent in self.sim_agents:
            if agent.agent_id == id:
                return agent
        return None

    def to_sexp(self, full: bool, node_cache: TransformNode=TransformNode()) -> str:
        sg = '((sg 1 0)'
        if full:
            sg += 'full'
        else:
            sg += 'diff'

        # start with root body (assuming it has id 0)
        sg += self._serialize_body(0, to_transformation_matrix((1, 0, 0, 0), (0, 0, 0)), False, not full, node_cache)

        sg += ')'

        return sg

    def _serialize_body(self, body_id: int, parent_tmat: Matrix4x4, parent_is_agent: bool, update: bool, cached_node: TransformNode):
        """Returns the serialized value of the given body."""

        body = self.mj_model.body(body_id)
        pos = self.mj_data.xpos[body_id].tolist()
        quat = self.mj_data.xquat[body_id].tolist()
        agent_id = AgentID.from_prefixed_name(body.name)
        sim_agent = self._get_sim_agent(agent_id) if agent_id is not None else None

        dsc = ''
        if not parent_is_agent and sim_agent is not None:
            dsc += f'(agent {sim_agent.team_name} {sim_agent.agent_id.player_no})'
        for desc in self.descriptions.get(body.name, []):
            dsc += f'({" ".join(desc)})'
        if dsc != '':
            if not update:
                result = f'(nd DSC{dsc}'
            else:
                result = '(nd'
        else:
            result = ''

        tmat = to_transformation_matrix(quat, pos)
        inverse_parent = transformation_matrix_inverse(parent_tmat)
        tmat_local = matrix_4x4_mul(inverse_parent, tmat)
        tmat_local = matrix_4x4_transpose(tmat_local)

        needs_update = cached_node.update(tmat_local, init=not update)
        if needs_update:
            slt = _serialize_slt(tmat_local)
            result += f'(nd TRF{slt}'
        else:
            result += '(nd'

        for geom_id in range(self.mj_model.ngeom):
            if self.mj_model.geom_bodyid[geom_id] != body_id:
                continue

            geom_pos = self.mj_model.geom_pos[geom_id]
            geom_quat = self.mj_model.geom_quat[geom_id]

            # Determine material
            mat_name = None
            mat_id = self.mj_model.geom_matid[geom_id]
            if mat_id >= 0:
                mat_name_adr = self.mj_model.name_matadr[mat_id]
                mat_name_adr_end = self.mj_model.names.find(b'\x00', mat_name_adr)
                mat_name = self.mj_model.names[mat_name_adr:mat_name_adr_end].decode('utf-8')
                mat_name = strip_agent_prefix(mat_name)
                if agent_id is not None and mat_name == 'team':
                    if agent_id.team_id == 0:
                        mat_name = 'matLeft'
                    elif agent_id.team_id == 1:
                        mat_name = 'matRight'
            if isinstance(mat_name, str):
                mat_str = f'(sMat {mat_name})'
            else:
                rgba = self.mj_model.geom_rgba[geom_id]
                mat_str = f'(rgba {rgba[0]} {rgba[1]} {rgba[2]} {rgba[3]})'

            geom_group = self.mj_model.geom_group[geom_id]
            visible = geom_group in (0, 1, 2)

            load_node = None
            scale = (1, 1, 1)
            match self.mj_model.geom_type[geom_id]:
                case mujoco.mjtGeom.mjGEOM_MESH:
                    if sim_agent is None:
                        continue
                    mesh_id = self.mj_model.geom_dataid[geom_id]

                    robot_type = sim_agent.spec.modelname
                    mesh_path_adr = self.mj_model.mesh_pathadr[mesh_id]
                    mesh_path_adr_end = self.mj_model.paths.find(b'\x00', mesh_path_adr)
                    mesh_path = self.mj_model.paths[mesh_path_adr:mesh_path_adr_end].decode('utf-8')
                    mesh_path = f'models/{robot_type}/{mesh_path}'
                    load_node = f'(load {mesh_path})'

                    scale = tuple(self.mj_model.mesh_scale[mesh_id])

                    inv_mesh_pos = np.empty(3)
                    inv_mesh_quat = np.empty(4)
                    mujoco.mju_negPose(inv_mesh_pos, inv_mesh_quat, self.mj_model.mesh_pos[mesh_id], self.mj_model.mesh_quat[mesh_id])
                    geom_pos = np.empty(3)
                    geom_quat = np.empty(4)
                    mujoco.mju_mulPose(geom_pos, geom_quat, self.mj_model.geom_pos[geom_id], self.mj_model.geom_quat[geom_id], inv_mesh_pos, inv_mesh_quat)

                case mujoco.mjtGeom.mjGEOM_BOX:
                    load_node = '(load StdUnitBox)'
                    scale = tuple(self.mj_model.geom_size[geom_id][i] * 2 for i in range(3))
                case mujoco.mjtGeom.mjGEOM_SPHERE:
                    load_node = '(load StdUnitSphere)'
                    size = self.mj_model.geom_size[geom_id][0]
                    scale = [size, size, size]
                case mujoco.mjtGeom.mjGEOM_CYLINDER:
                    load_node = '(load StdUnitCylinder)'
                    size = self.mj_model.geom_size[geom_id]
                    scale = [size[0], size[0], size[1] * 2]

            need_geom_transform = not (np.array_equal(geom_pos, [0, 0, 0]) and np.array_equal(geom_quat, [1, 0, 0, 0]))
            if need_geom_transform:
                if not update:
                    slt_mat = matrix_4x4_transpose(to_transformation_matrix(geom_quat, geom_pos))
                    slt = _serialize_slt(slt_mat)
                    result += f'(nd TRF{slt}'
                else:
                    result += '(nd'

            if load_node is not None:
                if not update:
                    scale_str = f'(sSc {scale[0]} {scale[1]} {scale[2]})' if scale[0] != 1 or scale[1] != 1 or scale[2] != 1 else ''
                    result += f'(nd SMN (setVisible {int(visible)}){load_node}{mat_str}{scale_str})'
                else:
                    result += '(nd)'

            if need_geom_transform:
                # Close geom TRF node
                result += ')'

        for i, child_id in enumerate(self.body_children_map[body_id]):
            if len(cached_node.children) > i:
                cached_child_node = cached_node.children[i]
            else:
                cached_child_node = TransformNode()
                cached_node.children.append(cached_child_node)
            result += self._serialize_body(child_id, tmat, parent_is_agent or sim_agent is not None, update, cached_child_node)

        # Close TRF node
        result += ')'

        if dsc != '':
            # Close DSC node
            result += ')'

        return result


def _serialize_slt(slt: Matrix4x4) -> str:
    """Generate an SLT attribute."""

    return f'(SLT {slt[0]:.4f} {slt[1]:.4f} {slt[2]:.4f} {slt[3]:.4f} {slt[4]:.4f} {slt[5]:.4f} {slt[6]:.4f} {slt[7]:.4f} {slt[8]:.4f} {slt[9]:.4f} {slt[10]:.4f} {slt[11]:.4f} {slt[12]:.4f} {slt[13]:.4f} {slt[14]:.4f} {slt[15]:.4f})'
