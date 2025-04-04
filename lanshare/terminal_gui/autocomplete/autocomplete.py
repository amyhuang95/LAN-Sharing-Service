"""Custom completers for the LAN Sharing Service application.

This module provides custom completers for paths and usernames to enhance the user
experience when entering commands.
"""

import os
from typing import List, Dict, Optional, Iterable, Union

from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.document import Document


class UserCompleter(Completer):
    """Complete usernames from the list of available peers."""

    def __init__(self, discovery):
        """Initialize the completer with the discovery service.
        
        Args:
            discovery: The discovery service that tracks peers.
        """
        self.discovery = discovery
        
    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """Return completions for the current input.
        
        Args:
            document: The document to complete.
            complete_event: The completion event.
            
        Returns:
            An iterable of completions.
        """
        # Get the word being completed
        word_before_cursor = document.get_word_before_cursor()
        
        # Get the list of peers from the discovery service
        peers = self.discovery.list_peers()
        
        # Return completions that match the current input
        for username in peers:
            if username.lower().startswith(word_before_cursor.lower()):
                # Calculate how much of the username has already been typed
                display = username
                yield Completion(
                    username,
                    start_position=-len(word_before_cursor),
                    display=display,
                    display_meta="User"
                )


class EnhancedPathCompleter(PathCompleter):
    """Enhanced path completer with better display of results."""
    
    def get_completions(self, document, complete_event):
        """Return completions for paths with enhanced display."""
        word_before_cursor = document.text
        
        # If just starting or at ~, initialize with current directory or home
        if not word_before_cursor or word_before_cursor == '~':
            path = os.path.expanduser('~') if word_before_cursor == '~' else '.'
            try:
                # List directory contents
                for filename in os.listdir(path):
                    full_path = os.path.join(path, filename)
                    is_dir = os.path.isdir(full_path)
                    display = filename + ('/' if is_dir else '')
                    meta = 'Directory' if is_dir else 'File'
                    
                    if path == '.':
                        # Just show filename for current directory
                        completion_text = filename + ('/' if is_dir else '')
                    else:
                        # Use full path when not in current directory
                        if path == os.path.expanduser('~'):
                            # Use ~ for home directory
                            completion_text = os.path.join('~', filename)
                            completion_text = completion_text + ('/' if is_dir else '')
                        else:
                            # Use absolute path
                            completion_text = full_path + ('/' if is_dir else '')
                            
                    yield Completion(
                        completion_text,
                        start_position=-len(word_before_cursor),
                        display=display,
                        display_meta=meta
                    )
                return
            except OSError:
                pass  # Fallback to normal path completion
        
        # Regular path completion with expanduser support
        yield from super().get_completions(document, complete_event)


