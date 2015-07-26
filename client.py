import sys
import socket
import threading
import time
import json
import hashlib
import uuid


import errorcodes  # Local Import


class Client(threading.Thread):

    '''
    Class that implements the client threads in this server
    Client Modes:
    B = Bot
    O = Oper
    k = can kill users from the server
    w = receives oper messages
    '''

    def __init__(self, client_sock, server):
        '''
        Initialize the object, save the socket that this thread will use.
        '''
        threading.Thread.__init__(self)
        self.client = client_sock
        self.server = server
        self.ip = self.client.getpeername()[0]  # Get the clients IP address
        self.nick = str(uuid.uuid4())
        self.channels = {}
        self.account = None
        self.flags = self.server.CONFIG["DEFAULT_CLIENT_FLAGS"]

    def set_nick(self, client, nick):
        """
        Sets the clients nick
        """
        if len(nick) <= self.server.CONFIG["MAX_NICK_LENGTH"]:
            for c in nick: # make sure each char in in the set
                if not c in self.server.CONFIG["NICK_CHAR_SET"]:
                    client.writeline(json.dumps({
                        "type": "ERROR",
                        "code": errorcodes.get("invalid channel/nick"),
                        "message": "Your nick my only contain these chars: %s" % (
                            self.server.CONFIG["NICK_CHAR_SET"]
                        )
                    }))
                    self.set_nick(client, client.readline())
            if nick not in self.server.users.keys() and nick not in self.server.CONFIG["RESERVED_NICKS"]:
                old_nick = str(client.nick)
                client.nick = str(nick)
                self.server.users[client.nick] = self
                self.writeline(json.dumps({
                    "type": "NICK",
                    "old_nick": old_nick,
                    "new_nick": client.nick
                }))
                self.server.writeline(
                    "%s is now known as %s" % (old_nick, nick))
            else:
                self.writeline(json.dumps({
                    "type": "ERROR",
                    "code": errorcodes.get("nick in use"),
                    "message": "%s is already in use. Please choose a new nick." % nick
                }))
                self.set_nick(client, client.readline())
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("nick excecced limit"),
                "message": "Your nick is too long. Please choose a nick with less than %i chars" %
                self.server.CONFIG["MAX_NICK_LENGTH"]
            }))
            self.set_nick(client, client.readline())

    def logged_in(self):
        return self.account

    def run(self):
        '''
        Thread's main loop. Once this function returns, the thread is finished
        and dies.
        '''
        try:
            # client needs to change their nick
            self.writeline(json.dumps({
                "type": "PICKNICK"
            }))
            self.set_nick(self, self.readline())
            # Need to declare QUIT as global, since the method can change it
            # Read data from the socket and process it
            while True:
                cmd = self.readline()
                args = cmd.split(" ")
                # Command `quit`
                if args[0].lower() == "quit":
                    if len(args) > 1:
                        self.command_quit(message=' '.join(args[1:]))
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: quit <message>"
                        }))
                # Command `nick`:
                elif args[0].lower() == "nick":
                    if len(args) > 1:
                        self.command_nick(nick=args[1])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: nick <nick>"
                        }))
                # Command `userflag`
                elif args[0].lower() == "userflag":
                    if len(args) > 2:
                        self.command_set_userflag(switch=args[1], flag=args[2])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "userflag <add/remove> <flag>"
                        }))
                # Command `chanlist`
                elif args[0].lower() == "chanlist":
                    self.command_channel_list()
                # Command `register`
                elif args[0].lower() == "register":
                    if len(args) > 2:
                        self.command_register(password=args[1], email=args[2])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: register <password> <email>"
                        }))
                # Command `login`
                elif args[0].lower() == "login":
                    if len(args) > 1:
                        self.command_login(password=args[1])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: login <password>"
                        }))
                # Command `usermsg`
                elif args[0].lower() == "usermsg":
                    if len(args) > 2:
                        self.command_message_user(
                            nick=args[1], message=' '.join(args[2:]))
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: usermsg <nick> <message>"
                        }))
                # Command `whois`
                elif args[0].lower() == "whois":
                    if len(args) > 1:
                        self.command_whois(nick=args[1])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: whois <nick>"
                        }))
                # Command `chanjoin`
                elif args[0].lower() == "chanjoin":
                    if len(args) == 2:
                        self.command_channel_join(
                            chan_name=args[1], password=None)
                    elif len(args) == 3:
                        self.command_channel_join(
                            chan_name=args[1], password=args[2])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: chanjoin <channel> [password]"
                        }))
                # Command `chanpart`
                elif args[0].lower() == "chanpart":
                    if len(args) > 2:
                        self.command_channel_part(
                            chan_name=args[1], message=' '.join(args[2:]))
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: chanpart <channel> <message>"
                        }))
                # Command `chanmsg`
                elif args[0].lower() == "chanmsg":
                    if len(args) > 2:
                        self.command_channel_message(
                            chan_name=args[1], message=' '.join(args[2:]))
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: chanmsg <channel> <message>"
                        }))
                # Command `chankick`
                elif args[0].lower() == "chankick":
                    if len(args) > 3:
                        self.command_channel_kick(
                            chan_name=args[1], nick=args[2],
                            message=' '.join(args[3:]))
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: chankick <channel> <nick> <reason>"
                        }))
                # Comamnd `chanflag`
                elif args[0] == "chanflag":
                    if len(args) > 4:
                        self.command_channel_flag(chan_name=args[1], switch=args[2],
                        flag=args[3], args=' '.join(args[4:]))
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: chanflag <channel> <add/remove> <flag> <args>"
                        }))
                # Command `chanban`
                elif args[0] == "chanban":
                    if len(args) > 2:
                        self.command_channel_ban(
                            chan_name=args[1], nick=args[2])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: chanban <channel> <nick>"
                        }))
                # Command `chanunban`
                elif args[0].lower() == "chanunban":
                    if len(args) > 2:
                        self.command_channel_unban(
                            chan_name=args[1], ip=args[2])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: chanunban <channel> <IP>"
                        }))
                # Command `chanregister`
                elif args[0].lower() == "chanregister":
                    if len(args) > 1:
                        self.command_channel_register(chan_name=args[1])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: chanregister <channel>"
                        }))
                # Command `chanbadword`
                elif args[0].lower() == "chanbadword":
                    if len(args) > 3:
                        self.command_channel_badword(
                            chan_name=args[1], switch=args[2],
                            badword=args[3])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMGS",
                            "message": "help: chanbadword <channel> <add/remove> <word>"
                        }))
                # Command  `chanclientflag`
                elif args[0].lower() == "chanclientflag":
                    if len(args) > 4:
                        self.command_channel_clientflag(
                            chan_name=args[1], switch=args[2],
                            nick=args[3], flag=args[4])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: chanflag <channel> <add/remove> <nick> <flag>"
                        }))
                # Command `chanusers`
                elif args[0].lower() == "chanusers":
                    if len(args) > 1:
                        self.command_channel_members(chan_name=args[1])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: chanusers <channel>"
                        }))
                # Command `oper`
                elif args[0].lower() == "oper":
                    if len(args) > 1:
                        self.command_oper(password=args[1])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: oper <password>"
                        }))
                # Command `opermsg`
                elif args[0].lower() == "opermsg":
                    if len(args) > 1:
                        self.command_oper_message(message=' '.join(args[1:]))
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: opermsg <message>"
                        }))
                # Command `kill`
                elif args[0].lower() == "kill":
                    if len(args) > 1:
                        self.command_oper_kill(args[1])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: kill <nick>"
                        }))
                # Command `sanick`
                elif args[0].lower() == "sanick":
                    if len(args) > 2:
                        self.command_oper_sanick(
                            nick=args[1], new_nick=args[2])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: sanick <nick> <new nick>"
                        }))
                # Command `sajoin`
                elif args[0].lower() == "sajoin":
                    if len(args) > 2:
                        self.command_oper_sajoin(
                            nick=args[1], chan_name=args[2])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: sajoin <nick> <channel>"
                        }))
                # Command `sapart`
                elif args[0].lower() == "sapart":
                    if len(args) > 2:
                        self.command_oper_sapart(
                            nick=args[1], chan_name=args[2])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: sapart <nick> <channel>"
                        }))
                # Command `serverban`
                elif args[0].lower() == "serverban":
                    if len(args) > 1:
                        self.command_oper_server_ban(ip=args[1])
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: serverban <IP>"
                        }))
                # Command `globalmsg`
                elif args[0].lower() == "globalmsg":
                    if len(args) > 1:
                        self.command_oper_global_message(
                            message=' '.join(args[1:]))
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: globalmsg <message>"
                        }))
                # Command `note`
                elif args[0].lower() == "usernote":
                    if len(args) > 2:
                        self.command_usernote(nick=args[1],
                            message=' '.join(args[2:]))
                    else:
                        self.writeline(json.dumps({
                            "type": "SERVERMSG",
                            "message": "help: usernote <nick> <message>"
                        }))
                else:
                    self.writeline(json.dumps({
                        "type": "INVALIDCOMMAND"
                    }))
            # Make sure the socket is closed once we're done with it
            self.client.close()
            return
        except Exception, err:
            print err
            self.client.close()
            return

