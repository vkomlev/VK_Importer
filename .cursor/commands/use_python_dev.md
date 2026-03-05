# Use Python Developer

Use agent profile `python-developer` for this chat task.

## Agent binding
- Rule: `.cursor/rules/agent-python-developer.mdc`
- Prompt: `.cursor/subagents/python-developer.prompt.md`

## Instructions
1. Apply the bound rule and prompt.
2. Execute task text after `/use_python_dev`.
3. If task text is empty, ask for objective and acceptance criteria.
4. Use MCP alias `postgresql` for DB diagnostics when task touches data.

