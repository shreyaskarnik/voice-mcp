#!/bin/bash
# Voice MCP notification hook
# Reads hook JSON from stdin and shows a macOS notification

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
EVENT=$(echo "$INPUT" | jq -r '.hook_event_name // empty')

case "$EVENT" in
  PreToolUse)
    case "$TOOL_NAME" in
      mcp__voice__listen)
        osascript -e 'display notification "Speak now…" with title "🎤 Listening"'
        # Always require explicit user consent before accessing the mic
        jq -n '{
          hookSpecificOutput: {
            hookEventName: "PreToolUse",
            permissionDecision: "ask",
            permissionDecisionReason: "🎤 Claude wants to listen via your microphone"
          }
        }'
        ;;
      mcp__voice__speak)
        TEXT=$(echo "$INPUT" | jq -r '.tool_input.text // empty' | head -c 100)
        osascript -e "display notification \"$TEXT\" with title \"🔊 Speaking\""
        ;;
    esac
    ;;
  PostToolUse)
    case "$TOOL_NAME" in
      mcp__voice__listen)
        TEXT=$(echo "$INPUT" | jq -r '.tool_response.content[0].text // .tool_response // empty' | head -c 100)
        osascript -e "display notification \"$TEXT\" with title \"✅ Heard you\""
        ;;
    esac
    ;;
esac

exit 0