class CommandCompleter(Completer):
    """Complete commands with context-aware username and path completion."""
    
    def __init__(self, discovery, commands):
        """Initialize the completer with discovery service and commands.
        
        Args:
            discovery: The discovery service that tracks peers.
            commands: Dictionary of available commands.
        """
        self.discovery = discovery
        self.commands = commands
        self.path_completer = EnhancedPathCompleter(
            expanduser=True,
            only_directories=False,
        )
        self.user_completer = UserCompleter(discovery)
        
        # Define which commands need username completion for their arguments
        self.user_arg_commands = {
            'msg': 0,      # msg <username>
            'sc': [1],     # sc to|from <username> add|rm
            'access': 1,   # access <resource_id> <username> add|rm
        }
        
        # Define which commands need path completion
        self.path_arg_commands = {
            'share': 0,  # share <path>
        }

        # Commands with specific first argument choices
        self.first_arg_choices = {
            'sc': ['to', 'from'],  # sc to|from <username> add|rm
            'clipboard': ['on', 'off'],  # clipboard on|off
            'registry': ['connect', 'disconnect', 'status'],  # registry connect|disconnect|status
        }

        # Commands with specific final argument choices
        self.final_arg_choices = {
            'sc': ['add', 'rm'],  # sc to|from <username> add|rm
            'access': ['add', 'rm'],  # access <resource_id> <username> add|rm
            'all': ['on', 'off'],  # all <resource_id> on|off
        }
        
    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """Return completions based on the current context.
        
        Args:
            document: The document to complete.
            complete_event: The completion event.
            
        Returns:
            An iterable of completions.
        """
        text = document.text
        
        # If no text, complete with commands
        if not text.strip():
            for command in sorted(self.commands.keys()):
                yield Completion(command, display=command, display_meta="Command")
            return
            
        # Split the input into words
        words = text.split()
        
        # If only one word or cursor is at the first word, complete commands
        if len(words) == 1 and not text.endswith(' '):
            word_before_cursor = document.get_word_before_cursor()
            for command in sorted(self.commands.keys()):
                if command.startswith(word_before_cursor):
                    yield Completion(
                        command,
                        start_position=-len(word_before_cursor),
                        display=command,
                        display_meta="Command"
                    )
            return
            
        # Handle next argument suggestion
        if text.endswith(' '):
            # We're at the start of a new argument
            command = words[0]
            arg_position = len(words)
            
            # Handle first argument choices for specific commands
            if arg_position == 1 and command in self.first_arg_choices:
                for choice in self.first_arg_choices[command]:
                    yield Completion(
                        choice,
                        start_position=0,
                        display=choice,
                        display_meta=f"{command} option"
                    )
                return
            
            # Handle resource ID suggestions for access and all commands
            if command == 'access' and arg_position == 1:
                # Getting resource IDs
                resources = self.discovery.file_share_manager.list_shared_resources()
                for resource in resources:
                    resource_id = resource.id
                    display_meta = f"{'Directory' if resource.is_directory else 'File'}: {os.path.basename(resource.path)}"
                    yield Completion(
                        resource_id,
                        start_position=0,
                        display=resource_id,
                        display_meta=display_meta
                    )
                return
            
            if command == 'all' and arg_position == 1:
                # Getting resource IDs for all command
                resources = self.discovery.file_share_manager.list_shared_resources()
                for resource in resources:
                    resource_id = resource.id
                    display_meta = f"{'Directory' if resource.is_directory else 'File'}: {os.path.basename(resource.path)}"
                    yield Completion(
                        resource_id,
                        start_position=0,
                        display=resource_id,
                        display_meta=display_meta
                    )
                return
            
            # Handle clipboard (sc) command's special structure
            if command == 'sc':
                if arg_position == 1:
                    # Direction options
                    for option in ['to', 'from']:
                        yield Completion(
                            option,
                            start_position=0,
                            display=option,
                            display_meta="Clipboard direction"
                        )
                    return
                elif arg_position == 2:
                    # Username suggestion for 'sc to/from <username>'
                    for username in self.discovery.list_peers():
                        yield Completion(
                            username,
                            start_position=0,
                            display=username,
                            display_meta="User"
                        )
                    return
                elif arg_position == 3:
                    # Add/Remove options
                    for option in ['add', 'rm']:
                        yield Completion(
                            option,
                            start_position=0,
                            display=option,
                            display_meta="Clipboard action"
                        )
                    return
            
            # Check if we need username completion for this position
            if command in self.user_arg_commands:
                positions = self.user_arg_commands[command]
                if isinstance(positions, int) and arg_position == positions + 1:
                    # Single position specified
                    for username in self.discovery.list_peers():
                        yield Completion(
                            username,
                            start_position=0,
                            display=username,
                            display_meta="User"
                        )
                    return
                elif isinstance(positions, list) and arg_position - 1 in positions:
                    # List of positions
                    for username in self.discovery.list_peers():
                        yield Completion(
                            username,
                            start_position=0,
                            display=username,
                            display_meta="User"
                        )
                    return
            
            # Handle path completion
            if command in self.path_arg_commands and arg_position == self.path_arg_commands[command] + 1:
                # Use empty path to suggest current directory contents
                empty_doc = Document("", 0)
                yield from self.path_completer.get_completions(empty_doc, complete_event)
                return
            
            # Check for final argument choices
            if command in self.final_arg_choices:
                # For sc, the final argument is at position 3 (sc to|from <username> add|rm)
                if command == 'sc' and arg_position == 3:
                    for option in self.final_arg_choices[command]:
                        yield Completion(
                            option,
                            start_position=0,
                            display=option,
                            display_meta=f"{command} action"
                        )
                    return
                # For access, the final argument is at position 3 (access <resource_id> <username> add|rm)
                elif command == 'access' and arg_position == 3:
                    for option in self.final_arg_choices[command]:
                        yield Completion(
                            option,
                            start_position=0,
                            display=option,
                            display_meta=f"{command} action"
                        )
                    return
                # For all, the final argument is at position 2 (all <resource_id> on|off)
                elif command == 'all' and arg_position == 2:
                    for option in self.final_arg_choices[command]:
                        yield Completion(
                            option,
                            start_position=0,
                            display=option,
                            display_meta=f"{command} option"
                        )
                    return
        
        # Handle completion within an argument (not at the start of a new one)
        command = words[0]
        arg_position = len(words) - 1
        
        # Create a new document with just the current word for specialized completers
        word_before_cursor = document.get_word_before_cursor()
        current_word_document = Document(word_before_cursor, len(word_before_cursor))
        
        # Resource ID completion for commands that need resource IDs
        if command == 'access' and arg_position == 1:
            # Get all available resource IDs from file_share_manager
            resources = self.discovery.file_share_manager.list_shared_resources()
            
            for resource in resources:
                resource_id = resource.id
                if resource_id.startswith(word_before_cursor):
                    display_meta = f"{'Directory' if resource.is_directory else 'File'}: {os.path.basename(resource.path)}"
                    yield Completion(
                        resource_id,
                        start_position=-len(word_before_cursor),
                        display=resource_id,
                        display_meta=display_meta
                    )
            return
        
        # Same for the 'all' command - first parameter should be resource ID
        if command == 'all' and arg_position == 1:
            # Get all available resource IDs from file_share_manager
            resources = self.discovery.file_share_manager.list_shared_resources()
            
            for resource in resources:
                resource_id = resource.id
                if resource_id.startswith(word_before_cursor):
                    display_meta = f"{'Directory' if resource.is_directory else 'File'}: {os.path.basename(resource.path)}"
                    yield Completion(
                        resource_id,
                        start_position=-len(word_before_cursor),
                        display=resource_id,
                        display_meta=display_meta
                    )
            return
        
        # Handle first argument for 'sc' and other commands with specific choices
        if arg_position == 1 and command in self.first_arg_choices:
            for choice in self.first_arg_choices[command]:
                if choice.startswith(word_before_cursor):
                    yield Completion(
                        choice,
                        start_position=-len(word_before_cursor),
                        display=choice,
                        display_meta=f"{command} option"
                    )
            return
            
        # Check if we need username completion for this command and position
        if command in self.user_arg_commands:
            positions = self.user_arg_commands[command]
            if isinstance(positions, int) and arg_position == positions + 1:
                # Single position specified
                yield from self.user_completer.get_completions(current_word_document, complete_event)
                return
            elif isinstance(positions, list) and arg_position - 1 in positions:
                # List of positions
                yield from self.user_completer.get_completions(current_word_document, complete_event)
                return
                
        # Check if we need path completion
        if command in self.path_arg_commands and arg_position == self.path_arg_commands[command] + 1:
            # Path position
            last_word = words[-1] if words else ""
            path_document = Document(last_word, len(last_word))
            yield from self.path_completer.get_completions(path_document, complete_event)
            return
        
        # Handle sc command's special structure for completion
        if command == 'sc':
            if arg_position == 1:
                # Direction options (to/from)
                for option in ['to', 'from']:
                    if option.startswith(word_before_cursor):
                        yield Completion(
                            option,
                            start_position=-len(word_before_cursor),
                            display=option,
                            display_meta="Clipboard direction"
                        )
                return
            elif arg_position == 2:
                # Username for 'sc to/from <username>'
                yield from self.user_completer.get_completions(current_word_document, complete_event)
                return
            elif arg_position == 3:
                # Add/Remove options
                for option in ['add', 'rm']:
                    if option.startswith(word_before_cursor):
                        yield Completion(
                            option,
                            start_position=-len(word_before_cursor),
                            display=option,
                            display_meta="Clipboard action"
                        )
                return
        
        # For any other case, provide command-specific completions
        if command == 'access' and arg_position == 3:
            # Complete add/rm for access command
            for option in ['add', 'rm']:
                if option.startswith(word_before_cursor):
                    yield Completion(
                        option,
                        start_position=-len(word_before_cursor),
                        display=option,
                        display_meta="Access action"
                    )
            return
            
        if command == 'all' and arg_position == 2:
            # Complete on/off for the all command
            for option in ['on', 'off']:
                if option.startswith(word_before_cursor):
                    yield Completion(
                        option,
                        start_position=-len(word_before_cursor),
                        display=option,
                        display_meta="Share option"
                    )
            return
            
        if command == 'clipboard' and arg_position == 1:
            # Complete on/off for the clipboard command
            for option in ['on', 'off']:
                if option.startswith(word_before_cursor):
                    yield Completion(
                        option,
                        start_position=-len(word_before_cursor),
                        display=option,
                        display_meta="Clipboard option"
                    )
            return
            
        if command == 'registry' and arg_position == 1:
            # Complete registry commands
            for option in ['connect', 'disconnect', 'status']:
                if option.startswith(word_before_cursor):
                    yield Completion(
                        option,
                        start_position=-len(word_before_cursor),
                        display=option,
                        display_meta="Registry command"
                    )
            return