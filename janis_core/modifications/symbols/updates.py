

"""
handles updates to InputSelectors and StepOutputSelectors required as a result of id changes.
these both use a string identifier to reference the input/output they are selecting, rather than object references.
"""


from typing import Any, Tuple

from janis_core import CommandToolBuilder, WorkflowBuilder, CodeTool
from janis_core import InputSelector, StepOutputSelector, ResourceSelector

from janis_core.introspection.trace import Tracer


class SelectorUpdater(Tracer):
    """reassigns input/output ids in InputSelectors and StepOutputSelectors"""

    def __init__(self, tool: CommandToolBuilder | WorkflowBuilder, id_map: dict[str, Tuple[str, str]]) -> None:
        super().__init__(tool)
        self.id_map = id_map

    def input_id_map(self, tool: CommandToolBuilder | WorkflowBuilder) -> dict[str, str]:
        if isinstance(tool, CommandToolBuilder):
            input_uuids = set([x.uuid for x in tool._inputs])
        elif isinstance(tool, WorkflowBuilder):
            input_uuids = set([x.uuid for x in tool.input_nodes.values()])
        else:
            raise RuntimeError
        the_dict = {v[0]: v[1] for k, v in self.id_map.items() if k in input_uuids}
        return the_dict

    def step_output_id_map(self, tool: CommandToolBuilder | WorkflowBuilder) -> dict[str, dict[str, str]]:
        the_dict = {}
        assert isinstance(tool, WorkflowBuilder)
        for step in tool.step_nodes.values():
            if isinstance(step.tool, CommandToolBuilder):
                output_uuids = set([x.uuid for x in step.tool._outputs])
            elif isinstance(step.tool, CodeTool):
                output_uuids = set([])
            elif isinstance(step.tool, WorkflowBuilder):
                output_uuids = set([x.uuid for x in step.tool.output_nodes.values()])
            else: 
                raise RuntimeError
            the_dict[step.id()] = {v[0]: v[1] for k, v in self.id_map.items() if k in output_uuids}
        return the_dict

    def output_id_map(self, tool: CommandToolBuilder | WorkflowBuilder) -> dict[str, str]:
        the_dict = {}
        if isinstance(tool, CommandToolBuilder):
            output_uuids = set([x.uuid for x in tool._outputs])
        elif isinstance(tool, WorkflowBuilder):
            output_uuids = set([x.uuid for x in tool.output_nodes.values()])
        else:
            raise RuntimeError
        the_dict = {v[0]: v[1] for k, v in self.id_map.items() if k in output_uuids}
        return the_dict

    def get_new_id(self, old_id: str, id_map: dict) -> str:
        if old_id in id_map:
            return id_map[old_id]
        else:
            return old_id

    def trace(self, entity: Any) -> None:
        if isinstance(entity, ResourceSelector):
            return 
        
        elif isinstance(entity, InputSelector):
            assert self.tool
            id_map = self.input_id_map(self.tool)
            entity.input_to_select = self.get_new_id(entity.input_to_select, id_map)
            
        elif isinstance(entity, StepOutputSelector):
            assert self.tool
            id_map = self.step_output_id_map(self.tool)[entity.node.id()]
            entity.tag = self.get_new_id(entity.tag, id_map)
        
        else:
            self.do_trace(entity)
