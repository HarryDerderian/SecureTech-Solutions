import asyncio
import sqlite3
import pathlib
import ssl
import bcrypt
import time
import os
import re
import json


from websockets.asyncio.server import serve
from websockets.asyncio.server import broadcast
from websockets.exceptions import ConnectionClosed
from websockets import serve


class User :
    def __init__(self, username, password) :
        self.username = username
        self.password = password


class RateLimiter:
    def __init__(self, max_messages, time_period):
        self.max_messages = max_messages
        self.time_period = time_period
        self.message_timestamps = []

    def can_send_message(self):
        current_time = time.time()

        # Remove timestamps that are older than the time period
        self.message_timestamps = [
            timestamp for timestamp in self.message_timestamps if current_time - timestamp <= self.time_period
        ] 

        # Check if the user has exceeded the message limit in the time period
        if len(self.message_timestamps) < self.max_messages:
            self.message_timestamps.append(current_time)
            return True
        else:
            return False



def initialize_db():
    # Check if the database file already exists
    if not os.path.exists("securechat.db"):
        conn = sqlite3.connect("securechat.db")
        cursor = conn.cursor()
        cursor.execute("""CREATE TABLE users (
                          user text,
                          pass text
                          )""")
        conn.commit()  # Commit changes to the database
        conn.close()   # Close the connection
    
