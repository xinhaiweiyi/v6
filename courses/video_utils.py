import math
import os
import tempfile


def extract_video_duration_seconds(file_obj):
    if not hasattr(file_obj, "read") or not hasattr(file_obj, "seek"):
        return 0

    original_position = None
    temp_path = None
    clip = None
    try:
        original_position = file_obj.tell()
        clip_class = _load_video_clip_class()
        if clip_class is None:
            return 0
        video_path, temp_path = _resolve_video_path(file_obj)
        clip = clip_class(video_path)
        duration = getattr(clip, "duration", 0) or 0
        return max(1, math.ceil(duration)) if duration > 0 else 0
    except Exception:
        return 0
    finally:
        if clip is not None:
            clip.close()
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass
        if original_position is not None:
            try:
                file_obj.seek(original_position)
            except (OSError, ValueError):
                pass


def _load_video_clip_class():
    try:
        from moviepy import VideoFileClip

        return VideoFileClip
    except ImportError:
        try:
            from moviepy.editor import VideoFileClip

            return VideoFileClip
        except ImportError:
            return None


def _resolve_video_path(file_obj):
    if hasattr(file_obj, "temporary_file_path"):
        try:
            return file_obj.temporary_file_path(), None
        except Exception:
            pass

    file_name = getattr(file_obj, "name", "")
    if file_name and os.path.exists(file_name):
        return file_name, None

    suffix = os.path.splitext(file_name)[1] or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        file_obj.seek(0)
        for chunk in _iter_file_chunks(file_obj):
            temp_file.write(chunk)
        temp_path = temp_file.name
    return temp_path, temp_path


def _iter_file_chunks(file_obj, chunk_size=1024 * 1024):
    chunks = getattr(file_obj, "chunks", None)
    if callable(chunks):
        yield from chunks()
        return

    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break
        yield chunk
