
from typing import Optional
from dataclasses import dataclass
from janis_core import WorkflowBuilder, CommandToolBuilder, PythonTool

from janis_core.translations.nextflow.model import VariableType

@dataclass 
class TaskInput:
    tinput_id: str
    vtype: VariableType
    value: Optional[str | list[str]] 

REGISTER: dict[str, dict[str, TaskInput]] = {}

def clear() -> None:
    global REGISTER
    REGISTER = {}
    
def update(tool_id: str, tinput_id: str, ttype: VariableType, value: Optional[str | list[str]]) -> None:
    """creates an entry for a given tool input in the REGISTER."""
    global REGISTER
    
    # if scope not yet in data structure, add
    if tool_id not in REGISTER:
        REGISTER[tool_id] = {}

    # create new TaskInput & add to data_structure
    REGISTER[tool_id][tinput_id] = TaskInput(tinput_id, ttype, value)

def get(tool_id: str, tinput_id: str) -> TaskInput:
    return REGISTER[tool_id][tinput_id]

def getall(tool_id: str) -> list[TaskInput]:
    return list(REGISTER[tool_id].values())

def exists(tool_id: str, tinput_id: Optional[str]=None) -> bool:
    # checks the tool id has an entry for this tool input
    if tool_id not in REGISTER:
        return False
    if tinput_id and tinput_id not in REGISTER[tool_id]:
        return False
    return True

def existsall(tool: WorkflowBuilder | CommandToolBuilder | PythonTool) -> bool:
    # checks the tool id has an entry 
    # checks each tinput id has an associated value in the entry
    if tool.id() not in REGISTER:
        return False
    for tinput in tool.tool_inputs():
        if tinput.id() not in REGISTER[tool.id()]:
            return False
    return True

def report() -> None:
    for tool_id, tinputs in REGISTER.items():
        print(f"\nTool ID: {tool_id} ---")
        for tinput_id, tinput in tinputs.items():
            print(f"{tinput_id}: {tinput.vtype} - {tinput.value}")

# def task_inputs(tool: WorkflowBuilder | CommandToolBuilder | PythonTool) -> set[str]:
#     all_inputs = ti_register.getall(tool)
#     return set([x.tinput_id for x in all_inputs if x.ti_type == VariableType.INPUT])

# def param_inputs(tool: WorkflowBuilder | CommandToolBuilder | PythonTool) -> set[str]:
#     all_inputs = ti_register.getall(tool)
#     return set([x.tinput_id for x in all_inputs if x.ti_type == VariableType.PARAM])

# def static_inputs(tool: WorkflowBuilder | CommandToolBuilder | PythonTool) -> set[str]:
#     all_inputs = ti_register.getall(tool)
#     return set([x.tinput_id for x in all_inputs if x.ti_type == VariableType.STATIC])

# def ignored_inputs(tool: WorkflowBuilder | CommandToolBuilder | PythonTool) -> set[str]:
#     all_inputs = ti_register.getall(tool)
#     return set([x.tinput_id for x in all_inputs if x.ti_type == VariableType.IGNORED])

# def local_inputs(tool: WorkflowBuilder | CommandToolBuilder | PythonTool) -> set[str]:
#     all_inputs = ti_register.getall(tool)
#     return set([x.tinput_id for x in all_inputs if x.ti_type == VariableType.LOCAL])



