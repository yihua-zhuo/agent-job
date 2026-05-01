"""Custom Uvicorn-based server for async Flask app."""
import asyncio
import uvicorn
from uvicorn.config import Config
from uvicorn.server import Server

# Import the Flask app
from src.app import app

if __name__ == "__main__":
    config = Config(
        app=app,
        host="0.0.0.0",
        port=8080,
        loop="asyncio",
        workers=1,
        limit_concurrency=100,
    )
    server = Server(config)
    asyncio.run(server.serve())