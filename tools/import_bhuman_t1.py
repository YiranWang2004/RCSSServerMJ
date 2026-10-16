#!/usr/bin/env python3
"""Import the original B-Human SimRobot T1, including its 14ms servo delay."""
import argparse
from pathlib import Path
from import_bhuman_k1 import convert

JOINTS = {
    'HeadYaw': ('AAHead_yaw', 'H1'),
    'HeadPitch': ('Head_pitch', 'H2'),
    'WaistYaw': ('Waist', 'Waist'),
}
for side, word, arm in [('L', 'Left', 'AL'), ('R', 'Right', 'AR')]:
    for index, (native, serial) in enumerate([
        ('ShoulderPitch', 'Shoulder_Pitch'), ('ShoulderRoll', 'Shoulder_Roll'),
        ('ElbowPitch', 'Elbow_Pitch'), ('ElbowYaw', 'Elbow_Yaw')], 1):
        JOINTS[side + native] = (word + '_' + serial, arm + str(index) if index < 4 else word.lower() + '_hand_link')
    for native, joint, body in [
        ('HipPitch', 'Hip_Pitch', 'Hip_Pitch'), ('HipRoll', 'Hip_Roll', 'Hip_Roll'),
        ('HipYaw', 'Hip_Yaw', 'Hip_Yaw'), ('KneePitch', 'Knee_Pitch', 'Shank'),
        ('AnklePitch', 'Ankle_Pitch', 'Ankle_Cross'), ('AnkleRoll', 'Ankle_Roll', 'foot_link')]:
        JOINTS[side + native] = (word + '_' + joint, word.lower() + '_foot_link' if body == 'foot_link' else body + '_' + word)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bhuman_repo', type=Path)
    args = parser.parse_args()
    convert(args.bhuman_repo.resolve(), Path(__file__).resolve().parents[1] / 'src/rcsssmj/resources/robots/T1BHuman', 'T1', JOINTS)
