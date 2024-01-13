

"""
handles updates to InputSelectors and StepOutputSelectors required as a result of id changes.
these both use a string identifier to reference the input/output they are selecting, rather than object references.
"""


from typing import Any, Tuple

from janis_core import CommandToolBuilder, WorkflowBuilder
from janis_core import InputSelector, StepOutputSelector, ResourceSelector

from janis_core.translations.common.trace import Tracer


class SelectorUpdater(Tracer):
    """reassigns input/output ids in InputSelectors and StepOutputSelectors"""

    def __init__(self, tool: CommandToolBuilder | WorkflowBuilder, id_map: dict[str, Tuple[str, str]]) -> None:
        super().__init__(tool)
        self.id_map = id_map
        if isinstance(tool, CommandToolBuilder):
            input_uuids = set([x.uuid for x in tool._inputs])
            self.input_id_map = {v[0]: v[1] for k, v in self.id_map.items() if k in input_uuids}
        if isinstance(tool, WorkflowBuilder):
            self.output_id_map = {}
            for step in tool.step_nodes.values():
                if isinstance(step.tool, CommandToolBuilder):
                    output_uuids = set([x.uuid for x in step.tool._outputs])
                elif isinstance(step.tool, WorkflowBuilder):
                    output_uuids = set([x.uuid for x in step.tool.output_nodes.values()])
                else:
                    raise RuntimeError
                self.output_id_map[step.id()] = {v[0]: v[1] for k, v in self.id_map.items() if k in output_uuids}

    def trace(self, entity: Any) -> None:
        if isinstance(entity, InputSelector):
            assert isinstance(self.tool, CommandToolBuilder)
            if not isinstance(entity, ResourceSelector):
                id_map = self.input_id_map
                old_id = entity.input_to_select
                new_id = id_map[old_id]
                entity.input_to_select = new_id
        elif isinstance(entity, StepOutputSelector):
            id_map = self.output_id_map[entity.node.id()]
            old_id = entity.tag
            new_id = id_map[old_id]
            entity.tag = new_id
        self.do_trace(entity)
