# Architecture Documentation

## Overview

The Agent Runtime Evaluation Platform is designed to evaluate the runtime quality of AI agents across 5 key dimensions. The platform uses LangGraph for workflow orchestration and FastAPI for the API layer.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer (FastAPI)                       │
├─────────────────────────────────────────────────────────────────┤
│  /api/v1/tasks     │  /api/v1/evaluations  │  /api/v1/reports   │
└────────────────────┴──────────────────────┴────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Service Layer (EvaluationService)             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  LangGraph Evaluation Workflow                   │
│  ┌─────────────┐                                               │
│  │   Validate   │                                               │
│  │    Input     │                                               │
│  └──────┬──────┘                                               │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Parallel Evaluation Nodes                    │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │  │
│  │  │Planning  │ │Tactical  │ │Tool Use  │ │ Memory   │    │  │
│  │  │Evaluator │ │Evaluator │ │Evaluator │ │Evaluator │    │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │  │
│  │       │             │            │            │           │  │
│  │       │        ┌──────────┐     │            │           │  │
│  │       │        │ Replan   │     │            │           │  │
│  │       │        │Evaluator │     │            │           │  │
│  │       │        └──────────┘     │            │           │  │
│  └───────┼────────────┼────────────┼────────────┼───────────┘  │
│          │            │            │            │               │
│          └────────────┼────────────┼────────────┘               │
│                       │            │                            │
│                       ▼            ▼                            │
│              ┌─────────────────────────┐                       │
│              │   Aggregate Results     │                       │
│              └─────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Database Layer (SQLAlchemy)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  AgentTask  │  │ Trajectory  │  │ Evaluation  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. API Layer (FastAPI)

- **Tasks API**: Create and manage agent tasks
- **Evaluations API**: Run and retrieve evaluations
- **Reports API**: Get analytics and summaries

### 2. Service Layer

- **EvaluationService**: Orchestrates the evaluation process
- Manages database operations
- Integrates with LangGraph workflow

### 3. LangGraph Workflow

The evaluation workflow is orchestrated using LangGraph:

1. **Validate Input**: Check required fields
2. **Parallel Evaluation**: Run 5 evaluators simultaneously
3. **Aggregate Results**: Combine scores and generate report

### 4. Evaluators

Each evaluator focuses on a specific dimension:

| Evaluator | Focus | Metrics |
|-----------|-------|---------|
| Planning | Plan quality | Coverage, Ordering, Granularity, Completeness |
| Tactical | Action decisions | Relevance, Efficiency, Correctness |
| Tool Use | Tool selection | Selection Quality, Parameter Accuracy, Result Utilization |
| Memory | Information retention | Retention, Relevance, Consistency |
| Replan | Replanning decisions | Trigger Appropriateness, Adaptation Quality, Learning |

### 5. Database Models

- **AgentTask**: Stores task information
- **AgentTrajectory**: Stores execution steps
- **Evaluation**: Stores evaluation results

## Data Flow

```
1. Create Task → AgentTask
2. Add Trajectory → AgentTrajectory[]
3. Run Evaluation → LangGraph Workflow
4. Store Results → Evaluation
5. Return Report → OverallEvaluation
```

## Design Decisions

### Why LangGraph?

- **Visual Workflow**: Easy to understand evaluation flow
- **Parallel Execution**: Evaluators run concurrently
- **State Management**: Clean state passing between nodes
- **Extensibility**: Easy to add new evaluators

### Why Async?

- **Performance**: Non-blocking I/O for LLM calls
- **Scalability**: Handle multiple evaluations concurrently
- **Modern Python**: Best practices for FastAPI

### Why Separate Evaluators?

- **Modularity**: Each evaluator is independent
- **Testability**: Easy to mock and test
- **Extensibility**: Add new dimensions without changing existing code
- **Clarity**: Clear separation of concerns
