import math
import struct


CONTAINER_BOX_TYPES = {
    b"moov",
    b"trak",
    b"mdia",
    b"minf",
    b"stbl",
    b"edts",
    b"udta",
    b"dinf",
}


def extract_video_duration_seconds(file_obj):
    duration = _extract_mp4_duration_seconds(file_obj)
    return duration or 0


def _extract_mp4_duration_seconds(file_obj):
    if not hasattr(file_obj, "read") or not hasattr(file_obj, "seek"):
        return 0

    try:
        original_position = file_obj.tell()
        file_obj.seek(0, 2)
        file_size = file_obj.tell()
        file_obj.seek(0)
        return _find_mvhd_duration(file_obj, file_size) or 0
    except (OSError, ValueError, struct.error):
        return 0
    finally:
        try:
            file_obj.seek(original_position)
        except (OSError, ValueError, UnboundLocalError):
            pass


def _find_mvhd_duration(file_obj, end_pos):
    while file_obj.tell() < end_pos:
        box_start = file_obj.tell()
        box_size, box_type, header_size = _read_box_header(file_obj, end_pos)
        if not box_size or box_size < header_size:
            return 0

        box_end = min(box_start + box_size, end_pos)
        if box_type == b"mvhd":
            return _parse_mvhd_box(file_obj)
        if box_type in CONTAINER_BOX_TYPES:
            duration = _find_mvhd_duration(file_obj, box_end)
            if duration:
                return duration
        file_obj.seek(box_end)
    return 0


def _read_box_header(file_obj, end_pos):
    remaining = end_pos - file_obj.tell()
    if remaining < 8:
        return 0, None, 0

    header = file_obj.read(8)
    box_size, box_type = struct.unpack(">I4s", header)
    header_size = 8

    if box_size == 1:
        if end_pos - file_obj.tell() < 8:
            return 0, None, 0
        box_size = struct.unpack(">Q", file_obj.read(8))[0]
        header_size = 16
    elif box_size == 0:
        box_size = end_pos - (file_obj.tell() - header_size)

    return box_size, box_type, header_size


def _parse_mvhd_box(file_obj):
    version_data = file_obj.read(1)
    if len(version_data) != 1:
        return 0

    version = version_data[0]
    file_obj.read(3)

    if version == 1:
        file_obj.read(16)
        timescale_data = file_obj.read(4)
        duration_data = file_obj.read(8)
        if len(timescale_data) != 4 or len(duration_data) != 8:
            return 0
        timescale = struct.unpack(">I", timescale_data)[0]
        duration = struct.unpack(">Q", duration_data)[0]
    else:
        file_obj.read(8)
        timescale_data = file_obj.read(4)
        duration_data = file_obj.read(4)
        if len(timescale_data) != 4 or len(duration_data) != 4:
            return 0
        timescale = struct.unpack(">I", timescale_data)[0]
        duration = struct.unpack(">I", duration_data)[0]

    if not timescale or not duration:
        return 0
    return max(1, math.ceil(duration / timescale))
