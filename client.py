import asyncio
import websockets
import ssl
import threading
import pathlib
import json
import webbrowser
import re
import base64
import os
from tkinter import Tk, Frame, Label, Entry, Button, Text, END, Canvas, PhotoImage, DISABLED, NORMAL, RIGHT, LEFT, BOTH, WORD, X, Listbox, Toplevel

from tkinter import filedialog

from PIL import Image, ImageTk


class Client:
    def __init__(self, gui) :
        self.URI = "wss://192.168.69.3:7778"
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.gui = gui
        self.key_pem = pathlib.Path(__file__).with_name("key.pem")
        self.ssl_context.load_verify_locations(self.key_pem)
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        self.ws = None  
        self.connected = False
        self.server_dc = True # block reconnecting
        self.connecting = False
        self.reconnect_attempts = 0
        self.username = None
        self.MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB # file uploads



    async def upload_file(self, file_path):
        if not self.connected or self.server_dc:
            self.gui.update_chat("[!] Not connected to server.")
            return

        try:
            file_size = os.path.getsize(file_path)
            if file_size > self.MAX_FILE_SIZE:
                self.gui.update_chat(f"[!] File is too large. Maximum size is {self.MAX_FILE_SIZE / (1024 * 1024)} MB.")
                return
            with open(file_path, 'rb') as file:
                file_data = file.read()
                file_name = pathlib.Path(file_path).name
                file_base64 = base64.b64encode(file_data).decode('utf-8')
                receiver = "group"
                if self.gui.current_dm_recipient : receiver = "private"
                msg_json = {
                    "type": "file_upload",
                    "file_name": file_name,
                    "file_data": file_base64,
                    "recipient": self.gui.current_dm_recipient,  # None for group chat
                    "receiver": receiver,
                    "sender": self.username
                }

                await self.send_message(msg_json)
                self.gui.update_chat(msg_json,True)
        except Exception as e:
            self.gui.update_chat(f"[!] Error uploading file: {e}")



    async def receive_messages(self):
                async for message in self.ws:
                   try :
                        msg_json = json.loads(message)
                        print(msg_json)
                        
                        if not isinstance(msg_json, dict):
                            print(f"Expected a dictionary, but got: {type(msg_json)}")
                            continue


                        if msg_json.get("type") == "file_upload":
                            print("file name")
                            file_name = msg_json.get("file_name")
                            print("file sender")
                            sender = msg_json.get("sender", "")
                            print("update chat")
                            self.gui.update_chat(msg_json, True)
                            continue 
                        
                        elif msg_json.get("type") == "load_files":
                            files = msg_json.get("content", [])
                            self.gui.update_chatbox_with_files(files) 
                            continue


                        # Normal message 
                        elif msg_json.get("type") == "group" or msg_json.get("type") == "server":
                            if msg_json.get("username") and msg_json.get("type") == "server":
                                self.username = msg_json.get("username")
                                self.gui.update_logged_in_status(f"User: {self.username}")
                            sender = msg_json.get("sender", "")
                            content = msg_json.get("content", "")
                            
                            # Append colon only if sender is not empty
                            if sender:
                                sender += ": "
                            if  msg_json.get("type") == "server" or self.gui.current_dm_recipient == None : 
                                self.gui.update_chat(f"{sender}{content}")
                            
                        
                                    
                        
                        elif msg_json.get("type") == "file_download":
                            self.gui.current_page.lock_ui()
                            file_name = msg_json.get("file_name")
                            file_data = msg_json.get("file_data")

                            # Decode the file data
                            file_bytes = base64.b64decode(file_data)

                            # Save the file to a directory
                            save_path = pathlib.Path(file_name)
                            with open(save_path, 'wb') as file:
                                file.write(file_bytes)
                            self.gui.update_chat(f"[+] File '{file_name}' downloaded successfully.")
                            self.gui.unlock_ui() 

                        # Handle "user_list" message type
                        elif msg_json.get("type") == "user_list":
                            self.gui.update_user_list(msg_json.get("content"))
                        
                        elif msg_json.get("type") == "load" :
                            self.gui.load_current_page(msg_json.get("content"))
                        # dms
                        elif msg_json.get("type") == "private":
                            sender = msg_json.get("sender", "")
                            content = msg_json.get("content", "")
                            
                            # Append colon only if sender is not empty
                           
                            if sender == self.gui.current_dm_recipient :
                                     if sender:
                                        sender += ": "
                                     self.gui.update_chat(f"{sender}{content}")

                            # Handle disconnect messages
                        elif message == "You have been disconnected by the server.":
                            self.server_dc = True
                            self.gui.handle_server_disconnect()  # Updated method call
                            break
                   except Exception as e :
                        print(str(e))  
                        


    async def download_file(self, file_name):
        """Request a file download from the server."""
        if not self.connected or self.server_dc:
            self.gui.update_chat("[!] Not connected to server.")
            return

        # Lock the UI
        self.gui.current_page.lock_ui()

        try:
            msg_json = {
                "type": "file_download",
                "file_name": file_name
            }
            await self.send_message(msg_json)
        except Exception as e:
            self.gui.update_chat(f"[!] Error during download: {e}")
        finally:
            # Unlock the UI
            self.gui.current_page.unlock_ui()



    async def switch_chat_mode(self, mode, recipient=None):
        """Switch the chat mode between group and private."""
        # Clear the current chat
        self.gui.clear_chatbox()

        # Update the current chat mode and recipient
        self.current_chat_mode = mode
        self.current_dm_recipient = recipient

        # Notify the server about the chat mode switch
        msg_json = {"type": "switch_mode", "mode": mode, "recipient": recipient}
        await self.send_message(msg_json)


    async def request_chat_logs(self, recipient):
        """Request chat logs for the specified recipient."""
        msg_json = {"type": "request_chat_logs", "recipient": recipient}
        await self.send_message(msg_json)




    async def send_message(self, msg_json):
            await self.ws.send(json.dumps(msg_json))



    async def connect(self):
             while not self.server_dc:
                try:
                    self.gui.update_chat("[+] Attempting to connect...")
                    self.ws = await websockets.connect(self.URI, ssl=self.ssl_context,   max_size= self.MAX_FILE_SIZE)
                    self.connected = True
                    self.reconnect_attempts = 0  # Reset after a successful connection
                    self.gui.update_chat("[+] Connected to server.")
                    self.connecting = False
                    self.gui.connection_successful()

                    # For now, we simply await receiving messages.
                    await self.receive_messages()
                except Exception as e:
                   print(str(e))

                finally: # attempt to reconnect as long as the server did not dc us aka we lost connection on our own
                    self.username = None
                    self.gui.update_logged_in_status("")
                    if not self.server_dc :
                        self.connecting = True
                        self.connected = False
                        self.gui.current_dm_recipient = None
                        if not self.gui.current_page.disconnect_button.cget("text") == "Connecting":
                            self.gui.current_page.disconnect_button.config(text="Connecting", bg="#00FF00", fg="black", state="disabled")
                        # Wait before reconnecting using exponential backoff
                        wait_time = min(2 ** self.reconnect_attempts, 5)
                        # move gui to main page
                        self.gui.update_chat(f"[+] Disconnected. Retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        self.reconnect_attempts += 1
             self.gui.update_chat("[!] Not connected to the server.")
             print("test")


    async def dc(self):
        if self.connected:  
            await self.switch_chat_mode("group") # reset the state of the gui
            self.gui.current_dm_recipient = None 
            self.connected = False
            self.server_dc = True  
            self.username = None
            self.gui.update_logged_in_status("")
            self.gui.update_chat("[!] Disconnecting from server...")
            try:
                await self.ws.close() 
                self.gui.update_chat("[!] Disconnected from server.")
            except Exception as e:
                self.gui.update_chat(f"[!] Error during disconnection: {e}")
               





#################################################################################################### 
#                                            G U I                                                 #                                                                        
####################################################################################################


#################################################################################################### 
#                                     DEFAULT TEMPLATE PAGE                                        #                                                                        
####################################################################################################

class BasePage(Frame):
    _BACKGROUND_COLOR = 'black'
    _TEXT_COLOR = 'white'
    _WIDTH = 1400
    _HEIGHT = 700
    _HEIGHT_RESIZEABLE = False
    _WIDTH_RESIZEABLE = False
    _LOGO_PATH = 'assets/oss_transparent.png'

    
    def __init__(self, root, main_app):
        self._root = root
        self._main_app = main_app
        self._build_root()
        self._build_main_window()
        self._add_logo()
        self._add_disconnect_button()
        self._add_close_button()
        self._add_logged_in_label()

    def _build_root(self):
        self._root.title("SECURE CHAT")
        self._root.geometry(f"{self._WIDTH}x{self._HEIGHT}")
        self._root.resizable(self._WIDTH_RESIZEABLE, self._HEIGHT_RESIZEABLE)
        self._root.configure(bg=self._BACKGROUND_COLOR)
        icon = PhotoImage(file="assets/oss.png")
        self._root.iconphoto(True, icon)

    def _build_main_window(self):
        self._main_window = Frame(self._root, bg=self._BACKGROUND_COLOR, height=self._HEIGHT, width=self._WIDTH)
        self._main_window.place(x=0, y=0)

        neon_green = "#00FF00"
        border_thickness = 5
        canvas = Canvas(self._main_window, width=self._WIDTH, height=self._HEIGHT, bd=0, highlightthickness=0, bg=self._BACKGROUND_COLOR)
        canvas.place(x=0, y=0)
        canvas.create_rectangle(border_thickness, border_thickness, self._WIDTH - border_thickness, self._HEIGHT - border_thickness, outline=neon_green, width=border_thickness)

    def _add_logo(self):
        logo_image = Image.open(self._LOGO_PATH)
        logo_image = logo_image.resize((300, 270), Image.Resampling.LANCZOS)
        logo = ImageTk.PhotoImage(logo_image)
        logo_label = Label(self._main_window, image=logo, bg=self._BACKGROUND_COLOR)
        logo_label.image = logo
        logo_label.place(x=1060, y=180)

    def _add_disconnect_button(self):
        self.disconnect_button = Button(
            self._main_window, text="Connect", font=("Lucida Console", 14),
            bg="#00FF00", fg="black", command=self._main_app.toggle_connection
        )
        self.disconnect_button.place(x=1050, y=20, width=120, height=50)

    def _add_close_button(self):
        self.close_button = Button(
            self._main_window, text="Close", font=("Lucida Console", 14),
            bg="red", fg="white", command=self._main_app.quit
        )
        self.close_button.place(x=1260, y=20, width=120, height=50)


    def _add_logged_in_label(self):
        """Add a label to display the 'logged in' status."""
        self.logged_in_label = Label(self._main_window, text="", fg="#00FF00", bg=self._BACKGROUND_COLOR,
            font=("Lucida Console", 14))
        self.logged_in_label.place(x=1100, y=500)  # Adjust position as needed

    def update_logged_in_label(self, username):
        """Update the 'logged in' label with the user's name."""
        self.logged_in_label.config(text=username)


    def show(self):
        """Make the page visible."""
        self._main_window.tkraise()

    def hide(self):
        """Hide the page."""
        self._main_window.lower()

class AuthPage(BasePage) :

    def __init__(self, root, main_app) :
        super().__init__(root, main_app)
        self.build_password_input()
        self.build_user_input()
        self.build_login_button()

    def build_password_input(self) :
        self.pass_label = Label(self._main_window, font=("Arial", 12), bg=self._BACKGROUND_COLOR,fg="white", text="Password")
        self.pass_label.place(x= 405, y = 376)
        self.pass_input = Entry(self._main_window, show="*", font=("Arial", 20), bg="gray20", fg="white", insertbackground="#00FF00")
        self.pass_input.place(x= 400, y = 400)

    def build_user_input(self) :
        self.user_label = Label(self._main_window, font=("Arial", 12), bg=self._BACKGROUND_COLOR,fg="white", text="Username")
        self.user_label.place(x= 405, y = 226)
        self.user_input = Entry(self._main_window, font=("Arial", 20), bg="gray20", fg="white", insertbackground="#00FF00")
        self.user_input.place(x= 400, y = 250)

    def build_login_button(self) :
        self.login_button = Button(
            self._main_window, text="Login", font=("Lucida Console", 14),
            bg="#00FF00", fg="black", command=self._main_app.quit
        )
        self.login_button.place(x=490, y=500, width=120, height=50)



class ChatPage(BasePage):
    def __init__(self, root, main_app):
        super().__init__(root, main_app)
        self._chatbox()
        self._input_box()
        self._add_clear_button()
        self._root.bind("<Return>", self.on_enter_pressed)
        self._add_sidebar()
        self._add_back_to_group_button()
        self._add_file_upload_button()

    def lock_ui(self):
        """Disable UI elements to prevent interaction during download."""
        self.file_upload_button.config(state=DISABLED)
        self.send_button.config(state=DISABLED)
        self.input_entry.config(state=DISABLED)
        self.clear_button.config(state=DISABLED)
        self.back_to_group_button.config(state=DISABLED)
        self.emoji_button.config(state=DISABLED)
        self.disconnect_button.config(state=DISABLED)

    def unlock_ui(self):
        """Re-enable UI elements after download is complete."""
        self.file_upload_button.config(state=NORMAL)
        self.send_button.config(state=NORMAL)
        self.input_entry.config(state=NORMAL)
        self.clear_button.config(state=NORMAL)
        self.back_to_group_button.config(state=NORMAL)
        self.emoji_button.config(state=NORMAL)
        self.disconnect_button.config(state=NORMAL)
    
    
    def _chatbox(self):
        self.chat_display = Text(
            self._main_window, bg=self._BACKGROUND_COLOR, fg=self._TEXT_COLOR,
            font=("Lucida Console", 14), state="disabled", wrap="word"
        )
        self.chat_display.place(x=220, y=20, width=800, height=550)

        # Tags for Italic and Bold
        self.chat_display.tag_configure("red_text", foreground="red")
        self.chat_display.tag_configure("italic", font=("Lucida Console", 14, "italic"))
        self.chat_display.tag_configure("bold", font=("Lucida Console", 14, "bold")) 
        self.chat_display.tag_configure("underline", font=("Lucida Console", 14, "underline"))
        #self.chat_display.tag_configure("link", foreground="blue", underline=True)
        self.chat_display.tag_configure("url_link", foreground="blue", underline=True)
        self.chat_display.tag_configure("file_link", foreground="red", underline=True)
        self.chat_display.tag_bind("url_link", "<Button-1>", self.open_url)
        self.chat_display.tag_bind("file_link", "<Button-1>", self.open_file_link)


    def open_url(self, event):
        index = self.chat_display.index(f"@{event.x},{event.y}")
        tags = self.chat_display.tag_names(index)
        if "url_link" in tags:
            start, end = self.chat_display.tag_prevrange("url_link", index)
            url = self.chat_display.get(start, end)
            webbrowser.open(url)

    def open_file_link(self, event):
            index = self.chat_display.index(f"@{event.x},{event.y}")
            tags = self.chat_display.tag_names(index)
            if "file_link" in tags:
                start, end = self.chat_display.tag_prevrange("file_link", index)
                file_name = self.chat_display.get(start, end)
                self.on_file_link_click(file_name)

    def clear_chatbox(self):
        if hasattr(self, 'chat_display') and self.chat_display.winfo_exists():
            self.chat_display.config(state="normal")
            self.chat_display.delete("1.0", "end")
            self.chat_display.config(state="disabled")

    def on_file_link_click(self, file_name):
        """Handle file link clicks and initiate the download."""
        if self._main_app.client.connected:
            asyncio.run_coroutine_threadsafe(self._main_app.client.download_file(file_name), self._main_app.loop)
        else:
            self.update_chatbox("[!] Not connected to server.")

    def update_chatbox(self, message, is_file=None):
        self.chat_display.config(state="normal")
        if is_file:
                # Handle file upload message (message is a JSON/dictionary)
                print("test")
                file_name = message.get("file_name")
                sender = message.get("sender")
                content = f"[+] File uploaded: {file_name} by {sender}"

                # Insert the file name as a clickable link (red)
                self.chat_display.insert("end", content + "\n", "red_text")  # Apply red_text tag
                self.chat_display.insert("end", file_name, ("file_link",))  # File link remains red
                self.chat_display.insert("end", "\n", "normal")
        else:
            i = 0
            length = len(message)

            while i < length:
                # Handle bold (**)
                if message[i:i+2] == '**':  # Check for bold markers
                    # Find the closing '**' for bold text
                    end = message.find('**', i + 2)
                    if end == -1:  # If no closing '**', treat the rest as normal text
                        part = message[i + 2:]
                        self.chat_display.insert("end", part)
                        break
                    else:
                        # Insert bold part
                        self.chat_display.insert("end", message[i + 2:end], "bold")
                        i = end + 2  # Skip past the closing '**'
                
                # Handle italics (*)
                elif message[i] == '*':  # Check for italic markers
                    # Find the closing '*' for italic text
                    end = message.find('*', i + 1)
                    if end == -1:  # If no closing '*', treat the rest as normal text
                        part = message[i + 1:]
                        self.chat_display.insert("end", part)
                        break
                    else:
                        # Insert italic part
                        self.chat_display.insert("end", message[i + 1:end], "italic")
                        i = end + 1  # Skip past the closing '*'
                
                # Handle underline (__)
                elif message[i:i+2] == '__':  # Check for underline markers
                    # Find the closing '__' for underline text
                    end = message.find('__', i + 2)
                    if end == -1:  # If no closing '__', treat the rest as normal text
                        part = message[i + 2:]
                        self.chat_display.insert("end", part)
                        break
                    else:
                        # Insert underlined part
                        self.chat_display.insert("end", message[i + 2:end], "underline")
                        i = end + 2  # Skip past the closing '__'
                
                # Handle links (http:// or https://)
                elif message[i:i+4] == "http":  # Check for links
                    # Use regex to capture the full URL (including those with punctuation and spaces)
                    url_match = re.match(r'(https?://[^\s]+)', message[i:])
                    if url_match:
                        url = url_match.group(0)
                        self.chat_display.insert("end", url, "url_link")
                        i += len(url)  # Skip past the link
                    else:
                        # If no valid link found, insert normal text
                        self.chat_display.insert("end", message[i])
                        i += 1
                
                else:
                    # Insert normal text (no formatting)
                    self.chat_display.insert("end", message[i])
                    i += 1  # Move to the next character

            self.chat_display.insert("end", "\n")
            self.chat_display.config(state="disabled")
            self.chat_display.see("end")
    
    def _add_file_upload_button(self):
        self.file_upload_button = Button(
            self._main_window, text="Upload", font=("Lucida Console", 14),
            bg="#00FF00", fg="black", command=self.upload_file
        )
        self.file_upload_button.place(x=1260, y=100, width=120, height=50)

    def upload_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self._main_app.upload_file(file_path)




    def _input_box(self):
        self.input_entry = Entry(
            self._main_window, font=("Arial", 14), bg="gray20", fg="white", insertbackground="#00FF00" 
        )
        self.input_entry.place(x=220, y=600, width=800, height=50)

        self.send_button = Button(
            self._main_window, text="Send", font=("Lucida Console", 14),
            bg="#00FF00", fg="black", command=self._send_message
        )
        self.send_button.place(x=1050, y=600, width=120, height=50)


        # Emoji picker button
        self.emoji_button = Button(self._main_window, text="😀", font=("Arial", 14), bg="#00FF00", command=self.open_emoji_picker)
        self.emoji_button.place(x=980, y=600, width=50, height=50)       

    
    def open_emoji_picker(self):
        emoji_picker = Toplevel(self._main_window)
        emoji_picker.title("Emojis")
        emoji_picker.geometry("300x300")
        emoji_picker.configure(bg="black")

        # Emoji list
        emojis = [
            "😀", "😁", "😂", "😃", "😄", "😅", "😆", "😇", "😉", "😊",
            "😋", "😎", "😍", "😘", "😗", "😙", "😚", "😜", "😝", "😭", 
            "😢", "😿", "😡", "😠", "😶", "😏", "😪", "😴", "😈", "☠️"]
        
        # Add buttons for each emoji
        for i, emoji in enumerate(emojis):
            emoji_button = Button(emoji_picker, text=emoji, font=("Arial", 14), bg="#00FF00", command=lambda e=emoji: self.insert_emoji(e))
            emoji_button.grid(row=i // 5, column=i % 5, padx=5, pady=5)


    def insert_emoji(self, emoji):
        current_text = self.input_entry.get()
        self.input_entry.delete(0, "end")
        self.input_entry.insert("end", current_text + emoji)


    def close_emoji_picker(self):
        if self.emoji_picker_window:
            self.emoji_picker_window.destroy()
            self.emoji_picker_window = None


    def _send_message(self):
        message = self.input_entry.get().strip()
        if message:
            self._main_app.send_message(message)
            self.input_entry.delete(0, "end")

    def on_enter_pressed(self, event):
        self._send_message()

    def _add_clear_button(self):
        self.clear_button = Button(
            self._main_window, text="Clear", font=("Lucida Console", 14),
            bg="#00FF00", fg="black", command=self.clear_chatbox
        )
        self.clear_button.place(x=1260, y=600, width=120, height=50)



    def _add_sidebar(self):
            """Add a sidebar to display the list of all users."""
            self.sidebar = Frame(self._main_window, bg="gray20", width=200)
            self.sidebar.place(x=10, y=10, height=680)

            self.user_listbox = Listbox(self.sidebar, bg="gray20", fg="white", font=("Lucida Console", 12))
            self.user_listbox.place(x=0, y=0, width=200, height=680)

            # Bind click event to handle user selection
            self.user_listbox.bind("<<ListboxSelect>>", self.on_user_selected)

    def on_user_selected(self, event):
            """Handle user selection from the sidebar."""
            selected_user = self.user_listbox.get(self.user_listbox.curselection())
            if selected_user:
                self._main_app.switch_to_dm(selected_user)

    def update_user_list(self, user_list):
        """Update the sidebar with the list of all users."""
        self.user_listbox.delete(0, END)
        for user in user_list:
            self.user_listbox.insert(END, user)

    def _add_back_to_group_button(self):
        """Add a button to switch back to the main group chat."""
        self.back_to_group_button = Button(
            self._main_window, text="Group", font=("Lucida Console", 14),
            bg="#00FF00", fg="black", command=self._main_app.switch_to_group_chat
        )
        self.back_to_group_button.place(x=1050, y=100, width=120, height=50)






class GUI:
    def __init__(self):
        self.root = Tk()
        self.client = Client(self)
        self.loop = None
        self.pages = {}  # Dictionary to store pages
        self.current_page = None  # Track the current page
        self.pages["auth"] = AuthPage(self.root, self)
        self.pages["main"] = ChatPage(self.root, self)
        self.switch_page("main")
        self.switch_page("auth")
        self.current_dm_recipient = None

        self.root.mainloop()

    def toggle_connection(self):
        if self.client.connected:
            self.disconnect()
        else:
            self.connect()


    def connect(self):
        # Check if the button is already in the "Connecting" state
        if self.current_page.disconnect_button.cget("text") == "Connecting":
            return  # Exit the function if already connecting

        if self.current_page == self.pages["main"]:
                self.client.server_dc = False
                self.client.connected = False
                self.current_page.disconnect_button.config(text="Connecting", bg="#00FF00", fg="black", state="disabled")
                # Start the connection process in a new thread
                threading.Thread(target=self.run_asyncio_loop, daemon=True).start()


    def update_chatbox_with_files(self, files):
        """Update the chat display with the list of previous files."""
        if self.current_page == self.pages["main"] or self.current_page == self.pages["dm"]:
            for file in files:
                self.current_page.update_chatbox(file, is_file=True)


    def lock_ui(self):
        """Lock the UI elements."""
        if self.current_page:
            self.current_page.lock_ui()

    def unlock_ui(self):
        """Unlock the UI elements."""
        if self.current_page:
            self.current_page.unlock_ui()


    def disconnect(self):
        if self.client.connected:
            if not self.current_page == self.pages["main"] : self.switch_page("main")
            self.current_dm_recipient = None
            asyncio.run_coroutine_threadsafe(self.client.dc(), self.loop)
            self.current_page.disconnect_button.config(text="Connect", bg="#00FF00", fg="black")


    def run_asyncio_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            # Run the connection process
            self.loop.run_until_complete(self.client.connect())
            
            # Update the button state and text after successful connection
            #self.root.after(0, self.update_button_connected)
        except Exception as e:
            # Handle any errors that occur during the connection process
            print(f"Connection failed: {e}")
            self.root.after(0, self.update_button_failed)

    def update_button_connected(self):
        """Update the button to reflect a successful connection."""
        if self.current_page == self.pages["main"]:
            self.current_page.disconnect_button.config(text="Disconnect", bg="#FF0000", fg="white", state="normal")

    def update_button_failed(self):
        """Update the button to reflect a failed connection."""
        if self.current_page == self.pages["main"]:
            self.current_page.disconnect_button.config(text="Connect", bg="#00FF00", fg="black", state="normal")

    
    
    
    def send_message(self, message):
        if not self.client.connected or self.client.server_dc:
            self.current_page.update_chatbox("[!] Not connected to server.")
        else:
            # Determine the chat type and recipient
            if self.current_dm_recipient:
                chat_type = "private"
                recipient = self.current_dm_recipient
                print(f"sending message to {recipient}")
            else:
                chat_type = "group"
                recipient = None
                print("sending group message")

            # Update the chat display
            if self.client.username :
                self.current_page.update_chatbox(f"{self.client.username}: {message}")
            else :
                self.current_page.update_chatbox(f"You: {message}")

            # Prepare the message payload
            msg_json = {
                "type": chat_type,  # 'group' or 'private'
                "content": message,
                "recipient": recipient  # Only for DMs
            }

            # Send the message to the server
            asyncio.run_coroutine_threadsafe(self.client.send_message(msg_json), self.loop)
    
    

    def quit(self):
        self.root.quit()
        self.root.destroy()

    def update_chat(self, message, is_file=None ):
        if self.current_page == self.pages["main"] or self.current_page == self.pages["dm"]:
                print("inside update chat")
                self.current_page.update_chatbox(message,is_file)

    def switch_page(self, page_name):
        """Switch to a different page."""
        if self.current_page:
            self.current_page.hide()  # Hide the current page

        self.current_page = self.pages[page_name]
        self.current_page.show()  # Show the new page



    def connection_successful(self):
        """Update the button state and text after a successful connection."""
        self.current_page.disconnect_button.config(text="Disconnect", bg="#FF0000", fg="white", state="normal")



    def load_current_page(self, messages):
        """Load a batch of messages into the chat display."""
        if self.current_page == self.pages["main"] or self.current_page == self.pages["dm"]:
            for message in messages:
                self.current_page.update_chatbox(message)

    def update_user_list(self, user_list) :
        user_list.remove(self.client.username)
        self.current_page.update_user_list(user_list)


    def switch_to_dm(self, recipient):
        """Switch to a DM chat with the selected user."""
        if not self.client.connected or self.client.server_dc:
            self.current_page.update_chatbox("[!] You must be connected to the server to start a DM.")
            return
        
        self.current_dm_recipient = recipient
        self.current_page.update_chatbox(f"[+] Started DM with {recipient}.")
        # Request previous DMs from the server
        if self.loop is not None:
            asyncio.run_coroutine_threadsafe(
                self.client.switch_chat_mode("private", recipient), self.loop
            )
        else:
            print("[!] Event loop is not running.")


    def clear_chatbox(self):
        """Clear the chat display."""
        if self.current_page == self.pages["main"]:
            self.current_page.clear_chatbox()

    def update_logged_in_status(self, username):
        """Update the 'logged in' label on the current page."""
        if self.current_page:
            self.current_page.update_logged_in_label(username)

    def switch_to_group_chat(self):
        """Switch back to the main group chat."""
        self.current_dm_recipient = None
        self.current_page.update_chatbox("[+] Switched back to group chat.")
        if self.loop is not None:
            asyncio.run_coroutine_threadsafe(
                self.client.switch_chat_mode("group"), self.loop
            )
        else:
            print("[!] Event loop is not running.")


    def upload_file(self, filepath) :
        if self.loop is not None:
            asyncio.run_coroutine_threadsafe(
               self.client.upload_file(filepath), self.loop
            )
        else:
            print("[!] Event loop is not running.")



async def main():
    gui = GUI()


asyncio.run(main())