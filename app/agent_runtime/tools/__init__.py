"""Agent Runtime tools — sandbox tools executed inside Docker containers."""

from app.agent_runtime.tools.base import SandboxTool, ToolProxy
from app.agent_runtime.tools.bash_execute import BashExecuteTool
from app.agent_runtime.tools.file_list import FileListTool
from app.agent_runtime.tools.file_read import FileReadTool
from app.agent_runtime.tools.file_write import FileWriteTool
from app.agent_runtime.tools.python_execute import PythonExecuteTool

TOOL_REGISTRY: dict[str, type[SandboxTool]] = {
    "python_execute": PythonExecuteTool,
    "bash_execute": BashExecuteTool,
    "file_read": FileReadTool,
    "file_write": FileWriteTool,
    "file_list": FileListTool,
}

__all__ = [
    "SandboxTool",
    "ToolProxy",
    "TOOL_REGISTRY",
    "PythonExecuteTool",
    "BashExecuteTool",
    "FileReadTool",
    "FileWriteTool",
    "FileListTool",
]
