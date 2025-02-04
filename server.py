import asyncio
import sqlite3

from websockets.asyncio.server import serve
from websockets.asyncio.server import broadcast
from websockets.exceptions import ConnectionClosed
from websockets import serve

class User :
    def __init__(self, username, password) :
        self.username = username
        self.password = password


def initialize_db() :
    conn = sqlite3.connect("securechat.db")
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE users (
                      user text,
                      pass text
                      )""")
    
    



class Server :

    def __init__(self) :
        self.connected_clients = {} # will change to a map of client : user -- client
        self.PORT = 7778 
        self.HOST = "localhost"
        self.db = sqlite3.connect("securechat.db")

    # Asking the user if they want to login or register upon connection
    async def initial_connect_prompt(self, client) -> User:
        # await self.welcome_msg(client)
        valid = False
        while(not valid) :
            await client.send("Welcome to Secure Chat. Type 'L' to login or 'R' to register.")
            response = await client.recv()
            if response.upper() == "L" : 
                user = await self.login(client)
                valid = True
            elif response.upper() == "R" : 
                user = await self.register(client)
                valid = True
            else : 
                await client.send("Invalid input. Please try again.")

        return user

    async def run(self):
        server = await serve(self.handle_connection, self.HOST, self.PORT)
        print(f"SecureTech Solutions: SecureChat\nServer listening on ws://{self.HOST}:{self.PORT}")
        await server.wait_closed()

    async def handle_connection(self, client) :
        try:
            user = await self.initial_connect_prompt(client) # return the user 
            if user  is None : print("We will disconnect that user")
            self.connected_clients[client] = user
            await self.messaging(client)
        except ConnectionClosed:
            print("Client disconnected.")
        finally: # will always run at no matter the outcome or the error raised for the client
            self.connected_clients.discard(client) # very important we dont leave hanging clients, get em out of here
            await self.chat_broadcast("User has left the chat.", excluded_client=client)
            

    async def messaging(self, client) :
         async for message in client :
            username = self.connected_clients[client].username
            message = f"{username}: {message}"
            await self.chat_broadcast(message, client)

    async def welcome_msg(self, client) :
        await client.send("Welcome to Secure Chat.")
    
    async def chat_broadcast(self, message, excluded_client = None):
         broadcast(set(self.connected_clients.keys()).difference({excluded_client}), message)
    
    async def login(self, client) :
        print("Login test")
        attempts = 3
        while attempts > 0 :
            await client.send("Enter your username: ")
            username = await client.recv()
            await client.send("Enter your password: ")
            password = await client.recv()

            cursor = self.db.cursor()
            cursor.execute("SELECT * FROM users WHERE user = ? AND pass = ?", (username, password))
            query = cursor.fetchone()
            cursor.close()
            if query is None :
                await client.send("Invalid credentials. Please try again.")
                attempts -= 1
            else : 
                user = User(username, password)
                return user

        print("Too many invalid attempts. Disconnecting user.")
        
        return None

        

    async def register(self, client) :
        # print("Register test")
        await client.send("Enter a username: ")
        username = await client.recv()
        await client.send("Enter a password: ")
        password = await client.recv()

        user = User(username, password)

        cursor = self.db.cursor()
        cursor.execute("INSERT INTO users VALUES (?, ?)", (username, password))
        cursor.close()
        # cursor.execute("SELECT * FROM users")
        # print(cursor.fetchall())

        return user


async def main() :
    # initialize_db()
    SecureChat = Server()
    await SecureChat.run()

if __name__ == "__main__":
    asyncio.run(main())