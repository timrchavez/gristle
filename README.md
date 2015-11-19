Gristle
=======

Gristle is a small application that polls GitHub repository events and relays
them to SSH-connected clients similar in fashion to the gerrit-event-stream.
There is a push currently in the OpenStack CI community to add GitHub support
to Zuul using webhooks.  My primary motivation for implementing this was to
create a stream service similar to what Gerrit offers, so that downstreams
that are unable to use webhooks due to security constraints (e.g. corporate
firewalls) have an alternative.

Installation
============

    apt-get install -y python-virtualenv
    virtualenv venv
    source venv/bin/activate
    pip install -r requirements.txt
    sudo python setup.py install

Operation
=========

    gristle --config=path/to/config

Configuration
=============

There are plans to create '/etc/gristle/' directory hierarchy upon
installation, but for now you'll want to create your directory, e.g.

    etc/
    └── gristle
        ├── config.yaml
        └── ssh
            ├── authorized_keys
            └── hostkey


config.yaml
-----------

This will contain all the configuration information Gristle needs to run the
service.

    ---
    sshd:
      host_key: etc/gristle/ssh/hostkey
      authorized_keys: etc/gristle/ssh/authorized_keys
      port: 2222
    accounts:
      - url: https://api.github.com
        username: $USERNAME
        password: $PASSWORD
        repos:
          - name: foo/foo
          - name: bar/foo
            polling: 60
          - name: bar/bar

ssh/authorized_keys
--------------------

This will contain all the public keys Gristle is willing to accept.  The
format is:

    key-type key-contents login-username

ssh/hostkey
-----------

This is the hostkey the Gristle SSH server will use.  You'll want to generate
this key yourself using the ssh-keygen program.

Todo
====

 * Flesh out installation process and upload to pypi
 * Write some unit tests... :/
 * Add token-based authentication
 * Add better documentation describing configuration
