## Project Documentation
# Setting Up the Server
To connect a client to the server, you need to host the server on an endpoint and assign an open port for it to listen on.

1) Open the server.py file.
2) Modify the following lines to fit your setup:
Set self.PORT = 7778.
Set self.HOST = "localhost". (Change "localhost" to your server's IP address or domain).
3) Ensure key.pem is in the same directory as server.py

# Setting Up the Client
1) Open the client.py file.
2) Set self.URI = "wss://localhost:7778". (Replace "localhost" and "7778" as needed).
3) Ensure key.pem is in the same directory as client.py

# Install Required Libraries Using pip
1) Install the necessary libraries by running the following command:
   pip install -r requirements.txt.
(This needs to be done for both the client and server if they are on separate systems).

# Running the Client
Run the client by executing the following command:
    python client.py

# Running the Server
Run the server by executing the following command:
    python server.py
(Ensure the server's listening port is not already in use)

## Once the client is started, you will see four buttons on the right side.

# To start the connection to the server, click the "Connect" button.
You will be prompted to log in or register following the instructions provided by the server.
The connect/disconnect button will allow you to disconnect and reconnect to the server. 

# To Send Messages
Enter text into the bottom gray rectangle, then click the "Send" button or hit "Enter".

# To Clear Your Chat
Click the "Clear" button.

# To Exit the Program
Click the "Close" button or the "X" at the top right corner.