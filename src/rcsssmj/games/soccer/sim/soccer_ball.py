from typing import Any

import numpy as np

from rcsssmj.sim.agent_id import AgentID
from rcsssmj.sim.sim_object import SimObject
from rcsssmj.utils.mjutils import filter_agent_contacts_with


class SoccerBall(SimObject):
    """The soccer ball object in simulation."""

    def __init__(self) -> None:
        """Construct a new soccer ball."""

        super().__init__('ball')

        self._radius: float = 0.11
        """The radius of the ball."""

        self._active_contact: AgentID | None = None
        """The currently active agent contact (can last more than one simulation cycle)."""

        self._active_contact_body_parts: set[str] | None = None
        """The body parts involved in the currently active contact."""

        self._last_contact: AgentID | None = None
        """The previous agent contact (updated after the active contact has changed / has been lost)."""

        self._contact_change: float | None = None
        """The timestep when the active agent contact changed last."""

    @property
    def radius(self) -> float:
        """The radius of the ball."""

        return self._radius

    @property
    def active_contact(self) -> AgentID | None:
        """The currently active agent contact (can last more than one simulation cycle)."""

        return self._active_contact

    @property
    def active_contact_body_parts(self) -> set[str] | None:
        """The body parts involved in the currently active contact."""

        return self._active_contact_body_parts

    @property
    def last_contact(self) -> AgentID | None:
        """The previous agent contact (updated after the active contact has changed / has been lost)."""

        return self._last_contact

    @property
    def contact_change(self) -> float | None:
        """The timestep when the agent contact changed last."""

        return self._contact_change

    def init(self, mj_spec: Any, mj_model: Any, mj_data: Any, radius: float = 0.11) -> None:
        """(Re-)Initialize the ball instance."""

        self.bind(mj_model, mj_data)

        # TODO: Fetch actual radius from model spec.

        self._prev_xpos = self.xpos.astype(np.float64)
        self._radius = radius
        self._active_contact = None
        self._active_contact_body_parts = None
        self._last_contact = None
        self._contact_change = None

    def _set_active_contact(self, contact: AgentID | None, body_parts: set[str] | None, sim_time: float) -> None:
        """Set the currently active agent contact.

        Parameter
        ---------
        contact: AgentID | None
            The agent currently in contact with the ball or None if there is no such contact at the moment.

        body_parts: set[str] | None
            The body parts of the agent currently in contact with the ball or None.

        sim_time: float
            The current simulation time.
        """

        if self._active_contact is not None:
            if self._active_contact != contact:
                self._last_contact = self._active_contact
                if contact is not None:
                    self._contact_change = sim_time
        elif contact is not None and self._last_contact != contact:
            self._contact_change = sim_time

        self._active_contact = contact
        self._active_contact_body_parts = body_parts

    def get_most_recent_contact(self) -> AgentID | None:
        """Return the most recent contact (either the active or the last contact)."""

        return self._last_contact if self._active_contact is None else self._active_contact

    def reset_contacts(self) -> None:
        """Reset agent contact information."""

        self._active_contact = None
        self._active_contact_body_parts = None
        self._last_contact = None
        self._contact_change = None

    def post_step(self, mj_model: Any, mj_data: Any) -> None:
        super().post_step(mj_model, mj_data)

        # update agent contacts
        ball_contacts = filter_agent_contacts_with('ball', mj_model, mj_data)
        if ball_contacts:
            if self._active_contact not in ball_contacts:
                active_agent = next(iter(ball_contacts))
                self._set_active_contact(active_agent, ball_contacts[active_agent], mj_data.time)
            else:
                self._active_contact_body_parts = ball_contacts[self._active_contact]
        else:
            self._set_active_contact(None, None, mj_data.time)

    def drop(self) -> None:
        """Drop the ball at its current location and reset all contacts."""

        self.place_at((self.xpos[0], self.xpos[1], self.radius))
        self.reset_contacts()

    def drop_at(self, x: float = 0.0, y: float = 0.0) -> None:
        """Drop the ball at the specified location and reset all contacts.

        Parameter
        ---------
        x: float, default=0.0
            The x-position at which to drop the ball.

        y: float, default=0.0
            The y-position at which to drop the ball.
        """

        self.place_at((x, y, self.radius))
        self.reset_contacts()
