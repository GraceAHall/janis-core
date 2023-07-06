

from typing import Any
from janis_core import WorkflowBuilder, InputNodeSelector, StepOutputSelector
from janis_core.workflow.workflow import OutputNode,StepNode, StepTagInput
from janis_core.translations.common import trace

from .model import ConnectionRegister, Connection, Node

def gather_connections(main_wf: WorkflowBuilder) -> ConnectionRegister:
    register = ConnectionRegister()
    do_gather_connections(main_wf, register)
    return register

def do_gather_connections(local_wf: WorkflowBuilder, register: ConnectionRegister) -> None:
    """gather connections from the perspective of connection dests & add to register"""
    # step sources
    for step in local_wf.step_nodes.values():
        for tinput_id, src in step.sources.items():
            
            # ignore null srcs (don't know if this happens)
            if src is None:
                continue
            
            # get the dest & src nodes
            dest_node = get_dest_node_step(step, tinput_id)
            src_nodes = get_src_nodes(src, local_wf)
            for src_node in src_nodes:
                connection = Connection(src_node, dest_node)
                register.add(connection)
            
        # recursive
        if isinstance(step.tool, WorkflowBuilder):
            do_gather_connections(step.tool, register) 
    
    # output sources
    for out in local_wf.output_nodes.values():
        dest_node = get_dest_node_output(out, local_wf)
        src_nodes = get_src_nodes(out.source, local_wf)
        for src_node in src_nodes:
            connection = Connection(src_node, dest_node)
            register.add(connection)


def get_dest_node_step(step: StepNode, tinput_id: str) -> Node:
    dest_node = [x for x in step.tool.tool_inputs() if x.id() == tinput_id][0]
    dest_task = step.tool.id()
    return Node(dest_node, dest_task)

def get_dest_node_output(out: OutputNode, local_wf: WorkflowBuilder) -> Node:
    dest_task = local_wf.id()
    dest_node = [x for x in local_wf.tool_outputs() if x.id() == out.id()][0]
    return Node(dest_node, dest_task)

def get_src_nodes(src: Any, local_wf: WorkflowBuilder) -> list[Node]:
    assert(src is not None)
    if isinstance(src, StepTagInput):
        sel = src.source_map[0].source
    else:
        sel = src

    # input node selector
    if isinstance(sel, InputNodeSelector):
        src_task = local_wf.id()
        src_node = [x for x in local_wf.tool_inputs() if x.id() == sel.input_node.id()][0]
        return [Node(src_node, src_task)]
    
    # step output selector
    elif isinstance(sel, StepOutputSelector):
        src_task = sel.node.tool.id()
        src_node = sel.node.outputs()[sel.tag]
        return [Node(src_node, src_task)]
    
    # complex expression
    else:
        nodes: list[Node] = []
        entities = trace.trace_entities(sel, local_wf)
        for entity in entities:
            if isinstance(entity, InputNodeSelector):
                src_task = local_wf.id()
                src_node = [x for x in local_wf.tool_inputs() if x.id() == entity.input_node.id()][0]
                nodes.append(Node(src_node, src_task))
            if isinstance(entity, StepOutputSelector):
                src_task = entity.node.tool.id()
                src_node = entity.node.outputs()[entity.tag]
                nodes.append(Node(src_node, src_task))
        
        if len(nodes) == 0:
            raise Exception(f"Could not find any sources for {sel}")
        return nodes

