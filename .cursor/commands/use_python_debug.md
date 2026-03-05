# Use Python Debugger

Use agent profile `python-debugger` for this chat task.

## Agent binding
- Rule: `.cursor/rules/agent-python-debugger.mdc`
- Prompt: `.cursor/subagents/python-debugger.prompt.md`

## Instructions
1. Apply the bound rule and prompt.
2. Execute task text after `/use_python_debug`.
3. If task text is empty, ask for reproduction context.
4. Use MCP alias `postgresql` for DB state diagnostics (read-only by default).

