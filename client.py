import asyncio
import websockets
import sys
import os

class Client:
    def __init__(self):
        self.URI = "ws://localhost:7778"

    async def receive_messages(self, websocket):
        first_message = True  # Track the first message
        try:
            async for message in websocket:
                sys.stdout.write("\r" + " " * 50 + "\r")  # Clear input line
                print(message)
                if first_message:
                    first_message = False  # Skip reprinting prompt on the first message
                else:
                    sys.stdout.write(">> ")
                    sys.stdout.flush()
        finally:
            pass

    async def send_messages(self, websocket):
        while True:
            message = await asyncio.to_thread(input, ">> ")
            await websocket.send(message)
    
    async def connect(self):
        attempts = 3
        while True:
            try:
                async with websockets.connect(self.URI) as websocket:
                    print("[+] Connected to server.")
                    receive_task = asyncio.create_task(self.receive_messages(websocket))
                    send_task = asyncio.create_task(self.send_messages(websocket))
                    await asyncio.gather(receive_task, send_task)
            except (websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK, OSError):
                    print("[!] Connection lost. Attempting to reconnect...")
                    await self.heartbeat(attempts)  # Pass attempts for backoff
                    attempts = attempts * 2

    
    
    async def heartbeat(self, attempts):
        max_attempts = 30  # Prevent infinite wait time
        while attempts < max_attempts:
            for i in range(attempts, 0, -1):
                os.system("cls" if os.name == "nt" else "clear")  # Clear console
                print(f"[!] Connection lost. Retrying in {i} second{'s' if i > 1 else ''}...")
                await asyncio.sleep(1)
            
            os.system("cls" if os.name == "nt" else "clear")  # Clear console before retry message
            print("[!] Retrying now...")
            return min(attempts * 2, max_attempts)

        print("[!] Maximum retry limit reached. Giving up.")
        return 3  # Reset attempts in case we want to restart later


async def main():
    URI = "ws://localhost:8765"
    client = Client()
    await client.connect()

asyncio.run(main())
