import yaml

from gristle.config.schema import ConfigSchema


class Config(object):
    def __init__(self, config_file):
        data = self.validate(yaml.safe_load(open(config_file)))
        self.log_file = data.get("log_file", None)
        self.sshd = data.get("sshd", {})
        self.accounts = data.get("accounts", {})

    def validate(self, data):
        schema = ConfigSchema()
        return schema.validate(data)
