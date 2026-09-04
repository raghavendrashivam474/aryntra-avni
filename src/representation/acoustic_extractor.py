"""Acoustic Feature Extractor — lightweight normalized voice representation.

Extracts normalized statistical and spectral features from audio to create a
deterministic, CPU-friendly, dependency-free voice representation.

Features extracted per sample (8-dimensional normalized vector):
1. Mean amplitude [-1.0, 1.0]
2. Standard deviation of amplitude [0.0, 1.0]
3. Zero-crossing rate [0.0, 1.0]
4. RMS energy [0.0, 1.0]
5. Normalized spectral centroid (relative to Nyquist frequency) [0.0, 1.0]
6. Low-band spectral energy ratio (0 - 500 Hz) [0.0, 1.0]
7. Mid-band spectral energy ratio (500 - 2000 Hz) [0.0, 1.0]
8. High-band spectral energy ratio (2000 - 8000 Hz) [0.0, 1.0]

All features are normalized in [0.0, 1.0] for balanced distance metrics.
"""

import logging
import math
import struct
import wave
from io import BytesIO
from typing import List, Tuple

from src.representation.base import (
    ExtractionError,
    RepresentationExtractor,
    VoiceRepresentation,
)

logger = logging.getLogger(__name__)

EXTRACTOR_ID = "acoustic_stats"
EXTRACTOR_VERSION = "1.0"
FEATURE_DIM = 8  # 8 normalized feature dimensions


def _read_pcm_frames(audio_bytes: bytes) -> Tuple[List[float], int]:
    """Read 16-bit mono PCM frames from WAV bytes, return (samples, sample_rate)."""
    try:
        buf = BytesIO(audio_bytes)
        with wave.open(buf, "rb") as wf:
            rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
            n_samples = len(raw) // 2
            samples = list(struct.unpack(f"<{n_samples}h", raw))
            return [s / 32768.0 for s in samples], rate
    except Exception as e:
        raise ExtractionError(f"Cannot read audio for feature extraction: {e}")


def _compute_features(samples: List[float], sample_rate: int) -> List[float]:
    """Compute normalized acoustic features from float samples."""
    n = len(samples)
    if n == 0:
        raise ExtractionError("Empty audio sample")

    # 1. Mean amplitude
    mean_val = sum(samples) / n

    # 2. Standard deviation
    variance = sum((s - mean_val) ** 2 for s in samples) / n
    std_val = math.sqrt(variance)

    # 3. Zero-crossing rate
    crossings = sum(
        1 for i in range(1, n)
        if (samples[i] >= 0) != (samples[i - 1] >= 0)
    )
    zcr = crossings / n

    # 4. RMS energy
    rms = math.sqrt(sum(s ** 2 for s in samples) / n)

    # Spectral analysis using subsampled DFT
    chunk_size = min(n, 2048)
    chunk = samples[:chunk_size]
    nyquist = sample_rate / 2.0

    magnitude_sum = 0.0
    weighted_freq_sum = 0.0
    low_band_energy = 0.0    # 0 - 500 Hz
    mid_band_energy = 0.0    # 500 - 2000 Hz
    high_band_energy = 0.0   # 2000 - 8000 Hz

    for k in range(chunk_size // 2):
        real = sum(chunk[t] * math.cos(2 * math.pi * k * t / chunk_size) for t in range(chunk_size))
        imag = sum(chunk[t] * math.sin(2 * math.pi * k * t / chunk_size) for t in range(chunk_size))
        mag = math.sqrt(real ** 2 + imag ** 2)
        freq = k * sample_rate / chunk_size

        magnitude_sum += mag
        weighted_freq_sum += freq * mag

        if freq < 500.0:
            low_band_energy += mag ** 2
        elif freq < 2000.0:
            mid_band_energy += mag ** 2
        else:
            high_band_energy += mag ** 2

    raw_centroid = (weighted_freq_sum / magnitude_sum) if magnitude_sum > 0 else 0.0
    norm_centroid = min(1.0, raw_centroid / nyquist) if nyquist > 0 else 0.0

    total_energy = low_band_energy + mid_band_energy + high_band_energy
    if total_energy > 0:
        ratio_low = low_band_energy / total_energy
        ratio_mid = mid_band_energy / total_energy
        ratio_high = high_band_energy / total_energy
    else:
        ratio_low, ratio_mid, ratio_high = 0.33, 0.33, 0.33

    return [
        mean_val,
        std_val,
        zcr,
        rms,
        norm_centroid,
        ratio_low,
        ratio_mid,
        ratio_high,
    ]


def _features_to_bytes(features: List[float]) -> bytes:
    """Serialize feature vector to bytes (little-endian doubles)."""
    return struct.pack(f"<{len(features)}d", *features)


def _bytes_to_features(data: bytes) -> List[float]:
    """Deserialize feature vector from bytes."""
    n = len(data) // 8
    return list(struct.unpack(f"<{n}d", data))


class AcousticFeatureExtractor(RepresentationExtractor):
    """Lightweight normalized acoustic-statistics voice representation extractor."""

    @property
    def extractor_id(self) -> str:
        return EXTRACTOR_ID

    @property
    def version(self) -> str:
        return EXTRACTOR_VERSION

    def extract(self, audio_samples: List[bytes]) -> VoiceRepresentation:
        """Extract normalized acoustic features from preprocessed WAV samples."""
        if not audio_samples:
            raise ExtractionError("No audio samples provided")

        all_features = []
        for audio in audio_samples:
            samples, rate = _read_pcm_frames(audio)
            features = _compute_features(samples, rate)
            all_features.append(features)

        avg_features = [
            sum(f[i] for f in all_features) / len(all_features)
            for i in range(FEATURE_DIM)
        ]

        rep_bytes = _features_to_bytes(avg_features)

        return VoiceRepresentation(
            representation_id=f"{EXTRACTOR_ID}_v{EXTRACTOR_VERSION}",
            version=EXTRACTOR_VERSION,
            data=rep_bytes,
            metadata={
                "extractor": EXTRACTOR_ID,
                "feature_dim": FEATURE_DIM,
                "sample_count": len(audio_samples),
                "features": {
                    "mean_amplitude": round(avg_features[0], 6),
                    "std_amplitude": round(avg_features[1], 6),
                    "zero_crossing_rate": round(avg_features[2], 6),
                    "rms_energy": round(avg_features[3], 6),
                    "norm_spectral_centroid": round(avg_features[4], 4),
                    "low_band_ratio": round(avg_features[5], 4),
                    "mid_band_ratio": round(avg_features[6], 4),
                    "high_band_ratio": round(avg_features[7], 4),
                },
            },
        )

    def similarity(
        self,
        rep_a: VoiceRepresentation,
        rep_b: VoiceRepresentation,
    ) -> float:
        """Cosine similarity between two normalized feature vectors."""
        if rep_a.version != rep_b.version:
            raise ExtractionError(
                f"Version mismatch: {rep_a.version} vs {rep_b.version}"
            )

        feats_a = _bytes_to_features(rep_a.data)
        feats_b = _bytes_to_features(rep_b.data)

        if len(feats_a) != len(feats_b):
            raise ExtractionError("Feature dimension mismatch")

        dot = sum(a * b for a, b in zip(feats_a, feats_b))
        norm_a = math.sqrt(sum(a ** 2 for a in feats_a))
        norm_b = math.sqrt(sum(b ** 2 for b in feats_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return max(0.0, min(1.0, dot / (norm_a * norm_b)))
