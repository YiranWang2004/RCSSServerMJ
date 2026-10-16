from typing import Protocol, runtime_checkable


@runtime_checkable
class PSimActionInterface(Protocol):
    """Protocol for a soccer action interface."""

    def ctrl_motor(
        self,
        name: str,
        q: float,
        dq: float,
        kp: float,
        kd: float,
        tau: float,
        max_torque: float | None = None,
    ) -> None:
        """Command a motor movement, which produces a torque on the actuator via a PD controller:

        ``applied_torque = kp * (q - q_current) + kd * (dq - dq_current) + tau``

        Parameter
        ---------
        name : str
            The name of the motor actuator.

        q : float
            The target position of the actuator.

        dq : float
            The target velocity of the actuator.

        kp : float
            The proportional gain of the actuator.

        kd : float
            The derivative gain of the actuator.

        tau : float
            The torque of the actuator.

        max_torque : float | None, default=None
            Optional summed torque limit in Nm for imported SimRobot motors.
            Omission keeps the current limit; ordinary server motors ignore it.
        """

    def say_message(
        self,
        actuator_name: str,
        volume: float,
        message: bytes | bytearray,
    ) -> None:
        """Perform a say action.

        Parameter
        ---------
        actuator_name: str
            The name of the say actuator.

        volume: float
            The volume gain parameter.

        message: bytes | bytearray
            The message to say.
        """


@runtime_checkable
class PSimCommandInterface(Protocol):
    """Protocol for the soccer command interface."""

    def kill_sim(self) -> None:
        """Kill the simulation (server)."""
