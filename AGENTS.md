# Repository Instructions

## Project Shape
- This is a zero-dependency Python MCP server implemented in `server.py`.
- `test_server.py` is the local JSON-RPC smoke-test harness.
- File operations are sandboxed to the generated `workspace/` directory.

## Commands
- Run the main verification with `python3 test_server.py`.
- No package installation is required for normal development or testing.

## Working Notes
- Keep changes scoped and dependency-free unless the project requirements change.
- Do not commit generated `workspace/` contents unless explicitly requested.
