"""Shared curve validation and presets; no hardware access."""
import copy
import re

QUIET = [[30, 0], [45, 0], [60, 0], [70, 0], [80, 20], [85, 35], [90, 65], [95, 100]]
BALANCED = [[30, 0], [40, 10], [50, 15], [60, 25], [70, 40], [80, 60], [90, 80], [95, 100]]
COOL = [[30, 20], [40, 25], [50, 35], [60, 45], [70, 60], [80, 75], [90, 90], [95, 100]]


def preset(identifier, name, points, low_power=False):
    return dict(id=identifier, name=name, cpu=copy.deepcopy(points),
                gpu=copy.deepcopy(points), low_power=low_power)


def defaults():
    return [preset('quiet', 'Quiet reading', QUIET, True),
            preset('balanced', 'Everyday', BALANCED),
            preset('cool', 'Cool & steady', COOL)]


def validate_points(points):
    if not isinstance(points, list) or len(points) != 8:
        raise ValueError('Each fan needs exactly eight curve points.')
    previous_temp, previous_speed = 28, 0
    for point in points:
        if not isinstance(point, list) or len(point) != 2 or any(type(v) is not int for v in point):
            raise ValueError('Temperatures and fan speeds must be whole numbers.')
        temp, speed = point
        if not 30 <= temp <= 95 or not 0 <= speed <= 100:
            raise ValueError('Use 30–95°C and 0–100% fan speed.')
        if temp < previous_temp + 2 or speed < previous_speed:
            raise ValueError('Temperatures need a 2°C gap; fan speeds must not decrease.')
        previous_temp, previous_speed = temp, speed
    if points[0][0] != 30 or points[-1] != [95, 100]:
        raise ValueError('Keep the first point at 30°C and the last at 95°C / 100%.')
    # Require cooling headroom near the rated 100°C junction limit.
    for temperature, floor in [(80, 20), (85, 30), (90, 60)]:
        if interpolate(points, temperature) < floor - 0.01:
            raise ValueError(f'Use at least {floor}% cooling at {temperature}°C.')
    return copy.deepcopy(points)


def interpolate(points, temperature):
    if temperature <= points[0][0]:
        return points[0][1]
    for a, b in zip(points, points[1:]):
        if temperature <= b[0]:
            return a[1] + (b[1] - a[1]) * (temperature - a[0]) / (b[0] - a[0])
    return points[-1][1]


def validate_profile(data):
    if not isinstance(data, dict):
        raise ValueError('Invalid profile.')
    identifier, name = data.get('id'), data.get('name')
    if not isinstance(identifier, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', identifier):
        raise ValueError('Invalid profile identifier.')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 48 or any(ord(c) < 32 for c in name):
        raise ValueError('Give your profile a name of 1–48 characters.')
    if type(data.get('low_power')) is not bool:
        raise ValueError('Low-power mode must be on or off.')
    return dict(id=identifier, name=name.strip(), low_power=data['low_power'],
                cpu=validate_points(data.get('cpu')), gpu=validate_points(data.get('gpu')))
