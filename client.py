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
                client.nick = nick
                self.server.users[client.nick] = self
            else:
                client.writeline("%s is already in use. Please choose a new nick.")
                self.set_nick(client, client.readline())
        else:
            client.writeline("Your nick is too long. Please choose nick with less than %i chars")
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
        done = False
        cmd = self.readline()
        # Read data from the socket and process it
        while not done:
            args = cmd.split(" ")
            if 'quit' == cmd:
                self.writeline('Ok, bye')
                done = True
            elif 'nick' == cmd:
                self.writeline("Your nick is: %s" % self.nick)
            elif 'register' == args[0]:
                self.server.register_account(self, args[1],
                    hashlib.md5(' '.join(args[2:])).hexdigest())
            elif 'login' == args[0]:
                self.server.client_login(self, hashlib.md5(' '.join(args[1:])).hexdigest())
            elif 'msg' == args[0]:
                self.message_nick(args[1], ' '.join(args[2:]))
            elif 'chanmsg' ==  args[0]:
                self.message_channel(args[1], ' '.join(args[2:]))
            elif 'oper?' == args[0]:
                self.writeline("Oper: %s" % str(self.is_oper))
            elif 'join' == args[0]:
                chan = self.join(args[1], ' '.join(args[2:]) if len(args) > 2 else None)
                if chan:
                    self.channels[chan.name] = chan
            #NOTE: Oper Commands
            elif 'oper' == args[0]:
                self.oper(hashlib.md5(' '.join(args[1:])).hexdigest())
            elif 'kill' == args[0]:
                self.kill(args[1])
            elif 'chanflag' == args[0]:
                chan = args[1]
                nick = args[2]
                flag = args[3]
                if chan in self.channels.keys():
                    self.channels[chan].add_client_flag(self, nick, flag)
                else:
                    self.writeline("You are not in %s" % chan)

            elif 'flags' == args[0]:
                self.writeline("FLAGS %s %s" % (self.nick, self.flags))

            else:
                self.writeline("%s: invalid command" % args[0])

            cmd = self.readline()

        # Make sure the socket is closed once we're done with it
        self.client.close()
        return

    def readline(self):
        '''
        Helper function, reads up to 1024 chars from the socket, and returns
        them as a string, all letters in lowercase, and without any end of line
        markers '''
        result = self.client.recv(1024)
        if(None != result):
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
        else:
            self.writeline("Invalid credentials")

    def join(self, channel, key=None):
        """
        Joins the client to a channel
        """
        return self.server.client_join_chanel(self, channel, key)

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

    ##### Oper Commands #####
    def kill(self, nick):
        """
        Disconnects a user from the server
        Kinda like a channel kick but from the server
        """
        if self.is_oper:
            if nick in self.server.users.keys():
                self.server.users[nick].on_kill("You were killed.")
            else:
                self.writeline("%s isn't on the server." % nick)
        else:
            self.writeline("ERROR You need to be an oper to use this command")
