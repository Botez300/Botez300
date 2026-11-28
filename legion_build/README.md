# LEGION BUILD — Engineering Division Deliverables

Three foundational components created on request:

1. **Signal Pipeline** (`signal_pipeline/legion_signal.py`)  
   Canonical LegionSignal dataclass + validation enforcing schema v1.1.  
   Research-only by default. Explicit verification status and confidence.

2. **Quant Research Workbench** (`quant_workbench/workbench.py`)  
   Reproducible backtesting scaffold.  
   Includes 200-day MA trend filter (with cost model) and multi-asset time-series momentum.  
   Uses free yfinance data.

3. **Multi-Agent Orchestration Skeleton** (`orchestration/orchestrator.py`)  
   Lightweight keyword router that maps objectives to specialist agents.  
   Wired to existing Grok Bot agent IDs for Macro, Technical, COMMAND, and Risk.

## Quick Start

```bash
cd legion_build

# Test signal schema
python signal_pipeline/legion_signal.py

# Run quant baseline suite
python quant_workbench/workbench.py

# Test orchestrator routing
python orchestration/orchestrator.py
```

All code is self-contained, dependency-light, and aligned with LEGION verification standards.
