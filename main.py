import sys
import socket
import threading
import time
import json

from server import Server

if __name__ == "__main__":
    server = Server()
    server.run()

    print "Terminated"
