# API Documentation

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Currently, the API does not require authentication. In production, add JWT or API key authentication.

## Endpoints

### Tasks

#### Create Task

```http
POST /tasks/
```

**Request Body:**
```json
{
  "goal": "Fix authentication bug in login flow",
  "context": {
    "project": "web-app",
    "language": "python"
  }
}
```

**Response (201):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "goal": "Fix authentication bug in login flow",
  "context": {
    "project": "web-app",
    "language": "python"
  },
  "status": "pending",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### Get Task

```http
GET /tasks/{task_id}
```

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "goal": "Fix authentication bug in login flow",
  "status": "completed",
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:05Z",
  "completed_at": "2024-01-15T10:35:00Z"
}
```

#### List Tasks

```http
GET /tasks/?skip=0&limit=100
```

**Response (200):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "goal": "Fix authentication bug",
    "status": "completed",
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

#### Add Trajectory

```http
POST /tasks/{task_id}/trajectory
```

**Request Body:**
```json
[
  {
    "step_number": 1,
    "action_type": "plan",
    "action_detail": {
      "goal": "Fix auth bug",
      "steps": [
        {"description": "Search for auth code"},
        {"description": "Read auth.py"},
        {"description": "Fix the bug"}
      ]
    },
    "timestamp": "2024-01-15T10:30:00Z"
  },
  {
    "step_number": 2,
    "action_type": "tool_call",
    "action_detail": {
      "tool_name": "search_code",
      "input": {"query": "authentication"}
    },
    "observation": "Found: auth.py, login.py",
    "timestamp": "2024-01-15T10:30:05Z"
  }
]
```

**Response (201):**
```json
{
  "message": "Added 2 trajectory steps",
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Evaluations

#### Run Evaluation

```http
POST /evaluations/
```

**Request Body:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "include_details": true
}
```

**Response (202):**
```json
{
  "id": "eval-uuid",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "created_at": "2024-01-15T10:35:00Z",
  "completed_at": "2024-01-15T10:35:30Z",
  "evaluation": {
    "planning": {
      "coverage": 85.0,
      "ordering": 90.0,
      "granularity": 80.0,
      "completeness": 85.0,
      "overall": 85.0,
      "feedback": "Good plan with clear milestones..."
    },
    "tactical": {
      "relevance": 90.0,
      "efficiency": 85.0,
      "correctness": 88.0,
      "overall": 88.0,
      "feedback": "Actions were relevant and efficient..."
    },
    "tool_use": {
      "selection_quality": 92.0,
      "parameter_accuracy": 88.0,
      "result_utilization": 85.0,
      "overall": 89.0,
      "feedback": "Good tool selection..."
    },
    "memory": {
      "retention": 85.0,
      "relevance": 90.0,
      "consistency": 88.0,
      "overall": 87.0,
      "feedback": "Key facts were retained..."
    },
    "replan": {
      "trigger_appropriateness": 100.0,
      "adaptation_quality": 100.0,
      "learning_from_failure": 100.0,
      "overall": 100.0,
      "feedback": "No replanning needed..."
    },
    "overall_score": 89.0,
    "summary": "Agent performance is good (overall: 89.0/100)...",
    "recommendations": [
      "Continue maintaining high performance"
    ]
  }
}
```

#### Get Evaluation

```http
GET /evaluations/{evaluation_id}
```

### Reports

#### Get Summary

```http
GET /reports/summary
```

**Response (200):**
```json
{
  "total_evaluations": 50,
  "average_scores": {
    "planning": 78.5,
    "tactical": 82.3,
    "tool_use": 75.8,
    "memory": 71.2,
    "replan": 85.0,
    "overall": 78.6
  },
  "score_distribution": {
    "planning": [85, 90, 75, ...],
    "tactical": [88, 92, 80, ...]
  },
  "top_issues": [
    "Memory retention is weak: Key facts are being forgotten"
  ],
  "recommendations": [
    "Strengthen memory management: Implement explicit fact tracking"
  ]
}
```

#### Get Task History

```http
GET /reports/tasks/{task_id}/history
```

#### Get Dimension Statistics

```http
GET /reports/dimensions/{dimension}
```

**Valid dimensions:** planning, tactical, tool_use, memory, replan, retrieval

## Error Responses

### 404 Not Found

```json
{
  "detail": "Task not found"
}
```

### 422 Validation Error

```json
{
  "detail": [
    {
      "loc": ["body", "goal"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Internal Server Error

```json
{
  "detail": "Internal server error"
}
```
