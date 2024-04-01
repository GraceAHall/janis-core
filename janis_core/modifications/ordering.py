

from collections import OrderedDict
from janis_core.introspection.graph import get_step_order
from janis_core import WorkflowBuilder, CommandToolBuilder, CodeTool

BuilderClass = WorkflowBuilder | CommandToolBuilder | CodeTool

def topological_steps(entity: BuilderClass) -> BuilderClass:
    if not isinstance(entity, WorkflowBuilder):
        return entity 
    
    for step in entity.step_nodes.values():
        if isinstance(step.tool, WorkflowBuilder):
            step.tool = topological_steps(step.tool)
    
    return _do_modify_workflow(entity)
    
def _do_modify_workflow(wf: WorkflowBuilder) -> WorkflowBuilder:
    # get correct order
    correct_order = get_step_order(wf)
    
    # reorder steps
    new_steps = OrderedDict()
    for step_id in correct_order:
        new_steps[step_id] = wf.step_nodes[step_id]
    wf.step_nodes = new_steps
    
    return wf 