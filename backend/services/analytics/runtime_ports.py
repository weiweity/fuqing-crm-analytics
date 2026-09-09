"""Explicit loopback port blocks for isolated synthetic runners."""


def runtime_port_base(config):
    value = config.get("port_base", 4315)
    if type(value) is not int or value not in (4315, 4325, 4335):
        raise ValueError("invalid isolated analytics port block")
    return value


def bridge_origin(config):
    return f"http://127.0.0.1:{runtime_port_base(config) + 1}"
