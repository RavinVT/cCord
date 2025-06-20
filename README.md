# cCord
A python based video call platform


cCord is a pet project of mine, where I am trying to create a video call platform that allows you to chat over a "secure" server that currently allows 2 people to chat with each other using pygame for the GUI and camera capture system and sends that over the internet with cryptography.fernet encryption.


## Packets
Packets that are sent use one simple system
```json
{
  "type": "<whatever>",
  "<whatever>": "<whatever>"
}
```
Every packet is pickle'd, msgpack'ed and cryptography.fernet'ed


## Server
The server uses a randomly generated key that it generates everytime on startup, the server does not process image data only connect and disconnect data, infact the server relies on a softerrer from the encrypted packets to skip the "connect", "disconnect" checks for the user. The client is added to a list of adders when they are added to the call, technically there is no limit on how many clients can be on one server but it will cause issues that are still to be delt with.


## Client
The client handles all of the "peer to peer" activity, it has the ability to encrypt and decrypt all of the messages execpt for the "connect" and "disconnect" messages as they arent sent to clients, when your camera is on it will send those images over the network, however by default this is disabled and instead text saying "Video Disabled" is sent over the network instead. The platform has a chat system, as currently there is no Microphone system.


## Compiling
Ok so probably the wrong word but there is an encluded `compile_client.sh` for those on linux with the pyinstaller command that is required. The server can be compiled via the `compile_server.sh` for those on linux with the pyinstaller command that is required. Windows versions coming soon. This should already work on MacOS if not it should work when the Windows versions are added.
