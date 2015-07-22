import socket
import json

CONFIG = {
    "nick": "cookie",
    "oper_pass": "",
    "address": "127.0.0.1",
    "port": 5050
}

sock = socket.socket()
sock.connect((CONFIG["address"], CONFIG["port"]))
sock.send(CONFIG["nick"])
while buffer:
    servmsg = sock.recv(1024)
    for msg in servmsg.split("\n"):
        if not msg.strip() == "":
            data = json.loads(msg)
            if data["type"] == "USERMSG":
                sock.send("usermsg %s Hello, World" % data["nick"])
            else:
                print data
