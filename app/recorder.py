import hashlib
import json
import os
import socket
from datetime import datetime, timezone

import soundfile as sf


def get_hostname():
    return socket.gethostname()


def get_capture_timestamp():
    """
    Return a UTC datetime and filesystem-safe capture ID.
    """
    timestamp = datetime.now(timezone.utc)

    capture_id = timestamp.strftime(
        "%Y%m%d_%H%M%S"
    )

    return timestamp, capture_id


def save_audio(audio, rate, path, hostname=None, capture_id=None):
    """
    Save audio as WAV and return the full path.

    If hostname/capture_id are supplied, they are used to ensure
    multiple artifacts from the same capture share the same filename.
    """
    os.makedirs(path, exist_ok=True)

    if hostname is None:
        hostname = get_hostname()

    if capture_id is None:
        _, capture_id = get_capture_timestamp()

    filename = f"{hostname}_{capture_id}.wav"

    full_path = os.path.join(
        path,
        filename
    )

    sf.write(
        full_path,
        audio,
        rate
    )

    return full_path


def sha256_file(path):
    """
    Calculate SHA-256 hash of a file.
    """
    sha256 = hashlib.sha256()

    with open(path, "rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b""
        ):
            sha256.update(chunk)

    return sha256.hexdigest()


def save_metadata(metadata, path, hostname, capture_id):
    """
    Save one JSON metadata sidecar for a capture.
    """
    os.makedirs(path, exist_ok=True)

    filename = f"{hostname}_{capture_id}.json"

    full_path = os.path.join(
        path,
        filename
    )

    with open(
        full_path,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            metadata,
            file,
            indent=2
        )

        file.write("\n")

    return full_path