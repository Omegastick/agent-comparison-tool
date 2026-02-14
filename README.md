# ACT (Agent Comparison Tool)

A tool for comparing AI coding agents using OpenCode. Runs multiple agents in isolated Docker containers, collects metrics, and generates AI analysis reports.

## Installation

```bash
uv sync
```

## Prerequisites

- Docker
- OpenCode CLI with authenticated providers (`opencode auth login`, then `opencode auth list` to verify)

## Usage

### Run an experiment and analyze

```bash
uv run act run-and-analyze experiments/basic-greenfield-plan-creation.toml
```

### Run an experiment only

```bash
uv run act run experiments/basic-greenfield-plan-creation.toml
```

### Analyze existing results

```bash
uv run act analyze results/basic-greenfield-plan-creation-2026-02-11-123456/
```

Requires an `[analysis]` section in the experiment config.

### List past experiments

```bash
uv run act list
```

## Configuration

Experiments are configured using TOML files. See `experiments/` for examples.

Each agent requires:
- `id` - Unique identifier for the agent
- `model` - Model in `provider/model-id` format (optional, uses default if not specified)
- `extra_args` - Additional CLI arguments for opencode (optional)

## Docker Image

The tool runs agents in Docker containers. Rebuild after code changes:

```bash
just rebuild
```

## Output Structure

Results are saved to `results/<experiment-name>-<timestamp>/`:

```
results/basic-greenfield-plan-creation-2026-02-11-123456/
├── config.toml              # Copy of experiment config
├── analysis.md              # AI-generated analysis report
├── stats.json               # AI-generated statistics
├── sonnet-4.5-1/            # Run 1 for sonnet agent
│   ├── metrics.json         # Quantitative metrics
│   ├── run.log              # Agent execution log
│   └── repo/                # Repository state after run
├── sonnet-4.5-2/            # Run 2 for sonnet agent
├── gpt-5-1/                 # Run 1 for gpt-5 agent
└── gpt-5-2/                 # Run 2 for gpt-5 agent
```
