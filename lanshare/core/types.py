"""This module defines data classes for representing peers and messages in a LAN sharing service."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional

@dataclass
class Peer:
    """Represents a peer in the LAN sharing service.
    
    Attributes:
        username: The username of the peer.
        address: The IP address of the peer.
        last_seen: The last time the peer was seen.
        first_seen: The first time the peer was seen.
        registry_peer: Whether this peer was discovered via a registry server.
    """

    username: str
    address: str
    port: int
    last_seen: datetime
    first_seen: datetime
    registry_peer: bool = False  # Discovered via registry
    broadcast_peer: bool = True  # Discovered via broadcast (default)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Peer':
        """Create an instance of Peer from a dictionary."""
        return cls(
            username=data['username'],
            address=data['address'],
            last_seen=data['last_seen'],
            first_seen=data['first_seen'],
            registry_peer=data.get('registry_peer', False),
            broadcast_peer=data.get('broadcast_peer', True)
        )
        
@dataclass
class Message:
    """Represents a message in the LAN Sharing Service.

    Attributes:
        id: Unique identifier for the message.
        sender: The sender username of the message.
        recipient: The recipient username of the message.
        title: The title of the message.
        content: The content of the message.
        timestamp: The timestamp when the message was processed.
        conversation_id: The ID of the conversation this message belongs to, if any.
        reply_to: The ID of the message this message is replying to, if any.
    """

    id: str
    sender: str
    recipient: str
    title: str
    content: str
    timestamp: datetime
    conversation_id: Optional[str] = None
    reply_to: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create an instance of Message from a dictionary.
        
        Args:
            data: A dictionary containing the message data.
        
        Returns:
            An instance of the Message class populated with the data from the dictionary.
        
        Raises:
            KeyError: If required keys are missing from the dictionary.
            ValueError: If the timestamp format is incorrect.
        """

        return cls(
            id=data['id'],
            sender=data['sender'],
            recipient=data['recipient'],
            title=data['title'],
            content=data['content'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            conversation_id=data.get('conversation_id'),
            reply_to=data.get('reply_to')
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the object to a dictionary representation.

        Returns:
            A dictionary containing the object's attributes.
        """

        return {
            'id': self.id,
            'sender': self.sender,
            'recipient': self.recipient,
            'title': self.title,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'conversation_id': self.conversation_id,
            'reply_to': self.reply_to
        }

@dataclass
class Clip:
    """
    Represents a clipboard content (clip) in the LAN sharing service.
    Attributes:
        id (str): Unique identifier for the clip.
        content (str): The actual content of the clip.
        source (str): The source/origin of the clip (e.g., device name or identifier).
    Methods:
        from_dict(data): Creates a Clip instance from a dictionary representation.
        to_dict(): Converts the Clip instance to a dictionary representation.
    """
    id: str
    content: str
    source: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Clip':
        return cls(
            id=data['id'],
            content=data['content'],
            source=data['source']
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'content': self.content,
            'source': self.source
        }