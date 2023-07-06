

from .model import ConnectionRegister
from .model import ConnectionGroup
from .model import Connection
from .model import Node


def get_mismatch_group(register: ConnectionRegister) -> ConnectionGroup:
    """
    from list of connections, identifies any connection with secondary mismatch. 
    identifies the specific node which is causing the issue, then finds any other connections
    referring to that node. 
    returns these in list of ConnectionGroup objects.
    """
    assert(register.mismatched_secondary_connections)
    central_node = register.mismatched_secondary_connections[0].src
    connections: list[Connection] = []
    for connection in register.connections:
        if connection.src.task_name == central_node.task_name:
            if connection.src.node.id() == central_node.node.id():
                connections.append(connection)
        elif connection.dest.task_name == central_node.task_name:
            if connection.dest.node.id() == central_node.node.id():
                connections.append(connection)
        else:
            continue

    return ConnectionGroup(central_node, connections)
