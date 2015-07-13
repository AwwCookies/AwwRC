import json


class Channel:
    """
    flags:
        n = No outside message
        k = key e.g password
        l = limit the amount of users
        O = server operators only
    """
    def __init__(self, name, flags={}, topic="", banlist=[], ops=[], owner=""):
        self.name = name
        self.flags = flags
        self.clients = []
        self.users = {}
        self.topic = topic
        self.banlist = banlist
        self.ops = ops
        self.owner = owner

    def add_client(self, client):
        self.clients.append(client)
        self.users[client.nick] = client
        self.writeline("JOIN %s %s %s has joined the channel" % (self.name, client.ip, client.nick))
        client.writeline("TOPIC %s %s" % (self.name, self.topic))
        client.writeline("USERS %s %s" % (self.name, str(' '.join([user.nick for user in self.clients]))))

    def on_join(self, client, key=None):
        """
        Runs when a client joins the channel
        Sends the client the topic
        Sends the client whos in the channel
        if the client is banned they will be unable
        to join the channel and they will recv a banned
        message from the channel
        """
        print("%s %s joined %s" % (client.nick, client.ip, self.name))
        if client.ip not in self.banlist:
            if self.flags.get('O'):
                if client.is_oper:
                    self.add_client(client)
                    return True
                else:
                    client.writeline("You must be an oper to join %s" % self.name)
            elif self.flags.get('k'): # if a key is set
                    if key == self.flags.get('k'):
                        self.add_client(client)
                        return True
                    elif key != None: # client gave a password but it was incorrect
                        client.writeline("Invalid password to join %s" % self.name)
                    else: # client did not give a password
                        client.writeline("You need a password to join  %s" % self.name)
            elif self.flags.get('l'): # Channel Limit
                print len(self.clients) > self.flags.get('l')
                if len(self.clients) > self.flags.get('l'): # excecced limit
                    client.writeline("Channel %s is full" % self.name)
                    return True
                else: # if no limit or within
                    self.add_client(client)
                    return True
        else:
            client.writeline("BANNED You are banned from this channel.")

    def on_part(self, client, message):
        """
        Runs when a client leaves the channel
        Removes the user from the channel is displays their
        part message
        """
        del self.users[client.nick]
        self.clients.remove(client)
        self.writeline("%s left the channel: %s" % (client.nick, message))

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
                client.writeline("KICK %s You kicked %s from %s: %s" % (
                    self.name, nick, self.name, reason))
            else:
                client.writeline("You are not an operator of %s" % self.name)
        else:
            client.writeline("%s isn't on the channel" % nick)

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
                self.writeline("BAN %s was banned %s from %s" % (client.nick, nick, self.name))
                self.save()
            else:
                client.writeline("You are not an operator of %s" % self.name)
        else:
            client.writeline("%s isn't on the channel" % nick)

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
                client.writeline("%s was removed from the ban list" % ip)
                self.save()
            else:
                client.writeline("%s is not in the banlist for %s" % (ip, self.name))
        else:
            client.writeline("You are not an operator of %s" % self.name)


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
            client.writeline("You are banned from %s" % self.name)
        else:
            if self.flags.get("n"): # if flag 'n' is set
                if client in self.clients:
                    self.writeline("CHANMSG %s %s %s %s" % (self.name, client.nick, client.ip, message))
                else:
                    client.writeline("%s doesn't allow outside message. Please join the channel to send a message" % self.name)
            else:
                self.writeline("CHANMSG %s %s %s %s" % (self.name, client.nick, client.ip, message))

    def writeline(self, message):
        """
        Sends a message to all users in this channel
        """
        for client in self.clients:
            client.writeline(message)

    def is_op(self, client):
        """
        Checks to see if the client is an operator
        Returns True if: client's uuid is in the channel file - Must be logged in
        Returns True if: client has the o flag
        Returns True if: client is a server admin
        """
        if client.logged_in():
            return client.account["uuid"] in self.ops or self.name + "|o" in client.flags or client.is_oper
        else:
            return client.is_oper or self.name + "|o" in client.flags

    def is_owner(self, client):
        """
        Chekcs to see if the client is an owner of the channel
        """
        if client.logged_in():
            return client.account["uuid"] in self.owner or client.is_oper
        else:
            return client.is_oper

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
            client.writeline("You are not an operator of %s" % self.name)


    def add_client_flag(self, client, nick, flag):
        """
        Adds a flag to a client
        Op/Owner only command
        client: op/owners client
        nick: nick to add flag to
        """
        if self.is_op(client):
            if nick in self.users:
                self.users[nick].flags.append(self.name + "|" + flag)
                client.writeline("You gave %s %s" % (nick, flag))
                self.writeline("CHANMODE + %s %s gave %s to %s" % (
                    self.name, client.nick, flag, nick))
            else:
                client.writeline("ERROR %s is not in %s" % (nick, self.name))
        else:
            client.writeline("You are not an operator of %s" % self.name)

    def remove_client_flag(self, client, nick, flag):
        """
        Removes a flag from a client
        Op/Owner only command
        client: op/owners client
        nick: nick to remove flag from
        """
        if is_op(client):
            if nick in self.clients:
                self.users[nick].flags.remove(self.name + "|" + flag)
                client.writeline("You removed %s's flag %s" % (nick, flag))
                self.writeline("CHANMODE - %s %s removed %s from %s" % (
                    self.name, client.nick, flag, nick))
            else:
                client.writeline("ERROR %s is not in %s" % (nick, self.name))
        else:
            client.writeline("You are not an operator of %s" % self.name)

    def set_topic(self, client, new_topic):
        """
        Sets the channel topic
        Ops/Owner only
        """
        if is_op(client):
            self.topic = new_topic
            self.writeline("TOPIC %s %s" % (self.name, self.topic))
            self.save()
        else:
            client.writeline("You're are not an operator of %s" % self.name)

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
            "owner": self.owner
        }
        with open("channels/%s.json" % self.name, 'w') as f:
            f.write(json.dumps(cvars, sort_keys=True, indent=4, separators=(',', ': ')))
