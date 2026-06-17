"""
Test evaluation flow
"""

import httpx
import time

BASE_URL = "http://localhost:8000/api/v1"


def main():
    print("=== Agent Evaluation Test ===\n")

    # 1. Create task
    print("[1] Creating task...")
    task = httpx.post(f"{BASE_URL}/tasks/", json={
        "goal": "Fix login bug",
        "context": {"project": "web-app"}
    }).json()
    task_id = task["id"]
    print(f"    Task created: {task_id}\n")

    # 2. Add trajectory
    print("[2] Adding trajectory...")
    trajectory = [
        {
            "step_number": 1,
            "action_type": "plan",
            "action_detail": {
                "steps": [
                    {"description": "Search for login code"},
                    {"description": "Fix the bug"},
                    {"description": "Run tests"}
                ]
            }
        },
        {
            "step_number": 2,
            "action_type": "tool_call",
            "action_detail": {
                "tool_name": "search_code",
                "input": {"query": "login"}
            },
            "observation": "Found: login.py, auth.py"
        },
        {
            "step_number": 3,
            "action_type": "think",
            "action_detail": {
                "thought": "Found the login code, need to check for bugs"
            }
        },
        {
            "step_number": 4,
            "action_type": "tool_call",
            "action_detail": {
                "tool_name": "read_file",
                "input": {"file_path": "login.py"}
            },
            "observation": "def login(user, password): ... found bug in line 42"
        },
        {
            "step_number": 5,
            "action_type": "tool_call",
            "action_detail": {
                "tool_name": "edit_file",
                "input": {"file_path": "login.py", "line": 42, "fix": "add validation"}
            },
            "observation": "Fixed successfully"
        },
        {
            "step_number": 6,
            "action_type": "tool_call",
            "action_detail": {
                "tool_name": "run_tests",
                "input": {"test_path": "tests/test_login.py"}
            },
            "observation": "All 10 tests passed"
        }
    ]

    resp = httpx.post(f"{BASE_URL}/tasks/{task_id}/trajectory", json=trajectory)
    print(f"    Trajectory added: {resp.status_code}\n")

    # 3. Run evaluation
    print("[3] Running evaluation (this may take 30-60 seconds)...")
    evaluation = httpx.post(f"{BASE_URL}/evaluations/", json={
        "task_id": task_id,
        "include_details": True
    }).json()

    if "id" not in evaluation:
        print(f"    Error: {evaluation}")
        return

    eval_id = evaluation["id"]
    print(f"    Evaluation ID: {eval_id}\n")

    # 4. Get results
    print("[4] Getting results...")
    time.sleep(2)
    result = httpx.get(f"{BASE_URL}/evaluations/{eval_id}").json()

    eval_data = result.get("evaluation", {})
    if not eval_data:
        print("    No evaluation data yet")
        print(f"    Status: {result.get('status')}")
        return

    print("\n" + "=" * 50)
    print("EVALUATION RESULTS")
    print("=" * 50)
    print(f"\nOverall Score: {eval_data.get('overall_score', 0):.1f}/100")

    for dim in ["planning", "tactical", "tool_use", "memory", "replan"]:
        score = eval_data.get(dim, {}).get("overall", 0)
        print(f"  {dim:15}: {score:.1f}/100")

    print(f"\nSummary: {eval_data.get('summary', 'N/A')}")

    recommendations = eval_data.get("recommendations", [])
    if recommendations:
        print("\nRecommendations:")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
