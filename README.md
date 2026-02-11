# Agent Benchmark

A framework for benchmarking AI coding agents using GitHub's spec-kit methodology.

## Overview

This tool enables systematic comparison of how different AI coding agents generate plans from a constitution and specification. It runs multiple agents in isolated Docker containers, collects metrics, and generates analysis reports.

## Installation

```bash
uv sync
```

## Usage

### Run an experiment

```bash
agent-benchmark run experiments/example.toml
```

### Analyze results

```bash
agent-benchmark analyze results/my-test-2024-01-15/
```

### List past experiments

```bash
agent-benchmark list
```

### View specific run details

```bash
agent-benchmark show results/my-test-2024-01-15/opencode-default-1/
```

## Configuration

Experiments are configured using TOML files. See `experiments/example.toml` for a sample configuration.

```toml
[experiment]
name = "spec-kit-plan-test"
description = "Compare plan generation quality"

[target]
repo = "https://github.com/user/test-repo"
commit = "abc123"

[prompt]
file = "PROMPT.md"

[settings]
runs_per_agent = 3
parallel = true
timeout_minutes = 30

[[agents]]
id = "opencode-default"
type = "opencode"
```

## Architecture

- **runner.py** - Orchestrates experiment execution
- **container.py** - Manages Docker containers
- **metrics.py** - Collects quantitative metrics
- **analysis.py** - Generates analysis reports
- **cli.py** - Command-line interface
- **display.py** - Rich TUI progress display
