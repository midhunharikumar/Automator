from sshtunnel import SSHTunnelForwarder
import logging
import time
import pync
import subprocess
import threading
import rumps


import signal
from contextlib import contextmanager
rumps.debug_mode(True)


@contextmanager
def timeout(time):
    # Register a function to raise a TimeoutError on the signal.
    signal.signal(signal.SIGALRM, raise_timeout)
    # Schedule the signal to be sent after ``time``.
    signal.alarm(time)

    try:
        yield
    except TimeoutError:
        pass
    finally:
        # Unregister the signal so it won't be triggered
        # if the timeout is not reached.
        signal.signal(signal.SIGALRM, signal.SIG_IGN)


def raise_timeout(signum, frame):
    raise TimeoutError


LOG = logging


class UnisonHandler(threading.Thread):

    def __init__(self, pref_file):
        super(UnisonHandler, self).__init__()
        self.pref_file = pref_file
        self.status = False
        self.daemon = True
        self.process = None

    def connect(self):
        self.status = True
        self.process = subprocess.Popen(
            ['unison prefs/{} -force newer'.format(self.pref_file)], shell=True)
        LOG.info('Exited')
        self.status = False

    def run(self):
        self.connect()

    def is_connected(self):
        return self.status

    def kill(self):
        self.process.terminate()
        LOG.info('Terminated Unison')


class TunnelObject():

    def __init__(self, address, inport, outport):
        self.address = address
        self.inport = inport
        self.outport = outport
        self.connection = None

    def connect(self):
        with timeout(3):
            self.connection = SSHTunnelForwarder(
                self.address,
                ssh_username='ubuntu',
                remote_bind_address=('127.0.0.1', self.inport),
                local_bind_address=('127.0.0.1', self.outport),
                ssh_pkey='/Users/mharikum/.ssh/adobesearch-dev.pem',
                ssh_private_key_password='p@%n8)3J9Fdg')

    def start(self):
        if self.connection:
            try:
                self.connection.start()
            except Exception as e:
                LOG.exception(e)
                return False
        return True

    def stop(self):
        with timeout(3):
            if self.connection:
                try:
                    self.connection.close()
                except Exception as e:
                    LOG.exception(e)
                    return False
            return True

    def is_connected(self):
        if self.connection.is_active:
            return True
        else:
            return False

    def restart(self):
        try:
            self.connect()
            self.start()
        except:
            return False
        return True


class AwesomeStatusBarApp(rumps.App):

    def __init__(self):
        super(AwesomeStatusBarApp, self).__init__("awstunnel")
        self.menu = ["Preferences", "Restart", "Reload", 'Unison_restart']
        self.unison_filename = 'unison.prefs.txt'
        self.unison_connect(self.unison_filename)
        self.initiate('clientlist.txt')
        pync.notify('Started monitoring')

    @rumps.clicked("Restart")
    def prefs(self, _):
        for i in self.tunnels:
            i.stop()
            i.restart()
        pync.notify("Tunnels Restarted")

    @rumps.clicked("Reload")
    def reload(self, _):
        print('Entering Reload')
        for i in self.tunnels:
            print('Stoppeing {}', i.address)
            i.stop()
        self.tunnels = []
        self.initiate('clientlist.txt')
        pync.notify('Reloaded')

    @rumps.clicked("Unison_restart")
    def unison_restart(self, _):
        LOG.info('unison restart')
        for i in self.unison_handles:
            i.kill()
        self.unison_connect(self.unison_filename)

    def unison_connect(self, filename):
        data = open('unison_prefs.txt').readlines()
        self.unison_handles = []
        for i in data:
            self.unison_handles.append(UnisonHandler(i))
            self.unison_handles[-1].start()
            LOG.info('Starting Unison on {}'.format(i))

    def initiate(self, filename):
        data = open(filename).readlines()
        self.tunnels = []
        LOG.info('Loaded Data from {}'.format(filename))
        for i in data:
            with timeout(3):
                address, port, external_port = i.split(' ')
                self.tunnels.append(
                    TunnelObject(
                        address,
                        int(external_port),
                        int(port)))
                self.tunnels[-1].connect()
                self.tunnels[-1].start()
                print('Starting {}'.format(i))
if __name__ == "__main__":
    AwesomeStatusBarApp().run()
