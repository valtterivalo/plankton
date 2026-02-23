## Code Quality Enforcement (plankton)

This project uses Claude Code hooks for automated code quality enforcement.

### Linting Ownership Policy (Boy Scout Rule)

When you edit a file using Edit or Write operations, you accept responsibility
for ALL linting violations in that file - whether you introduced them or they
were pre-existing. There are no exceptions.

- Fix violations immediately when the PostToolUse hook reports them
- Use targeted Edit operations - never rewrite entire files to fix violations
- Address violations before moving on to the next task

### Linter Config File Protection

Linter config files are protected from modification. Modifying them to make
violations disappear (instead of fixing the code) is strictly forbidden.
Fix the code, not the rules.

### Hook Behavior

- **PostToolUse**: Runs linters after every Edit/Write. Auto-formats, collects
  violations, and delegates fixes to a subprocess
- **PreToolUse**: Blocks modifications to linter config files and hook scripts
- **Stop**: Checks for config file modifications at session end
