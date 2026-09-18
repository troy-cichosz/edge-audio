import subprocess

import numpy as np


class AudioCapture:

    def __init__(self, config):
        self.device = config["device"]
        self.rate = config["sample_rate"]
        self.channels = config["channels"]
        self.chunk_seconds = config["chunk_seconds"]

        if self.channels < 1:
            raise ValueError(
                "capture.channels must be at least 1"
            )

        self.bytes_per_sample = 4  # S32_LE

    def record(self, seconds=None):

        if seconds is None:
            seconds = self.chunk_seconds

        frames = int(self.rate * seconds)

        expected_bytes = (
            frames
            * self.channels
            * self.bytes_per_sample
        )

        command = [
            "arecord",
            "-q",
            "-D",
            self.device,
            "-t",
            "raw",
            "-f",
            "S32_LE",
            "-r",
            str(self.rate),
            "-c",
            str(self.channels),
            "-d",
            str(seconds),
        ]

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        raw_data, stderr = process.communicate()

        if process.returncode != 0:
            error = stderr.decode(
                "utf-8",
                errors="replace"
            ).strip()

            raise RuntimeError(
                f"arecord failed with exit code "
                f"{process.returncode}: {error}"
            )

        if len(raw_data) != expected_bytes:
            raise RuntimeError(
                f"Unexpected audio data length: "
                f"expected {expected_bytes} bytes, "
                f"received {len(raw_data)} bytes"
            )

        # Convert raw S32_LE samples to NumPy.
        audio = np.frombuffer(
            raw_data,
            dtype="<i4"
        ).copy()

        # ALSA provides interleaved channel samples:
        #
        #   2 channels:
        #   L, R, L, R, L, R, ...
        #
        #   1 channel:
        #   C0, C0, C0, ...
        #
        # Reshape to:
        #
        #   [[C0, C1],
        #    [C0, C1],
        #    ...]
        #
        audio = audio.reshape(
            -1,
            self.channels
        )

        return audio