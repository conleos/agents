# restart_program_tool.py

import json
import os
import pickle
import sys

from agent.tools.base_tool import ToolDefinition

# ------------------------------------------------------------------
# Input schema for the restart_program tool
# ------------------------------------------------------------------
RestartProgramInputSchema = {
    "type": "object",
    "properties": {
        "reason": {
            "type": "string",
            "description": "Optional reason for restarting the program"
        },
        "save_file": {
            "type": "string",
            "description": "Optional file path to save conversation context to. Defaults to 'conversation_context.pkl'"
        }
    }
}


def restart_program(input_data: dict) -> str:
    """
    Saves the current conversation context to a file and restarts the program.
    Returns a JSON string with the status of the operation.
    """
    # support raw JSON string or already-parsed dict
    if isinstance(input_data, str):
        input_data = json.loads(input_data)

    reason = input_data.get("reason", "Reloading tools")

    result = {
        "message": f"Program will restart.",
        "reason": reason,
        "restart": True,
        "agent_initiated": True  # Flag to indicate this restart was initiated by the agent
    }
    return json.dumps(result)


def load_conversation_context(save_file: str = "conversation_context.pkl"):
    """
    Call this once at your program’s entrypoint to restore a prior session.
    """
    if os.path.exists(save_file):
        with open(save_file, "rb") as f:
            context = pickle.load(f)
        return context
    return None


def save_conversation(conversation, save_file: str):
    """Save the conversation context to a file"""
    try:
        with open(save_file, 'wb') as f:
            pickle.dump(conversation, f)
        return True
    except Exception as e:
        error_message = f"Error saving conversation: {str(e)}"
        print(error_message)
        try:
            with open("error.txt", "a") as f:
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"\n[{timestamp}] ERROR: {error_message}\n")
        except Exception:
            pass  # Silently fail if we can't log to error.txt
        return False


def save_conv_and_restart(conversation, save_file: str = "conversation_context.pkl"):
    save_conversation(conversation, save_file)

    # Set a flag to indicate we're intentionally restarting
    sys.is_restarting = True
    
    # re-exec in-place:
    python = sys.executable
    os.execv(python, [python] + sys.argv)


# ------------------------------------------------------------------
# ToolDefinition instance
# ------------------------------------------------------------------
RestartProgramDefinition = ToolDefinition(
    name="restart_program",
    description=(
        "Restart the Python program while preserving the conversation context "
        "by saving it to a file and reloading on startup"
    ),
    input_schema=RestartProgramInputSchema,
    function=restart_program
)
