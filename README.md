# AwwRC
Because IRC didn't have enough Aww

## How to use!
Start the server: `python2 main.py`

Connect with a client: `telnet 127.0.0.1 5050`

### Channel Flags
- n: No outside messages allowed
- k: Password protected channel
- l: Limits the amount of users
- O: Server operators only
- F: Redirects users to another channel
- p: Prevents the channel from showing in the public list
- G: Enabled bad word list
- P: Playback - Sends the last x lines to a new client joining the channel
- B: prevents clients with the `B` (bot flag) from joining
- R: Only registered clients can join (not implemeted)

### User Flags
- O: Server Operator/Server Admin/Oper
- B: Flags the client as a bot
- w: Allows the client to receive oper messages
- k: Allows the client to use the `kill` command (not implemeted)
- S: Allows the client to use SA commands e.g `sajoin` `sanick` (not implemeted)
- i: Prevents the user from showing up on server user list (not implemented)
- a: Marks the client as away (not implemented)
