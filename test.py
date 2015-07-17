import socket
import time

clients = []

for x in xrange(10000):
    clients.append(socket.socket())

for client in clients:
    client.connect(('smile.sh', 5050))
    client.send('%s' % int(time.time()))
#    time.sleep(0.1)
#    client.send('join #chat')
#    client.send('chanmsg #chat NIGGA')

while True:
    pass
