import socket
import os
import threading
import uuid

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