# Commands

    def command_quit(self, message="bye bye"):
        """
        Disconnects the client from the server
        """
        self.writeline(json.dumps({
            "type": "YOUQUIT",
            "message": message
        }))
        self.quit()

    def command_nick(self, nick):
        """
        Changes the clients nick
        """
        self.set_nick(self, nick)

    def command_set_userflag(self, switch, flag):
        """
        Lets the client set flags on themselves
        """
        allowed_flags = ['B']
        if switch == "add":
            if flag in allowed_flags and flag not in self.flags:
                self.flags.append(flag)
                self.writeline(json.dumps({
                    "type": "SERVERMSG",
                    "message": "You set +%s on yourself" % flag
                }))
        elif switch == "remove":
            if flag in self.flags:
                self.flags.remove(flag)
                self.writeline(json.dumps({
                    "type": "SERVERMSG",
                    "message": "You set -%s on yourself" % flag
                }))

    def command_usernote(self, nick, message):
        """
        Lets a client leave a note for another client
        """
        account = self.server.get_account(nick)
        if account:
            account.get("notes").append({
                "from": self.nick,
                "message": message
            })
            # Save changes
            with open("accounts/%s.json" % nick, 'w') as f:
                f.write(json.dumps(account,
                sort_keys=True, indent=4, separators=(',', ': ')))
            self.writeline(json.dumps({
                "type": "SERVERMSG",
                "message": "You sent a note to %s" % nick
            }))
        else:
            self.writeline(json.dumps({
                "type": "SERVERMSG",
                "message": "%s doesn't have an account." % nick
            }))

    def command_channel_list(self):
        """
        Sends the client the server channel list
        Public channels if the client isn't an oper
        All channels if the client is an oper
        """
        self.server.channel_list(self)

    def command_register(self, password, email):
        """
        Register an account with the server
        password: plain text password
        email: email address of the user
        """
        hashedpw = hashlib.md5(password).hexdigest()
        self.server.register_account(self, email, hashedpw)

    def command_login(self, password):
        """
        Login into the server
        password: plain text password
        """
        hashedpw = hashlib.md5(password).hexdigest()
        self.server.client_login(self, hashedpw)

    def command_message_user(self, nick, message):
        """
        Send a message to other user on this server
        nick: nick of client you want to send the message to
        message: the message you want to send to that client
        """
        self.message_nick(nick, message)

    def command_whois(self, nick):
        """
        Get WHOIS data from other client on the server
        nick: nick of client you want to get the data from
        """
        self.server.client_whois(self, nick)

    def command_channel_join(self, chan_name, password=None):
        """
        Joins this client to a channel on the server
        chan_name: Channel name
        password: Channel password
        """
        self.join(chan_name, password)

    def command_channel_part(self, chan_name, message="bye"):
        """
        Parts this client from a channel on this server
        chan_name: Channel name
        message: part message
        """
        self.part(chan_name, message)

    def command_channel_message(self, chan_name, message):
        """
        Sends a message to a channel on the server
        chan_name: Channel name
        message: message you want to send to the channel
        """
        self.message_channel(chan_name, message)


    def command_channel_members(self, chan_name):
        """
        Gives a list of all the clients in a channel
        chan_name: Channel name
        """
        if chan_name in self.channels:
            self.writeline(json.dumps({
                "type": "CHANUSERS",
                "channel": chan_name,
                "members": self.channels[chan_name].users.keys()
            }))
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not in channel"),
                "message": "You are not in %s" % chan_name
            }))

    def command_channel_kick(self, chan_name, nick, message="GTFO"):
        """
        Kick a client from a channel
        chan_name: Channel name
        nick: nick of client you want to kick from channel
        message: reason you're kicking this client
        """
        if chan_name in self.channels:
            self.channels[chan_name].kick_user(self, nick, message)
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not in channel"),
                "message": "You are not in %s" % chan_name
            }))

    def command_channel_ban(self, chan_name, nick):
        """
        Bad a client from a channel
        chan_name: Channel name
        nick: nick of user you want to bad
        """
        if chan_name in self.channels:
            self.channels[chan_name].ban_user(self, nick)
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not in channel"),
                "message": "You are not in %s" % chan_name
            }))

    def command_channel_unban(self, chan_name, ip):
        """
        Unban an IP from a channel
        chan_name: Channel name
        ip: ip you want to unban
        """
        if chan_name in self.channels:
            self.channels[chan_name].unban_ip(self, ip)
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not in channel"),
                "message": "You are not in %s" % chan_name
            }))

    def command_channel_register(self, chan_name):
        """
        Register a channel on the serevr
        chan_name: name of channel you want to register
        """
        if chan_name in self.channels:
            self.channels[chan_name].register(self)
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not in channel"),
                "message": "You're not in %s" % chan_name
            }))

    def command_channel_flag(self, chan_name, switch, flag, args=True):
        """
        Sets a flag in a channel
        chan_name: name of channel you want to set the
        flag in
        flag: the flag you want to set
        args: arguments for that flag
        """
        if args == "true":
            args = True
        elif args == "false":
            args = False
        elif args.isdigit():
            args = int(args)

        if switch == "add":
            if chan_name in self.channels:
                self.channels[chan_name].add_channel_flag(self, flag, args)
            else:
                self.writeline(json.dumps({
                    "type": "ERROR",
                    "code": errorcodes.get("not in channel"),
                    "message": "You're not in %s" % chan_name
                }))
        elif switch == "remove":
            if chan_name in self.channels:
                self.channels[chan_name].remove_channel_flag(self, flag)
            else:
                self.writeline(json.dumps({
                    "type": "ERROR",
                    "code": errorcodes.get("not in channel"),
                    "message": "You're not in %s" % chan_name
                }))

    def command_channel_badword(self, chan_name, switch, badword):
        """
        Adds a word to the channel badword list
        chan_name: Channel name
        switch: add or remove bad word
        badword: word to add to the badword list
        """
        if chan_name in self.channels:
            if switch.lower() == "add":
                self.channels[chan_name].add_badword(self, badword)
            elif switch.lower() == "remove":
                self.channels[chan_name].remove_badword(badword)
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not in channel"),
                "message": "You're not in %s" % chan_name
            }))

    def command_channel_clientflag(self, chan_name, switch, nick, flag):
        """
        Add a flag to a client on a channel
        chan_name: Channel name
        switch: add or remove bad word
        flag: flag you want to add/remove
        """
        if chan_name in self.channels:
            if switch.lower() == "add":
                self.channels[chan_name].add_client_flag(
                    self, nick, flag)
            elif switch.lower() == "remove":
                self.channels[chan_name].remove_client_flag(
                    self, nick, flag)
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not in channel"),
                "message": "You're not in %s" % chan_name
            }))

    def command_oper(self, password):
        """
        Turns this client into an oper
        password: password
        """
        self.server.oper(self, hashlib.md5(password).hexdigest())

    def command_oper_message(self, message):
        """
        Sends a message to all opers connected to the server
        """
        if self.is_oper():
            self.server.oper_message(self, message)
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not an oper"),
                "message": "You need to be an oper to use the `kill` command"
            }))

    def command_oper_kill(self, nick):
        """
        Disconnects a client from the server
        nick: nick of client you want to disconnect
        """
        self.kill(nick)

    def command_oper_sanick(self, nick, new_nick):
        """
        Changes a clients nick to a new nick by force
        nick: clients current nick
        new_nick: clients new nick
        """
        self.sanick(nick, new_nick)

    def command_oper_sajoin(self, nick, chan_name):
        """
        Forces a client to join a channel
        nick: client to force into channel
        chan_name: channel to force client into
        """
        self.sajoin(nick, chan_name)

    def command_oper_sapart(self, nick, chan_name):
        """
        Forces a client to leave a channel
        nick: client to force to leave channel
        chan_name: channel to force client to leave
        """
        self.sapart(nick, chan_name)

    def command_oper_server_ban(self, ip):
        """
        Bans a client from the server
        ip: ip to ban
        """
        self.ban_ip(ip)

    def command_oper_global_message(self, message):
        """
        Sends a message to all clients connected to the server
        """
        if self.is_oper():
            self.server.global_message(message)
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not an oper"),
                "message": "You need to be an oper to use the `announcement` command"
            }))

    def command_oper_rehash(self):
        if self.is_oper():
            self.server.rehash()
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not an oper"),
                "message": "You need to be an oper to use the `announcement` command"
            }))


