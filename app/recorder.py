import hashlib
import json
import os
import socket
import uuid
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

def build_evidence_envelope(
    service,
    service_version,
    node_id,
    capture_id,
    timestamp,
    monotonic_start_ns,
    time_context,
    raw_path,
    raw_sha256,
    processed_path,
    processed_sha256,
    duration_seconds,
    sample_rate,
    channels,
    processing,
):
    """Build the Round 1 common evidence envelope for one audio capture."""
    evidence_id = str(uuid.uuid4())
    raw_artifact_id = f"{evidence_id}:raw"

    return {
        "schema": "ai-legal.evidence.envelope.v1",
        "evidence_id": evidence_id,
        "service": service,
        "service_version": service_version,
        "node_id": node_id,
        "source": {},
        "capture": {
            "start": timestamp.isoformat(),
            "end": None,
            "monotonic_start_ns": monotonic_start_ns,
            "time_semantics": "capture_boundary_reference_not_physical_sample",
        },
        "time_context": time_context,
        "artifacts": [
            {
                "artifact_id": raw_artifact_id,
                "role": "authoritative",
                "filename": os.path.basename(raw_path),
                "media_type": "audio/wav",
                "size": os.path.getsize(raw_path),
                "sha256": raw_sha256,
            },
            {
                "artifact_id": f"{evidence_id}:processed",
                "role": "derived",
                "filename": os.path.basename(processed_path),
                "media_type": "audio/wav",
                "size": os.path.getsize(processed_path),
                "sha256": processed_sha256,
                "derived_from": raw_artifact_id,
            },
        ],
        "configuration": None,
        "derivation": {
            "method": "edge-audio DSP processing",
        },
        "service_metadata": {
            "capture_id": capture_id,
            "duration_seconds": duration_seconds,
            "sample_rate": sample_rate,
            "channels": channels,
            "processing": processing,
        },
    }
