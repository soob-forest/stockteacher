"""WebSocket connection manager for chat sessions."""

from __future__ import annotations

from typing import Dict

from fastapi import WebSocket


class ConnectionManager:
    """Manages active WebSocket connections for chat sessions."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        """Accept and register a WebSocket connection.

        Args:
            session_id: Chat session ID
            websocket: WebSocket connection to register
        """
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        """Remove a WebSocket connection.

        Args:
            session_id: Chat session ID to disconnect
        """
        self.active_connections.pop(session_id, None)

    async def send_message(self, session_id: str, message: dict):
        """Send a JSON message to a specific session.

        Args:
            session_id: Target chat session ID
            message: Dictionary to send as JSON

        Returns:
            True if message sent successfully, False if session not connected
        """
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)
            return True
        return False


# Global instance
manager = ConnectionManager()
