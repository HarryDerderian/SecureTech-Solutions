import asyncio
import websockets
import sys
class Client:
    def __init__(self):
        self.URI = "ws://localhost:7778"

    async def receive_messages(self, websocket):
        try:
            async for message in websocket:
                sys.stdout.write("\r" + " " * 50 + "\r")  # Clear input line
                print(message)
                sys.stdout.write(">> ")  # Reprint the prompt
                sys.stdout.flush()  # Ensure it appears immediately
        finally:
            pass

    async def send_messages(self, websocket):
        while True:
            message = await asyncio.to_thread(input, ">> ")
            await websocket.send(message)

    async def connect(self):
        async with websockets.connect(self.URI) as websocket:
            receive_task = asyncio.create_task(self.receive_messages(websocket))
            send_task = asyncio.create_task(self.send_messages(websocket))
            await asyncio.gather(receive_task, send_task)

async def main():
    URI = "ws://localhost:8765"
    client = Client()
    await client.connect()

asyncio.run(main())
