import asyncio
import websockets
import sys
import os
import ssl
import threading
import pathlib

from tkinter import Tk, Frame, Label, Entry, Button, Text, END



class Client:
    def __init__(self, gui):
        self.URI = "wss://localhost:7778"
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.gui = gui
        self.localhost_pem = pathlib.Path(__file__).with_name("localhost.pem")
        self.ssl_context.load_verify_locations(self.localhost_pem)
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        self.tmp = True

    async def receive_messages(self, websocket):
        try:
            async for message in websocket:
                self.gui.update_chatbox(message)
        finally:
            pass

    async def send_message(self, message):
        print(f"Attempting to send message: {message}")

        #if self.ws and self.ws.open:
        if self.ws :
            print("sending msg")
            print(self.ws)
            print(f"ws = {self.ws.id}")
            await self.ws.send(message)
        else:
            print("error")
            self.gui.update_chatbox("[!] Not connected to server.")
    
    async def connect(self):
        attempts = 3

        while self.tmp: 
            try:
                async with websockets.connect(self.URI, ssl=self.ssl_context) as websocket:
                    self.ws = websocket
                    self.gui.update_chatbox("[+] Connected to server.")    
                    await self.receive_messages(self.ws)
                    # edge case catching goes here <------
            except Exception as e: # resolve better exception handling
                    print(e)
                    self.gui.update_chatbox("[!] Connection failed. Retrying in 3s...")
                    self.tmp = False
                    #await asyncio.sleep(3)

    
    




class GUI:
        _BACKGROUND_COLOR = 'black'
        _TEXT_COLOR = 'white'
        _TITLE = "SECURE CHAT"
        _WIDTH = 1200
        _HEIGHT = 700
        _HEIGHT_RESIZEABLE = False
        _WIDTH_RESIZEABLE = False


        def __init__(self) :
            self._build_root()
            self._build_main_window()
            self._chatbox()
            self._input_box()
            self._root.bind("<Return>", self.on_enter_pressed)

            self.client = Client(self)
            threading.Thread(target=self.run_asyncio_loop, daemon=True).start()




            self._root.mainloop()

        def _build_root(self) :
            self._root = Tk()
            self._root.title(self._TITLE)
            self._root.geometry(str(self._WIDTH) + "x" + str(self._HEIGHT))
            self._root.resizable(self._WIDTH_RESIZEABLE, self._HEIGHT_RESIZEABLE)
        
        def _build_main_window(self) :
            self._main_window = Frame(self._root, 
                                bg = self._BACKGROUND_COLOR, 
                                height = self._HEIGHT, width = self._WIDTH)
            self._main_window.place(x = 0, y = 0)
        
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
            self.chat_display.place(x=20, y=20, width=900, height=550)

        def update_chatbox(self, message):
            """Appends a message to the chat display"""
            self.chat_display.config(state="normal")
            self.chat_display.insert(END, message + "\n")
            self.chat_display.config(state="disabled")
            self.chat_display.see(END)

        def _input_box(self):
            """Creates an input box with a send button"""
            self.input_entry = Entry(self._main_window, font=("Arial", 14), bg="gray20", fg="white")
            self.input_entry.place(x=20, y=600, width=800, height=50)

            # Send Button
            self.send_button = Button(
                self._main_window, text="Send", font=("Lucida Console", 14), 
                bg="green", fg="white", command=self._send_message
            )
            self.send_button.place(x=850, y=600, width=100, height=50)

        def _send_message(self):
            """Handles sending messages and updating the chat display"""
            message = self.input_entry.get().strip()
            if message:
                self.update_chatbox("You: " + message)
                self.input_entry.delete(0, END)  # Clear input field
                future = asyncio.run_coroutine_threadsafe(self.client.send_message(message), self.loop)



        def run_asyncio_loop(self):
            """Runs the asyncio event loop in a separate thread"""
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.client.connect())

        
        def on_enter_pressed(self, event):
            """Handles the Enter key being pressed"""
            self._send_message()





async def main():
    gui = GUI()


asyncio.run(main())
