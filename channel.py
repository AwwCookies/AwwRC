class Channel:
    """
    flags:
        n = No outside message
        k = key e.g password
        l = number of clients limit
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
        self.writeline("JOIN %s %s has joined the channel" % (self.name, client.nick))
        client.writeline("TOPIC %s %s" % (self.name, self.topic))
        client.writeline("USERS %s" % str(' '.join([user.nick for user in self.clients])))

    def on_join(self, client, key=None):
        """
        Runs when a client joins the channel
        Sends the client the topic
        Sends the client whos in the channel
        if the client is banned they will be unable
        to join the channel and they will recv a banned
        message from the channel
        """
        print("%s joined %s" % (client.nick, self.name))
        if client.ip not in self.banlist:
            # if self.flags.get('l'): # Channel Limit
            #     print len(self.clients) > self.flags.get('l')
            #     if len(self.clients) > self.flags.get('l'): # excecced limit
            #         client.writeline("Channel %s is full" % self.name)
            #         return
            #     else: # within limit
            #         self.add_client(client)
            # else: # if no limit
            #     self.add_client(client)

            if self.flags.get('k'): # if a key is set
                if key == self.flags.get('k'):
                    self.add_client(client)
                elif key != None: # client gave a password but it was incorrect
                    client.writeline("Invalid password to join %s" % self.name)
                else: # client did not give a password
                    client.writeline("You need a password to join  %s" % self.name)
            else: # if no key
                self.add_client(client)
        else:
            client.writeline("BANNED", "BANNED You are banned from this channel.")

    def on_part(self, client):
        """
        Runs when a client leaves the channel
        Currently does nothing
        """
        pass

    def on_quit(self, client):
        """
        Runs when a client quits the server
        Currently does nothing
        """
        pass

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
            if self.flags["n"]: # if flag 'n' is set
                if client in self.clients:
                    self.writeline("CHANMSG %s %s %s" % (self.name, client.nick, message))
                else:
                    client.writeline("%s doesn't allow outside message. Please join the channel to send a message" % self.name)
            else:
                self.writeline("CHANMSG %s %s %s" % (self.name, client.nick, message))

    def writeline(self, message):
        """
        Sends a message to all users in this channel
        """
        for client in self.clients:
            client.writeline(message)

    def is_op(self, client):
        """
        Checks to see if the client is an operator
        """
        if client.logged_in():
            return client.account["uuid"] in self.ops or self.name + "|o" in client.flags

    def is_owner(self, client):
        """
        Chekcs to see if the client is an owner of the channel
        """
        if client.logged_in():
            return client.account["uuid"] in self.owner

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
        with open("channels/%s.json", 'w') as f:
            f.write(json.dumps(cvars, sort_keys=True, indent=4, separators=(',', ': ')))
