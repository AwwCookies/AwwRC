import sys
import socket
import threading
import time
import json
import hashlib
import uuid


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
        self.ip = self.client.getpeername()[0] # Get the clients IP address
        self.nick = uuid.uuid4()
        self.is_oper = False
        self.channels = {}
        self.account = None
        self.flags = []

    def set_nick(self, client, nick):
        """
        Sets the clients nick
        """
        #TODO: add nick restrictions
        if len(nick) <= self.server.CONFIG["MAX_NICK_LENGTH"]:
            if nick not in self.server.users.keys():
                old_nick = client.nick
                client.nick = nick
                self.server.users[client.nick] = self
                self.writeline("You are now known as %s" % nick)
                print("%s is now known as %s" % (old_nick, nick))
            else:
                client.writeline("%s is already in use. Please choose a new nick." % nick)
                self.set_nick(client, client.readline())
        else:
            client.writeline("Your nick is too long. Please choose nick with less than %i chars" %
                self.server.CONFIG["MAX_NICK_LENGTH"])
            self.set_nick(client, client.readline())

    def logged_in(self):
        return self.account

    def run(self):
        '''
        Thread's main loop. Once this function returns, the thread is finished
        and dies.
        '''
        # client needs to change their nick
        self.writeline("Please pick a nick")
        self.set_nick(self, self.readline())
        # Need to declare QUIT as global, since the method can change it
        cmd = self.readline()
        # Read data from the socket and process it
        while True:
            args = cmd.split(" ")
            if 'quit' == cmd:
                self.writeline('Ok, bye')
                return
            elif 'nick' == cmd:
                self.writeline("Your nick is: %s" % self.nick)
            elif 'register' == args[0]:
                self.server.register_account(self, args[1],
                    hashlib.md5(' '.join(args[2:])).hexdigest())
            elif 'login' == args[0]:
                self.server.client_login(self, hashlib.md5(' '.join(args[1:])).hexdigest())
            elif 'kick' == args[0]:
                if args[1] in self.channels:
                    self.channels[args[1]].kick_user(self, args[2], ' '.join(args[3:]))
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
            elif 'msg' == args[0]:
                self.message_nick(args[1], ' '.join(args[2:]))
            elif 'chanmsg' ==  args[0]:
                self.message_channel(args[1], ' '.join(args[2:]))
            elif 'channels' == args[0]:
                self.writeline("You're in: %s" % self.channels.keys())
            elif 'oper?' == args[0]:
                self.writeline("Oper: %s" % str(self.is_oper))
            elif 'whois' == args[0]:
                self.server.client_whois(self, args[1])
            elif 'join' == args[0]:
                self.join(args[1], ' '.join(args[2:]) if len(args) > 2 else None)
            elif 'part' == args[0]:
                self.part(args[1], ' '.join(args[2:]) if len(args) > 2 else None)
            elif 'flags' == args[0]:
                self.writeline("FLAGS %s %s" % (self.nick, self.flags))
            #NOTE: Oper Commands
            elif 'oper' == args[0]:
                self.oper(hashlib.md5(' '.join(args[1:])).hexdigest())
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
                        self.channels[chan].add_client_flag(self, nick, flag)
                    elif args[1] == "remove":
                        self.channels[chan].remove_client_flag(self, nick, flag)
                else:
                    self.writeline("You are not in %s" % chan)
            elif 'flags' == args[0]:
                self.writeline("FLAGS %s %s" % (self.nick, self.flags))
            elif 'ban' == args[0]:
                self.ban_ip(args[1])
            else:
                self.writeline("%s: invalid command" % args[0])

            cmd = self.readline()

        # Make sure the socket is closed once we're done with it
        self.client.close()
        return

    def readline(self):
        '''
        Helper function, reads up to MAX_RECV_SIZE chars from the socket, and returns
        them as a string, all letters in lowercase, and without any end of line
        markers '''
        result = self.client.recv(self.server.CONFIG["MAX_RECV_SIZE"])
        if(result != None):
            result = result.strip().lower()
        return result

    def writeline(self, text):
        '''
        Helper function, writes teh given string to the socket, with an end of
        line marker appended at the end
        '''
        self.client.send(text.strip() + '\n')

    def message_nick(self, nick, message):
        """
        Sends a message to a specific user on the server
        """
        self.server.client_message_nick(self, nick, message)

    def message_channel(self, channel, message):
        """
        Sends a message to a channel on the server
        """
        self.server.client_message_channel(self, channel, message)

    def oper(self, hashedpw):
        """
        Turns the client into an oper (Server Operator)
        """
        if self.server.oper(self, hashedpw):
            self.is_oper = True
            self.writeline("You are now an oper!")
            print("%s oppered" % self.nick)
        else:
            self.writeline("Invalid credentials")


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
                self.writeline("You're already in %s" % channel)
        else:
            if self.server.CONFIG.get("CHANNEL_CREATION"):
                self.server.create_channel(self, channel)
                self.channels[channel] = self.server.channels[channel]
            else:
                self.writeline("This server does not allow the creation of channels")

    def part(self, channel, message="bye"):
        """
        Make the client leave the channel
        """
        if channel in self.channels:
            self.channels[channel].on_part(self, message)
            del self.channels[channel]
            self.writeline("You left %s (%s)" % (channel, message))
        else:
            self.writeline("You are not in %s" % channel)

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
        self.writeline("KILLED %s" % message)
        self.quit()

    def on_kick(self, channel, reason):
        """
        Runs when you've been kicked from a channel
        """
        del self.channels[channel.name]
        self.writeline("YOURKICK You've been kicked from %s: %s" % (channel.name, reason))

    def on_ban(self, channel):
        """
        Runs when you've been banned from a channel
        """
        self.writeline("BAN %s you were banned in %s" % (channel.name, channel.name))

    def on_sanick(self, new_nick):
        """
        Runs when a oper uses sanick on this client
        """
        self.writeline("Your nick was changed by a server admin to %s" % new_nick)

    def on_whois(self, client):
        """
        Runs when a user uses the whois command on this client
        """
        client.writeline("WHOIS %s Nick: %s" % (self.nick, self.nick))
        client.writeline("WHOIS %s IP: %s" % (self.nick, self.ip))
        client.writeline("WHOIS %s Oper: %s" % (self.nick, self.is_oper))
        client.writeline("WHOIS %s Logged In: %s" % (self.nick, bool(self.logged_in())))
        if self.logged_in():
            client.writeline("WHOIS %s Account UUID: %s" % (self.nick, self.account["uuid"]))

    def on_sajoin(self, channel):
        """
        Runs when a server admin forces you into a channel
        """
        self.channels[channel] = self.server.channels[channel]
        self.writeline("YOUSAJOIN you were forced to join %s" % channel)

    def on_sapart(self, channel):
        """
        Runs when a server admin forces you to leave a channel
        """
        del self.channels[channel]
        self.writeline("YOUSAPART you were forced to leave %s" % channel)

    ##### Oper Commands #####
    def kill(self, nick):
        """
        Disconnects a user from the server
        Kinda like a channel kick but from the server
        """
        if self.is_oper:
            if nick in self.server.users.keys():
                self.server.users[nick].on_kill("You were killed.")
                self.writeline("You killed %s" % nick)
                print("%s killed %s" % (self.nick, nick))
            else:
                self.writeline("%s isn't on the server." % nick)
        else:
            self.writeline("ERROR You need to be an oper to use this command")

    def sanick(self, nick, new_nick):
        """
        Force a user to change their nick
        """
        if self.is_oper:
            if self.server.users.get(nick):
                self.server.users[nick].nick = new_nick
                self.server.users[nick].on_sanick(new_nick)
                self.server.users[new_nick] = self.server.users[nick]
                self.writeline("You changed %s nick to %s" % (nick, new_nick))
                print("%s changed %s's nick to %s" % (self.nick, nick, new_nick))
        else:
            self.writeline("ERROR You need to be an oper to use this command")

    def sajoin(self, nick, channel):
        """
        Force a user to join a channel
        this will bypass all restrictions
        """
        if self.is_oper:
            if channel in self.server.channels:
                if nick in self.server.users:
                    self.server.channels[channel].add_client(self.server.users[nick])
                    self.server.users[nick].on_sajoin(channel)
                    self.writeline("%s was forced to join %s" % (nick, channel))
                else:
                    self.writeline("%s isn't on the server" % nick)
            else:
                self.writeline("%s doesn't exist" % channel)
        else:
            self.writeline("ERROR You need to be an oper to use this command")

    def sapart(self, nick, channel):
        """
        Force a user to leave (part) a channel
        """
        if self.is_oper:
            if nick in self.server.users:
                if channel in self.server.channels:
                    self.server.channels[channel].on_part(self.server.users[nick], "sapart")
                    self.server.users[nick].on_sapart(channel)
                    self.writeline("You forced %s to leave %s" % (nick, channel))
                else:
                    self.writeline("%s doesn't exist" % channel)
            else:
                self.writeline("%s isn't on the server" % nick)
        else:
            self.writeline("ERROR You need to be an oper to use this command")

    def ban_ip(self, ip):
        """
        Adds an ip to the banlist.txt
        """
        if self.is_oper:
            self.server.ban_ip(self, ip)
            self.writeline("Banned %s from the server" % ip)
        else:
            self.writeline("ERROR You need to be an oper to use this command")
