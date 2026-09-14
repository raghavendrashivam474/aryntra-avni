# Aryntra Avni — V3.0 Identity Control Research Experiment

This directory contains the experimental harnesses, configurations, artifacts, and reports for the V3.0 Identity Control and Disentanglement Research Spike (S0).

## Directory Structure

```text
experiments/v3_0_identity_control/
├── config/       # Experiment configuration files
├── scripts/      # Standalone experiment execution scripts
│   └── run_disentanglement_experiment.py
├── results/      # Generated audio WAVs and raw metric JSONs
│   ├── output_converted_condition_1_source_b_eval_1.wav
│   ├── output_converted_condition_2_source_b_eval_2.wav
│   ├── output_converted_condition_3_source_b_eval_3.wav
│   └── s0_results.json
└── reports/      # Markdown synthesis and analysis
    └── v3_0_s0_research_report.md
How to Reproduce
PowerShell

python experiments/v3_0_identity_control/scripts/run_disentanglement_experiment.py
