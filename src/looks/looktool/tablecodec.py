"""Validate the camera's planar signed-seven-bit table without a fitting runtime."""


def validate(raw):
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise TypeError('Expected a bytes-like correction table')
    if len(raw) != 1215:
        raise ValueError('Expected three 405-byte correction planes')
    if any(64 <= value < 192 for value in raw):
        raise ValueError('Expected signed 7-bit integer corrections')
