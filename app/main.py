import logging
import os
import numpy as np
import threading
import time

from calibration import CalibrationWorker
from controller import ControllerClient
from config import load_config, validate_config
from capture import AudioCapture
from dsp import DSP
from recorder import (
    get_capture_timestamp,
    get_hostname,
    save_audio,
    save_metadata,
    sha256_file,
    build_evidence_envelope,
)
from time_context import TimeContextClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)


TIMING_DEBUG = os.environ.get("EDGE_AUDIO_TIMING_DEBUG", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def timing_log(message, *args):
    """Emit capture timing diagnostics only when explicitly enabled."""
    if TIMING_DEBUG:
        logging.info("TIMING " + message, *args)


def channel_stats(audio, channel):
    """
    Calculate peak and RMS for a single audio channel.

    Audio may contain int32 S32_LE samples, so convert to float64
    before squaring to prevent integer overflow.
    """
    channel_data = audio[:, channel].astype(np.float64)

    peak = np.max(np.abs(channel_data))
    rms = np.sqrt(np.mean(channel_data ** 2))

    return float(peak), float(rms)


def all_channel_stats(audio):
    return [
        channel_stats(audio, channel)
        for channel in range(audio.shape[1])
    ]


def channel_config(config, channel_index):
    channels = config.get("channels", [])

    if channel_index >= len(channels):
        return {
            "id": channel_index,
            "name": f"channel_{channel_index}",
            "enabled": True,
            "gain_db": 0,
        }

    return channels[channel_index]


def merge_config(base, overrides):
    """
    Recursively merge controller configuration overrides
    into the local configuration.

    Controller values override local values.
    Nested dictionaries are merged rather than replaced.
    """
    if not isinstance(base, dict) or not isinstance(overrides, dict):
        return overrides

    for key, value in overrides.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, dict)
        ):
            merge_config(base[key], value)
        else:
            base[key] = value

    return base


