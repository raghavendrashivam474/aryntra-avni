"""Enrollment Service — orchestrates voice enrollment.

Flow:
    EnrollmentRequest
        → validate request
        → validate audio files
        → preprocess audio
        → extract representation (via RepresentationExtractor)
        → produce EnrollmentResult
"""

import logging
import time
from pathlib import Path
from typing import List, Optional

from src.enrollment.contracts import (
    AudioSample,
    EnrollmentRequest,
    EnrollmentResult,
    EnrollmentStatus,
)
from src.enrollment.audio_validator import validate_audio_file
from src.enrollment.preprocessor import preprocess_audio

logger = logging.getLogger(__name__)


class EnrollmentService:
    """Orchestrates the voice enrollment pipeline.

    The representation extractor is injected, keeping this
    service independent of any specific embedding model.
    """

    def __init__(self, representation_extractor=None):
        """
        Args:
            representation_extractor: A RepresentationExtractor instance
                or callable that takes a list of preprocessed audio byte
                streams and returns (representation_bytes, version_string).
                None = extraction step is skipped (S1 boundary).
        """
        self._extractor = representation_extractor

    def enroll(self, request: EnrollmentRequest) -> EnrollmentResult:
        """Execute the full enrollment pipeline."""
        t0 = time.perf_counter()
        logger.info(
            "Enrollment started | identity=%s samples=%d",
            request.identity_id, len(request.samples),
        )

        # 1 — Validate request structure
        request_errors = request.validate()
        if request_errors:
            logger.warning("Enrollment validation failed: %s", request_errors)
            return EnrollmentResult(
                status=EnrollmentStatus.INSUFFICIENT_INPUT,
                identity_id=request.identity_id,
                errors=request_errors,
                sample_count=len(request.samples),
            )

        # 2 — Validate each audio file
        audio_errors = {}
        valid_samples = []
        for sample in request.samples:
            is_valid, errors = validate_audio_file(sample.file_path)
            if is_valid:
                valid_samples.append(sample)
            else:
                audio_errors[str(sample.file_path)] = errors

        if len(valid_samples) < 2:
            all_errors = []
            for path, errs in audio_errors.items():
                for e in errs:
                    all_errors.append(f"{path}: {e}")
            return EnrollmentResult(
                status=EnrollmentStatus.INVALID_AUDIO,
                identity_id=request.identity_id,
                errors=all_errors,
                sample_count=len(request.samples),
            )

        # 3 — Preprocess valid audio
        preprocessed = []
        for sample in valid_samples:
            try:
                audio_bytes = preprocess_audio(sample.file_path)
                preprocessed.append(audio_bytes)
                logger.debug(
                    "Preprocessed | file=%s bytes=%d",
                    sample.file_path.name, len(audio_bytes),
                )
            except Exception as e:
                logger.error(
                    "Preprocessing failed for %s: %s",
                    sample.file_path, e,
                )
                audio_errors[str(sample.file_path)] = [str(e)]

        if len(preprocessed) < 2:
            return EnrollmentResult(
                status=EnrollmentStatus.INVALID_AUDIO,
                identity_id=request.identity_id,
                errors=[f"Only {len(preprocessed)} samples survived preprocessing"],
                sample_count=len(request.samples),
            )

        # 4 — Extract representation
        representation_data = None
        representation_version = None
        extractor_metadata = {}

        if self._extractor is not None:
            try:
                # Support both RepresentationExtractor objects and plain callables
                if hasattr(self._extractor, "extract"):
                    rep = self._extractor.extract(preprocessed)
                    representation_data = rep.data
                    representation_version = rep.version
                    extractor_metadata = rep.metadata
                else:
                    representation_data, representation_version = self._extractor(
                        preprocessed
                    )

                logger.info(
                    "Representation extracted | version=%s bytes=%d",
                    representation_version,
                    len(representation_data) if representation_data else 0,
                )
            except Exception as e:
                logger.error("Representation extraction failed: %s", e)
                return EnrollmentResult(
                    status=EnrollmentStatus.EXTRACTION_FAILURE,
                    identity_id=request.identity_id,
                    errors=[f"Extraction failed: {e}"],
                    sample_count=len(valid_samples),
                )
        else:
            logger.info(
                "No extractor configured — S1 boundary. "
                "Enrollment validated but no representation produced."
            )

        elapsed = time.perf_counter() - t0
        logger.info(
            "Enrollment complete | identity=%s status=SUCCESS "
            "samples=%d latency=%.3fs",
            request.identity_id, len(valid_samples), elapsed,
        )

        metadata = {
            "enrollment_latency_sec": round(elapsed, 4),
            "valid_samples": len(valid_samples),
            "total_samples": len(request.samples),
            "extractor_configured": self._extractor is not None,
        }
        if extractor_metadata:
            metadata["representation"] = extractor_metadata

        return EnrollmentResult(
            status=EnrollmentStatus.SUCCESS,
            identity_id=request.identity_id,
            representation_data=representation_data,
            representation_version=representation_version,
            sample_count=len(valid_samples),
            metadata=metadata,
        )
