import pygtk
import gtk
import sys
import socket
import gobject
import json


class GUIClient:

    def __init__(self):
        '''Constructor: Sets up all widgets, window, and socket'''
        self.buffers = {}
        self.current_buffer = None
        # Connection Window
        self.connectWindow = gtk.Window(gtk.WINDOW_TOPLEVEL)

        self.connectIPBox = gtk.Entry(0)
        self.connectIPBox.set_text("")
        self.connectPortBox = gtk.Entry(0)
        self.connectPortBox.set_text("")
        self.connectButton = gtk.Button("Connect")
        self.connectButton.set_sensitive(False)
        self.channel_buttons = gtk.HBox(False, 0)
        self.channel_status_button = gtk.Button("status")
        self.channel_status_button.connect('clicked', self.button_switch_buffer)
        self.channel_buttons.pack_start(self.channel_status_button)

        self.connectIPBox.show()
        self.connectPortBox.show()
        self.connectButton.show()

        self.ipLabel = gtk.Label("IP")
        self.portLabel = gtk.Label("Port")

        self.ipLabel.show()
        self.portLabel.show()

        self.connectTable = gtk.Table(2, 3)
        self.connectTable.attach(self.ipLabel, 0, 1, 0, 1)
        self.connectTable.attach(self.portLabel, 0, 1, 1, 2)
        self.connectTable.attach(self.connectIPBox, 1, 2, 0, 1)
        self.connectTable.attach(self.connectPortBox, 1, 2, 1, 2)
        self.connectTable.attach(self.connectButton, 2, 3, 0, 2)
        self.connectTable.set_focus_chain(
            (self.connectIPBox, self.connectPortBox, self.connectButton))
        self.connectTable.show()

        self.connectWindow.add(self.connectTable)
        self.connectWindow.show()

        self.connectIPBox.connect("activate", self.makeConnection)
        self.connectPortBox.connect("activate", self.makeConnection)
        self.connectButton.connect("clicked", self.makeConnection)
        self.connectWindow.connect("delete_event", self.delete_event)
        self.connectWindow.connect("destroy", self.destroy)
        self.connectIPBox.connect("changed", self.changedText)
        self.connectPortBox.connect("changed", self.changedText)

        # IRC Window
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_size_request(800, 800)
        self.window.set_title("IRC Client")

        self.scrollbox = gtk.ScrolledWindow()
        self.scrollbox.show()

        self.windowBox = gtk.VBox(False, 0)
        self.windowBox.show()
        #self.messages = gtk.VBox(False, 0)
        # self.messages.show()
        self.messages = gtk.TextView()
        self.switch_buffer("status")
        self.editBox = gtk.HBox(False, 0)
        self.editBox.show()
        self.entry = gtk.Entry(0)
        self.sendButton = gtk.Button("Send")
        self.editBox.pack_start(self.entry, True, True, 0)
        self.editBox.pack_end(self.sendButton, False, False, 0)
        self.entry.connect("activate", self.send)
        self.sendButton.connect("clicked", self.send)
        self.window.connect("delete_event", self.delete_event)
        self.window.connect("destroy", self.destroy)
        self.windowBox.pack_start(self.channel_buttons, False, False, 0)
        self.windowBox.pack_start(self.messages, True, True, 0)
        self.windowBox.pack_end(self.editBox, False, False, 0)
        self.window.add(self.windowBox)
        self.window.show_all()
        # self.window.show()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.dataBuffer = ""

    def makeConnection(self, widget, data=None):
        '''
        Takes data from IP and Port fields and attempts to make a connection to
        the server specified in these fields.
        '''
        ip = ""
        try:
            ip = socket.gethostbyname(self.connectIPBox.get_text())
        except Exception as e:
            fail = gtk.MessageDialog(None, 0, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK,
                                     "Failed to resolve host\n" + str(e))
            fail.run()
            fail.destroy()
            return
        port = int(self.connectPortBox.get_text())
        self.connectTo((ip, port))

    def changedText(self, widget, data=None):
        sensitive = len(self.connectIPBox.get_text()) > 0 and \
            len(self.connectPortBox.get_text()) > 0 and \
            self.connectPortBox.get_text().isdigit() and \
            int(self.connectPortBox.get_text()) > 0
        self.connectButton.set_sensitive(sensitive)

    def connectTo(self, addr):
        try:
            self.socket.settimeout(1)
            self.socket.connect(addr)
        except Exception as e:
            fail = gtk.MessageDialog(None, 0, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK,
                                     "Failed to connect\n" + str(e))
            fail.run()
            fail.destroy()
            return
        self.connectWindow.hide()
        self.window.show()
        self.entry.grab_focus()
        self.socket.setblocking(False)
        gobject.io_add_watch(self.socket.fileno(), gobject.IO_IN, self.read)
        gobject.io_add_watch(
            self.socket.fileno(), gobject.IO_ERR, self.disconnect)
        gobject.io_add_watch(
            self.socket.fileno(), gobject.IO_HUP, self.disconnect)

    def disconnect(self, source=None, condition=None):
        dia = gtk.MessageDialog(None, 0, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK,
                                "Lost connection to server")
        dia.run()
        dia.destroy()
        sys.exit(0)

    def send(self, widget, data=None):
        message = self.entry.get_text()
        self.entry.set_text("")
        self.entry.grab_focus()
        if message.startswith("/"):
            args = message.split()
            if args[0] == "/win":
                self.switch_buffer(args[1])
            elif args[0] == "/raw":
                self.socket.send(' '.join(message.split()[1:]) + "\n")
            elif args[0] == "/join":
                if len(args) > 2:
                    self.socket.send("chanjoin %s %s" % (args[1], args[2]))
                else:
                    self.socket.send("chanjoin %s" % args[1])
        else:
            args = message.split()
            self.socket.send("chanmsg %s %s" %
                             (self.current_buffer, ' '.join(args[2:])))
        # else:
        # message.strip()
        #   self.socket.sendall(message + "\n")

    def read(self, source, condition):
        data = self.socket.recv(256)
        if not data:
            self.disconnect()
        self.dataBuffer += data

        message = self.getNextMessage()
        while message:
            if not message.strip() == "":
                for msg in message.split('\n'):
                    msg = json.loads(msg)
                    if msg["type"] == "YOUJOIN":
                        self.button = gtk.Button(msg["channel"])
                        self.button.connect("clicked", self.button_switch_buffer)
                        self.channel_buttons.pack_start(self.button)
                        self.channel_buttons.show_all()
                    if msg["type"] == "CHANMSG":
                        self.add_message_buffer(msg["channel"],
                        "<%s> | %s" % (msg["nick"], msg["message"]))
                    else:
                        self.add_message(message)
                    message = self.getNextMessage()
        return True

    def getNextMessage(self):
        msg = ""
        if '\n' in self.dataBuffer:
            index = self.dataBuffer.find('\n')
            msg = self.dataBuffer[:index + 1]
            self.dataBuffer = self.dataBuffer[index + 1:]
        return msg.strip()

    def create_buffer(self, buff_name):
        if buff_name not in self.buffers:
            self.buffers[buff_name] = gtk.TextBuffer()

    def button_switch_buffer(self, wig):
        self.switch_buffer(wig.get_label())

    def switch_buffer(self, buff_name):
        if buff_name in self.buffers:
            self.messages.set_buffer(self.buffers[buff_name])
            self.current_buffer = buff_name
        else:
            self.create_buffer(buff_name)
            self.switch_buffer(buff_name)

    def add_message_buffer(self, buff_name, message):
        self.create_buffer(buff_name)
        start_iter = self.buffers[buff_name].get_start_iter()
        end_iter = self.buffers[buff_name].get_end_iter()
        self.buffers[buff_name].set_text(
            self.buffers[buff_name].get_text(start_iter, end_iter, True) + message + "\n")

    def add_message(self, message):
        if (not message):
            return
    #   tbox = gtk.HBox(False, 0)
    #   tbox.set_border_width(5)
    #   tbox.show()
      #
    #   text = gtk.Label(message)
    #   text.set_line_wrap(True)
    #   tbox.pack_start(text, False, True, 0)
    #   text.show()
      #
    #   self.messages.pack_start(tbox, False, True, 0)
        start_iter = self.messages.get_buffer().get_start_iter()
        end_iter = self.messages.get_buffer().get_end_iter()
        self.messages.get_buffer().set_text(
            self.messages.get_buffer().get_text(start_iter, end_iter, True) + message + "\n")
        adj = self.scrollbox.get_vadjustment()
        adj.set_value(adj.get_upper())

    def delete_event(self, widget, event, data=None):
        return False

    def destroy(self, widget, data=None):
        # TODO: Cleanup
        gtk.main_quit()

    def main(self):
        gtk.main()

if __name__ == "__main__":
    base = GUIClient()
    base.main()
