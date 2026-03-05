# Use Agent

Switch to a specific VK_Importer agent profile and execute the task with that profile.

## Command format
`/use_agent <agent> <task>`

Tip:
- Use dedicated slash commands with autocomplete:
  - `/use_python_dev`
  - `/use_python_debug`
  - `/pydev`
  - `/pydebug`

## Agent map (VK_Importer)
- `python-developer`
  - Rule: `.cursor/rules/agent-python-developer.mdc`
  - Prompt: `.cursor/subagents/python-developer.prompt.md`
- `python-debugger`
  - Rule: `.cursor/rules/agent-python-debugger.mdc`
  - Prompt: `.cursor/subagents/python-debugger.prompt.md`

## Execution instructions
1. Parse first token after command as `agent`.
2. Treat remaining text as `task`.
3. Load and follow mapped rule/prompt for selected `agent`.
4. If `agent` is unknown, show supported agents and stop.
