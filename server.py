import asyncio
import sqlite3
import pathlib
import ssl
import bcrypt
import time
import os
import re
import json
import uuid
import base64

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
        
        # Create the users table
        cursor.execute("""CREATE TABLE IF NOT EXISTS users (
                          user TEXT,
                          pass TEXT
                          )""")
        
        # Create the messages table
        cursor.execute("""CREATE TABLE IF NOT EXISTS messages (
                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                          username TEXT,
                          message TEXT,
                          chat_type TEXT, 
                          recipient TEXT, 
                          conversation_id TEXT,
                          timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                          )""")
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS files (
                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                          file_name TEXT,
                          file_path TEXT,
                          sender TEXT,
                          recipient TEXT,
                          chat_type TEXT,
                          timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
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
        server = await serve(self.handle_connection, self.HOST, self.PORT, ssl = self.ssl_context,  max_size=100 * 1024 * 1024)
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


    async def get_all_users(self):
        """Fetch all users from the database."""
        cursor = self.db.cursor()
        cursor.execute("SELECT user FROM users")
        users = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return users


    async def send_user_list(self):
        """Send the list of all users to all clients."""
        all_users = await self.get_all_users()
        msg_json = {
            "type": "user_list",
            "content": all_users
        }
        await self.chat_broadcast(json.dumps(msg_json))


    async def handle_connection(self, client):
        try:
            client_ip = client.remote_address[0]
            if client_ip in self.connections_per_ip:
                self.connections_per_ip[client_ip] += 1
            else:
                self.connections_per_ip[client_ip] = 1
            if await self.connection_limiting(client):
                return

            user = await self.initial_connect_prompt(client)  # return the user
            if user is None:
                await self.disconnect(client, client_ip)
                return

            self.connected_clients[client] = user
            all_users = await self.get_all_users()
            msg_json = {
                "type": "user_list",
                "content": all_users
            }
            await client.send(json.dumps(msg_json))
            # Send previous group chat messages to the client
            await self.send_previous_messages(client, "group")

            await self.chat_broadcast(f"{self.connected_clients[client].username} has joined the chat.", excluded_client=client)
            await self.messaging(client)
        except ConnectionClosed:
            print("Client disconnected.")
        finally:
            if client_ip and self.connections_per_ip[client_ip] > 0:
                self.connections_per_ip[client_ip] -= 1
            if client in self.connected_clients.keys():
                await self.chat_broadcast(f"{self.connected_clients[client].username} has left the chat.", excluded_client=client)
                del self.connected_clients[client]  # very important we don't leave hanging clients, get them out of here



    async def send_previous_messages(self, client, chat_type, recipient=None):
        """Send previous messages for the specified chat type."""
        print("loading messages.......")
        
        cursor = self.db.cursor()
        if chat_type == "group":
            cursor.execute("SELECT username, message FROM messages WHERE chat_type = ? ORDER BY timestamp ASC", (chat_type,))
        elif chat_type == "private":
             current_user = self.connected_clients[client].username

            # Generate conversation_id based on usernames in alphabetical order
             conversation_id = "_".join(sorted([current_user, recipient]))

            # Fetch messages for the conversation_id
             cursor.execute("""
                SELECT username, message 
                FROM messages 
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            """, (conversation_id,))

        # Fetch all results
        messages = cursor.fetchall()     
        cursor.close()

        if messages:
            # Format messages as a list of strings
            print(f"messages found {messages}")
            formatted_messages = [f"{msg[0]}: {msg[1]}" for msg in messages]
            load_message = json.dumps({"type": "load", "content": formatted_messages})
            await client.send(load_message)
        else:
            no_messages_msg = json.dumps({
                    "type": "server",  # Indicates this is a server-generated message
                    "content": "No previous messages found."  # Informative message for the client
                })
            await client.send(no_messages_msg)
            return



    
    def generate_conversation_id(user1, user2):
        """Generate a unique conversation ID based on usernames in alphabetical order."""
        return "_".join(sorted([user1, user2]))






    async def switch_chat_mode(self, client, recipient=None):
        """Switch between group chat and DMs."""
        if recipient :
            await self.send_previous_messages(client, "private", recipient)
        else :
             await self.send_previous_messages(client, "group")


    async def messaging(self, client):
            rate_limiter = self.rate_limiter.get(client)
            if rate_limiter is None:
                self.rate_limiter[client] = RateLimiter(max_messages=1, time_period=1)  # 5 messages per second
                rate_limiter = self.rate_limiter[client]

            async for json_msg in client:
                # Check if the user has exceeded the message limit
                msg_data = json.loads(json_msg)
                message = msg_data.get("content")
                chat_type = msg_data.get("type")  # 'group' or 'private'
                recipient = msg_data.get("recipient")  # For DMs, stores the recipient's username

                if chat_type == "switch_mode" :
                    await self.switch_chat_mode(client, recipient)
                    continue  

                if chat_type == "file_download":
                    # Handle file download request
                    file_name = msg_data.get("file_name")
                    await self.handle_file_download(client, file_name)
                    continue



                if chat_type == "file_upload":
                    # Handle file upload
                    # Generate a unique identifier
                    unique_id = uuid.uuid4().hex
                    # Append the unique identifier to the file name
                    file_name = msg_data.get("file_name")
                    unique_file_name = f"{unique_id}_{file_name}"
                    file_data = msg_data.get("file_data")
                    receiver = msg_data.get("receiver")
                    sender = self.connected_clients[client].username

                    # Decode the file data
                    file_bytes = base64.b64decode(file_data)

                    # Save the file to a directory
                    save_path = pathlib.Path("uploads") / unique_file_name
                    with open(save_path, 'wb') as file:
                        file.write(file_bytes)

                    # Save file metadata to the database
                    cursor = self.db.cursor()
                    cursor.execute("""
                        INSERT INTO files (file_name, file_path, sender, recipient, chat_type)
                        VALUES (?, ?, ?, ?, ?)
                    """, (file_name, str(save_path), sender, recipient, chat_type))
                    self.db.commit()

                    # Notify the recipient(s)
                    if receiver == "group":
                         broadcast(set(self.connected_clients.keys()).difference({client}),  json.dumps({
                                "type": "file_upload",
                                "file_name": file_name,
                                "sender": sender,
                                "content": f"File '{file_name}' uploaded by {sender}."
                            }))
                    elif receiver == "private":
                         for cli, user in self.connected_clients.items():
                            if user.username == recipient:
                                data = {
                                        "type": "file_upload",
                                        "file_name": file_name,
                                        "sender": sender,
                                        "content": f"File '{file_name}' received from {sender}."
                                    }
                                await cli.send(json.dumps(data))
                                break
                    continue

                if not rate_limiter.can_send_message():
                    msg_json = {
                        "type": "server",
                        "content": "You are sending messages too quickly. Please wait before sending another message."
                    }
                    await client.send(json.dumps(msg_json))
                    continue

                username = self.connected_clients[client].username
                formatted_message = f"{message}"

                cursor = self.db.cursor()
                if chat_type == "group":
                    cursor.execute("INSERT INTO messages (username, message, chat_type, recipient, conversation_id) VALUES (?, ?, ?, ?, ?)",
                                (username, message, chat_type, None, None))  # No recipient or conversation_id for group messages
                elif chat_type == "private":
                    # Generate conversation_id based on usernames in alphabetical order
                    conversation_id = "_".join(sorted([username, recipient]))
                    cursor.execute("INSERT INTO messages (username, message, chat_type, recipient, conversation_id) VALUES (?, ?, ?, ?, ?)",
                                (username, message, chat_type, recipient, conversation_id))
                self.db.commit()





                # Broadcast the message to the appropriate clients
                if chat_type == "group":
                    await self.chat_broadcast(formatted_message, client, username,"group")
                elif chat_type == "private":
                    await self.send_dm(username, recipient, formatted_message)




    async def handle_file_download(self, client, file_name):
        """Send the requested file to the client."""
        cursor = self.db.cursor()
        cursor.execute("SELECT file_path FROM files WHERE file_name = ?", (file_name,))
        file_record = cursor.fetchone()
        cursor.close()

        if file_record:
            file_path = file_record[0]
            try:
                with open(file_path, 'rb') as file:
                    file_data = file.read()
                    file_base64 = base64.b64encode(file_data).decode('utf-8')
                    msg_json = {
                        "type": "file_download",
                        "file_name": file_name,
                        "file_data": file_base64
                    }
                    await client.send(json.dumps(msg_json))
            except Exception as e:
                print(f"Error reading file: {e}")
                await client.send(json.dumps({
                    "type": "server",
                    "content": f"Error downloading file '{file_name}'."
                }))
        else:
            await client.send(json.dumps({
                "type": "server",
                "content": f"File '{file_name}' not found."
            }))


    async def send_dm(self, sender, recipient, message):
        """Send a direct message to the specified recipient."""
        for client, user in self.connected_clients.items():
            if user.username == recipient:
                msg_json = {
                    "type": "private",
                    "sender": sender,
                    "content": message
                }
                await client.send(json.dumps(msg_json))
                break




    async def welcome_msg(self, client) :
        msg_json = {
                "type": "server",
                "content": "Welcome to Secure Chat."
             }
        await client.send(json.dumps(msg_json))    
    


    async def chat_broadcast(self, message, excluded_client = None, sender = "", type="server"):
         
         msg_json = {
                "type": type,
                "content": message,
                "sender": sender,
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
                    msg_json = {
                            "type": "server",
                            "username": username
                        }
                    await client.send(json.dumps(msg_json)) 
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
                all_users = await self.get_all_users()
                msg_json = {
                    "type": "user_list",
                    "content": all_users
                }
                broadcast(set(self.connected_clients.keys()), json.dumps(msg_json))
                msg_json["content"] = f"Welcome to SecureChat, {username}! 🎉\nYou have successfully registered. Enjoy secure and private conversations!"
                msg_json["type"] = "server"
                await client.send(json.dumps(msg_json)) 
                msg_json = {
                            "type": "server",
                            "username": username
                        }
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