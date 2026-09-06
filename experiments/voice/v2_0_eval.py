"""V2.0 Real-World Voice Identity Evaluation — Main Entry Point.

Usage:
    python -m experiments.voice.v2_0_eval

Prerequisites:
    1. Authorized human WAV recordings placed in:
       data/evaluation/speaker_a/enrollment/  (>=2 files)
       data/evaluation/speaker_a/evaluation/  (>=2 files)
       data/evaluation/speaker_b/enrollment/  (>=2 files)
       data/evaluation/speaker_b/evaluation/  (>=2 files)
    2. All files must be WAV format
    3. SpeechBrain and SpeechT5 models will be downloaded on first run
"""

import logging
import subprocess
import sys
from pathlib import Path

# Ensure project root is on path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from experiments.voice.v2_0_harness import ExperimentConfig, V2EvaluationHarness

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("v2.0_eval")


def get_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=str(project_root),
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def main():
    data_dir = project_root / "data" / "evaluation"
    output_dir = project_root / "data" / "evaluation" / "output"

    config = ExperimentConfig(
        experiment_id="v2_0_real_speech_validation",
        data_dir=str(data_dir),
        output_dir=str(output_dir),
        speakers=["speaker_a", "speaker_b"],
        enrollment_count=2,
        evaluation_count=3,
        git_commit=get_git_commit(),
    )

    harness = V2EvaluationHarness(config)

    # --- Phase 1: Discover data ---
    logger.info("=" * 60)
    logger.info("V2.0 REAL-WORLD VOICE IDENTITY EVALUATION")
    logger.info("=" * 60)

    all_files = {}
    for speaker_id in config.speakers:
        files = harness.discover_speaker_files(speaker_id)
        all_files[speaker_id] = files
        n_enroll = len(files["enrollment"])
        n_eval = len(files["evaluation"])
        logger.info(
            "%s: %d enrollment, %d evaluation files",
            speaker_id, n_enroll, n_eval,
        )
        if n_enroll < 2:
            logger.error(
                "FATAL: %s needs >= 2 enrollment files. Found %d.",
                speaker_id, n_enroll,
            )
            logger.error(
                "Place authorized WAV recordings in: %s",
                data_dir / speaker_id / "enrollment",
            )
            sys.exit(1)
        if n_eval < 1:
            logger.error(
                "FATAL: %s needs >= 1 evaluation file. Found %d.",
                speaker_id, n_eval,
            )
            sys.exit(1)

    # --- Phase 2: Representation experiments ---
    logger.info("-" * 40)
    logger.info("Phase 2: Representation-level experiments")
    logger.info("-" * 40)

    from src.representation.neural_extractor import NeuralSpeakerExtractor
    extractor = NeuralSpeakerExtractor()

    rep_results = {}
    for speaker_id, files in all_files.items():
        logger.info("Running representation experiment for %s", speaker_id)
        rep_results[speaker_id] = harness.run_representation_experiment(
            extractor=extractor,
            speaker_id=speaker_id,
            enrollment_files=files["enrollment"],
            evaluation_files=files["evaluation"],
        )

    # Cross-speaker separation
    logger.info("Running cross-speaker separation")
    harness.run_cross_speaker_separation(extractor, rep_results)

    # --- Phase 3: End-to-end identity experiments ---
    logger.info("-" * 40)
    logger.info("Phase 3: End-to-end identity experiments")
    logger.info("-" * 40)

    enrollment_files = {
        sid: files["enrollment"] for sid, files in all_files.items()
    }
    e2e_results = harness.run_end_to_end_identity(
        extractor=extractor,
        rep_results=rep_results,
        enrollment_files=enrollment_files,
    )

    # --- Phase 4: Finalize ---
    logger.info("-" * 40)
    logger.info("Phase 4: Finalizing results")
    logger.info("-" * 40)

    result = harness.finalize()

    # Print summary
    print("\n" + "=" * 60)
    print("V2.0 EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Experiment: {result.experiment_id}")
    print(f"Timestamp:  {result.timestamp}")
    print(f"Git commit: {config.git_commit}")
    print(f"Errors:     {result.errors_count}")
    print()

    for metric_name, stats in result.summary.items():
        print(f"{metric_name}:")
        print(f"  count={stats['count']}  mean={stats['mean']}  "
              f"min={stats['min']}  max={stats['max']}")
    print()

    if result.errors:
        print("ERRORS:")
        for err in result.errors:
            print(f"  - {err}")

    print(f"\nFull results: {output_dir / f'{config.experiment_id}_results.json'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
