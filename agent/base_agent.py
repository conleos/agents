#!/usr/bin/env python3
import datetime
import sys

from agent.agent_work_log import send_work_log
from agent.context_handling import (set_conversation_context, load_conversation,
                                    get_all_from_message_queue, add_to_message_queue)
from agent.llm import run_inference
from agent.tools_utils import get_tool_list, execute_tool, deal_with_tool_results
from agent.util import check_for_agent_restart, get_user_message, get_new_messages_from_group_chat


def get_new_message(is_team_mode: bool, consecutive_tool_count: list, read_user_input: bool) -> dict | None:
    if is_team_mode:
        # check message queue for new messages
        messages: list[str] = get_all_from_message_queue()

        if len(messages) > 0:
            consecutive_tool_count[0] = 0
            all_messages: str = ""
            for message in messages:
                all_messages += message + "\n"
            return {"role": "user", "content": all_messages}

        return {"role": "user", "content": "[Automated Message] There are currently no new messages. Please wait."}
    else:
        if read_user_input:
            # prompt for user
            try:
                print(f"\033[94mYou\033[0m: ", end="", flush=True)
                user_input, ok = get_user_message()
            except KeyboardInterrupt:
                # Let the atexit handler take care of deleting the context file
                print("\nExiting program.")
                sys.exit(0)
            if not ok:
                pass
            # Reset consecutive tool count when user provides input
            consecutive_tool_count[0] = 0
            return {"role": "user", "content": user_input}

    return None


class Agent:
    def __init__(self, agent_name: str, llm_client, team_mode: bool):
        self.llm_client = llm_client
        self.tools = get_tool_list(team_mode)
        self.is_team_mode = team_mode
        self.read_user_input = not team_mode  # initialise to True if not in team mode
        # Initialize counter for tracking consecutive tool calls without human interaction
        self.consecutive_tool_count = 0
        # Maximum number of consecutive tool calls allowed before forcing ask_human
        self.max_consecutive_tools = 10
        self.group_chat_messages = []
        self.last_logged_index = 0  # Last index of the group chat messages that were logged
        self.last_log_time = datetime.datetime.utcnow().isoformat()  # Last time a log was sent

        self.name = agent_name

        # For work log tracking
        self.steps_since_last_log = 0
        self.log_every_n_steps = 10  # Default: Send log every 10 steps

    def check_and_send_work_log(self, conversation):
        """Checks if a work log should be sent and sends it if necessary."""
        if self.steps_since_last_log >= self.log_every_n_steps:
            # Check if there are new messages since the last log
            new_messages = conversation[self.last_logged_index:]
            first_timestamp = self.last_log_time
            last_timestamp = datetime.datetime.utcnow().isoformat()
            success = send_work_log(self.name, new_messages, first_timestamp, last_timestamp)
            if success:
                self.steps_since_last_log = 0
                self.last_logged_index = len(conversation)
                self.last_log_time = last_timestamp

    def check_group_messages(self):
        """Checks for new group chat messages and adds them to the message queue.
        If there are no new messages, nothing happens.
        """
        new_messages = get_new_messages_from_group_chat(self.group_chat_messages)
        self.group_chat_messages.extend(new_messages)
        # Add new messages to the queue
        for message in new_messages:
            formatted_message = f"[Group Chat] {message['username']}: {message['message']}"
            add_to_message_queue(formatted_message)

    def run(self):
        # Try to load saved conversation context
        conversation = load_conversation()

        # Check if this is a restart initiated by the agent
        agent_initiated_restart = False
        if conversation:
            print("Restored previous conversation context")
            agent_initiated_restart = check_for_agent_restart(conversation)
            # If we're continuing after a restart, add a system message to inform the agent
            if agent_initiated_restart:
                conversation.append({
                    "role": "user",
                    "content": [{
                        "type": "text",
                        "text": "The program has restarted and is continuing execution automatically. Please continue from where you left off.",
                        "cache_control": {"type": "ephemeral"}
                    }]
                })
                self.read_user_input = False
        else:
            conversation = []

        # Set the global conversation context reference
        set_conversation_context(conversation)

        while True:
            if self.is_team_mode:
                # Check for new group messages at each cycle
                self.check_group_messages()

            tool_count_object = [self.consecutive_tool_count]
            message = get_new_message(self.is_team_mode, tool_count_object, self.read_user_input)
            self.consecutive_tool_count = tool_count_object[0]
            if message is not None:
                conversation.append(message)

            response = run_inference(conversation, self.llm_client, self.tools, self.consecutive_tool_count,
                                     self.name, self.is_team_mode,
                                     self.max_consecutive_tools)
            tool_results = []

            # print assistant text and collect any tool calls
            for block in response.content:
                if block.type == "text":
                    print(f"\033[93m{self.name}\033[0m: {block.text}")
                elif block.type == "tool_use":
                    # If the tool is ask_human, reset counter before executing
                    if block.name == "ask_human":
                        self.consecutive_tool_count = 0
                    else:  # Only increment for non-ask_human tools
                        self.consecutive_tool_count += 1
                        print(
                            f"\033[96mConsecutive tool count: {self.consecutive_tool_count}/{self.max_consecutive_tools}\033[0m")

                    result = execute_tool(self.tools, block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            # 2) First, append the assistant's own message (including its tool_use blocks!)
            conversation.append({
                "role": "assistant",
                "content": [
                    # for each block LLM returned, mirror it exactly
                    {
                        "type": b.type,
                        **({
                               "text": b.text
                           } if b.type == "text" else {
                            "id": b.id,
                            "name": b.name,
                            "input": b.input
                        }),
                        "cache_control": {"type": "ephemeral"}
                    }
                    for b in response.content
                ]
            })

            # 3) If there were any tool calls, follow up with tool_results as a user turn
            if tool_results:
                self.read_user_input = False
                deal_with_tool_results(tool_results, conversation)
            else:
                self.read_user_input = not self.is_team_mode

            # Count a step
            self.steps_since_last_log += 1

            # Check if a work log should be sent
            self.check_and_send_work_log(conversation)
