import yaml


def read_yaml(config_name, config_path):
    """
    config_name: name of the configuration content to read
    config_path: path of the configuration file
    """
    if config_path:
        with open(config_path, 'r', encoding='utf-8') as f:
            conf = yaml.safe_load(f.read())
            if config_name and config_name in conf.keys():
                return conf[config_name]
            else:
                return conf
    else:
        raise ValueError('Please enter the correct configuration file path')


def read_prometheus_metrics_yaml(config_path, node_exporter_instance, postgresql_exporter_instance):
    """
    config_path: configuration file path
    """
    if not config_path:
        raise ValueError('Please enter the correct configuration file path')

    result_dict = {}
    with open(config_path, 'r', encoding='utf-8') as f:
        prometheus_metrics = yaml.safe_load(f.read())

        for key in prometheus_metrics:
            items = prometheus_metrics[key]

            if isinstance(items, list):
                query_list = []
                for item in items:
                    instance_from = item.get('instance_from')
                    instance = node_exporter_instance if instance_from == 'node' else (
                        postgresql_exporter_instance if instance_from == 'postgresql' else None
                    )
                    if not instance:
                        continue
                    query_list.append(item['query'].replace('$instance', instance))
                result_dict[key] = query_list

            elif isinstance(items, dict):
                instance_from = items.get('instance_from')
                instance = node_exporter_instance if instance_from == 'node' else (
                    postgresql_exporter_instance if instance_from == 'postgresql' else None
                )
                if not instance:
                    raise ValueError('Please enter the correct instance_from')
                result_dict[key] = items['query'].replace('$instance', instance)

    return result_dict
