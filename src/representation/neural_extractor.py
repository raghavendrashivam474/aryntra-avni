"""Neural Speaker Representation Extractor for Avni V1.5.

Extracts deep neural speaker embeddings (512-dimensional x-vectors)
from authorized audio samples using SpeechBrain's VoxCeleb model.

Implements the RepresentationExtractor abstract base class.
"""

import io
import logging
import math
import struct
import wave
from typing import List, Optional, Tuple

import numpy as np

from src.representation.base import (
    ExtractionError,
    RepresentationExtractor,
    VoiceRepresentation,
)

logger = logging.getLogger(__name__)

EXTRACTOR_ID = "neural_xvector"
EXTRACTOR_VERSION = "1.0"
EMBEDDING_DIM = 512


def _read_wav_samples(audio_bytes: bytes) -> Tuple[List[float], int]:
    """Read 16-bit mono PCM frames from WAV bytes, return (samples, sample_rate)."""
    try:
        buf = io.BytesIO(audio_bytes)
        with wave.open(buf, "rb") as wf:
            rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
            n_samples = len(raw) // 2
            samples = list(struct.unpack(f"<{n_samples}h", raw))
            return [s / 32768.0 for s in samples], rate
    except Exception as e:
        raise ExtractionError(f"Cannot read audio for neural extraction: {e}")


def _embedding_to_bytes(embedding: List[float]) -> bytes:
    """Serialize float embedding vector to bytes (little-endian float32)."""
    return struct.pack(f"<{len(embedding)}f", *embedding)


def _bytes_to_embedding(data: bytes) -> List[float]:
    """Deserialize float embedding vector from bytes."""
    n = len(data) // 4
    return list(struct.unpack(f"<{n}f", data))


class NeuralSpeakerExtractor(RepresentationExtractor):
    """Deep neural speaker representation extractor producing 512-dim x-vectors."""

    def __init__(
        self,
        model_source: str = "speechbrain/spkrec-xvect-voxceleb",
        device: Optional[str] = None,
    ) -> None:
        self._model_source = model_source
        self._device = device or "cpu"
        self._classifier = None

    @property
    def extractor_id(self) -> str:
        return EXTRACTOR_ID

    @property
    def version(self) -> str:
        return EXTRACTOR_VERSION

    @property
    def embedding_dim(self) -> int:
        return EMBEDDING_DIM

    def _get_classifier(self):
        if self._classifier is None:
            try:
                from speechbrain.inference.speaker import EncoderClassifier
                logger.info("Loading SpeechBrain speaker encoder from '%s'", self._model_source)
                self._classifier = EncoderClassifier.from_hparams(
                    source=self._model_source,
                    run_opts={"device": self._device},
                )
            except Exception as exc:
                logger.error("Failed to load neural speaker encoder '%s': %s", self._model_source, exc)
                raise ExtractionError(
                    f"Failed to load speaker encoder model '{self._model_source}': {exc}",
                    details={"source": self._model_source, "error": str(exc)},
                ) from exc
        return self._classifier

    def extract(self, audio_samples: List[bytes]) -> VoiceRepresentation:
        """Extract a 512-dim neural speaker embedding from preprocessed WAV samples."""
        if not audio_samples:
            raise ExtractionError("No audio samples provided for extraction")

        import torch

        classifier = self._get_classifier()
        sample_embeddings = []

        for idx, audio in enumerate(audio_samples):
            samples, rate = _read_wav_samples(audio)
            if len(samples) == 0:
                raise ExtractionError(f"Audio sample {idx} is empty")

            # SpeechBrain expects [batch, time] float32 tensor
            tensor = torch.tensor(samples, dtype=torch.float32).unsqueeze(0).to(self._device)

            try:
                with torch.no_grad():
                    emb = classifier.encode_batch(tensor)
                    emb = emb.squeeze().cpu()
                    if emb.dim() > 1:
                        emb = emb.squeeze()
                    # Normalize embedding to unit sphere
                    norm = torch.norm(emb, p=2)
                    if norm > 0:
                        emb = emb / norm
                    sample_embeddings.append(emb.numpy().tolist())
            except Exception as exc:
                logger.error("Neural encoding failed on sample %d: %s", idx, exc)
                raise ExtractionError(
                    f"Neural extraction failed on sample {idx}: {exc}",
                    details={"sample_index": idx, "error": str(exc)},
                ) from exc

        # Aggregate across samples (average and re-normalize)
        avg_emb = np.mean(sample_embeddings, axis=0)
        norm = np.linalg.norm(avg_emb)
        if norm > 0:
            avg_emb = avg_emb / norm
        final_embedding = avg_emb.tolist()

        rep_bytes = _embedding_to_bytes(final_embedding)

        return VoiceRepresentation(
            representation_id=f"{EXTRACTOR_ID}_v{EXTRACTOR_VERSION}",
            version=EXTRACTOR_VERSION,
            data=rep_bytes,
            metadata={
                "extractor": EXTRACTOR_ID,
                "model_source": self._model_source,
                "embedding_dim": len(final_embedding),
                "sample_count": len(audio_samples),
                "norm": float(norm),
            },
        )

    def similarity(
        self,
        rep_a: VoiceRepresentation,
        rep_b: VoiceRepresentation,
    ) -> float:
        """Compute cosine similarity between two neural representations."""
        if rep_a.version != rep_b.version:
            raise ExtractionError(
                f"Version mismatch: {rep_a.version} vs {rep_b.version}"
            )

        emb_a = np.array(_bytes_to_embedding(rep_a.data), dtype=np.float32)
        emb_b = np.array(_bytes_to_embedding(rep_b.data), dtype=np.float32)

        if len(emb_a) != len(emb_b):
            raise ExtractionError(
                f"Embedding dimension mismatch: {len(emb_a)} vs {len(emb_b)}"
            )

        norm_a = np.linalg.norm(emb_a)
        norm_b = np.linalg.norm(emb_b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        dot = float(np.dot(emb_a, emb_b))
        sim = dot / (norm_a * norm_b)
        return float(max(0.0, min(1.0, (sim + 1.0) / 2.0)))  # mapped to [0.0, 1.0]
