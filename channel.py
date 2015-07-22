import json
import errorcodes

from collections import defaultdict

class Channel:
    """
    flags:
        n = No outside message
        k = Key e.g password
        l = Limit the amount of users
        O = server operators only
        F = Redirects users to another channel
        p = Prevents the channel from showing in the public list
        G = Enabled badword list
        P = Playback: sends the last x lines to a new client
        B = No bots: pervents clients with the `B` flag from joining
    """
    def __init__(self, server, name, flags={}, topic="", banlist=[], ops=[], owner="", badwords=[]):
        self.server = server
        self.name = name
        self.flags = flags
        self.clients = []
        self.users = {}
        self.user_flags = defaultdict(list)
        self.topic = topic[0:self.server.CONFIG["CHAN_TOPIC_LIMIT"]]
        self.banlist = banlist
        self.ops = ops
        self.owner = owner
        self.badwords = badwords
        self.messages = []

    def add_client(self, client):
        self.clients.append(client)
        self.users[client.nick] = client
        self.writeline(json.dumps({
            "type": "CHANJOIN",
            "nick": client.nick,
            "ip": client.ip,
            "channel": self.name
        }))
        client.writeline(json.dumps({
            "type": "CHANTOPIC",
            "channel": self.name,
            "topic": self.topic
        }))
        client.writeline(json.dumps({
            "type": "CHANUSERS",
            "channel": self.name,
            "userlist": self.users.keys()
        }))
        if self.flags.get("P"): # if playback is enabled
            self.playback(client, amount=self.flags.get("P"))

    def playback(self, client, amount=10):
        """
        Send the last x lines to clinet
        """
        for msg in self.messages[-abs(amount):]:
            client.writeline(msg)

    def on_join(self, client, key=None):
        """
        Runs when a client joins the channel
        Sends the client the topic
        Sends the client whos in the channel
        if the client is banned they will be unable
        to join the channel and they will recv a banned
        message from the channel
        """

        if self.flags.get("F"): # If the forward flag is set
            client.join(self.flags["F"])
            return False

        if self.flags.get("B"): # no bots
            client.writeline(json.dumps({
                "type": "SERVERMSG",
                "message": "%s doesn't allow bots" % self.name
            }))

        print("%s %s joined %s" % (client.nick, client.ip, self.name))
        if client.ip not in self.banlist:
            if self.flags.get('O'):
                if client.is_oper():
                    self.add_client(client)
                    return True
                else:
                    client.writeline(json.dumps({
                        "type": "CHANERROR",
                        "channel": self.name,
                        "message": "not an oper"
                    }))
            elif self.flags.get('k'): # if a key is set
                    if key == self.flags.get('k'):
                        self.add_client(client)
                        return True
                    elif key != None: # client gave a password but it was incorrect
                        client.writeline(json.dumps({
                            "type": "CHANERROR",
                            "channel": self.name,
                            "message": "invalid password"
                        }))
                    else: # client did not give a password
                        client.writeline(json.dumps({
                            "type": "CHANERROR",
                            "channel": self.name,
                            "message": "password protected channel"
                        }))
            elif self.flags.get('l'): # Channel Limit
                print len(self.clients) > self.flags.get('l')
                if len(self.clients) > self.flags.get('l'): # excecced limit
                    client.writeline(json.dumps({
                        "type": "CHANERROR",
                        "channel": self.name,
                        "message": "channel full"
                    }))
                    return True
                else: # if no limit or within
                    self.add_client(client)
                    return True
            else:
                self.add_client(client)
                return True
        else:
            client.writeline(json.dumps({
                "type": "YOUCHANBANNED",
                "channel": self.name
            }))

    def on_part(self, client, message):
        """
        Runs when a client leaves the channel
        Removes the user from the channel is displays their
        part message
        """
        del self.users[client.nick]
        self.clients.remove(client)
        self.writeline(json.dumps({
            "type": "CHANPART",
            "channel": self.name,
            "nick": client.nick,
            "ip": client.ip,
            "message": message
        }))

    def on_quit(self, client):
        """
        Runs when a client quits the server
        Currently does nothing
        """
        pass

    def kick_user(self, client, nick, reason):
        """
        Removes a user from the channel
        client: operator that is kicking
        nick: user to be kicked
        reason: reason for the kick
        """
        if nick in self.users.keys():
            if self.is_op(client):
                self.users[nick].on_kick(self, reason)
                self.clients.remove(self.users[nick])
                del self.users[nick]
                self.writeline(json.dumps({
                    "type": "CHANKICK",
                    "channel": self.name,
                    "nick": nick,
                    "message": reason
                }))
            else:
                client.writeline(json.dumps({
                    "type": "CHANERROR",
                    "channel": self.name,
                    "message": "not an operator"
                }))
        else:
            client.writeline(json.dumps({
                "type": "CHANERROR",
                "channel": self.name,
                "message": "nick not on channel"
            }))

    def ban_user(self, client, nick):
        """
        Ban a user from the channel
        client: operator that is banning
        nick: user to be banned
        """
        if nick in self.users:
            if self.is_op(client):
                self.users[nick].on_ban(self)
                self.banlist.append(self.users[nick].ip)
                self.writeline(json.dumps({
                    "type": "CHANBAN",
                    "channel": self.name,
                    "nick": nick
                }))
                self.save()
            else:
                client.writeline(json.dumps({
                    "type": "CHANERROR",
                    "channel": self.name,
                    "message": "not an operator"
                }))
        else:
            client.writeline(json.dumps({
                "type": "CHANERROR",
                "channel": self.name,
                "message": "nick not on channel"
            }))

    def unban_ip(self, client, ip):
        """
        Unbans a user from the channel
        client: operator that is unbanning
        ip: ip to be unbanned
        """
        if self.is_op(client):
            if ip in self.banlist:
                self.banlist.remove(ip)
                self.writeline("UNBAN %s was unbanned from %s" % (ip, self.name))
                self.writeline(json.dumps({
                    "type": "CHANUNBAN",
                    "channel": self.name,
                    "ip": ip
                }))
                self.save()
            else:
                client.writeline(json.dumps({
                    "type": "CHANERROR",
                    "channel": self.name,
                    "message": "nick not in ban list"
                }))
        else:
            client.writeline(json.dumps({
                "type": "CHANERROR",
                "channel": self.name,
                "message": "not an operator"
            }))


    def on_message(self, client, message):
        """
        Runs when a user sends a message to the channel
        Checks to see if the client is banned
        if the user is banned their message will not be sent
        if the channel has the flag 'n' it will block all outside
        messages from the channel otherwise it will send the clients
        message to everyone in the channel
        """
        if client.ip in self.banlist: # if the user is banned
            client.writeline(json.dumps({
                "type": "YOUCHANBANNED",
                "channel": self.name,
                "message": "You are banned from %s" % self.name
            }))
        elif self.flags.get('G'): # if badwords enabled
            badword = False
            for bw in self.badwords:
                print bw
                if bw in message:
                    badword = True
            if badword:
                client.writeline(json.dumps({
                    "type": "CHANERROR",
                    "channel": self.name,
                    "message": "You said a bad word. '%s'" % bw
                }))
            else:
                self.writeline(json.dumps({
                    "type": "CHANMSG",
                    "channel": self.name,
                    "nick": client.nick,
                    "ip": client.ip,
                    "message": message
                }))
                if self.flags.get("P"):
                    self.messages.append(json.dumps({
                        "type": "CHANMSG",
                        "channel": self.name,
                        "nick": client.nick,
                        "ip": client.ip,
                        "message": message
                    }))
        else:
            if self.flags.get("n"): # if flag 'n' is set
                if client in self.clients:
                    self.writeline(json.dumps({
                        "type": "CHANMSG",
                        "channel": self.name,
                        "nick": client.nick,
                        "ip": client.ip,
                        "message": message
                    }))
                    if self.flags.get("P"):
                        self.messages.append(json.dumps({
                            "type": "CHANMSG",
                            "channel": self.name,
                            "nick": client.nick,
                            "ip": client.ip,
                            "message": message
                        }))
                else:
                    client.writeline(json.dumps({
                        "type": "CHANERROR",
                        "channel": self.name,
                        "message": "no outside messages"
                    }))
            else:
                self.writeline(json.dumps({
                    "type": "CHANMSG",
                    "channel": self.name,
                    "nick": client.nick,
                    "ip": client.ip,
                    "message": message
                }))
                if self.flags.get("P"):
                    self.messages.append(json.dumps({
                        "type": "CHANMSG",
                        "channel": self.name,
                        "nick": client.nick,
                        "ip": client.ip,
                        "message": message
                    }))

    def writeline(self, message):
        """
        Sends a message to all users in this channel
        """
        for client in self.clients:
            try:
                client.writeline(message)
            except:
                self.on_part(client, "error")
                client.quit()

    def is_op(self, client):
        """
        Checks to see if the client is an operator
        Returns True if: client's uuid is in the channel file - Must be logged in
        Returns True if: client has the o flag
        Returns True if: client is a server admin/oper
        """
        if client.logged_in():
            return client.account["uuid"] in self.ops or "o" in self.user_flags[client.nick] or client.is_oper()
        else:
            return client.is_oper() or "o" in self.user_flags[client.nick]

    def is_owner(self, client):
        """
        Chekcs to see if the client is an owner of the channel
        """
        if client.logged_in():
            return client.account["uuid"] in self.owner or client.is_oper()
        else:
            return client.is_oper()

    def add_op(self, client, users_uuid):
        """
        Add an op to the channel
        Owner only command
        client: Owners client
        nick: the nick of the user you want to make op
              they must have an account with the server
        """
        if self.is_owner(client):
            self.ops.append(users_uuid)
            self.save()
        else:
            client.writeline(json.dumps({
                "type": "CHANERROR",
                "channel": self.name,
                "message": "not an operator"
            }))


    def add_client_flag(self, client, nick, flag):
        """
        Adds a flag to a client
        Op/Owner only command
        client: op/owners client
        nick: nick to add flag to
        """
        if self.is_op(client):
            if nick in self.users:
                # self.users[nick].flags.append(self.name + "|" + flag)
                self.user_flags[nick].append(flag)
                self.writeline(json.dumps({
                    "type": "CHANFLAG",
                    "channel": self.name,
                    "nick": nick,
                    "operator": client.nick,
                    "flag": "+%s" % flag
                }))
            else:
                client.writeline(json.dumps({
                    "type": "CHANERROR",
                    "channel": self.name,
                    "message": "nick not on channel"
                }))
        else:
            client.writeline(json.dumps({
                "type": "CHANERROR",
                "channel": self.name,
                "message": "not an operator"
            }))

    def remove_client_flag(self, client, nick, flag):
        """
        Removes a flag from a client
        Op/Owner only command
        client: op/owners client
        nick: nick to remove flag from
        """
        if self.is_op(client):
            if nick in self.clients:
                # self.users[nick].flags.remove(self.name + "|" + flag)
                if flag in self.user_flags[nick]:
                    self.user_flags[nick].remove(flag)
                    self.writeline(json.dumps({
                        "type": "CHANFLAG",
                        "channel": self.name,
                        "nick": nick,
                        "operator": client.nick,
                        "flag": "-%s" % flag
                    }))
            else:
                client.writeline(json.dumps({
                    "type": "CHANERROR",
                    "channel": self.name,
                    "message": "nick not on channel"
                }))
        else:
            client.writeline(json.dumps({
                "type": "CHANERROR",
                "channel": self.name,
                "message": "not an operator"
            }))

    def add_badword(self, client, badword):
        """
        Adds a bad word to the badword list
        """
        if self.is_op(client):
            if len(self.badwords) < self.server.CONFIG["CHAN_BADWORD_LIMIT"]:
                if not badword in self.badwords:
                    self.badwords.append(badword)
                    client.writeline(json.dumps({
                        "type": "SERVERMSG",
                        "message": "You added a badword to %s" % self.name
                    }))
                else:
                    client.writeline(json.dumps({
                        "type": "CHANERROR",
                        "channel": self.name,
                        "message": "%s is already in badword list" % ()
                    }))
            else:
                client.writeline(json.dumps({
                    "type": "CHANERROR",
                    "channel": self.name,
                    "message": "badword list full"
                }))
        else:
            client.writeline(json.dumps({
                "type": "CHANERROR",
                "channel": self.name,
                "message": "not an operator"
            }))

    def remove_badword(self, client, badword):
        """
        Removes a bad word from the badword list
        """
        if self.is_op(client):
            if badword in self.badwords:
                self.badwords.remove(badword)
                client.writeline(json.dumps({
                    "type": "SERVERMSG",
                    "message": "%s removed from %s's badword list" % (badword, self.name)
                }))
        else:
            client.writeline(json.dumps({
                "type": "CHANERROR",
                "channel": self.name,
                "message": "not an operator"
            }))

    def set_topic(self, client, new_topic):
        """
        Sets the channel topic
        Ops/Owner only
        """
        if is_op(client):
            self.topic = new_topic
            self.writeline(json.dumps({
                "type": "CHANTOPIC",
                "channel": self.name,
                "topic": self.topic
            }))
            self.save()
        else:
            client.writeline(json.dumps({
                "type": "CHANERROR",
                "channel": self.name,
                "message": "not an operator"
            }))

    def register(self, client):
        """
        Gives ownership of the channel to an account
        """
        if self.owner: # If the channel is already regsitered to someone else
            client.writeline(json.dumps({
                "type": "SEVREMSG",
                "message": "%s is already registered to %s" % (self.name, self.owner)
            }))
        else: # If the channel is not registered
            if client.logged_in():
                self.owner = client.account["uuid"]
                client.writeline(json.dumps({
                    "type": "SERVERMSG",
                    "message": "You registered %s" % self.name
                }))
                self.save()
            else:
                client.writeline(json.dumps({
                    "type": "SERVERMSG",
                    "message": "You need to be logged in to register a channel"
                }))

    def save(self):
        """
        Saves the channel vars into a json file
        """
        cvars = {
            "name": self.name,
            "topic": self.topic,
            "flags": self.flags,
            "banlist": self.banlist,
            "ops": self.ops,
            "owner": self.owner,
            "badwords": self.badwords
        }
        with open("channels/%s.json" % self.name, 'w') as f:
            f.write(json.dumps(cvars, sort_keys=True, indent=4, separators=(',', ': ')))
