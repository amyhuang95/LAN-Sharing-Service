# LAN Sharing Service
A local-area-network (LAN) sharing service that shares files and clipboards across different devices in local area network, essientially, it means transferring files directly between devices on the same network without going through the internet. 

## Table of Contents
- [Overview](#lan-sharing-service)
- [Critical User Journeys (CUJ)](#cuj)
- [Prerequisites](#prerequisite)
- [Getting Started](#start)
- [Usage Notes](#note)
- [Demonstrations](#demo)
  - [Video Demos iter 1](#video-iter1)
  - [Video Demos iter 2](#video-iter1)
- [File Sharing Features](#iter2-file-sharing-commands)
  - [Sharing Files](#share-share-path-to-a-filedirectory)
  - [Viewing Shared Files](#show-all-shared-files-files)
  - [Managing Access](#regular-access-command-access-resource_id-user_id-addrm)
- [Clipboard Sharing](#iter1-basic-commands---peer-discovery--message)
  - [sc/rc](#user-list-ul)
- [Peer Discovery & Msg Exchange](#iter1-basic-commands---peer-discovery--message)
  - [msg](#user-list-ul)
  - [lm/om](#debug-view-debug)
- [GUI](#iter1-basic-commands---peer-discovery--message)
  - [gui=terminal](#user-list-ul)
- [Auto-Complete](#iter1-basic-commands---peer-discovery--message)
  - [gui=terminal](#user-list-ul)



## CUJ
- *CUJ#1:* sub LAN with access code;
- *CUJ#2:* peer discoveries (in LAN and sub-LAN);
- *CUJ#3:* access level (secured mode, admin, visitor, ...);
- *CUJ#4:* messages transmission & history (text only);
- *CUJ#5:* file transmission (different format);
- *CUJ#6:* streaming across LAN;
- *CUJ#7:* backup and restore;

## Prerequisite
First, make a new folder and clone the repo:
```sh
mkdir lanss && cd lanss
git clone git@github.com:amyhuang95/LAN-Sharing-Service.git
cd LAN-Sharing-Service
```

download all python dependencies:

```
pip install -r requirements.txt
```
**Notes: Make sure all the device are in the same LAN to discover your peers.**

## Start
Create a user with `username = evan-dayy`. Add `--share_clipboard` or `-sc` flag to activate clipboard sharing feature.
```sh
python create.py create --username <USERNAME> [-sc]
```
Type `help` to see the LAN Terminal command;
```

Welcome to LAN Share, evan-dayy#81b6!
Type 'help' for available commands
evan-dayy#81b6@LAN(192.168.4.141)# help

Available commands:
  ul     - List online users
  msg    - Send a message (msg <username>)
  lm     - List all messages
  om     - Open a message conversation (om <conversation_id>)
  share  - Share a file or directory (share <path>)
  files  - List shared files
  access - Manage access to shared resources (access <id> <user> [add|rm])
  all    - Share resource with everyone (all <id> [on|off])
  sc     - Share clipboard (sc <username_1> <username_2> ...)
  rc     - Receive clipboard from peers (rc <username_1> <username_2> ...)
  debug  - Toggle debug mode
  clear  - Clear screen
  help   - Show this help message
  exit   - Exit the session
evan-dayy#81b6@LAN(192.168.4.141)#

```

#### Note
* To enable two way exchange of clipboard content, peers needs to add each other to their sending and receiving lists with `sc` and `rc` commands. For example, if Peer1 and Peer2 want to exchange clipboard data:

  Peer1 needs to run:
  ```
  sc Peer2
  rc Peer2
  ```

  Peer2 needs to run:
  ```
  sc Peer1
  rc Peer1
  ```
  With this setup, when Peer1 copies some text, Peer2 will be able to paste right away. Same for the opposite direction. 

## Demo
### Video (iter1) 

https://github.com/user-attachments/assets/549d37ee-d8e8-4d7f-b6bb-4cc80f819626

### Video (iter2) 


https://github.com/user-attachments/assets/3b515191-a86d-436f-904b-736dbc586298


## Iter2 File Sharing Commands

These commands show all the basic usages on how to share a file or directory with a peer, however, there are some important features doesn't show here, here are the summary we provide on file sharing features:
- Share a file or directory to everyone;
- Almost all types of files - including pdf, scripts, pictures, even videos
- Give/Remove certain user an access to a file or directory;
- **Auto-sync**: The update in the host file or directory will be synced to peers;
- Access Provision & Deletion during new peers emerge or quit;
- An Interactive UI to easily interact with the files sharing;

### Share `share <path to a [file|directory]>`
```
evan-dayy#07a8@LAN(192.168.4.141)# share ~/Desktop/samwise
evan-dayy#07a8@LAN(192.168.4.141)# share ./create.py
```
- You can share any file (including video or images) or directory (including recusive directory) by using this command;
- The path can be any format - including relative path or absolute path;
- All shared file will be stored in a the home directory folder called shared, and each peer should has its own shared folder.
```
lanshare
    |____shared
            |____evan-dayy#07a8
            |____jennifer#24fs
            |____(other peers shared files)
```

### Show all shared files `files`
```
evan-dayy#07a8@LAN(192.168.4.141)# files
```
![Local Image](assets/files.png)

- There are some sub-commands listed in the view, press `e` to in this view to quickly give acccess to everyone;
![Local Image](assets/files2.png)


### Regular Access Command `access <resource_id> <user_id> [add|rm]` 
```
evan-dayy#07a8@LAN(192.168.4.141)# access samwise_id jennifer#24s7 add
Successfully added to access list for jennifer#24s7
evan-dayy#07a8@LAN(192.168.4.141)# access samwsize_id jennifer#24s7 rm
Successfully removed from access list for jennifer#24s7
```
- Give access to a particular user; 
