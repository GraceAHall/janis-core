

from typing import Any
from janis_core import CommandToolBuilder, CodeTool
from janis_core import WorkflowBuilder, InputNodeSelector, StepOutputSelector
from .EntityModifier import EntityModifier

 
class WrapToolModifier(EntityModifier): 

    def handle_cmdtool(self, cmdtool: CommandToolBuilder) -> Any:
        wf = WorkflowBuilder(f'{cmdtool.id()}_wf')

        # add workflow input for each tool input
        for inp in cmdtool._inputs:
            wf.input(
                identifier=inp.id(),
                datatype=inp.input_type,
                default=None,
            )

        # add step
        kwargs = {inp.id(): InputNodeSelector(wf.input_nodes[inp.id()]) for inp in cmdtool._inputs}
        step = wf.step(
            f'{cmdtool.id()}_step',
            cmdtool(**kwargs)
        )

        # add output for each tool output
        for out in cmdtool._outputs: 
            wf.output(
                identifier=out.id(),
                datatype=out.output_type,
                source=StepOutputSelector(step, out.id())
            )

        return wf 
    
    def handle_codetool(self, codetool: CodeTool) -> Any:
        raise NotImplementedError
        