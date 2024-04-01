

from janis_core import WorkflowBuilder
from janis_core import CommandToolBuilder

from .tools import simplify_tools_and_sources
from .workflows import simplify_main_workflow_inputs

"""
exists to enable the settings.translate.MODE feature. 
simplifies the main workflow inputs, so that only those which are used are kept.
simplifies tool inputs which aren't used. 
simplifies step sources which aren't used.

"""
 
def simplify_workflow(wf: WorkflowBuilder) -> None:
    tools = gather_tools(wf)
    simplify_tools_and_sources(wf, tools)
    simplify_main_workflow_inputs(wf)

def gather_tools(wf: WorkflowBuilder) -> dict[str, CommandToolBuilder]:
    gathered_tools: dict[str, CommandToolBuilder] = {}
    return do_gather_tools(wf, gathered_tools)

def do_gather_tools(wf: WorkflowBuilder, gathered_tools: dict[str, CommandToolBuilder]) -> dict[str, CommandToolBuilder]:
    for step in wf.step_nodes.values():
        if isinstance(step.tool, WorkflowBuilder):
            gathered_tools = do_gather_tools(step.tool, gathered_tools)
        elif isinstance(step.tool, CommandToolBuilder) and step.tool.id() not in gathered_tools:
            gathered_tools[step.tool.id()] = step.tool
        else:
            continue
    return gathered_tools
