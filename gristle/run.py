import argparse
import gevent
import json
import logging
import paramiko
import socket
import sys
import traceback

from binascii import hexlify
from datetime import datetime, timedelta
from gevent import monkey; monkey.patch_all()
from github import Github
from paramiko.py3compat import decodebytes

from gristle import __version__
from gristle.config import Config


class SSHServer(paramiko.ServerInterface):
    """A custom SSH server"""
    def __init__(self, authorized_keys_file):
        self.authorized_keys = {}

        try:
            with open(authorized_keys_file) as authorized_keys:
                for key_info in authorized_keys.readlines():
                    key_type, key_contents, key_user = key_info.split()
                    if key_type == "ssh-rsa":
                        user = key_user.lower()
                        self.authorized_keys[user] = paramiko.RSAKey(
                            data=decodebytes(key_contents))
        except IOError as e:
            logging.error(str(e))
            traceback.print_exc()
            sys.exit(1)

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_publickey(self, username, key):
        logging.info("Auth attempt with key: {0}".format(
            hexlify(key.get_fingerprint())))
        if username in self.authorized_keys:
            if key == self.authorized_keys[username]:
                return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return "publickey"

    def check_channel_shell_request(self, channel):
        return True

    def check_channel_pty_request(
        self, channel, term, width, height, pixelwidth, pixelheight, modes):
        return True


class Gristle(object):
    """GitHub event streaming service

    Scan GitHub repositories for new events and relay them to connected SSH
    clients.  This approximates the event streaming concept used by Gerrit.
    """
    DEFAULT_PORT = 9595
    DEFAULT_LISTEN_QUEUE = 100
    DEFAULT_ACCEPT_TIMEOUT = 20
    DEFAULT_POLLING_PERIOD = 5

    def __init__(self, config):
        self.config = config
        self.channels = []
        self._port = self.config.sshd.get("port", self.DEFAULT_PORT)
        self._host_key = paramiko.RSAKey(filename=self.config.sshd["host_key"])
        self._listen_queue = self.config.sshd.get(
            "listen_queue", self.DEFAULT_LISTEN_QUEUE)
        self._accept_timeout = self.config.sshd.get(
            "accept_timeout", self.DEFAULT_ACCEPT_TIMEOUT)

        if self.config.log_file:
            paramiko.util.log_to_file(self.config.log_file)

    def _start_ssh_server(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", self._port))
        except Exception as e:
            logging.error("Bind failed: {0}".format(str(e)))
            traceback.print_exc()
            sys.exit(1)

        try:
            logging.info("Listening for new connections")
            sock.listen(self._listen_queue)
        except Exception as e:
            logging.error("Listen failed: {0}".format(str(e)))
            traceback.print_exc()
            sys.exit(1)

        server = SSHServer(self.config.sshd["authorized_keys"])

        while True:
            connection, address = sock.accept()

            t = paramiko.Transport(connection)
            t.add_server_key(self._host_key)
            try:
                t.start_server(server=server)
            except paramiko.SSHException:
                logging.error("SSH negotiation failed")
                sys.exit(1)

            try:
                channel = t.accept(self._accept_timeout)
                if channel is None:
                    logging.error("No channel")
                    sys.exit(1)

                channel.send("Welcome to Gristle v{0}!\r\n".format(__version__))
                # FIXME: Manage channel in thread, read input to support CTRL-C

                self.channels.append(channel)
            except Exception as e:
                logging.error("Caught exception: {0}: {1}".format(
                    str(e.__class__), str(e)))
                traceback.print_exc()
                try:
                    t.close()
                except:
                    pass
                sys.exit(1)

    def _start_repo_scanning(self):
        events = []
        for account in self.config.accounts:
            gh = Github(
                account["username"], account["password"], base_url=account["url"])
            for repo in account["repos"]:
                # Per-project polling, just cause
                polling = repo.get("polling", self.DEFAULT_POLLING_PERIOD)
                events.append(
                    gevent.spawn(self._scan_repo, gh, repo["name"], polling))

    def _scan_repo(self, gh, repo, period):
        """Scan GitHub repository for new events

        Use an infinite loop to scan a GitHub repository using a configurable
        period (to avoid hitting your rate limit).  The raw JSON data of any
        new events discovered between scans will be relayed to all clients
        connected to the SSH server.
        """
        namespace, repo_name = repo.split("/")

        owner = gh.get_user(namespace)
        if not owner:
            owner = gh.get_organization(namespace)
        if not owner:
            logging.error("Could not find repository {0} with owner {1}".format(
                namespace, repo_name))
            return

        repo = owner.get_repo(repo_name)
        if not repo:
            logging.error("Could not find repository {0} with owner {1}".format(
                namespace, repo_name))
            return

        next_scan_time = scan_time = datetime.utcnow()
        while True:
            if scan_time >= next_scan_time:
                logging.info(
                    "Scanning '{0}/{1}'...".format(repo.owner.login, repo.name))
                for event in repo.get_events():
                    if event.created_at >= scan_time - timedelta(seconds=period):
                        for channel in self.channels:
                            channel.send(
                                "{0}\r\n".format(json.dumps(event.raw_data)))
                next_scan_time = scan_time + timedelta(seconds=period)
            gevent.sleep(0)
            scan_time = datetime.utcnow()

    def start(self):
        self._start_repo_scanning()
        self._start_ssh_server()


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Stream GitHub repo events")
    parser.add_argument(
        "--config",
        default="/etc/gristle/config.yaml",
        help="The gristle config file"
    )
    # FIXME: Add an argument for "daemon" mode
    args = parser.parse_args()
    config = Config(args.config)

    gristle = Gristle(config)
    gristle.start()

if __name__ == "__main__":
    main()
