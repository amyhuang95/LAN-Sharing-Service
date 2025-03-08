import socket
import os
import threading

class FileTransferClient:
    def __init__(self, server_ip, port=60000):
        self.server_ip = server_ip
        self.port = port

    def send_file(self, file_path):
        if not os.path.exists(file_path):
            print("File does not exist:", file_path)
            return

        file_name = os.path.basename(file_path)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.server_ip, self.port))
        try:
            # Send file name padded to 256 bytes
            sock.sendall(file_name.ljust(256).encode())
            
            # Wait for the recipient's decision
            response = sock.recv(1024).decode().strip()
            if response != "ACCEPT":
                print("Recipient declined the file transfer.")
                return
            
            # Proceed to send file content if accepted
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    sock.sendall(chunk)
            print(f"File '{file_name}' sent successfully.")
        except Exception as e:
            print("Error sending file:", e)
        finally:
            sock.close()

class FileTransferServer:
    def __init__(self, host='0.0.0.0', port=60000, save_directory='received_files'):
        self.host = host
        self.port = port
        self.save_directory = save_directory
        self.running = True
        
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
                print(f"Accepted file transfer connection from {addr}")
                threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
            except Exception as e:
                print("Error accepting connection:", e)
    
    def _handle_client(self, conn, addr):
        try:
            # Receive file name (first 256 bytes, padded)
            file_name = conn.recv(256).decode().strip()
            print(f"Incoming file '{file_name}' from {addr}")
            
            # Ask the recipient whether to accept the file
            decision = input(f"Accept file '{file_name}' from {addr}? (y/n): ")
            if decision.lower() != 'y':
                conn.sendall(b"REJECT")
                print("File transfer rejected.")
                return
            else:
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
            print("Error receiving file:", e)
        finally:
            conn.close()
    
    def stop(self):
        self.running = False
        self.server_socket.close()
        print("File Transfer Server stopped.")
