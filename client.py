import asyncio
import websockets
import ssl
import threading
import pathlib
import json


from tkinter import Tk, Frame, Label, Entry, Button, Text, END, Canvas, PhotoImage, DISABLED, NORMAL, RIGHT, LEFT, BOTH, WORD, X, Listbox


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
                        msg_json = json.loads(message)
                        print(msg_json)
                        # Normal message 
                        if msg_json.get("type") == "group" or msg_json.get("type") == "server":
                            sender = msg_json.get("sender", "")
                            content = msg_json.get("content", "")
                            
                            # Append colon only if sender is not empty
                            if sender:
                                sender += ": "
                            if  msg_json.get("type") == "server" or self.gui.current_dm_recipient == None : 
                                self.gui.update_chat(f"{sender}{content}")
                            
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
                    self.ws = await websockets.connect(self.URI, ssl=self.ssl_context)
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
        self._add_sidebar()
        self._add_back_to_group_button()

    def _chatbox(self):
        self.chat_display = Text(
            self._main_window, bg=self._BACKGROUND_COLOR, fg=self._TEXT_COLOR,
            font=("Lucida Console", 14), state="disabled", wrap="word"
        )
        self.chat_display.place(x=220, y=20, width=800, height=550)

    def clear_chatbox(self):
        if hasattr(self, 'chat_display') and self.chat_display.winfo_exists():
            self.chat_display.config(state="normal")
            self.chat_display.delete("1.0", "end")
            self.chat_display.config(state="disabled")

    def update_chatbox(self, message):
        self.chat_display.config(state="normal")
        self.chat_display.insert("end", message + "\n")
        self.chat_display.config(state="disabled")
        self.chat_display.see("end")

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
      #  self.pages["login"] = LoginPage(self.root, self)
        self.pages["main"] = ChatPage(self.root, self)
        self.switch_page("main")
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
            if chat_type == "private":
                self.current_page.update_chatbox(f"You: {message}")
            else:
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

    def update_chat(self, message):
        if self.current_page == self.pages["main"] or self.current_page == self.pages["dm"]:
                self.current_page.update_chatbox(message)

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


async def main():
    gui = GUI()


asyncio.run(main())
