import numpy as np
from scipy.signal import butter, filtfilt


class DSP:

    def __init__(self, config):
        self.rate = config["sample_rate"]
        self.hp = config["highpass_hz"]
        self.limiter_db = config["limiter_db"]
        self.channels = config["channels"]

    def highpass(self, audio):

        nyquist = self.rate / 2
        cutoff = self.hp / nyquist

        if cutoff <= 0:
            return audio

        if cutoff >= 1:
            raise ValueError(
                "highpass_hz must be below half the sample rate"
            )

        b, a = butter(
            2,
            cutoff,
            btype="high"
        )

        if audio.ndim == 1:
            return filtfilt(b, a, audio)

        return np.column_stack([
            filtfilt(b, a, audio[:, channel])
            for channel in range(audio.shape[1])
        ])

    def process(self, audio):

        audio = audio.astype(np.float32)

        # Normalize S32_LE to approximately [-1, 1].
        audio /= 2147483648.0

        # Remove DC offset independently for each channel.
        if audio.ndim == 1:
            audio -= np.mean(audio)
        else:
            audio -= np.mean(
                audio,
                axis=0,
                keepdims=True
            )

        # High-pass filter.
        audio = self.highpass(audio)

        # Apply per-channel gain and enabled state.
        if audio.ndim == 1:
            channel_configs = self.channels[:1]
        else:
            channel_configs = self.channels

        for channel_index, channel_config in enumerate(
            channel_configs
        ):
            if not channel_config["enabled"]:
                audio[:, channel_index] = 0
                continue

            gain_db = float(
                channel_config["gain_db"]
            )

            multiplier = 10 ** (gain_db / 20)

            audio[:, channel_index] *= multiplier

        # Limiter.
        limit = 10 ** (self.limiter_db / 20)

        audio = np.clip(
            audio,
            -limit,
            limit
        )

        return audio