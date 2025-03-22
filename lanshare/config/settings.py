"""This module sets the configuration for the peer discovery service.

Usage example:

  config = Config()
  service = UDPPeerDiscovery(username, config)
"""

from pathlib import Path
import json

class Config:
    """Configuration class for UDP broadcast and debug message settings.
    
    By default, the debug mode is turned off, and it keeps a maximum of 100
    entries of the most recent debug messages. It also sets the port number
    and frequency for UDP broadcast.
    """

    def __init__(self):
        """Initializes the configuration instance and loads settings from the 
        config file.
        """
        self.debug = False
        self.debug_messages = []
        
        # Store the config in the lanshared folder (temporary)
        self.config_file = Path.cwd() / '.lanshare.conf'
        
        self.max_debug_messages = 100
        self._port = 12345  # Default port for all UDP communication
        self._clipboard_port = 12346  # Default clipboard port (port+1)
        self.peer_timeout = 2.0  # seconds
        self.broadcast_interval = 0.1  # seconds
        self.load_config()
    
    @property
    def port(self):
        """Gets the current port configuration."""
        return self._port
    
    @port.setter
    def port(self, value):
        """Sets the port value and updates related settings."""
        if isinstance(value, int) and value > 0:
            self._port = value
    
    @property
    def clipboard_port(self):
        """Gets the current clipboard port configuration."""
        return self._clipboard_port
    
    @clipboard_port.setter
    def clipboard_port(self, value):
        """Sets the clipboard port value."""
        if isinstance(value, int) and value > 0:
            self._clipboard_port = value
    
    def load_config(self):
        """Loads configuration settings from the config file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.debug = config.get('debug', False)
                    # Note: ports are not loaded from config file since they need to be
                    # set consistently across all components and are provided via command line
            except Exception as e:
                print(f"Error loading config: {e}")

    def save_config(self):
        """Saves the current configuration settings to the config file."""
        try:
            # Make sure the directory exists
            self.config_file.parent.mkdir(exist_ok=True)
            
            with open(self.config_file, 'w') as f:
                json.dump({
                    'debug': self.debug,
                    # Note: ports are not saved to config file since they're provided via command line
                }, f)
        except Exception as e:
            print(f"Error saving config: {e}")

    def add_debug_message(self, message: str):
        """Adds a debug message to the debug message history.

        Formats the timestamp of the message like 23:59:59. Maintains 100 most
        recent debug messages.
        
        Args:
          message: information to be logged for debugging.
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.debug_messages.append((timestamp, message))
        if len(self.debug_messages) > self.max_debug_messages:
            self.debug_messages.pop(0)