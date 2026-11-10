"""Protocol series rules shared by authentication and local discovery."""
import re


def parse_version(value):
    if not isinstance(value,str) or not re.fullmatch(r'(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})',value):
        return None
    return tuple(map(int,value.split('.')))


def compatible(remote, local):
    a,b=parse_version(remote),parse_version(local)
    return a is not None and b is not None and a[:2]==b[:2]


def host_version_error(remote, local):
    a,b=parse_version(remote),parse_version(local)
    if a is None or b is None:return 'Missing or malformed protocol version; install matching FrameViz runtime and SDK.'
    if a[:2]==b[:2]:return None
    if a[:2]<b[:2]:return f'Host protocol {remote} is older than SDK {local}. Upgrade the FrameViz runtime to {b[0]}.{b[1]}.x.'
    return f'Host protocol {remote} is newer than SDK {local}. Upgrade the Python SDK to {a[0]}.{a[1]}.x.'
