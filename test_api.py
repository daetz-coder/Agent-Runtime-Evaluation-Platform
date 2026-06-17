"""
Quick API test script.

Usage:
    python test_api.py
"""

import httpx
import json

BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint."""
    print("🔍 Testing health endpoint...")
    response = httpx.get(f"{BASE_URL}/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    return response.status_code == 200


def test_root():
    """Test root endpoint."""
    print("\n🔍 Testing root endpoint...")
    response = httpx.get(f"{BASE_URL}/")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def test_create_task():
    """Test task creation."""
    print("\n🔍 Testing task creation...")
    data = {
        "goal": "Fix authentication bug in login flow",
        "context": {"project": "web-app", "language": "python"}
    }
    response = httpx.post(f"{BASE_URL}/api/v1/tasks/", json=data)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")

    if response.status_code == 201:
        return response.json().get("id")
    return None


def test_list_tasks():
    """Test task listing."""
    print("\n🔍 Testing task listing...")
    response = httpx.get(f"{BASE_URL}/api/v1/tasks/")
    print(f"   Status: {response.status_code}")
    print(f"   Tasks count: {len(response.json())}")
    return response.status_code == 200


def test_get_summary():
    """Test evaluation summary."""
    print("\n🔍 Testing evaluation summary...")
    response = httpx.get(f"{BASE_URL}/api/v1/reports/summary")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def main():
    """Run all tests."""
    print("=" * 50)
    print("Agent Evaluation Platform - API Test")
    print("=" * 50)

    try:
        # Test health
        if not test_health():
            print("❌ Health check failed!")
            return

        # Test root
        test_root()

        # Test task creation
        task_id = test_create_task()

        # Test task listing
        test_list_tasks()

        # Test summary
        test_get_summary()

        print("\n" + "=" * 50)
        print("✅ All tests passed!")
        print("=" * 50)

        if task_id:
            print(f"\n📝 Created task ID: {task_id}")
            print("   You can now run evaluation using this task ID.")

    except httpx.ConnectError:
        print("\n❌ Connection failed! Make sure the server is running:")
        print("   python -m app.main")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
