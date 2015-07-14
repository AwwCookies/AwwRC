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
import errorcodes


class Server:

    '''
    Server class. Opens up a socket and listens for incoming connections.
    Every time a new connection arrives, it creates a new Client thread
    object and defers the processing of the connection to it.
    '''

    def __init__(self):
        self.CONFIG = self.load_config()
        self.sock = None
        self.clients = []
        self.users = {}
        self.channels = self.load_channels()
        print self.CONFIG
        self.channels[self.CONFIG["SERVER_ADMIN_CHANNEL"]] = Channel(
            self.CONFIG["SERVER_ADMIN_CHANNEL"], {"O": True}, "Server Admin Channel")

    def rehash(self, client):
        """
        Reloads the config and channels
        """
        if client.is_oper():
            self.channels = self.load_channels()
            self.CONFIG = self.load_config()

    def load_config(p="./config.json"):
        config = {}
        tconfig = json.loads(open("./config.json", 'r').read())
        config = {
            "PORT": tconfig["PORT"] if tconfig.get("PORT") else 5050,
            "TIMEOUT": tconfig["TIMEOUT"] if tconfig.get("TIMEOUT") else 0.5,
            "ADDRESS": tconfig["ADDRESS"] if tconfig.get("ADDRESS") else "127.0.0.1",
            "MAX_NICK_LENGTH": int(tconfig["MAX_NICK_LENGTH"]) if tconfig.get("MAX_NICK_LENGTH") else 12,
            "CHANNEL_CREATION": tconfig["CHANNEL_CREATION"] if tconfig.get("CHANNEL_CREATION") else False,
            "MAX_RECV_SIZE": int(tconfig["MAX_RECV_SIZE"]) if tconfig.get("MAX_RECV_SIZE") else 1024,
            "SERVER_ADMIN_CHANNEL": tconfig["SERVER_ADMIN_CHANNEL"] if tconfig.get("SERVER_ADMIN_CHANNEL") else "&ADMIN",
            "SERVER_MAX_USERS": int(tconfig["SERVER_MAX_USERS"]) if tconfig.get("SERVER_MAX_USERS") else 100,
        }
        return config

    def load_channels(self):
        """
        Looks in the channel folder for channel json files
        and creates channels based of that information
        """
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
        if len(self.clients) > self.CONFIG["SERVER_MAX_USERS"]:
            return False
        banlist = [ip.strip() for ip in open("./banlist.txt").readlines()]
        # if this client is banned tell them to GTFO and disconnect them
        if client.ip in banlist:
            self.writeline("%s is banned." % (client.ip))
            client.writeline(
                json.dumps({"type": "YOURSERVERBAN", "ip": client.ip}))
            client.quit()
            return False
        else:
            self.users[client.nick] = client
            self.writeline("%s is registered as %s" % (client.ip, client.nick))
            if os.path.exists("motd.txt"):
                for line in open("motd.txt", 'r').readlines():
                    client.writeline(
                        json.dumps({"type": "SERVERMOTD", "message": line}))
            client.writeline(
                json.dumps({"type": "SERVERCONFIG", "config": json.dumps(self.CONFIG)}))
            client.writeline(
                json.dumps({"type": "SERVERUSERS", "amount": len(self.clients)}))
            return True

    def register_account(self, client, email, hashedpw):
        if os.path.exists("accounts/%s.json" % client.nick):
            client.writeline("This nick is already registered.")
            client.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("nick already registered"),
                "message": "Nick is already registered"
            }))
        else:
            with open("accounts/%s.json" % client.nick, 'w') as f:
                f.write(json.dumps({
                    "email": email,
                    "password": hashedpw,
                    "uuid": client.nick + ':' + str(uuid.uuid4()),
                    "time_registered": int(time.time())
                }, sort_keys=True, indent=4, separators=(',', ': ')))
            self.writeline(
                "%s created a new account [%s]" % (client.ip, client.nick))
            client.writeline(json.dumps({
                "type": "SERVERMSG",
                "message": "Your nick is now registered! You can now login with `login <password>`"
            }))

    def client_login(self, client, hashedpw):
        if os.path.exists("accounts/%s.json" % client.nick):
            user = json.loads(
                open("accounts/%s.json" % client.nick, 'r').read())
            if hashedpw == user["password"]:
                client.account = user
                client.writeline(json.dumps({
                    "type": "SERVERMSG",
                    "message": "You're now logged in!"
                }))
                self.writeline("%s logged in" % client.nick)
            else:
                client.writeline("ERROR Invalid password for %s" % client.nick)
                client.writeline(json.dumps({
                    "type": "ERROR",
                    "code": errorcodes.get("invalid nick password"),
                    "message": "invalid password for %s" % client.nick
                }))
                self.writeline("%s failed to login" % client.nick)
        else:
            client.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("invalid account name"),
                "message": "account %s not found." % client.nick
            }))

    def client_message_nick(self, client, nick, message):
        if nick in self.users.keys():
            self.users[nick].writeline(json.dumps({
                "type": "USERMSG",
                "nick": client.nick,
                "ip": client.ip,
                "message": message
            }))
        else:
            client.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("invalid channel/nick"),
                "message": "%s isn't on the server" % client.nick
            }))

    def client_message_channel(self, client, channel, message):
        if channel in self.channels.keys():
            self.channels[channel].on_message(client, message)
        else:
            client.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("invalid channel/nick"),
                "message": "No channel named %s" % channel
            }))

    def oper(self, client, hashedpw):
        self.writeline("%s used the oper command" % client.ip)
        for oper in [op.strip() for op in open("./opers.txt", "r").readlines()]:
            if client.ip + '|' + hashedpw == oper:
                return True


    def server_announcement(self, message):
        """
        Send a message to all clients connected to the server
        """
        for client in self.clients:
            client.writeline(json.dumps({
                "type": "SERVERMSG",
                "message": "ANNOUNCEMENT: " + message
            }))

    def client_whois(self, client, nick):
        if self.users.get(nick):
            self.users[nick].on_whois(client)
            self.writeline("%s used whois on %s" % (client.nick, nick))
        else:
            client.writeline(json.dumps({
                "type": "ERROR",
                "code": errorcodes.get("invalid channel/nick"),
                "message": "%s isn't on the server" % client.nick
            }))

    def create_channel(self, client, name, flags={}, topic=""):
        if name not in self.channels.keys():
            self.channels[name] = Channel(name, flags, topic)
            self.writeline("%s created a new channel %s" % (client.nick, name))
        else:
            client.writeline(json.dumps({
                "type": "SERVERMSG",
                "message": "Channel %s is already created" % name
            }))

    def ban_ip(self, ip):
        """
        Ban a ip from joining the server
        """
        with open("banlist.txt", 'a') as f:
            f.write(ip + "\n")
        self.writeline("Added %s to banlist.txt" % ip)

    def set_motd(self, motd):
        pass

    def writeline(self, message):
        print(message)
        self.channels[self.CONFIG["SERVER_ADMIN_CHANNEL"]].writeline(json.dumps({
            "type": "CHANMSG",
            "channel": self.CONFIG["SERVER_ADMIN_CHANNEL"],
            "nick": "SERVER",
            "message": message
        }))

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
                    self.sock.settimeout(0.5)  # .5 second timeout
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
                        self.clients.append(client)
                        client.start()
                    # Go over the list of threads, remove those that have finished
                    # (their run method has finished running) and wait for them
                    # to fully finish
                    self.users = {}
                    for client in self.clients:
                        if not client.isAlive():
                            self.clients.remove(client)
                        else:
                            self.users[client.nick] = client
                except Exception, err:
                    print("Client error: %s" % err)

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
        for client in self.clients:
            client.join(1.0)
        # Close the socket once we're done with it
        self.sock.close()
