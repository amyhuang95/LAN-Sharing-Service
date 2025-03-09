import socket
import os
import threading
import uuid
import time

class FileTransferServer:
    def __init__(self, host='0.0.0.0', port=60000, save_directory='received_files', notify_ui_callback=None):
        self.host = host
        self.port = port
        self.save_directory = save_directory
        self.notify_ui_callback = notify_ui_callback  # Callback to notify the UI of a file request
        self.running = True
        self.pending_requests = {}  # Map request_id -> request details

        if not os.path.exists(self.save_directory):
            os.makedirs(self.save_directory)
        
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
    
    def start(self):
        print("Starting File Transfer Server on port", self.port)
        thread = threading.Thread(target=self._accept_connections, daemon=True)
        thread.start()
    
    def _accept_connections(self):
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
            except Exception as e:
                print("Error accepting connection:", e)
    
    def _handle_client(self, conn, addr):
        try:
            # Receive file name (assume first 256 bytes are the padded file name)
            file_name = conn.recv(256).decode().strip()
            request_id = str(uuid.uuid4())[:5]  # 5-character request id
            self.pending_requests[request_id] = {
                "conn": conn,
                "addr": addr,
                "file_name": file_name
            }
            print(f"Received file request '{file_name}' from {addr}, request_id={request_id}")
            
            # Notify the UI via callback
            if self.notify_ui_callback:
                self.notify_ui_callback(request_id, file_name, addr)
            
            # Start a timer thread to auto-reject the request after 3 minutes (180 seconds)
            threading.Thread(target=self._request_timeout, args=(request_id,), daemon=True).start()
        except Exception as e:
            print("Error handling file request:", e)
            conn.close()
    
    def _request_timeout(self, request_id):
        # Wait for 180 seconds (3 minutes)
        time.sleep(180)
        # If the request is still pending, process it as a rejection
        if request_id in self.pending_requests:
            print(f"Request {request_id} timed out after 3 minutes.")
            self.process_file_request(request_id, accept=False)

    def process_file_request(self, request_id: str, accept: bool):
        """Called by the UI (or timeout) after the user decides to accept or reject the file."""
        request = self.pending_requests.pop(request_id, None)
        if not request:
            print(f"Request {request_id} not found.")
            return

        conn = request["conn"]
        addr = request["addr"]
        file_name = request["file_name"]

        if not accept:
            try:
                conn.sendall(b"REJECT")
            except Exception as e:
                print("Error sending REJECT:", e)
            conn.close()
            print(f"File transfer '{file_name}' from {addr} was rejected.")
            return

        # Accept the file transfer
        try:
            conn.sendall(b"ACCEPT")
            file_path = os.path.join(self.save_directory, file_name)
            with open(file_path, 'wb') as f:
                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    f.write(data)
            print(f"File '{file_name}' saved to '{file_path}'")
        except Exception as e:
            print(f"Error receiving file '{file_name}':", e)
        finally:
            conn.close()
    
    def stop(self):
        self.running = False
        self.server_socket.close()
        print("File Transfer Server stopped.")
