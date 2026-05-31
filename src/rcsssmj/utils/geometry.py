from __future__ import annotations

from typing import Final


class AABB2D:
    """2-dimensional axis-aligned bounding-box."""

    def __init__(
        self,
        min_x: float = -1,
        max_x: float = 1,
        min_y: float = -1,
        max_y: float = 1,
    ) -> None:
        """Construct a new 2D axis-aligned bounding-box.

        Parameter
        ---------
        min_x: float = -1
            The lower bound along the x-axis.

        max_x: float = 1
            The upper bound along the x-axis.

        min_y: float = -1
            The lower bound along the y-axis.

        max_y: float = 1
            The upper bound along the y-axis.
        """

        if min_x > max_x:
            min_x, max_x = max_x, min_x

        if min_y > max_y:
            min_y, max_y = max_y, min_y

        self.min_x: Final[float] = min_x
        self.max_x: Final[float] = max_x
        self.min_y: Final[float] = min_y
        self.max_y: Final[float] = max_y

    def center(self) -> tuple[float, float]:
        """Return the center of the bounding-box."""

        return (self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2

    def contains_x(self, x: float) -> bool:
        """Check if the given x-coordinate is within the bounding box."""

        return self.min_x <= x and x <= self.max_x

    def contains_y(self, y: float) -> bool:
        """Check if the given y-coordinate is within the bounding box."""

        return self.min_y <= y and y <= self.max_y

    def contains(self, x: float, y: float) -> bool:
        """Check if the given x- and y-coordinate is within the bounding box."""

        return self.min_x <= x and x <= self.max_x and self.min_y <= y and y <= self.max_y


class AABB3D:
    """3-dimensional axis-aligned bounding-box."""

    def __init__(
        self,
        min_x: float = -1,
        max_x: float = 1,
        min_y: float = -1,
        max_y: float = 1,
        min_z: float = -1,
        max_z: float = 1,
    ) -> None:
        """Construct a new 3D axis-aligned bounding-box.

        Parameter
        ---------
        min_x: float = -1
            The lower bound along the x-axis.

        max_x: float = 1
            The upper bound along the x-axis.

        min_y: float = -1
            The lower bound along the y-axis.

        max_y: float = 1
            The upper bound along the y-axis.

        min_z: float = -1
            The lower bound along the z-axis.

        max_z: float = 1
            The upper bound along the z-axis.
        """

        if min_x > max_x:
            min_x, max_x = max_x, min_x

        if min_y > max_y:
            min_y, max_y = max_y, min_y

        if min_z > max_z:
            min_z, max_z = max_z, min_z

        self.min_x: Final[float] = min_x
        self.max_x: Final[float] = max_x
        self.min_y: Final[float] = min_y
        self.max_y: Final[float] = max_y
        self.min_z: Final[float] = min_z
        self.max_z: Final[float] = max_z

    def center(self) -> tuple[float, float, float]:
        """Return the center of the bounding-box."""

        return (self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2, (self.min_z + self.max_z) / 2

    def contains_x(self, x: float) -> bool:
        """Check if the given x-coordinate is within the bounding box."""

        return self.min_x <= x and x <= self.max_x

    def contains_y(self, y: float) -> bool:
        """Check if the given y-coordinate is within the bounding box."""

        return self.min_y <= y and y <= self.max_y

    def contains_z(self, z: float) -> bool:
        """Check if the given z-coordinate is within the bounding box."""

        return self.min_z <= z and z <= self.max_z

    def contains_xy(self, x: float, y: float) -> bool:
        """Check if the given x- and y-coordinates are within the bounding box."""

        return self.min_x <= x and x <= self.max_x and self.min_y <= y and y <= self.max_y

    def contains(self, x: float, y: float, z: float) -> bool:
        """Check if the given x-, y- and z-coordinates are within the bounding box."""

        return self.min_x <= x and x <= self.max_x and self.min_y <= y and y <= self.max_y and self.min_z <= z and z <= self.max_z


Matrix4x4 = tuple[float, float, float, float, float, float, float, float, float, float, float, float, float, float, float, float]


def matrix_4x4_mul(a: Matrix4x4, b: Matrix4x4) -> Matrix4x4:
    """Multiply two 4x4 matrices."""

    return tuple(a[i * 4] * b[j] + a[i * 4 + 1] * b[4 + j] + a[i * 4 + 2] * b[8 + j] + a[i * 4 + 3] * b[12 + j] for i in range(4) for j in range(4))


def matrix_4x4_transpose(m: Matrix4x4) -> Matrix4x4:
    """Transpose a 4x4 matrix."""

    # fmt: off
    return (
        m[0], m[4], m[8],  m[12],
        m[1], m[5], m[9],  m[13],
        m[2], m[6], m[10], m[14],
        m[3], m[7], m[11], m[15],
    )
    # fmt: on


def to_transformation_matrix(quat: tuple[float, float, float, float], pos: tuple[float, float, float]) -> Matrix4x4:
    """Create a transformation matrix from a quaternion and a position."""

    # fmt: off
    return (
        2 * (quat[0] * quat[0] + quat[1] * quat[1]) - 1, 2 * (quat[1] * quat[2] - quat[0] * quat[3]),     2 * (quat[1] * quat[3] + quat[0] * quat[2]),     pos[0],
        2 * (quat[1] * quat[2] + quat[0] * quat[3]),     2 * (quat[0] * quat[0] + quat[2] * quat[2]) - 1, 2 * (quat[2] * quat[3] - quat[0] * quat[1]),     pos[1],
        2 * (quat[1] * quat[3] - quat[0] * quat[2]),     2 * (quat[2] * quat[3] + quat[0] * quat[1]),     2 * (quat[0] * quat[0] + quat[3] * quat[3]) - 1, pos[2],
        0,                                               0,                                               0,                                               1,
    )
    # fmt: on


def transformation_matrix_inverse(
    m: Matrix4x4,
) -> Matrix4x4:
    """
    Calculate the inverse of a transformation matrix.
    """

    # fmt: off
    return (
        m[0], m[4], m[8],  -(m[0] * m[3] + m[4] * m[7] + m[8]  * m[11]),
        m[1], m[5], m[9],  -(m[1] * m[3] + m[5] * m[7] + m[9]  * m[11]),
        m[2], m[6], m[10], -(m[2] * m[3] + m[6] * m[7] + m[10] * m[11]),
        0.0,  0.0,  0.0,   1.0
    )
    # fmt: on
