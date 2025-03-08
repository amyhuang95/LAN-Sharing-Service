import socket
import threading
import os

class FileTransferServer:
    def __init__(self, host='0.0.0.0', port=60000, save_directory='received_files'):
        self.host = host
        self.port = port
        self.save_directory = save_directory
        self.running = True
        
        # Create the save directory if it doesn't exist
        if not os.path.exists(self.save_directory):
            os.makedirs(self.save_directory)
        
        # Setup TCP server socket
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
                print(f"Accepted connection from {addr}")
                threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
            except Exception as e:
                print("Error accepting connection:", e)
    
    def _handle_client(self, conn, addr):
        try:
            # Receive file name (assume first 256 bytes contain the file name, padded)
            file_name = conn.recv(256).decode().strip()
            print(f"Incoming file '{file_name}' from {addr}")
            
            # Ask the user if they want to accept the file transfer
            response = input(f"Do you want to accept the file '{file_name}' from {addr}? (y/n): ")
            if response.lower() != 'y':
                conn.sendall(b"REJECT")
                print("File transfer rejected.")
                return
            else:
                conn.sendall(b"ACCEPT")
            
            # Begin receiving file data if accepted
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

# Example usage:
if __name__ == '__main__':
    server = FileTransferServer()
    server.start()
    input("Press Enter to stop the server...\n")
    server.stop()
