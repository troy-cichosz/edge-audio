import os
import yaml


def load_config():
    path = os.environ.get(
        "AUDIO_CONFIG",
        "/app/config/audio.yaml"
    )

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    return validate_config(config)


def validate_config(config):
    capture = config.get("capture", {})
    processing = config.get("processing", {})

    if capture.get("channels", 2) < 1:
        raise ValueError("capture.channels must be at least 1")

    if capture.get("sample_rate", 0) <= 0:
        raise ValueError("capture.sample_rate must be greater than 0")

    if capture.get("chunk_seconds", 0) <= 0:
        raise ValueError("capture.chunk_seconds must be greater than 0")

    if processing.get("highpass_hz", 0) < 0:
        raise ValueError("processing.highpass_hz cannot be negative")

    channels = config.get("channels")

    # Backward compatibility with the original configuration format.
    if channels is None:
        channel_count = capture["channels"]
        legacy_gain = processing.get("gain_db", 0)

        channels = [
            {
                "id": channel,
                "name": "left" if channel == 0 else "right",
                "enabled": True,
                "gain_db": legacy_gain,
            }
            for channel in range(channel_count)
        ]

        config["channels"] = channels

    if len(channels) != capture["channels"]:
        raise ValueError(
            "channels configuration must contain exactly "
            "capture.channels entries"
        )

    channel_ids = set()

    for channel in channels:
        if "id" not in channel:
            raise ValueError("Each channel must have an id")

        if channel["id"] in channel_ids:
            raise ValueError(
                f"Duplicate channel id: {channel['id']}"
            )

        channel_ids.add(channel["id"])

        channel.setdefault(
            "name",
            f"channel_{channel['id']}"
        )

        channel.setdefault(
            "enabled",
            True
        )

        channel.setdefault(
            "gain_db",
            0
        )

        if not isinstance(channel["enabled"], bool):
            raise ValueError(
                f"Channel {channel['id']} enabled must be boolean"
            )

    return config