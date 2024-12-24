import threading
import chainlit as cl
from chainlit.server import run_server
import uvicorn

def start_chainlit():
    """Starts the Chainlit server in a background thread"""
    config = uvicorn.Config(app=run_server(), host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    server.run()

@cl.on_chat_start
async def chat_start():
    """Runs at the start of a new chat session"""
    await cl.Message(
        content="Hello! I'm ready to chat. How can I help you today?"
    ).send()

@cl.on_message
async def on_message(message: str):
    """Handles incoming chat messages"""
    await cl.Message(
        content=f"You said: {message}"
    ).send()

def main():
    """Main entry point of the application."""
    print("Starting main application...")
    
    # Start Chainlit in a background thread
    chainlit_thread = threading.Thread(target=start_chainlit, daemon=True)
    chainlit_thread.start()
    
    print("Chainlit server is running on http://localhost:8000")
    
    # Your main application logic can continue here
    try:
        while True:
            # Keep the main thread running
            # You can add other processing here
            pass
    except KeyboardInterrupt:
        print("\nShutting down...")

if __name__ == "__main__":
    main()
