import yaml

CHAT_HISTORY_FILE = "chat_history.json"

def read_yaml(config_name, config_path):
    """
    config_name: name of the configuration content to read
    config_path: path of the configuration file
    """
    print(config_name)
    if config_name and config_path:
        with open(config_path, 'r', encoding='utf-8') as f:
            conf = yaml.safe_load(f.read())
        if config_name in conf.keys():
            return conf[config_name]
        else:
            raise KeyError('Corresponding configuration not found')
    else:
        raise ValueError('Please enter the correct config name or config file path')
