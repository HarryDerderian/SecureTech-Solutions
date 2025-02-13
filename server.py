import asyncio
import sqlite3
import pathlib
import ssl
import bcrypt

from websockets.asyncio.server import serve
from websockets.asyncio.server import broadcast
from websockets.exceptions import ConnectionClosed
from websockets import serve


# TO-DO 
# only allow one instances of a user at one time aka you can only log in once per session no double harry
# some basic Rate Limiting

# Finished
# Real-Time Messaging
# Secure Connection
# User Authentication
# Detect and handle dropped connections gracefully (Join & Disconnect functionality)
# Reconnect clients automatically in case of interruptions (e.g heartbeat functionality) 


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
        self.connected_clients = {} 
        self.connections_per_ip = {} # ip : total connections
        self.PORT = 7778 
        self.HOST = "localhost"
        self.db = sqlite3.connect("securechat.db")
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.localhost_pem = pathlib.Path(__file__).with_name("localhost.pem")
        self.ssl_context.load_cert_chain(self.localhost_pem)


     # Asking the user if they want to login or register upon connection
    async def initial_connect_prompt(self, client) -> User:
        valid = False
        while(not valid) :
            await client.send("Welcome to Secure Chat. Type 'L' to login or 'R' to register.")
            response = await client.recv()
            print(response)
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
        server = await serve(self.handle_connection, self.HOST, self.PORT, ssl = self.ssl_context)
        print(f"SecureTech Solutions: SecureChat\nServer listening on wss://{self.HOST}:{self.PORT}")
        await server.wait_closed()

    async def connection_limiting(self, client) :
        ip = client.remote_address[0] 
        if ip in self.connections_per_ip and self.connections_per_ip[ip] > 2 :
                await self.disconnect(client)
                return True
        return False

    async def handle_connection(self, client) :
        try:
            client_ip = client.remote_address[0]
            if client_ip in self.connections_per_ip :
                self.connections_per_ip[client_ip] += 1
            else :
                self.connections_per_ip[client_ip] = 1
            if(await self.connection_limiting(client)) : return
            
            user = await self.initial_connect_prompt(client) # return the user 
            if user is None : 
                await self.disconnect(client)
                return
                
            self.connected_clients[client] = user
            if(await self.connection_limiting(client)) :
                return
            await self.chat_broadcast(f"{self.connected_clients[client].username} has joined the chat.", excluded_client=client)
            await self.messaging(client)
        except ConnectionClosed:
            print("Client disconnected.")
            self.connections_per_ip[client_ip] -= 1
        finally: # will always run at no matter the outcome or the error raised for the client
            if client in self.connected_clients.keys() :
                await self.chat_broadcast(f"{self.connected_clients[client].username} has left the chat.", excluded_client=client)
                del self.connected_clients[client]# very important we dont leave hanging clients, get em out of here

            
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
        attempts = 3
        cursor = self.db.cursor()
        while attempts > 0 :
            await client.send("Enter your username: ")
            username = await client.recv()
            await client.send("Enter your password: ")
            password = await client.recv()
            userBytes = password.encode()

            dbUser = cursor.execute("SELECT * FROM users WHERE user = ?", (username,)).fetchone()

            if dbUser:
                stored_hash = dbUser[1]  # dbUser[1] is the hashed password
                if bcrypt.checkpw(userBytes, stored_hash):  # Compare entered password with hash
                    print("User " + dbUser[0] + " authenticated")
                    user = User(username, password)
                    await client.send(f"Welcome back, {username}! 🔐\nYou are now securely connected to SecureChat. Enjoy your conversation!")
                    cursor.close()
                    return user
            else:
                await client.send("Invalid credentials. Please try again.")
                attempts -= 1

        cursor.close()
        return None

    async def register(self, client) :
        cursor = self.db.cursor()
        while True :
            await client.send("Enter a username: ")
            username = await client.recv()
            cursor.execute("SELECT * FROM users WHERE user = ?", (username,))
            # Check that the username is not already taken.
            if cursor.fetchone() is None : break 
            else : await client.send("username already taken.")
        
        await client.send("Enter a password: ")
        password = await client.recv()
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        print(password)
        print(hashed_password)
        user = User(username, hashed_password)
        print(user.password)
        cursor.execute("INSERT INTO users VALUES (?, ?)", (username, hashed_password))
        cursor.close()
        self.db.commit() # save the changes to the db
        await client.send(f"Welcome to SecureChat, {username}! 🎉\nYou have successfully registered. Enjoy secure and private conversations!")
        return user
    
    async def disconnect(self, client) :
        client_ip = client.remote_address[0]
        self.connections_per_ip[client_ip] -= 1
        await client.send("You have been disconnected by the server.")
        await client.close()
        if client in self.connected_clients :
            del self.connected_clients[client]


async def main() :
    SecureChat = Server()
    await SecureChat.run()

if __name__ == "__main__":
    asyncio.run(main())