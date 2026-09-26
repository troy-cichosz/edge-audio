import logging
import threading
import time

import numpy as np

from controller import ControllerClient


logger = logging.getLogger(__name__)


class CalibrationWorker:

    def __init__(self, controller, audio_capture, capture_lock):
        self.controller = controller
        self.audio_capture = audio_capture
        self.capture_lock = capture_lock

        self.running = True

    def start(self):
        thread = threading.Thread(
            target=self._run,
            name="calibration-worker",
            daemon=True,
        )

        thread.start()

        return thread

    def stop(self):
        self.running = False

    def _run(self):
        logger.info("Calibration worker started")

        while self.running:

            try:
                job = self.controller.get_pending_calibration()

                if job is not None:
                    self._execute(job)

            except Exception:
                logger.exception(
                    "Calibration worker error"
                )

            time.sleep(2)

    def _execute(self, job):
        calibration_id = job["id"]
        duration_seconds = int(
            job["duration_seconds"]
        )

        logger.info(
            "Starting calibration job %s duration=%ss",
            calibration_id,
            duration_seconds,
        )

        try:

            # Prevent calibration from competing with the
            # normal continuous capture process for /dev/snd.
            with self.capture_lock:

                audio = self.audio_capture.record(
                    duration_seconds
                )

            result = self._analyze(
                audio,
                duration_seconds
            )

            self.controller.complete_calibration(
                calibration_id,
                status="complete",
                result=result,
            )

            logger.info(
                "Calibration job %s complete",
                calibration_id,
            )

        except Exception as exc:

            logger.exception(
                "Calibration job %s failed",
                calibration_id,
            )

            try:
                self.controller.complete_calibration(
                    calibration_id,
                    status="failed",
                    result=None,
                    error=str(exc),
                )

            except Exception:
                logger.exception(
                    "Failed to report calibration failure %s",
                    calibration_id,
                )

    @staticmethod
    def _analyze(audio, duration_seconds):

        audio_float = audio.astype(
            np.float64
        )

        scale = 2147483648.0

        normalized = (
            audio_float / scale
        )

        result = {
            "duration_seconds": duration_seconds,
            "frames": int(audio.shape[0]),
            "channels": int(audio.shape[1]),
            "channels_data": [],
        }

        for channel in range(
            audio.shape[1]
        ):

            samples = audio_float[:, channel]

            normalized_channel = (
                normalized[:, channel]
            )

            peak = float(
                np.max(
                    np.abs(samples)
                )
            )

            rms = float(
                np.sqrt(
                    np.mean(
                        samples ** 2
                    )
                )
            )

            peak_normalized = float(
                np.max(
                    np.abs(normalized_channel)
                )
            )

            rms_normalized = float(
                np.sqrt(
                    np.mean(
                        normalized_channel ** 2
                    )
                )
            )

            if peak_normalized > 0:
                peak_dbfs = float(
                    20.0 *
                    np.log10(
                        peak_normalized
                    )
                )
            else:
                peak_dbfs = float("-inf")

            if rms_normalized > 0:
                rms_dbfs = float(
                    20.0 *
                    np.log10(
                        rms_normalized
                    )
                )
            else:
                rms_dbfs = float("-inf")

            clipping_samples = int(
                np.count_nonzero(
                    np.abs(samples)
                    >= 2147483647
                )
            )

            dc_offset = float(
                np.mean(samples)
            )

            result["channels_data"].append(
                {
                    "channel": channel,
                    "peak": peak,
                    "rms": rms,
                    "peak_dbfs": peak_dbfs,
                    "rms_dbfs": rms_dbfs,
                    "dc_offset": dc_offset,
                    "clipping_samples": clipping_samples,
                }
            )

        return result