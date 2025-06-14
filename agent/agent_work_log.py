#!/usr/bin/env python3
import os

import requests
from typing import List, Dict, Any

from pydantic import BaseModel

WORK_LOG_BASE_URL = os.getenv("WORK_LOG_BASE_URL") or "http://localhost:8082"

class WorklogRequest(BaseModel):
    agent_id: str
    first_timestamp: str
    last_timestamp: str
    messages: List[Dict[str, Any]]

def send_work_log(agent_id: str, new_messages: List[Dict[str, Any]], first_timestamp: str, last_timestamp: str):
    """
    Sends a work log to the Group Work Log Service.

    Args:
        agent_id: The ID of the agent
        new_messages: The current conversation
        last_timestamp: The timestamp of the last log
        first_timestamp: The timestamp of the first log in this session
    """

    # Prepare the request payload
    payload = WorklogRequest(
        agent_id=agent_id,
        first_timestamp=first_timestamp,
        last_timestamp=last_timestamp,
        messages=new_messages
    )

    try:
        # Send the request to the Group Work Log Service
        response = requests.post(f"{WORK_LOG_BASE_URL}/submit-worklog", json=payload)
        if response.status_code == 200:
            print(f"\033[92mWork log successfully sent\033[0m")
            return True
        else:
            print(f"\033[91mError sending work log: {response.status_code}\033[0m")
            return False
    except Exception as e:
        print(f"\033[91mError sending work log: {str(e)}\033[0m")
        return False