# End Commands

    def readline(self):
        """
        Helper function, reads up to MAX_RECV_SIZE chars from the socket,
        and returns them as a string, without any end of line markers
        """
        result = self.client.recv(self.server.CONFIG["MAX_RECV_SIZE"])
        if(result != None):
            result = result.strip()
        return result

    def writeline(self, message):
        """
        Helper function, writes the given string to the socket, with an end of
        line marker appended at the end
        """
        self.client.send(message.strip() + '\n')

    def join(self, channel, key=None):
        """
        Joins the client to a channel on the server
        if CHANNEL_CREATION is False the client
        can only join channels that are already made.
        if CHANNEL_CREATION is True the client can
        join premade channels as well as create new
        channels.
        """
        if channel in self.server.channels:
            if channel not in self.channels:
                if self.server.channels[channel].on_join(self, key):
                    self.channels[channel] = self.server.channels[channel]
                    self.writeline(json.dumps({
                        "type": "YOUJOIN",
                        "channel": channel
                    }))
            else:
                self.writeline(json.dumps({
                    "type": "SERVERMSG",
                    "message": "You're already in %s" % channel
                }))
        else:
            if self.server.CONFIG.get("CHANNEL_CREATION"):
                if self.server.create_channel(self, channel):
                    self.channels[channel] = self.server.channels[channel]
                    self.server.channels[channel].on_join(self, key)
                    self.writeline(json.dumps({
                        "type": "YOUJOIN",
                        "channel": channel
                    }))
            else:
                self.writeline(json.dumps({
                    "type": "SERVERMSG",
                    "message": "This server does not allow the creation of channels"
                }))

    def part(self, channel, message="bye"):
        """
        Make the client leave the channel
        """
        if channel in self.channels:
            self.channels[channel].on_part(self, message)
            del self.channels[channel]
            self.writeline(json.dumps({
                "type": "YOUPART",
                "channel": channel,
                "message": message
            }))
        else:
            self.writeline(json.dumps({
                "type": "SERVERMSG",
                "message": "You are not in %s" % channel
            }))

    def add_flag(self, flag):
        """
        Gives this client a flag
        """
        if not flag in self.flags:
            self.flags.append(flag)

    def add_flags(self, flags):
        """
        Gives this client a flag
        """
        for flag in flags:
            self.add_flag(flag)

    def remove_flag(self, flag):
        """
        Removes a flag from this client
        """
        if flag in self.flags:
            self.flags.remove(flag)

    def remove_flags(self, flags):
        """
        Removes flags from this client
        """
        for flag in flags:
            self.remove_flag(flag)

    def quit(self):
        """
        Disconnects the client from the server
        """
        self.client.close()
        quit()

    ##### Handlers #####
    def on_kill(self, message):
        """
        Runs when the user gets killed from the network
        """
        self.writeline(json.dumps({
            "type": "YOUKILLED",
            "message": message
        }))
        self.quit()

    def on_kick(self, channel, reason):
        """
        Runs when you've been kicked from a channel
        """
        del self.channels[channel.name]
        self.writeline(json.dumps({
            "type": "YOUKICKED",
            "channel": channel.name,
            "message": reason
        }))

    def on_ban(self, channel):
        """
        Runs when you've been banned from a channel
        """
        self.writeline(json.dumps({
            "type": "YOUBANED",
            "channel": channel.name
        }))

    def on_sanick(self, new_nick):
        """
        Runs when a oper uses sanick on this client
        """
        self.writeline(
            "Your nick was changed by a server admin to %s" % new_nick)
        self.writeline(json.dumps({
            "type": "YOUSANICKED",
            "new_nick": new_nick
        }))

    def on_whois(self, client):
        """
        Runs when a user uses the whois command on this client
        """
        client.writeline(json.dumps({
            "type": "WHOIS",
            "nick": self.nick,
            "message": "Nick: %s" % (self.nick)
        }))
        client.writeline(json.dumps({
            "type": "WHOIS",
            "nick": self.nick,
            "message": "IP: %s" % (self.ip)
        }))
        client.writeline(json.dumps({
            "type": "WHOIS",
            "nick": self.nick,
            "message": "Oper: %s" % (self.is_oper())
        }))
        client.writeline(json.dumps({
            "type": "WHOIS",
            "nick": self.nick,
            "message": "Logged In: %s" % (bool(self.logged_in()))
        }))
        if not 'i' in self.flags or client.is_oper():
            client.writeline(json.dumps({
                "type": "WHOIS",
                "nick": self.nick,
                "message": "Channels: %s" % ', '.join(self.channels)
            }))
        if self.logged_in():
            client.writeline(json.dumps({
                "type": "WHOIS",
                "nick": self.nick,
                "message": "Account UUID: %s" % (self.account["uuid"])
            }))
        if client.is_oper():
            client.writeline(json.dumps({
                "type": "WHOIS",
                "nick": self.nick,
                "message": "Flags: %s" % ', '.join(self.flags)
            }))

    def on_sajoin(self, channel):
        """
        Runs when a server admin forces you into a channel
        """
        self.channels[channel] = self.server.channels[channel]
        self.writeline(json.dumps({
            "type": "YOUSAJOINED",
            "channel": channel
        }))

    def on_sapart(self, channel):
        """
        Runs when a server admin forces you to leave a channel
        """
        del self.channels[channel]
        self.writeline(json.dumps({
            "type": "YOUSAPARTED",
            "channel": channel
        }))

    def on_login(self):
        """
        Runs when this client logins
        """
        # Send unread notes to client
        for note in self.account.get("notes"):
            self.writeline(json.dumps({
                "type": "NOTE",
                "from": note.get("from"),
                "message": note.get("message")
            }))
        if self.account:
            self.account["notes"] = []
            with open("accounts/%s.json" % self.nick, 'w') as f:
                f.write(json.dumps(self.account,
                sort_keys=True, indent=4, separators=(',', ': ')))

    ##### Oper Commands #####
    def is_oper(self):
        return "O" in self.flags

    def kill(self, nick):
        """
        Disconnects a user from the server
        Kinda like a channel kick but from the server
        """
        if self.is_oper():
            if nick in self.server.users.keys():
                self.server.users[nick].on_kill("You were killed.")
                self.writeline(json.dumps({
                    "type": "SERVERMSG",
                    "message": "You killed %s" % nick
                }))
                self.server.writeline("%s killed %s" % (self.nick, nick))
            else:
                self.writeline(json.dumps({
                    "type": "ERROR",
                    "code": errorcodes.get("invalid channel/nick"),
                    "message": "%s isn't on the server." % nick
                }))
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not an oper"),
                "message": "You need to be an oper to use the `kill` command"
            }))

    def sanick(self, nick, new_nick):
        """
        Force a user to change their nick
        """
        if self.is_oper():
            if self.server.users.get(nick):
                self.server.users[nick].nick = new_nick
                self.server.users[nick].on_sanick(new_nick)
                self.server.users[new_nick] = self.server.users[nick]
                self.writeline(json.dumps({
                    "type": "SERVERMSG",
                    "message": "You changed %s nick to %s" % (nick, new_nick)
                }))
                self.server.writeline(
                    "%s changed %s's nick to %s" % (self.nick, nick, new_nick))
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not an oper"),
                "message": "You need to be an oper to use the `sanick` command"
            }))

    def sajoin(self, nick, channel):
        """
        Force a user to join a channel
        this will bypass all restrictions
        """
        if self.is_oper():
            if channel in self.server.channels:
                if nick in self.server.users:
                    self.server.channels[channel].add_client(
                        self.server.users[nick])
                    self.server.users[nick].on_sajoin(channel)
                    self.writeline("%s was forced to join %s" %
                                   (nick, channel))
                    self.writeline(json.dumps({
                        "type": "SERVERMSG",
                        "message": "You forced %s to join %s" % (nick, channel)
                    }))
                    self.server.writeline("%s forced %s to join %s" %
                                          (self.nick, nick, channel))
                else:
                    self.writeline(json.dumps({
                        "type": "ERROR",
                        "code": errorcodes.get("invalid channel/nick"),
                        "message": "%s isn't on the server." % nick
                    }))
            else:
                self.writeline(json.dumps({
                    "type": "ERROR",
                    "code": errorcodes.get("invalid channel/nick"),
                    "message": "%s doesn't exist" % channel
                }))
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not an oper"),
                "message": "You need to be an oper to use the `sajoin` command"
            }))

    def sapart(self, nick, channel):
        """
        Force a user to leave (part) a channel
        """
        if self.is_oper():
            if nick in self.server.users:
                if channel in self.server.channels:
                    self.server.channels[channel].on_part(
                        self.server.users[nick], "sapart")
                    self.server.users[nick].on_sapart(channel)
                    self.writeline("You forced %s to leave %s" %
                                   (nick, channel))
                    self.server.writeline("%s forced %s to leave %s" % (
                        self.nick, nick, channel))
                else:
                    self.writeline(json.dumps({
                        "type": "ERROR",
                        "code": errorcodes.get("invalid channel/nick"),
                        "message": "%s isn't on the server." % nick
                    }))
            else:
                self.writeline(json.dumps({
                    "type": "ERROR",
                    "code": errorcodes.get("invalid channel/nick"),
                    "message": "%s doesn't exist" % channel
                }))
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not an oper"),
                "message": "You need to be an oper to use the `sapart` command"
            }))

    def ban_ip(self, ip):
        """
        Adds an ip to the banlist.txt
        """
        if self.is_oper():
            self.server.ban_ip(self, ip)
            self.writeline(json.dumps({
                "type": "SERVERMSG",
                "message": "Banned %s from the server" % ip
            }))
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not an oper"),
                "message": "You need to be an oper to use the `ban` command"
            }))

    def message_nick(self, nick, message):
        """
        Sends a message to another client on the server
        nick: nick of the client you want to message
        message: the message you want to send to that client
        """
        users = [(nick, nick.lower()) for nick in self.server.users.keys()]
        for n in users:
            if n[1] == nick.lower():
                self.server.users[nick].writeline(json.dumps({
                    "type": "USERMSG",
                    "nick": self.nick,
                    "ip": self.ip,
                    "message": message
                }))
                return
        self.writeline(json.dumps({
            "type": "ERROR",
            "code": errorcodes.get("invalid channel/nick"),
            "message": "%s isn't on the server" % self.nick
        }))

    def message_channel(self, channel, message):
        """
        Sends a message to a channel on the server
        """
        if channel in self.server.channels.keys():
            self.server.channels[channel].on_message(self, message)
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("invalid channel/nick"),
                "message": "No channel named %s" % channel
            }))
