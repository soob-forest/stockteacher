"""Test WebSocket chat endpoint."""
import asyncio
import json
import sys

import websockets
import pytest

pytestmark = pytest.mark.skip(reason="WebSocket 수동 테스트 스크립트 - 자동 테스트에서 건너뜀")


async def test_websocket():
    session_id = sys.argv[1] if len(sys.argv) > 1 else "chat_f18e80ebb246"
    uri = f"ws://127.0.0.1:8000/api/chat/ws/{session_id}"

    print(f"Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected!")

            # Send test message
            message = {"type": "message", "content": "안녕하세요, 테스트입니다."}
            print(f"Sending: {message}")
            await websocket.send(json.dumps(message))

            # Receive responses
            chunks = []
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                print(f"Received: {data['type']}")

                if data['type'] == 'chunk':
                    chunks.append(data['content'])
                    print(f"  Chunk: {data['content'][:50]}...")
                elif data['type'] == 'done':
                    print(f"✓ Streaming complete!")
                    print(f"Full response: {''.join(chunks)}")
                    break
                elif data['type'] == 'error':
                    print(f"✗ Error: {data['detail']}")
                    break

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_websocket())
