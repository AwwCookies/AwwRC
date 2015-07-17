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
    '''

    def __init__(self, client_sock, server):
        '''
        Initialize the object, save the socket that this thread will use.
        '''
        threading.Thread.__init__(self)
        self.client = client_sock
        self.server = server
        self.ip = self.client.getpeername()[0]  # Get the clients IP address
        self.nick = uuid.uuid4()
        self.channels = {}
        self.account = None
        self.flags = []

    def set_nick(self, client, nick):
        """
        Sets the clients nick
        """
        # TODO: add nick restrictions
        if len(nick) <= self.server.CONFIG["MAX_NICK_LENGTH"]:
            if nick not in self.server.users.keys():
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
                "type": "PICKNICK",
                "message": "Please pick a nick"
            }))
            self.set_nick(self, self.readline())
            # Need to declare QUIT as global, since the method can change it
            cmd = self.readline()
            # Read data from the socket and process it
            while True:
                # NOTE: Basic Commands
                args = cmd.split(" ")
                if 'quit' == cmd:
                    self.writeline('Ok, bye')
                    return
                elif 'nick' == cmd:
                    self.writeline("Your nick is: %s" % self.nick)
                elif 'chanlist' == args[0]:
                    self.server.channel_list(self)
                elif 'register' == args[0]:
                    self.server.register_account(self, args[1],
                                                 hashlib.md5(' '.join(args[2:])).hexdigest())
                elif 'login' == args[0]:
                    self.server.client_login(
                        self, hashlib.md5(' '.join(args[1:])).hexdigest())
                elif 'msg' == args[0]:
                    self.message_nick(args[1], ' '.join(args[2:]))
                elif 'channels' == args[0]:
                    self.writeline("You're in: %s" % self.channels.keys())
                elif 'oper?' == args[0]:
                    self.writeline("Oper: %s" % str(self.is_oper()))
                elif 'whois' == args[0]:
                    self.server.client_whois(self, args[1])
                elif 'flags' == args[0]:
                    self.writeline("FLAGS %s %s" % (self.nick, self.flags))

                # NOTE: Channel Commands
                elif 'join' == args[0]:
                    self.join(
                        args[1], ' '.join(args[2:]) if len(args) > 2 else None)
                elif 'part' == args[0]:
                    self.part(
                        args[1], ' '.join(args[2:]) if len(args) > 2 else None)
                elif 'chanmsg' == args[0]:
                    self.message_channel(args[1], ' '.join(args[2:]))
                elif 'kick' == args[0]:
                    if args[1] in self.channels:
                        self.channels[args[1]].kick_user(
                            self, args[2], ' '.join(args[3:]))
                    else:
                        self.writeline("You are not in %s" % args[1])
                elif 'ban' == args[0]:
                    if args[1] in self.channels:
                        self.channels[args[1]].ban_user(self, args[2])
                    else:
                        self.writeline("You are not in %s" % args[1])
                elif 'unban' == args[0]:
                    if args[1] in self.channels:
                        self.channels[args[1]].unban_ip(self, args[2])
                    else:
                        self.writeline("You are not in %s" % args[1])
                elif 'chanregister' == args[0]:
                    self.register_channel(args[1])

                # NOTE: Oper Commands
                elif 'oper' == args[0]:
                    self.server.oper(
                        self, hashlib.md5(' '.join(args[1:])).hexdigest())
                elif 'kill' == args[0]:
                    self.kill(args[1])
                elif 'sanick' == args[0]:
                    self.sanick(args[1], args[2])
                elif 'sajoin' == args[0]:
                    self.sajoin(args[1], args[2])
                elif 'sapart' == args[0]:
                    self.sapart(args[1], args[2])
                elif 'chanflag' == args[0]:
                    chan = args[2]
                    nick = args[3]
                    flag = args[4]
                    if chan in self.channels.keys():
                        if args[1] == "add":
                            self.channels[chan].add_client_flag(
                                self, nick, flag)
                        elif args[1] == "remove":
                            self.channels[chan].remove_client_flag(
                                self, nick, flag)
                    else:
                        self.writeline("You are not in %s" % chan)
                elif 'flags' == args[0]:
                    self.writeline("FLAGS %s %s" % (self.nick, self.flags))
                elif 'ban' == args[0]:
                    self.ban_ip(args[1])
                elif 'announcement' == args[0]:
                    self.server_announcemet(' '.join(args[1]))
                else:
                    self.writeline("%s: invalid command" % args[0])

                cmd = self.readline()

            # Make sure the socket is closed once we're done with it
            self.client.close()
            return
        except Exception, err:
            print err
            self.client.close()
            return

    def readline(self):
        '''
        Helper function, reads up to MAX_RECV_SIZE chars from the socket, and returns
        them as a string, without any end of line
        markers '''
        result = self.client.recv(self.server.CONFIG["MAX_RECV_SIZE"])
        if(result != None):
            result = result.strip()
        return result

    def writeline(self, text):
        '''
        Helper function, writes teh given string to the socket, with an end of
        line marker appended at the end
        '''
        self.client.send(text.strip() + '\n')

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
            else:
                self.writeline(json.dumps({
                    "type": "SERVERMSG",
                    "message": "You're already in %s" % channel
                }))
        else:
            if self.server.CONFIG.get("CHANNEL_CREATION"):
                self.server.create_channel(self, channel)
                # self.channels[channel] = self.server.channels[channel]
                self.join(channel, key)
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
            "type": "YOUNICK",
            "channel": channel,
            "message": reason
        }))

    def on_ban(self, channel):
        """
        Runs when you've been banned from a channel
        """
        self.writeline(json.dumps({
            "type": "YOUBAN",
            "channel": channel
        }))

    def on_sanick(self, new_nick):
        """
        Runs when a oper uses sanick on this client
        """
        self.writeline(
            "Your nick was changed by a server admin to %s" % new_nick)
        self.writeline(json.dumps({
            "type": "YOUSANICK",
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
            "type": "YOUSAJOIN",
            "channel": channel
        }))

    def on_sapart(self, channel):
        """
        Runs when a server admin forces you to leave a channel
        """
        del self.channels[channel]
        self.writeline(json.dumps({
            "type": "YOUSAPART",
            "channel": channel
        }))

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

    def server_announcemet(self, message):
        """
        Send a message to all clients connected to the server
        """
        if self.is_oper():
            self.server.server_announcement(message)
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("not an oper"),
                "message": "You need to be an oper to use the `announcement` command"
            }))

    def register_channel(self, chan_name):
        """
        Register a channel on the server
        """
        if chan_name in self.channels:
            self.channels[chan_name].register(self)
        else:
            self.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("invalid channel/nick"),
                "message": "You're not in %s" % chan_name
            }))

    def message_nick(self, nick, message):
        """
        Sends a message to another client on the server
        nick: nick of the client you want to message
        message: the message you want to send to that client
        """
        if nick in self.server.users.keys():
            self.server.users[nick].writeline(json.dumps({
                "type": "USERMSG",
                "nick": self.nick,
                "ip": self.ip,
                "message": message
            }))
        else:
            client.writeline(json.dumps({
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
            client.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("invalid channel/nick"),
                "message": "No channel named %s" % channel
            }))
