import asyncio
import websockets
import ssl
import threading
import pathlib


from tkinter import Tk, Frame, Label, Entry, Button, Text, END, Canvas, PhotoImage
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
        self.reconnect_attempts = 0  



    async def receive_messages(self):
                async for message in self.ws:
                    self.gui.update_chatbox(message)
                    if message == "You have been disconnected by the server.":
                            self.server_dc = True
                            self.gui._disconnect()
                            break



    async def send_message(self, message):
            await self.ws.send(message)



    async def connect(self):
             while not self.server_dc:
                try:
                    self.gui.update_chatbox("[+] Attempting to connect...")
                    self.ws = await websockets.connect(self.URI, ssl=self.ssl_context)
                    self.connected = True
                    self.reconnect_attempts = 0  # Reset after a successful connection
                    self.gui.update_chatbox("[+] Connected to server.")

                    # start heartbeat or other tasks here.
                    # For now, we simply await receiving messages.
                    await self.receive_messages()
                except Exception as e:
                   pass

                finally: # attempt to reconnect as long as the server did not dc us aka we lost connection on our own
                    if not self.server_dc :
                        self.connected = False
                        # Wait before reconnecting using exponential backoff
                        wait_time = min(2 ** self.reconnect_attempts, 60)
                        self.gui.update_chatbox(f"[+] Disconnected. Retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        self.reconnect_attempts += 1
             self.gui.update_chatbox("[!] Not  connected to the server.")
    


    async def disconnect(self):
        if self.connected:  
            self.connected = False
            self.server_dc = True  
            self.gui.update_chatbox("[!] Disconnecting from server...")
            try:
                await self.ws.close() 
                self.gui.update_chatbox("[!] Disconnected from server.")
            except Exception as e:
                self.gui.update_chatbox(f"[!] Error during disconnection: {e}")
               


        

class GUI:
        _BACKGROUND_COLOR = 'black'
        _TEXT_COLOR = 'white'
        _TITLE = "SECURE CHAT"
        _WIDTH = 1200
        _HEIGHT = 700
        _HEIGHT_RESIZEABLE = False
        _WIDTH_RESIZEABLE = False
        _LOGO_PATH = 'assets/oss_transparent.png'



        def __init__(self) :
            self._build_root()
            self._build_main_window()
            self._chatbox()
            self._input_box()
            self._add_logo()
            self._add_disconnect_button()
            self._add_close_button()
            self._add_clear_button()
            self._root.bind("<Return>", self.on_enter_pressed)
            self.client = Client(self)
            threading.Thread(target=self.run_asyncio_loop, daemon=True).start()
            self._root.mainloop()



        def _build_root(self) :
            self._root = Tk()
            self._root.title(self._TITLE)
            self._root.geometry(str(self._WIDTH) + "x" + str(self._HEIGHT))
            self._root.resizable(self._WIDTH_RESIZEABLE, self._HEIGHT_RESIZEABLE)
            self._root.configure(bg=self._BACKGROUND_COLOR)
            
            icon = PhotoImage(file="assets/oss.png")
            self._root.iconphoto(True, icon)
        


        def _build_main_window(self):
            # Create main window frame
            self._main_window = Frame(self._root, 
                                    bg=self._BACKGROUND_COLOR, 
                                    height=self._HEIGHT, width=self._WIDTH)
            self._main_window.place(x=0, y=0)

            # Draw border on the frame by using the canvas
            neon_green = "#00FF00"
            border_thickness = 5
            canvas = Canvas(self._main_window, width=self._WIDTH, height=self._HEIGHT, bd=0, highlightthickness=0, bg=self._BACKGROUND_COLOR)
            canvas.place(x=0, y=0)

            # Draw the border
            canvas.create_rectangle(border_thickness, border_thickness, 
                                    self._WIDTH - border_thickness, self._HEIGHT - border_thickness, 
                                    outline=neon_green, width=border_thickness)

        


        def _chatbox(self):
            """Creates a chat display box with a scrollbar"""
            self.chat_display = Text(
                self._main_window, 
                bg=self._BACKGROUND_COLOR, 
                fg=self._TEXT_COLOR, 
                font=("Lucida Console", 14), 
                state="disabled", 
                wrap="word"
            )
            self.chat_display.place(x=20, y=20, width=800, height=550)
        
        
        def clear_chatbox(self):
            if hasattr(self, 'chat_display') and self.chat_display.winfo_exists():
                self.chat_display.config(state="normal")  # Enable editing
                self.chat_display.delete("1.0", "end")    # Delete all text
                self.chat_display.config(state="disabled")  # Re-disable editing



        def update_chatbox(self, message):
            """Appends a message to the chat display"""
            self.chat_display.config(state="normal")
            self.chat_display.insert(END, message + "\n")
            self.chat_display.config(state="disabled")
            self.chat_display.see(END)



        def _input_box(self):
            """Creates an input box with a send button"""
            self.input_entry = Entry(self._main_window, font=("Arial", 14), bg="gray20", fg="white",  insertbackground="#00FF00")
            self.input_entry.place(x=20, y=600, width=800, height=50)

            # Send Button
            self.send_button = Button(
                self._main_window, text="Send", font=("Lucida Console", 14), 
                bg="#00FF00", fg="black", command=self._send_message
            )
            self.send_button.place(x=850, y=600,  width=120, height=50)



        def _send_message(self):
            """Handles sending messages and updating the chat display"""
            message = self.input_entry.get().strip()
            if message:
                if not self.client.connected or self.client.server_dc: self.update_chatbox("[!] Not connected to server.")
                else :
                    self.update_chatbox("You: " + message)
                    future = asyncio.run_coroutine_threadsafe(self.client.send_message(message), self.loop)
                self.input_entry.delete(0, END)  # Clear input field



        def run_asyncio_loop(self):
            """Runs the asyncio event loop in a separate thread"""
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.client.connect())



        def on_enter_pressed(self, event):
            """Handles the Enter key being pressed"""
            self._send_message()



        def _add_logo(self):
            """Add the logo image to the window"""
            logo_image = Image.open(self._LOGO_PATH)
            logo_image = logo_image.resize((300, 270), Image.Resampling.LANCZOS)
            logo = ImageTk.PhotoImage(logo_image)

            logo_label = Label(self._main_window, image=logo, bg=self._BACKGROUND_COLOR)
            logo_label.image = logo
            logo_label.place(x=860, y=180)



        def _add_disconnect_button(self):
            """Add a disconnect button to the window"""
            self.disconnect_button = Button(
                self._main_window, text="Connect", font=("Lucida Console", 14), 
              bg="#00FF00", fg="black", command=self._disconnect
            )
            self.disconnect_button.place(x=850, y=20, width=120, height=50)



        def _add_close_button(self):
            """Add a close button to the window"""
            self.close_button = Button(
                self._main_window, text="Close", font=("Lucida Console", 14), 
                bg="red", fg="white", command=self._quit
            )
            self.close_button.place(x=1060, y=20, width=120, height=50)
        


        def _add_clear_button(self) :
                       
            self.clear_button = Button(
                self._main_window, text="Clear", font=("Lucida Console", 14), 
                 bg="#00FF00", fg="black", command=  self.clear_chatbox
            )
            self.clear_button.place(x=1060, y=600, width=120, height=50)
        


        def _disconnect(self):
            if self.disconnect_button.cget("text") == "Disconnect":
                asyncio.run_coroutine_threadsafe(self.client.disconnect(), self.loop)
                self.disconnect_button.config(text="Connect", bg="#00FF00", fg="black")
            else :
                 self._connect()




        def _quit(self):
            """Quits the application"""
            self._root.quit()
            self._root.destroy()



        def _connect(self):
            """Attempts to reconnect to the server."""
            # Only try to connect if not already connected.
            # Reset connection flags so that the client's connect loop will run.
            self.client.server_dc = False
            self.client.connected = False
            # Update the button to reflect that we're now trying to connect.
            self.disconnect_button.config(text="Disconnect", bg="red", fg="white")
            # Start a new asyncio loop in a separate thread for the connection.
            threading.Thread(target=self.run_asyncio_loop, daemon=True).start()
        
        


async def main():
    gui = GUI()


asyncio.run(main())
