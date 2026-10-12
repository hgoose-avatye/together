#!/bin/bash
# PostToolUse(Write|Edit): 수정된 파일 하나만 포맷한다. 도구가 아직 없으면 조용히 넘어간다.
export PATH="$HOME/.local/bin:$PATH"
f=$(jq -r '.tool_response.filePath // .tool_input.file_path // empty')
[ -z "$f" ] && exit 0

case "$f" in
  *.py)
    command -v uvx >/dev/null && uvx ruff format --quiet "$f"
    ;;
  */frontend/*.ts | */frontend/*.tsx | */frontend/*.js | */frontend/*.jsx | */frontend/*.css | */frontend/*.json)
    p="$CLAUDE_PROJECT_DIR/frontend/node_modules/.bin/prettier"
    [ -x "$p" ] && "$p" --write --log-level warn "$f"
    ;;
esac
exit 0
