import socket
import json

from faker import Faker
fake = Faker()

for x in xrange(10000):
    CONFIG = {
        "nick": fake.first_name(),
        "oper_pass": "",
        "address": "127.0.0.1",
        "port": 5050
    }

    sock = socket.socket()
    sock.connect((CONFIG["address"], CONFIG["port"]))
    sock.send(CONFIG["nick"])
    servmsg = sock.recv(1024)
    sock.send("register %s %s" % (fake.password(), fake.email())
    sock.close()
