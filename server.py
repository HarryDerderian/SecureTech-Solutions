import asyncio

from websockets.asyncio.server import serve
from websockets.asyncio.server import broadcast
from websockets.exceptions import ConnectionClosed
from websockets import serve

class Server :

    def __init__(self) :
        self.connected_clients = set() # will change to a map of client : user
        self.PORT = 7778 
        self.HOST = "localhost"

    async def run(self):
        server = await serve(self.handle_connection, self.HOST, self.PORT)
        print(f"SecureTech Solutions: SecureChat\nServer listening on ws://{self.HOST}:{self.PORT}")
        await server.wait_closed()

    async def handle_connection(self, client) :
        try:
            await self.welcome_msg(client)
            await self.login(client)
            self.connected_clients.add(client)
            await self.messaging(client)
        except ConnectionClosed:
            print("Client disconnected.")
        finally: # will always run at no matter the outcome or the error raised for the client
            self.connected_clients.discard(client) # very important we dont leave hanging clients, get em out of here
            await self.chat_broadcast("User has left the chat.", excluded_client=client)
            

    async def messaging(self, client) :
         async for message in client :
            await self.chat_broadcast(message, client)

    async def welcome_msg(self, client) :
        await client.send("Welcome to Secure Chat.")
    
    async def chat_broadcast(self, message, excluded_client = None):
         broadcast(self.connected_clients.difference({excluded_client}), message)
    
    async def login(self, client) :
        pass

    async def register(self, client) :
        pass


async def main() :
    SecureChat = Server()
    await SecureChat.run()

if __name__ == "__main__":
    asyncio.run(main())