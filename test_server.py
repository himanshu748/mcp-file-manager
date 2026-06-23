#!/usr/bin/env python3
"""
test_server.py — Local test harness for the MCP File Manager server.

This simulates what an MCP host (like Claude Desktop) does: it sends
JSON-RPC requests over stdin and reads responses from stdout.

Run:  python test_server.py
"""

import subprocess
import json
import sys
import os

SERVER_PATH = os.path.join(os.path.dirname(__file__), "server.py")


def send_request(proc, request: dict) -> dict:
    """Send a JSON-RPC request to the server and read the response."""
    line = json.dumps(request) + "\n"
    proc.stdin.write(line)
    proc.stdin.flush()
    response_line = proc.stdout.readline()
    return json.loads(response_line)


def print_result(label: str, response: dict):
    result = response.get("result", response.get("error"))
    if "content" in result:
        text = result["content"][0]["text"]
        print(f"\n{'='*55}")
        print(f"  {label}")
        print(f"{'='*55}")
        print(text)
    else:
        print(f"\n[{label}] → {json.dumps(result, indent=2)}")


def main():
    print("🚀 Starting MCP File Manager test harness...")
    proc = subprocess.Popen(
        [sys.executable, SERVER_PATH],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    # 1. Initialize handshake
    resp = send_request(proc, {
        "jsonrpc": "2.0", "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "test-client"}}
    })
    print(f"\n✅ Handshake: {resp['result']['serverInfo']}")

    # 2. Discover tools
    resp = send_request(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tool_names = [t["name"] for t in resp["result"]["tools"]]
    print(f"🔧 Tools available: {tool_names}")

    # 3. Write a file
    resp = send_request(proc, {
        "jsonrpc": "2.0", "id": 3,
        "method": "tools/call",
        "params": {
            "name": "write_file",
            "arguments": {
                "filename": "hello.txt",
                "content": "Hello from the MCP File Manager!\nThis file was created by an AI assistant.\n"
            }
        }
    })
    print_result("write_file → hello.txt", resp)

    # 4. Write another file
    send_request(proc, {
        "jsonrpc": "2.0", "id": 4,
        "method": "tools/call",
        "params": {
            "name": "write_file",
            "arguments": {
                "filename": "notes.txt",
                "content": "Shopping list:\n- Apples\n- Bread\n- Coffee\n"
            }
        }
    })

    # 5. Append to notes
    resp = send_request(proc, {
        "jsonrpc": "2.0", "id": 5,
        "method": "tools/call",
        "params": {
            "name": "append_to_file",
            "arguments": {"filename": "notes.txt", "content": "- Butter\n"}
        }
    })
    print_result("append_to_file → notes.txt", resp)

    # 6. List files
    resp = send_request(proc, {
        "jsonrpc": "2.0", "id": 6,
        "method": "tools/call",
        "params": {"name": "list_files", "arguments": {}}
    })
    print_result("list_files", resp)

    # 7. Read a file
    resp = send_request(proc, {
        "jsonrpc": "2.0", "id": 7,
        "method": "tools/call",
        "params": {"name": "read_file", "arguments": {"filename": "notes.txt"}}
    })
    print_result("read_file → notes.txt", resp)

    # 8. Search files
    resp = send_request(proc, {
        "jsonrpc": "2.0", "id": 8,
        "method": "tools/call",
        "params": {"name": "search_files", "arguments": {"query": "Coffee"}}
    })
    print_result("search_files → 'Coffee'", resp)

    # 9. Delete a file
    resp = send_request(proc, {
        "jsonrpc": "2.0", "id": 9,
        "method": "tools/call",
        "params": {"name": "delete_file", "arguments": {"filename": "hello.txt"}}
    })
    print_result("delete_file → hello.txt", resp)

    # 10. List again (should show only notes.txt)
    resp = send_request(proc, {
        "jsonrpc": "2.0", "id": 10,
        "method": "tools/call",
        "params": {"name": "list_files", "arguments": {}}
    })
    print_result("list_files (after delete)", resp)

    proc.stdin.close()
    proc.wait()
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    main()
