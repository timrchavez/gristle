import voluptuous as v


class GitHubRepoConfig(object):

    def get_schema(self):
        return {
            v.Required("name"): v.All(str, v.Length(min=1)),
            v.Optional("polling"): v.All(int)
        }


class GitHubAccountConfig(object):

    def get_schema(self):
        repos = GitHubRepoConfig().get_schema()
        return {
            v.Required("url"): v.Url(str),
            v.Required("username"): v.All(str, v.Length(min=1)),
            v.Required("password"): v.All(str, v.Length(min=1)),
            v.Required("repos"): [repos]
        }


class SSHServer(object):

    def get_schema(self):
        return {
            v.Required("host_key"): v.All(str, v.Length(min=1)),
            v.Required("authorized_keys"): v.All(str, v.Length(min=1)),
            v.Optional("port"): v.All(int)
        }


class ConfigSchema(object):

    def validate(self, data):
        sshd = SSHServer().get_schema()
        accounts = GitHubAccountConfig().get_schema()
        schema = v.Schema({
            v.Optional("log_file"): v.All(str, v.Length(min=1)),
            v.Required("sshd"): sshd,
            v.Required("accounts"): [accounts],
        })

        return schema(data)
