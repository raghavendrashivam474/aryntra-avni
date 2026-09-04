"""Acoustic Feature Extractor — lightweight voice representation.

Extracts statistical acoustic features from audio to create a
deterministic, CPU-friendly, dependency-free voice representation.

Features extracted per sample:
- Mean and standard deviation of signal amplitude
- Zero-crossing rate
- RMS energy
- Spectral centroid (approximate via FFT)
- Signal duration

The final representation is the average across all enrollment samples,
producing a stable 40-byte feature vector.

This is a V1 foundation representation. Future milestones may replace
this with neural embeddings (d-vectors, x-vectors) behind the same
RepresentationExtractor interface.
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
FEATURE_DIM = 5  # mean, std, zcr, rms, spectral_centroid


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
    """Compute acoustic features from normalized float samples."""
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

    # 5. Spectral centroid (approximate via magnitude-weighted frequency)
    # Use a simple DFT on a subsample for CPU efficiency
    chunk_size = min(n, 2048)
    chunk = samples[:chunk_size]
    magnitude_sum = 0.0
    weighted_freq_sum = 0.0
    for k in range(chunk_size // 2):
        real = sum(chunk[t] * math.cos(2 * math.pi * k * t / chunk_size) for t in range(chunk_size))
        imag = sum(chunk[t] * math.sin(2 * math.pi * k * t / chunk_size) for t in range(chunk_size))
        mag = math.sqrt(real ** 2 + imag ** 2)
        freq = k * sample_rate / chunk_size
        magnitude_sum += mag
        weighted_freq_sum += freq * mag

    spectral_centroid = (weighted_freq_sum / magnitude_sum) if magnitude_sum > 0 else 0.0

    return [mean_val, std_val, zcr, rms, spectral_centroid]


def _features_to_bytes(features: List[float]) -> bytes:
    """Serialize feature vector to bytes (little-endian doubles)."""
    return struct.pack(f"<{len(features)}d", *features)


def _bytes_to_features(data: bytes) -> List[float]:
    """Deserialize feature vector from bytes."""
    n = len(data) // 8
    return list(struct.unpack(f"<{n}d", data))


class AcousticFeatureExtractor(RepresentationExtractor):
    """Lightweight acoustic-statistics voice representation extractor.

    No external ML dependencies. Pure Python + stdlib.
    Produces a deterministic, reproducible representation.
    """

    @property
    def extractor_id(self) -> str:
        return EXTRACTOR_ID

    @property
    def version(self) -> str:
        return EXTRACTOR_VERSION

    def extract(self, audio_samples: List[bytes]) -> VoiceRepresentation:
        """Extract acoustic features from preprocessed WAV samples."""
        if not audio_samples:
            raise ExtractionError("No audio samples provided")

        logger.info(
            "Extracting acoustic features from %d samples", len(audio_samples)
        )

        all_features = []
        for i, audio in enumerate(audio_samples):
            samples, rate = _read_pcm_frames(audio)
            features = _compute_features(samples, rate)
            all_features.append(features)
            logger.debug("Sample %d features: %s", i, [round(f, 6) for f in features])

        # Average features across all samples for stable representation
        avg_features = [
            sum(f[i] for f in all_features) / len(all_features)
            for i in range(FEATURE_DIM)
        ]

        rep_bytes = _features_to_bytes(avg_features)

        logger.info(
            "Representation extracted | dim=%d bytes=%d",
            FEATURE_DIM, len(rep_bytes),
        )

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
                    "spectral_centroid": round(avg_features[4], 2),
                },
            },
        )

    def similarity(
        self,
        rep_a: VoiceRepresentation,
        rep_b: VoiceRepresentation,
    ) -> float:
        """Cosine similarity between two acoustic feature vectors."""
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