class Server :
    def __init__(self) :
        self.connected_clients = {} 
        self.connections_per_ip = {} # ip : total connections
        self.PORT = 7778 
        self.HOST = "localhost"
        self.db = sqlite3.connect("securechat.db")
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.key_pem = pathlib.Path(__file__).with_name("key.pem")
        self.ssl_context.load_cert_chain(self.key_pem)
        self.rate_limiter = {}


     # Asking the user if they want to login or register upon connection
    async def initial_connect_prompt(self, client) -> User:
        valid = False
        while(not valid) :
            msg_json = {
                "type": "server",
                "content": "Welcome to Secure Chat. Type 'L' to login or 'R' to register."
            }
            await client.send(json.dumps(msg_json))
            message = await client.recv()
            json_msg = json.loads(message)
            response = json_msg.get("content")
            if response.upper() == "L" : 
                user = await self.login(client)
                valid = True
            elif response.upper() == "R" : 
                user = await self.register(client)
                valid = True
            else : 
                msg_json = {
                "type": "server",
                "content": "Invalid input. Please try again."
                }
                await client.send(json.dumps(msg_json))
        return user



    async def run(self):
        server = await serve(self.handle_connection, self.HOST, self.PORT, ssl = self.ssl_context)
        print(f"SecureTech Solutions: SecureChat\nServer listening on wss://{self.HOST}:{self.PORT}")
        await server.wait_closed()



    async def connection_limiting(self, client) :
        ip = client.remote_address[0] 
        if ip in self.connections_per_ip and self.connections_per_ip[ip] > 2 :
                await self.disconnect(client, ip)
                return True
        return False



    async def sso(self, username) :
        for user in self.connected_clients.values() :
            if username == user.username :
                return False
        return True



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
                await self.disconnect(client, client_ip)
                return
                
            self.connected_clients[client] = user
            await self.chat_broadcast(f"{self.connected_clients[client].username} has joined the chat.", excluded_client=client)
            await self.messaging(client)
        except ConnectionClosed:
            print("Client disconnected.")
           
        finally: # will always run at no matter the outcome or the error raised for the client
            if client_ip and self.connections_per_ip[client_ip] > 0 : self.connections_per_ip[client_ip] -= 1
            if client in self.connected_clients.keys() :
                await self.chat_broadcast(f"{self.connected_clients[client].username} has left the chat.", excluded_client=client)
                del self.connected_clients[client]# very important we dont leave hanging clients, get em out of here



    async def messaging(self, client) :
        rate_limiter = self.rate_limiter.get(client)
        if rate_limiter is None :
            self.rate_limiter[client] = RateLimiter(max_messages=1, time_period=1) # 5 messages per second
            rate_limiter = self.rate_limiter[client]

        async for json_msg in client :
            # Check if the user has exceeded the message limit
            msg_data = json.loads(json_msg)
            message = msg_data.get("content")
            if not rate_limiter.can_send_message():
                msg_json = {
                            "type": "server",
                            "content": "You are sending messages too quickly. Please wait before sending another message."
                }
                await client.send(json.dumps(msg_json))    
                continue

            username = self.connected_clients[client].username
            message = f"{username}: {message}"
            await self.chat_broadcast(message, client)



    async def welcome_msg(self, client) :
        msg_json = {
                "type": "server",
                "content": "Welcome to Secure Chat."
             }
        await client.send(json.dumps(msg_json))    
    


    async def chat_broadcast(self, message, excluded_client = None):
         msg_json = {
                "type": "server",
                "content": message
         }
         broadcast(set(self.connected_clients.keys()).difference({excluded_client}), json.dumps(msg_json))
    


    async def login(self, client) :
        attempts = 3
        cursor = self.db.cursor()
        while attempts > 0 :
            msg_json = {
                "type": "server",
                "content": "Enter your username: "
             }
            await client.send(json.dumps(msg_json))  
            message = await client.recv()
            json_msg = json.loads(message)
            username = json_msg.get("content")
            msg_json["content"] = "Enter your password: "
            await client.send(json.dumps(msg_json))  
            
            message = await client.recv()
            json_msg = json.loads(message)
            password = json_msg.get("content")
            userBytes = password.encode()
            dbUser = cursor.execute("SELECT * FROM users WHERE user = ?", (username,)).fetchone()  
            if dbUser : stored_hash = dbUser[1] 
            
            if dbUser and bcrypt.checkpw(userBytes,  stored_hash) :
                print("User " + dbUser[0] + " authenticated")
                user = User(username, password)
                if not await self.sso(username) :
                    msg_json["content"] = f"[!] You are already signed in."
                    await client.send(json.dumps(msg_json))  
                    return None
                else :
                    msg_json["content"] = f"Welcome back, {username}! 🔐\nYou are now securely connected to SecureChat. Enjoy your conversation!"
                    await client.send(json.dumps(msg_json))  
                    cursor.close()
                    return user
            else:
                msg_json["content"] = "Invalid credentials. Please try again."
                await client.send(json.dumps(msg_json))  
                attempts -= 1

        cursor.close()
        return None



    async def register(self, client) :
           try :
                cursor = self.db.cursor()
                msg_json = {
                    "type": "server",
                    "content": "Enter a username: "
                     }
                while True :
                    msg_json["content"] = "Enter a username: "
                    await client.send(json.dumps(msg_json))  
                    message = await client.recv()
                    json_msg = json.loads(message)
                    username = json_msg.get("content")
                    cursor.execute("SELECT * FROM users WHERE user = ?", (username,))
                    # Check that the username is not already taken.
                    if cursor.fetchone() is None : 
                        print("nothing found")
                        break 
                    else : 
                        msg_json["content"] = "username already taken."
                        await client.send(json.dumps(msg_json))  
                
                while True :
                    msg_json["content"] = "Enter a password: "
                    await client.send(json.dumps(msg_json))  
                    message = await client.recv()
                    json_msg = json.loads(message)
                    password = json_msg.get("content")
                    # Check if the password meets the requirements
                    if await self.check_password(client, password):
                        break

                hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
                user = User(username, hashed_password)

                cursor.execute("INSERT INTO users VALUES (?, ?)", (username, hashed_password))
                cursor.close()
                self.db.commit() # save the changes to the db
                msg_json["content"] = f"Welcome to SecureChat, {username}! 🎉\nYou have successfully registered. Enjoy secure and private conversations!"
                await client.send(json.dumps(msg_json)) 
                return user
           except Exception as e:
                    print(f"Error during registration: {e}")  # Log the error
                    return None  # Return None if an error occurs
           finally:
                    if cursor:
                        cursor.close()  # Ensure the cursor is always closed



    async def check_password(self, client, password):
        if len(password) < 15:
            msg_json = {
                "type": "server",
                "content": "Password must be at least 15 characters long."
                }
            await client.send(json.dumps(msg_json))
            return False
        if not re.search("[A-Z]", password):
            msg_json = {
                "type": "server",
                "content": "Password must contain at least one uppercase letter."
             }
            await client.send(json.dumps(msg_json))
            return False
        if not re.search("[a-z]", password):
            msg_json = {
                "type": "server",
                "content": "Password must contain at least one lowercase letter."
             }
            await client.send(json.dumps(msg_json))
            return False
        if not re.search("[0-9]", password):
            msg_json = {
                "type": "server",
                "content": "Password must contain at least one digit."
             }
            await client.send(json.dumps(msg_json))
            return False    
        if not re.search("[!@#$%^&*]", password):
            msg_json = {
                "type": "server",
                "content": "Password must contain at least one special character."
             }
            await client.send(json.dumps(msg_json))
            return False
        if " " in password:
            msg_json = {
                "type": "server",
                "content": "Password cannot contain spaces."
             }
            await client.send(json.dumps(msg_json))            
            return False
        
        # If all checks pass
        return True
    


    async def disconnect(self, client, client_ip) :
        self.connections_per_ip[client_ip] -= 1
        msg_json = {
                "type": "server",
                "content": "You have been disconnected by the server."
             }
        await client.send(json.dumps(msg_json))    
        await client.close()
        if client in self.connected_clients :
            del self.connected_clients[client]


async def main() :
    initialize_db()
    SecureChat = Server()
    await SecureChat.run()

if __name__ == "__main__":
    asyncio.run(main())