import threading

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from agent.context_handling import add_to_message_queue

# Initialize FastAPI app and agent
app = FastAPI()


class MessageRequest(BaseModel):
    message: str
    from_agent: str


class ApiResponse(BaseModel):
    response: str
    status: str = "queued"


@app.post("/send-message")
async def send_to_agent(request: MessageRequest):
    """
    API endpoint for sending messages to the agent
    The message is added to the conversation queue
    """
    formatted_message = f"[Direct message from {request.from_agent}]: {request.message}"
    # Add message to the queue
    add_to_message_queue(formatted_message)

    # Return immediate feedback
    return ApiResponse(
        response="Your message has been sent to the agent and will be processed in the conversation.",
        status="sent"
    )


def start_uvicorn_app():
    uvicorn.run(app, host="0.0.0.0", port=8000)


def start_api():
    """Start the API server in the background"""
    # todo add ability to set port via env var
    api_thread = threading.Thread(target=start_uvicorn_app, daemon=True)
    api_thread.start()
    print(f"\033[92mAPI server has been started and is available at http://localhost:8000/\033[0m")
