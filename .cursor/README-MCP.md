# MCP Policy (VK_Importer)

## Standard alias
Use `postgresql` as MCP server alias.

## Default access mode
- DB analysis is read-only by default.
- Use write operations only when task explicitly requires this and rollback is defined.

## Notes
- Current DSN points to local `Pipeline` database.
- For shared environments, replace with least-privilege credentials.

