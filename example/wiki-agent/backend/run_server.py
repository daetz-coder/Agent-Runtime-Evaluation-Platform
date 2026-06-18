"""启动后端服务"""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("WIKI_AGENT_PORT", "8001")),
        reload=True
    )
