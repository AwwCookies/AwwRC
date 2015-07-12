import sys
import socket
import threading
import time
import json
import glob
import os
import uuid

# Local Imports
from client import Client
from channel import Channel


class Server:
    '''
    Server class. Opens up a socket and listens for incoming connections.
    Every time a new connection arrives, it creates a new Client thread
    object and defers the processing of the connection to it.
    '''
    def __init__(self):
        self.sock = None
        self.thread_list = []
        self.users = {}
        self.channels = self.load_channels()
        self.CONFIG = self.load_config()
        print self.CONFIG

    def load_config(p="./config.json"):
        config = {}
        tconfig = json.loads(open("./config.json", 'r').read())
        config = {
            "PORT": tconfig["PORT"] if tconfig.get("PORT") else 5050,
            "TIMEOUT": tconfig["TIMEOUT"] if tconfig.get("TIMEOUT") else 0.5,
            "ADDRESS": tconfig["ADDRESS"] if tconfig.get("ADDRESS") else "127.0.0.1",
            "MAX_NICK_LENGTH": tconfig["MAX_NICK_LENGTH"] if tconfig.get("MAX_NICK_LENGTH") else 12,
            "CHANNEL_CREATION": tconfig["CHANNEL_CREATION"] if tconfig.get("CHANNEL_CREATION") else False,
        }
        return config


    def load_channels(self):
        channels = {}
        for c in glob.glob("channels/*.json"):
            try:
                channel = json.loads(open(c, 'r').read())
                channels[channel["name"]] = Channel(
                    channel["name"], channel["flags"], channel["topic"],
                    channel["banlist"], channel["ops"], channel["owner"])
                print("Loaded channel %s from %s" % (channel["name"], c))
            except:
                print("Failed to load channel json %s" % c)
        return channels

    def register_client(self, client):
        banlist = [ip.strip() for ip in open("./banlist.txt").readlines()]
        if client.ip in banlist: # if this client is banned tell them to GTFO and disconnect them
            print("%s is banned." % (client.ip))
            client.writeline("You are banned. Please GTFO")
            client.quit()
            return False
        else:
            self.users[client.nick] = client
            print("%s is registered as %s" % (client.ip, client.nick))
            if os.path.exists("motd.txt"):
                for line in open("motd.txt", 'r').readlines():
                    client.writeline("MOTD " + line)
            return True

    def register_account(self, client, email, hashedpw):
        if os.path.exists("accounts/%s.json" % client.nick):
            client.writeline("This nick is already registered.")
        else:
            with open("accounts/%s.json" % client.nick, 'w') as f:
                f.write(json.dumps({"email": email, "password": hashedpw,
                    "uuid": client.nick + ':' + str(uuid.uuid4())},
                        sort_keys=True, indent=4, separators=(',', ': ')))
            print("%s created a new account [%s]" % (client.ip, client.nick))
            client.writeline("Your nick is now registered! You can now login with `login <password>`")

    def client_login(self, client, hashedpw):
        if os.path.exists("accounts/%s.json" % client.nick):
            user = json.loads(open("accounts/%s.json" % client.nick, 'r').read())
            if hashedpw == user["password"]:
                client.account = user
                client.writeline("You're now logged in!")
            else:
                client.writeline("ERROR Invalid password for %s" % client.nick)
        else:
            client.writeline("There is no account by the name %s" % client.nick)

    def client_message_nick(self, client, nick, message):
        if nick in self.users.keys():
            self.users[nick].writeline("USERMSG %s %s" % (client.nick, message))
        else:
            client.writeline("No user named: %s" % nick)


    def client_message_channel(self, client, channel, message):
        if channel in self.channels.keys():
            self.channels[channel].on_message(client, message)
        else:
            client.writeline("No channel named %s" % channel)


    def oper(self, client, hashedpw):
        print("%s used the oper command" % client.ip)
        for oper in [op.strip() for op in open("./opers.txt", "r").readlines()]:
            if client.ip + '|' + hashedpw == oper:
                return True


    def client_whois(self, client, nick):
        if self.users.get(nick):
            self.users[nick].on_whois(client)
        else:
            client.writeline("%s isn't on the server" % nick)

    def client_join_chanel(self, client, channel, key):
        if channel in self.channels.keys():
            self.channels[channel].on_join(client, key)
            return self.channels[channel]
        else:
            if self.CONFIG.get("CHANNEL_CREATION"):
                self.create_channel(client, channel)
            else:
                client.writeline("This server does not allow the creation of channels")


    def create_channel(self, client, name, flags={}, topic=""):
        if name not in self.channels.keys():
            self.channels[name] = Channel(name, flags, topic)
            print self.channels
        else:
            client.writeline("Channel %s is already created" % name)


    def ban_ip(self, client, ip):
        """
        Ban a ip from joining the server
        """
        if client.is_oper:
            with open("banlist.txt", 'a') as f:
                f.write(ip + "\n")
            print("Added %s to banlist.txt" % ip)


    def run(self):
        '''
        Server main loop.
        Creates the server (incoming) socket, and listens on it of incoming
        connections. Once an incomming connection is deteceted, creates a
        Client to handle it, and goes back to listening mode.
        '''
        all_good = False
        try_count = 0
        # Attempt to open the socket
        while not all_good:
            if try_count > 3:
                # Tried more than 3 times, without success... Maybe the port
                # is in use by another program
                sys.exit(1)
            try:  # Create the socket
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # Bind it to the interface and port we want to listen on
                self.sock.bind((self.CONFIG["ADDRESS"], self.CONFIG["PORT"]))
                # Listen for incoming connections. This server can handle up to
                # 5 simultaneous connections
                self.sock.listen(5)
                all_good = True
                break
            except socket.error, err:
                # Could not bind on the interface and port, wait for 10 seconds
                print 'Socket connection error... Waiting 10 seconds to retry.'
                del self.sock
                time.sleep(10)
                try_count += 1

        print "Server is listening for incoming connections."
        print "Try to connect through the command line, with:"
        print "telnet localhost 5050"
        print "and then type whatever you want."
        print
        print "typing 'bye' finishes the thread, but not the server ",
        print "(eg. you can quit telnet, run it again and get a different ",
        print "thread name"
        print "typing 'quit' finishes the server"

        try:
            while True:
                try:
                    self.sock.settimeout(0.5) # .5 second timeout
                    client_sock = self.sock.accept()[0]
                except socket.timeout:
                    # No connection detected, sleep for one second, then check
                    time.sleep(1)
                    continue
                # Create the Client object and let it handle the incoming
                # connection
                try:
                    client = Client(client_sock, self)
                    if self.register_client(client):
                        self.thread_list.append(client)
                        client.start()
                    # Go over the list of threads, remove those that have finished
                    # (their run method has finished running) and wait for them
                    # to fully finish
                    for client in self.thread_list:
                        if not client.isAlive():
                            self.thread_list.remove(client)
                            del self.users[client.nick]
                            thread.join()
                except:
                    print("Client error")

        except KeyboardInterrupt:
            print 'Ctrl+C pressed... Shutting Down'
            quit()
        except Exception, err:
            print 'Exception caught: %s\nClosing...' % err
            quit()
        # Clear the list of threads, giving each thread 1 second to finish
        # NOTE: There is no guarantee that the thread has finished in the
        #    given time. You should always check if the thread isAlive() after
        #    calling join() with a timeout paramenter to detect if the thread
        #    did finish in the requested time
        #
        for thread in self.thread_list:
            thread.join(1.0)
        # Close the socket once we're done with it
        self.sock.close()
