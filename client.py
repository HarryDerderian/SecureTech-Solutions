import asyncio
import websockets
import ssl
import threading
import pathlib
import json
import webbrowser


from tkinter import Tk, Frame, Label, Entry, Button, Text, END, Canvas, PhotoImage, DISABLED, NORMAL, RIGHT, LEFT, BOTH, WORD, X


from PIL import Image, ImageTk


class Client:
    def __init__(self, gui) :
        self.URI = "wss://localhost:7778"
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



    async def receive_messages(self):
                async for message in self.ws:
                   try :
                        print(message)
                        msg_json = json.loads(message)
                        print(msg_json)
                        # Normal message 
                        if msg_json.get("type") == "group" or msg_json.get("type") == "server":
                                self.gui.update_main_chat(msg_json.get("content"))
                        # dms
                        elif msg_json.get("type") == "private":
                                sender = msg_json.get("sender", "Unknown")
                                content = msg_json.get("content")
                                self.gui.update_main_chat(f"[Private from {sender}]: {content}")

                            # Handle disconnect messages
                        elif message == "You have been disconnected by the server.":
                            self.server_dc = True
                            self.gui.handle_server_disconnect()  # Updated method call
                            break
                   except Exception as e :
                        print(str(e))  
                        



    async def send_message(self, msg_json):
            await self.ws.send(json.dumps(msg_json))



    async def connect(self):
             while not self.server_dc:
                try:
                    self.gui.update_main_chat("[+] Attempting to connect...")
                    self.ws = await websockets.connect(self.URI, ssl=self.ssl_context)
                    self.connected = True
                    self.reconnect_attempts = 0  # Reset after a successful connection
                    self.gui.update_main_chat("[+] Connected to server.")
                    self.connecting = False
                    self.gui.connection_successful()

                    # For now, we simply await receiving messages.
                    await self.receive_messages()
                except Exception as e:
                   print(str(e))

                finally: # attempt to reconnect as long as the server did not dc us aka we lost connection on our own
                    if not self.server_dc :
                        self.connecting = True
                        self.connected = False
                        if not self.gui.current_page.disconnect_button.cget("text") == "Connecting":
                            self.gui.current_page.disconnect_button.config(text="Connecting", bg="#00FF00", fg="black", state="disabled")
                        # Wait before reconnecting using exponential backoff
                        wait_time = min(2 ** self.reconnect_attempts, 5)
                        # move gui to main page
                        self.gui.update_main_chat(f"[+] Disconnected. Retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        self.reconnect_attempts += 1
             self.gui.update_main_chat("[!] Not connected to the server.")
             print("test")


    async def dc(self):
        if self.connected:  
            self.connected = False
            self.server_dc = True  
            self.gui.update_main_chat("[!] Disconnecting from server...")
            try:
                await self.ws.close() 
                self.gui.update_main_chat("[!] Disconnected from server.")
            except Exception as e:
                self.gui.update_main_chat(f"[!] Error during disconnection: {e}")
               





#################################################################################################### 
#                                            G U I                                                 #                                                                        
####################################################################################################


#################################################################################################### 
#                                     DEFAULT TEMPLATE PAGE                                        #                                                                        
####################################################################################################

class BasePage(Frame):
    _BACKGROUND_COLOR = 'black'
    _TEXT_COLOR = 'white'
    _WIDTH = 1200
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
        logo_label.place(x=860, y=180)

    def _add_disconnect_button(self):
        self.disconnect_button = Button(
            self._main_window, text="Connect", font=("Lucida Console", 14),
            bg="#00FF00", fg="black", command=self._main_app.toggle_connection
        )
        self.disconnect_button.place(x=850, y=20, width=120, height=50)

    def _add_close_button(self):
        self.close_button = Button(
            self._main_window, text="Close", font=("Lucida Console", 14),
            bg="red", fg="white", command=self._main_app.quit
        )
        self.close_button.place(x=1060, y=20, width=120, height=50)


    def show(self):
        """Make the page visible."""
        self._main_window.tkraise()

    def hide(self):
        """Hide the page."""
        self._main_window.lower()



class ChatPage(BasePage):
    def __init__(self, root, main_app):
        super().__init__(root, main_app)
        self._chatbox()
        self._input_box()
        self._add_clear_button()
        self._root.bind("<Return>", self.on_enter_pressed)

    def _chatbox(self):
        self.chat_display = Text(
            self._main_window, bg=self._BACKGROUND_COLOR, fg=self._TEXT_COLOR,
            font=("Lucida Console", 14), state="disabled", wrap="word"
        )
        self.chat_display.place(x=20, y=20, width=800, height=550)

        # Tags for Italic and Bold
        self.chat_display.tag_configure("italic", font=("Lucida Console", 14, "italic"))
        self.chat_display.tag_configure("bold", font=("Lucida Console", 14, "bold")) # Use Arial for bold text
        self.chat_display.tag_configure("underline", font=("Lucida Console", 14, "underline"))
        self.chat_display.tag_configure("link", foreground="blue", underline=True)

        self.chat_display.tag_bind("link", "<Button-1>", self.open_link)


    def open_link(self, event):
        index = self.chat_display.index(f"@{event.x},{event.y}")
        tags = self.chat_display.tag_names(index)
        if "link" in tags:
            start, end = self.chat_display.tag_prevrange("link", index)
            url = self.chat_display.get(start, end)
            webbrowser.open(url) # Open the URL in default web browser

    def clear_chatbox(self):
        if hasattr(self, 'chat_display') and self.chat_display.winfo_exists():
            self.chat_display.config(state="normal")
            self.chat_display.delete("1.0", "end")
            self.chat_display.config(state="disabled")



    def update_chatbox(self, message):
        self.chat_display.config(state="normal")

        i = 0
        length = len(message)

        while i < length:
            # Handle bold (**)
            if message[i:i+2] == '**':
                end = message.find('**', i + 2)
                if end == -1:  # If no closing '**', treat the rest as normal text
                    part = message[i+2:]
                    self.chat_display.insert("end", part)
                    break
                else:
                    self.chat_display.insert("end", message[i + 2:end], "bold")
                    i = end + 2  # Skip past the closing '**'
            
            # Handle italics (*)
            elif message[i] == '*':
                end = message.find('*', i + 1)
                if end == -1:  # If no closing '*', treat the rest as normal text
                    part = message[i + 1:]
                    self.chat_display.insert("end", part)
                    break
                else:
                    self.chat_display.insert("end", message[i + 1:end], "italic")
                    i = end + 1  # Skip past the closing '*'
            
            # Handle underline (__)
            elif message[i:i+2] == '__':
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
            elif message[i:i+4] == "http": 
                end = message.find(' ', i)
                if end == -1:
                    end = length 
                self.chat_display.insert("end", message[i:end], "link")
            
            else:
                # Insert normal text (no formatting)
                self.chat_display.insert("end", message[i])
                i += 1

        self.chat_display.insert("end", "\n")
        self.chat_display.config(state="disabled")
        self.chat_display.see("end")

    def _input_box(self):
        self.input_entry = Entry(
            self._main_window, font=("Arial", 14), bg="gray20", fg="white", insertbackground="#00FF00" 
        )
        self.input_entry.place(x=20, y=600, width=800, height=50)

        self.send_button = Button(
            self._main_window, text="Send", font=("Lucida Console", 14),
            bg="#00FF00", fg="black", command=self._send_message
        )
        self.send_button.place(x=850, y=600, width=120, height=50)

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
        self.clear_button.place(x=1060, y=600, width=120, height=50)


class LoginPage(BasePage):
    def __init__(self, root, main_app):
        super().__init__(root, main_app)
        self.is_login_mode = True  # Default to login mode
        self._add_login_interface()

    def _add_login_interface(self):
        # Username
        self.username_label = Label(self._main_window, text="Username:", font=("Lucida Console", 14), bg=self._BACKGROUND_COLOR, fg=self._TEXT_COLOR)
        self.username_label.place(x=400, y=200)
        self.username_entry = Entry(self._main_window, font=("Lucida Console", 14), bg="gray20", fg="white", insertbackground="#00FF00")
        self.username_entry.place(x=550, y=200, width=200)

        # Password
        self.password_label = Label(self._main_window, text="Password:", font=("Lucida Console", 14), bg=self._BACKGROUND_COLOR, fg=self._TEXT_COLOR)
        self.password_label.place(x=400, y=250)
        self.password_entry = Entry(self._main_window, show="*", font=("Lucida Console", 14), bg="gray20", fg="white", insertbackground="#00FF00")
        self.password_entry.place(x=550, y=250, width=200)

        # Confirm Password (hidden by default)
        self.confirm_password_label = Label(self._main_window, text="Confirm Password:", font=("Lucida Console", 14), bg=self._BACKGROUND_COLOR, fg=self._TEXT_COLOR)
        self.confirm_password_entry = Entry(self._main_window, show="*", font=("Lucida Console", 14), bg="gray20", fg="white", insertbackground="#00FF00")

        # Toggle Button
        self.toggle_button = Button(
            self._main_window, text="Switch to Register", font=("Lucida Console", 14),
            bg="#00FF00", fg="black", command=self.toggle_mode
        )
        self.toggle_button.place(x=550, y=360, width=200, height=50)

        # Submit Button
        self.submit_button = Button(
            self._main_window, text="Login", font=("Lucida Console", 14),
            bg="#00FF00", fg="black", command=self._main_app.submit_credentials
        )
        self.submit_button.place(x=550, y=420, width=120, height=50)

    def toggle_mode(self):
        """Toggle between login and register modes."""
        self.is_login_mode = not self.is_login_mode
        if self.is_login_mode:
            self.toggle_button.config(text="Switch to Register")
            self.submit_button.config(text="Login")
            self.confirm_password_label.place_forget()
            self.confirm_password_entry.place_forget()
        else:
            self.toggle_button.config(text="Switch to Login")
            self.submit_button.config(text="Register")
            self.confirm_password_label.place(x=400, y=300)
            self.confirm_password_entry.place(x=550, y=300, width=200)


class GUI:
    def __init__(self):
        self.root = Tk()
        self.client = Client(self)
        self.loop = None
        self.pages = {}  # Dictionary to store pages
        self.current_page = None  # Track the current page
        self.pages["login"] = LoginPage(self.root, self)
        self.pages["main"] = ChatPage(self.root, self)
        self.switch_page("login")

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



    def disconnect(self):
        if self.client.connected:
            if not self.current_page == self.pages["main"] : self.switch_page("main")
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
            self.current_page.update_chatbox(f"You: {message}")
            msg_json = {"type": "group", "content": message}
            asyncio.run_coroutine_threadsafe(self.client.send_message(msg_json), self.loop)

    def quit(self):
        self.root.quit()
        self.root.destroy()

    def update_main_chat(self, message):
        self.current_page.update_chatbox(message)

    def switch_page(self, page_name):
        """Switch to a different page."""
        if self.current_page:
            self.current_page.hide()  # Hide the current page

        self.current_page = self.pages[page_name]
        self.current_page.show()  # Show the new page

    def submit_credentials(self):
        username = self.pages["login"].username_entry.get()
        password = self.pages["login"].password_entry.get()
        print(username)
        print(password)

        # After a successful login, switch to the main page
        self.switch_page("main")

    def connection_successful(self):
        """Update the button state and text after a successful connection."""
        self.current_page.disconnect_button.config(text="Disconnect", bg="#FF0000", fg="white", state="normal")



async def main():
    gui = GUI()


asyncio.run(main())
