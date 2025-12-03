#!/usr/bin/env python3
"""Test WebSocket connection to chat endpoint."""
import asyncio
import json
import sys

import pytest

pytestmark = pytest.mark.skip(reason="WebSocket 수동 테스트 스크립트 - 자동 테스트에서 건너뜀")

try:
    import websockets
except ImportError:
    print("websockets not installed. Installing...")
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets


async def test_websocket(session_id: str):
    """Test WebSocket connection and send a message."""
    uri = f"ws://localhost:8000/api/chat/ws/{session_id}"
    print(f"Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected successfully!")

            # Send a test message
            message = {"type": "message", "content": "Hello, this is a test"}
            print(f"Sending: {message}")
            await websocket.send(json.dumps(message))

            # Receive responses
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(response)
                    print(f"Received: {data}")

                    if data.get("type") == "done":
                        print("✓ Message processing complete")
                        break
                    elif data.get("type") == "error":
                        print(f"✗ Error: {data.get('detail')}")
                        break

                except asyncio.TimeoutError:
                    print("✗ Timeout waiting for response")
                    break

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False

    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        session_id = sys.argv[1]
    else:
        session_id = "chat_ae2de9e082d2"

    success = asyncio.run(test_websocket(session_id))
    sys.exit(0 if success else 1)
