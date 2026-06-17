# Getting Started

## Prerequisites

- Python 3.11+
- PostgreSQL (or SQLite for development)
- Redis (optional, for caching)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/agent-eval-platform.git
cd agent-eval-platform
```

### 2. Create virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -e .
```

### 4. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Required: LLM API keys
OPENAI_API_KEY=sk-your-key-here

# Optional: Use Anthropic instead
# ANTHROPIC_API_KEY=sk-ant-your-key-here
# DEFAULT_LLM_PROVIDER=anthropic
# DEFAULT_LLM_MODEL=claude-3-sonnet-20240229

# Database (default: PostgreSQL)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agent_eval

# For development with SQLite:
# DATABASE_URL=sqlite+aiosqlite:///./agent_eval.db
```

### 5. Initialize database

```bash
# For PostgreSQL, create the database first:
createdb agent_eval

# The app will create tables automatically on startup
```

### 6. Run the application

```bash
# Development
python -m app.main

# Or with uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 7. Access the API

- API Documentation: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

## Quick Start Example

### 1. Create a task

```bash
curl -X POST http://localhost:8000/api/v1/tasks/ \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Fix authentication bug in login flow",
    "context": {"project": "web-app"}
  }'
```

### 2. Add trajectory steps

```bash
curl -X POST http://localhost:8000/api/v1/tasks/{task_id}/trajectory \
  -H "Content-Type: application/json" \
  -d '[
    {
      "step_number": 1,
      "action_type": "plan",
      "action_detail": {
        "steps": [
          {"description": "Search for auth code"},
          {"description": "Read auth.py"},
          {"description": "Fix the bug"}
        ]
      }
    },
    {
      "step_number": 2,
      "action_type": "tool_call",
      "action_detail": {
        "tool_name": "search_code",
        "input": {"query": "authentication"}
      },
      "observation": "Found: auth.py, login.py"
    }
  ]'
```

### 3. Run evaluation

```bash
curl -X POST http://localhost:8000/api/v1/evaluations/ \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "{task_id}",
    "include_details": true
  }'
```

### 4. View results

```bash
# Get evaluation summary
curl http://localhost:8000/api/v1/reports/summary

# Get dimension statistics
curl http://localhost:8000/api/v1/reports/dimensions/planning
```

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest

# With coverage
pytest --cov=app --cov-report=html
```

## Development

### Code Formatting

```bash
# Install ruff
pip install ruff

# Format code
ruff format .

# Check linting
ruff check .
```

### Type Checking

```bash
# Install mypy
pip install mypy

# Run type checking
mypy app
```

## Project Structure

```
agent-eval-platform/
├── app/
│   ├── api/v1/endpoints/    # API endpoints
│   ├── core/                # Configuration
│   ├── db/                  # Database models
│   ├── evaluators/          # 5 evaluation dimensions
│   ├── graphs/              # LangGraph workflow
│   ├── models/              # Pydantic schemas
│   ├── services/            # Business logic
│   └── main.py              # FastAPI app
├── tests/                   # Test suite
├── docs/                    # Documentation
├── pyproject.toml           # Project config
└── README.md
```

## Next Steps

1. Review the [Architecture Documentation](architecture.md)
2. Check the [API Documentation](api.md)
3. Explore the evaluators in `app/evaluators/`
4. Run the example agent in `app/agents/example_agent.py`
