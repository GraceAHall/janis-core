

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .model import ConnectionGroup
    from .model import SecondaryTypeRegister

from janis_core import WorkflowBuilder, CommandToolBuilder
from janis_core.types import DataType
from copy import deepcopy
from . import utils


def apply_new_types(local_wf: WorkflowBuilder, register: SecondaryTypeRegister, group: ConnectionGroup) -> None:
    """
    go through each workflow node: 
      - workflow input, workflow output, tool input, tool output
    if the node is present in the group connections, update the type
    recursive
    """
    update_tools(local_wf, register, group.node_signatures)
    update_workflow(local_wf, register, group.node_signatures)
    
    for step in local_wf.step_nodes.values():
        if isinstance(step.tool, WorkflowBuilder):
            apply_new_types(step.tool, register, group)

    # update_workflow_inputs(local_wf, new_type, signatures)
    # update_tool_inputs(local_wf, new_type, signatures)
    # update_tool_outputs(local_wf, new_type, signatures)
    # update_subwf_inputs(local_wf, new_type, signatures)
    # update_subwf_outputs(local_wf, new_type, signatures)
    # update_workflow_outputs(local_wf, new_type, signatures)
    # # recursive
    
def update_tools(local_wf: WorkflowBuilder, register: SecondaryTypeRegister, node_signatures: set[str]) -> None:
    for step in local_wf.step_nodes.values():
        tool = step.tool
        if isinstance(tool, CommandToolBuilder):
            update_tool_inputs(tool, register, node_signatures)
            update_tool_outputs(tool, register, node_signatures)
            
def update_tool_inputs(tool: CommandToolBuilder, register: SecondaryTypeRegister, node_signatures: set[str]) -> None:
    for inp in tool._inputs:  # type: ignore
        sig = '|'.join([tool.id(), inp.id()]) 
        if sig in node_signatures:
            inp.input_type = utils.gen_type(register, inp.input_type)

def update_tool_outputs(tool: CommandToolBuilder, register: SecondaryTypeRegister, node_signatures: set[str]) -> None:
    for out in tool._outputs:  # type: ignore
        sig = '|'.join([tool.id(), out.id()]) 
        if sig in node_signatures:
            out.output_type = utils.gen_type(register, out.output_type)

def update_workflow(local_wf: WorkflowBuilder, register: SecondaryTypeRegister, node_signatures: set[str]) -> None:
    update_workflow_inputs(local_wf, register, node_signatures)
    update_workflow_outputs(local_wf, register, node_signatures)

def update_workflow_inputs(local_wf: WorkflowBuilder, register: SecondaryTypeRegister, node_signatures: set[str]) -> None:
    for inp in local_wf.input_nodes.values():
        sig = '|'.join([local_wf.id(), inp.id()]) 
        if sig in node_signatures:
            inp.datatype = utils.gen_type(register, inp.datatype)

def update_workflow_outputs(local_wf: WorkflowBuilder, register: SecondaryTypeRegister, node_signatures: set[str]) -> None:
    for out in local_wf.output_nodes.values():
        sig = '|'.join([local_wf.id(), out.id()]) 
        if sig in node_signatures:
            out.datatype = utils.gen_type(register, out.datatype)






# def update_workflow_inputs(local_wf: WorkflowBuilder, new_type: DataType, signatures: set[str]) -> None:
#     for inp in local_wf.input_nodes.values():
#         sig = '|'.join([local_wf.id(), inp.id()]) 
#         if sig in signatures:
#             # TODO check if datatypes already patched?
#             inp.datatype = utils.gen_type(new_type, inp.datatype)

# def update_tool_inputs(local_wf: WorkflowBuilder, new_type: DataType, signatures: set[str]) -> None:
#     for step in local_wf.step_nodes.values():
#         tool = step.tool
#         if isinstance(tool, CommandToolBuilder):
#             for inp in tool._inputs:  # type: ignore
#                 sig = '|'.join([tool.id(), inp.id()]) 
#                 if sig in signatures:
#                     inp.input_type = utils.gen_type(new_type, inp.input_type)

# def update_tool_outputs(local_wf: WorkflowBuilder, new_type: DataType, signatures: set[str]) -> None:
#     for step in local_wf.step_nodes.values():
#         tool = step.tool
#         if isinstance(tool, CommandToolBuilder):
#             for out in tool._outputs:  # type: ignore
#                 sig = '|'.join([tool.id(), out.id()]) 
#                 if sig in signatures:
#                     out.output_type = utils.gen_type(new_type, out.output_type)

# def update_subwf_inputs(local_wf: WorkflowBuilder, new_type: DataType, signatures: set[str]) -> None:
#     for step in local_wf.step_nodes.values():
#         tool = step.tool
#         if isinstance(tool, WorkflowBuilder):
#             for inp in tool.input_nodes.values():  # type: ignore
#                 sig = '|'.join([tool.id(), inp.id()]) 
#                 if sig in signatures:
#                     inp.datatype = utils.gen_type(new_type, inp.datatype)

# def update_subwf_outputs(local_wf: WorkflowBuilder, new_type: DataType, signatures: set[str]) -> None:
#     for step in local_wf.step_nodes.values():
#         tool = step.tool
#         if isinstance(tool, WorkflowBuilder):
#             for out in tool.output_nodes.values():  # type: ignore
#                 sig = '|'.join([tool.id(), out.id()]) 
#                 if sig in signatures:
#                     out.datatype = utils.gen_type(new_type, out.datatype)

# def update_workflow_outputs(local_wf: WorkflowBuilder, new_type: DataType, signatures: set[str]) -> None:
#     for out in local_wf.output_nodes.values():
#         sig = '|'.join([local_wf.id(), out.id()]) 
#         if sig in signatures:
#             out.datatype = utils.gen_type(new_type, out.datatype)


