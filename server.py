"""
MCP File Manager Server
A Model Context Protocol server that gives AI assistants the ability
to read, write, list, and delete files in a sandboxed workspace folder.

Author: Tutorial for Codédex Monthly Challenge
Protocol: MCP (Model Context Protocol) over stdio
"""

import json
import sys
import os
import datetime
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────────────────

# All file operations are sandboxed to this directory.
# The AI can only touch files inside here — nothing else on your machine.
WORKSPACE = Path(__file__).parent / "workspace"
WORKSPACE.mkdir(exist_ok=True)


# ─── MCP Protocol Helpers ────────────────────────────────────────────────────

def send(obj: dict):
    """Send a JSON-RPC message to stdout (the MCP host reads from here)."""
    print(json.dumps(obj), flush=True)


def send_result(request_id, result):
    """Send a successful JSON-RPC result."""
    send({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result
    })


def send_error(request_id, code: int, message: str):
    """Send a JSON-RPC error response."""
    send({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message}
    })


# ─── Tool Definitions ────────────────────────────────────────────────────────
# These tell the AI host (e.g. Claude Desktop) what tools are available,
# what arguments they take, and what they do.

TOOLS = [
    {
        "name": "list_files",
        "description": (
            "List all files in the managed workspace folder. "
            "Returns filenames, sizes, and last-modified timestamps."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "read_file",
        "description": "Read the full text content of a file from the workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Name of the file to read (e.g. 'notes.txt')"
                }
            },
            "required": ["filename"]
        }
    },
    {
        "name": "write_file",
        "description": (
            "Create a new file or overwrite an existing file in the workspace "
            "with the provided text content."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Name of the file to create or overwrite"
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write into the file"
                }
            },
            "required": ["filename", "content"]
        }
    },
    {
        "name": "append_to_file",
        "description": "Append text to the end of an existing file (or create it if it doesn't exist).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Name of the file to append to"
                },
                "content": {
                    "type": "string",
                    "description": "Text content to append"
                }
            },
            "required": ["filename", "content"]
        }
    },
    {
        "name": "delete_file",
        "description": "Permanently delete a file from the workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Name of the file to delete"
                }
            },
            "required": ["filename"]
        }
    },
    {
        "name": "search_files",
        "description": "Search for a text string across all files in the workspace. Returns matching filenames and line snippets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The text string to search for"
                }
            },
            "required": ["query"]
        }
    },
]


# ─── Tool Implementations ────────────────────────────────────────────────────

def safe_path(filename: str) -> Path:
    """
    Resolve a filename to an absolute path, ensuring it stays inside WORKSPACE.
    This prevents path-traversal attacks like '../../etc/passwd'.
    """
    # Strip any path separators so the AI can't escape the sandbox
    safe_name = Path(filename).name
    return WORKSPACE / safe_name


def tool_list_files() -> str:
    files = list(WORKSPACE.iterdir())
    if not files:
        return "The workspace is empty — no files yet."

    lines = ["📁 Workspace files:\n"]
    for f in sorted(files):
        if f.is_file():
            stat = f.stat()
            size = stat.st_size
            modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            lines.append(f"  • {f.name}  ({size} bytes, modified {modified})")
    return "\n".join(lines)


def tool_read_file(filename: str) -> str:
    path = safe_path(filename)
    if not path.exists():
        return f"❌ File '{filename}' does not exist in the workspace."
    if not path.is_file():
        return f"❌ '{filename}' is not a file."
    content = path.read_text(encoding="utf-8")
    return f"📄 Contents of '{filename}':\n\n{content}"


def tool_write_file(filename: str, content: str) -> str:
    path = safe_path(filename)
    path.write_text(content, encoding="utf-8")
    return f"✅ '{filename}' written successfully ({len(content)} characters)."


def tool_append_to_file(filename: str, content: str) -> str:
    path = safe_path(filename)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)
    return f"✅ Appended {len(content)} characters to '{filename}'."


def tool_delete_file(filename: str) -> str:
    path = safe_path(filename)
    if not path.exists():
        return f"❌ File '{filename}' does not exist."
    path.unlink()
    return f"🗑️ '{filename}' deleted."


def tool_search_files(query: str) -> str:
    results = []
    query_lower = query.lower()

    for filepath in sorted(WORKSPACE.iterdir()):
        if not filepath.is_file():
            continue
        try:
            lines = filepath.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue  # Skip binary files

        matches = [
            f"    Line {i+1}: {line.strip()}"
            for i, line in enumerate(lines)
            if query_lower in line.lower()
        ]
        if matches:
            results.append(f"  📄 {filepath.name}:")
            results.extend(matches)

    if not results:
        return f"🔍 No files contain '{query}'."
    return f"🔍 Search results for '{query}':\n\n" + "\n".join(results)


# ─── Request Dispatcher ──────────────────────────────────────────────────────

def dispatch_tool(tool_name: str, arguments: dict) -> str:
    """Route a tool call to the correct implementation."""
    if tool_name == "list_files":
        return tool_list_files()
    elif tool_name == "read_file":
        return tool_read_file(arguments.get("filename", ""))
    elif tool_name == "write_file":
        return tool_write_file(arguments.get("filename", ""), arguments.get("content", ""))
    elif tool_name == "append_to_file":
        return tool_append_to_file(arguments.get("filename", ""), arguments.get("content", ""))
    elif tool_name == "delete_file":
        return tool_delete_file(arguments.get("filename", ""))
    elif tool_name == "search_files":
        return tool_search_files(arguments.get("query", ""))
    else:
        return f"❌ Unknown tool: '{tool_name}'"


# ─── Main Event Loop ─────────────────────────────────────────────────────────

def main():
    """
    The MCP server's main loop.

    MCP communicates over stdio using JSON-RPC 2.0.
    We read one JSON object per line from stdin, process it, and write
    a JSON-RPC response to stdout.
    """
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        try:
            request = json.loads(raw_line)
        except json.JSONDecodeError:
            # Malformed input — skip it
            continue

        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        # ── Handshake ──────────────────────────────────────────────────────
        if method == "initialize":
            send_result(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "mcp-file-manager",
                    "version": "1.0.0"
                }
            })

        # ── Tool Discovery ─────────────────────────────────────────────────
        elif method == "tools/list":
            send_result(req_id, {"tools": TOOLS})

        # ── Tool Execution ─────────────────────────────────────────────────
        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            try:
                output = dispatch_tool(tool_name, arguments)
            except Exception as e:
                output = f"❌ Error running '{tool_name}': {e}"

            send_result(req_id, {
                "content": [{"type": "text", "text": output}]
            })

        # ── Notifications (no response needed) ─────────────────────────────
        elif method == "notifications/initialized":
            pass  # Acknowledge but don't respond

        # ── Unknown Methods ────────────────────────────────────────────────
        elif req_id is not None:
            send_error(req_id, -32601, f"Method not found: {method}")


if __name__ == "__main__":
    main()