def main():
    # ---------------------------------------------------------
    # Load local configuration
    # ---------------------------------------------------------
    config = load_config()
    hostname = get_hostname()

    # ---------------------------------------------------------
    # Controller
    # ---------------------------------------------------------
    controller = ControllerClient()
    controller.register()
    controller_stop = threading.Event()

    def controller_registration_loop():
        interval = max(
            1.0,
            float(
                os.environ.get(
                    "EDGE_CONTROLLER_REGISTER_INTERVAL_SECONDS",
                    "30",
                )
            ),
        )

        while not controller_stop.wait(interval):
            controller.register()

    controller_thread = threading.Thread(
        target=controller_registration_loop,
        name="controller-registration",
        daemon=True,
    )
    controller_thread.start()

    controller_config = controller.get_configuration()

    if controller_config:
        logging.info(
            "Controller configuration received: %s",
            controller_config,
        )

        merge_config(config, controller_config)
        config = validate_config(config)

    # ---------------------------------------------------------
    # Build runtime configuration
    # ---------------------------------------------------------
    capture_cfg = config["capture"]
    processing_cfg = config["processing"]

    dsp_cfg = {
        **capture_cfg,
        **processing_cfg,
        "channels": config["channels"],
    }

    audio = AudioCapture(capture_cfg)
    dsp = DSP(dsp_cfg)
    time_context_client = TimeContextClient()

    # ---------------------------------------------------------
    # Calibration
    # ---------------------------------------------------------
    capture_lock = threading.Lock()

    calibration_worker = CalibrationWorker(
        controller,
        audio,
        capture_lock,
    )
    calibration_worker.start()

    logging.info("Starting edge-audio")
    logging.info("Capture device: %s", capture_cfg["device"])
    logging.info("Sample rate: %s Hz", capture_cfg["sample_rate"])
    logging.info("Channels: %s", capture_cfg["channels"])

    # ---------------------------------------------------------
    # Capture loop
    # ---------------------------------------------------------
    while True:
        # -----------------------------------------------------
        # Establish edge-time context and capture identity under
        # the same lock used by calibration. This prevents a
        # calibration operation from delaying the capture timestamp
        # or acquiring the audio device between timestamp/context
        # acquisition and the actual recording.
        # -----------------------------------------------------
        capture_timing_start_ns = time.monotonic_ns()
        with capture_lock:
            lock_acquired_ns = time.monotonic_ns()
            timing_log(
                "capture_lock_wait_ms=%.3f",
                (lock_acquired_ns - capture_timing_start_ns) / 1_000_000,
            )

            timestamp_start_ns = time.monotonic_ns()
            timestamp, capture_id = get_capture_timestamp()
            timestamp_end_ns = time.monotonic_ns()
            timing_log(
                "get_capture_timestamp_ms=%.3f",
                (timestamp_end_ns - timestamp_start_ns) / 1_000_000,
            )

            context_start_ns = time.monotonic_ns()
            time_context = time_context_client.capture_context()
            context_end_ns = time.monotonic_ns()
            timing_log(
                "time_context_ms=%.3f success=%s",
                (context_end_ns - context_start_ns) / 1_000_000,
                time_context is not None,
            )

            record_start_ns = time.monotonic_ns()
            raw = audio.record(capture_cfg["chunk_seconds"])
            record_end_ns = time.monotonic_ns()
            timing_log(
                "audio_record_ms=%.3f",
                (record_end_ns - record_start_ns) / 1_000_000,
            )

            capture_timing_end_ns = time.monotonic_ns()
            timing_log(
                "capture_locked_total_ms=%.3f timestamp_to_context_ms=%.3f timestamp_to_record_start_ms=%.3f",
                (capture_timing_end_ns - lock_acquired_ns) / 1_000_000,
                (context_end_ns - timestamp_end_ns) / 1_000_000,
                (record_start_ns - timestamp_end_ns) / 1_000_000,
            )

        # Raw statistics must be calculated before processing.
        raw_stats_start_ns = time.monotonic_ns()
        raw_stats = all_channel_stats(raw)
        raw_stats_end_ns = time.monotonic_ns()
        timing_log(
            "raw_stats_ms=%.3f",
            (raw_stats_end_ns - raw_stats_start_ns) / 1_000_000,
        )

        # -----------------------------------------------------
        # Process audio
        # -----------------------------------------------------
        processing_start_ns = time.monotonic_ns()
        processed = dsp.process(raw)
        processed_stats = all_channel_stats(processed)
        processing_end_ns = time.monotonic_ns()
        timing_log(
            "processing_and_stats_ms=%.3f",
            (processing_end_ns - processing_start_ns) / 1_000_000,
        )

        for channel_index, stats in enumerate(raw_stats):
            channel = channel_config(config, channel_index)
            logging.info(
                "RAW     %s Peak %.4f RMS %.4f",
                channel["name"],
                stats[0],
                stats[1],
            )

        for channel_index, stats in enumerate(processed_stats):
            channel = channel_config(config, channel_index)
            logging.info(
                "PROCESSED %s Peak %.4f RMS %.4f",
                channel["name"],
                stats[0],
                stats[1],
            )

        # -----------------------------------------------------
        # Save audio artifacts
        # -----------------------------------------------------
        save_audio_start_ns = time.monotonic_ns()
        raw_path = save_audio(
            raw,
            capture_cfg["sample_rate"],
            config["output"]["raw_path"],
            hostname=hostname,
            capture_id=capture_id,
        )

        processed_path = save_audio(
            processed,
            capture_cfg["sample_rate"],
            config["output"]["processed_path"],
            hostname=hostname,
            capture_id=capture_id,
        )
        save_audio_end_ns = time.monotonic_ns()
        timing_log(
            "save_audio_both_ms=%.3f",
            (save_audio_end_ns - save_audio_start_ns) / 1_000_000,
        )

        # -----------------------------------------------------
        # Calculate artifact hashes
        # -----------------------------------------------------
        hash_start_ns = time.monotonic_ns()
        raw_sha256 = sha256_file(raw_path)
        processed_sha256 = sha256_file(processed_path)
        hash_end_ns = time.monotonic_ns()
        timing_log(
            "hash_both_ms=%.3f",
            (hash_end_ns - hash_start_ns) / 1_000_000,
        )

        # -----------------------------------------------------
        # Build channel metadata
        # -----------------------------------------------------
        channel_metadata = []

        for channel_index in range(len(raw_stats)):
            channel = channel_config(config, channel_index)
            raw_peak, raw_rms = raw_stats[channel_index]
            processed_peak, processed_rms = processed_stats[channel_index]

            channel_metadata.append({
                "id": channel.get("id", channel_index),
                "name": channel.get("name", f"channel_{channel_index}"),
                "enabled": channel.get("enabled", True),
                "gain_db": channel.get("gain_db", 0),
                "statistics": {
                    "raw": {
                        "peak": raw_peak,
                        "rms": raw_rms,
                    },
                    "processed": {
                        "peak": processed_peak,
                        "rms": processed_rms,
                    },
                },
            })

        # -----------------------------------------------------
        # Build metadata
        # -----------------------------------------------------
        metadata = {
            "schema_version": "${SER_VER}",
            "capture": {
                "capture_id": capture_id,
                "hostname": hostname,
                "timestamp_utc": timestamp.isoformat(),
                "duration_seconds": capture_cfg["chunk_seconds"],
                "sample_rate": capture_cfg["sample_rate"],
                "channels": capture_cfg["channels"],
                "format": "S32_LE",
            },
            "time_context": time_context if time_context else {
                "status": "unavailable",
                "reason": "edge-time Capture Time Context could not be acquired immediately before capture",
            },
            "audio": {
                "raw": {
                    "path": raw_path,
                    "sha256": raw_sha256,
                },
                "processed": {
                    "path": processed_path,
                    "sha256": processed_sha256,
                },
            },
            "processing": {
                "highpass_hz": processing_cfg["highpass_hz"],
                "limiter_db": processing_cfg["limiter_db"],
            },
            "channels": channel_metadata,
        }

        evidence_envelope = build_evidence_envelope(
            service=controller.service_id,
            service_version=controller.service_version,
            node_id=controller.node_id,
            capture_id=capture_id,
            timestamp=timestamp,
            monotonic_start_ns=record_start_ns,
            time_context=time_context,
            raw_path=raw_path,
            raw_sha256=raw_sha256,
            processed_path=processed_path,
            processed_sha256=processed_sha256,
            duration_seconds=capture_cfg["chunk_seconds"],
            sample_rate=capture_cfg["sample_rate"],
            channels=capture_cfg["channels"],
            processing={
                "highpass_hz": processing_cfg["highpass_hz"],
                "limiter_db": processing_cfg["limiter_db"],
            },
        )
        metadata["evidence_envelope"] = evidence_envelope

        # -----------------------------------------------------
        # Save metadata sidecar
        # -----------------------------------------------------
        metadata_start_ns = time.monotonic_ns()
        metadata_path = save_metadata(
            metadata,
            config["output"]["metadata_path"],
            hostname,
            capture_id,
        )
        metadata_end_ns = time.monotonic_ns()
        timing_log(
            "save_metadata_ms=%.3f",
            (metadata_end_ns - metadata_start_ns) / 1_000_000,
        )

        logging.info("Saved capture: %s", capture_id)
        logging.info("Raw: %s", raw_path)
        logging.info("Processed: %s", processed_path)
        logging.info("Metadata: %s", metadata_path)


if __name__ == "__main__":
    main()