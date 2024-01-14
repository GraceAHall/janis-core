

from typing import Any
from dataclasses import dataclass, field

from janis_core import WorkflowBuilder, TInput, TOutput, CommandToolBuilder, PythonTool
from janis_core.workflow.workflow import StepNode
from janis_core.operators.selectors import InputNodeSelector
from janis_core.operators.selectors import StepOutputSelector
from janis_core import translation_utils as utils
from janis_core.translation_utils import DTypeType
from janis_core.translations.common.trace import StepOutputTracer


@dataclass
class InputTaskInput:
    step_id: str
    value: InputNodeSelector

@dataclass
class ConnectionTaskInput:
    step_id: str
    value: StepOutputSelector

@dataclass
class OtherTaskInput:
    step_id: str
    value: Any

TaskInput = InputTaskInput | ConnectionTaskInput | OtherTaskInput


@dataclass
class TaskInputRegister:
    tinput: TInput
    sources: list[TaskInput] = field(default_factory=list)

    @property
    def is_optional(self) -> bool:
        dtt = utils.get_dtt(self.tinput.intype)
        if dtt == DTypeType.FILENAME:
            return False
        elif self.tinput.intype.optional == True:
            return True
        return False
    
    @property
    def input_sources(self) -> list[InputTaskInput]:
        return [x for x in self.sources if isinstance(x, InputTaskInput)]
    
    @property
    def connection_sources(self) -> list[ConnectionTaskInput]:
        return [x for x in self.sources if isinstance(x, ConnectionTaskInput)]
    
    @property
    def other_sources(self) -> list[OtherTaskInput]:
        return [x for x in self.sources if isinstance(x, OtherTaskInput)]
    
    @property
    def mandatory_input_sources(self) -> list[InputTaskInput]:
        sources = self.input_sources
        sources = [x for x in sources if x.value.input_node.datatype.optional == False]
        return sources
    
    @property
    def placeholder_sources(self) -> list[InputTaskInput]:
        sources: list[InputTaskInput] = []
        for source in self.input_sources:
            # does the source input node source look like a placeholder?
            node = source.value.input_node
            step_id = source.step_id
            if utils.looks_like_placeholder_node(node, step_id, self.tinput.id(), self.tinput.intype):
                sources.append(source)
        return sources
    
    def add_value(self, step_id: str, src: Any) -> None:
        if isinstance(src, InputNodeSelector):
            ti = InputTaskInput(step_id, src)
        elif isinstance(src, StepOutputSelector):
            ti = ConnectionTaskInput(step_id, src)
        else:
            ti = OtherTaskInput(step_id, src)
        self.sources.append(ti)


@dataclass
class TaskOutputRegister:
    toutput: TOutput
    sources: list[Any] = field(default_factory=list)

    @property
    def is_optional(self) -> bool:
        dtt = utils.get_dtt(self.toutput.outtype)
        if dtt == DTypeType.FILENAME:
            return False
        elif self.toutput.outtype.optional == True:
            return True
        return False
    


class TaskIOCollector:
    """
    for a given tool_id, searches the workflow for each step calling that tool.
    records the values provided to each TInput in that step call. 
    """
    def __init__(self, tool: CommandToolBuilder | PythonTool | WorkflowBuilder) -> None:
        self.tool = tool
        self.input_register = {tinp.id(): TaskInputRegister(tinp) for tinp in self.tool.tool_inputs()}
        self.output_register = {tout.id(): TaskOutputRegister(tout) for tout in self.tool.tool_outputs()}
        self.step_count: int = 0

    def collect(self, wf: WorkflowBuilder) -> None:
        # identify if any workflow outputs reference this tool's outputs
        wout_sources = [x.source for x in wf.output_nodes.values()]
        self.update_output_register(wout_sources)

        # iterate over steps
        for step in wf.step_nodes.values():
            if not isinstance(step.tool, CommandToolBuilder | PythonTool | WorkflowBuilder):
                raise RuntimeError
            
            # step sources
            stp_sources = {k: v.source_map[0].source for k, v in step.sources.items()}
            
            # update task outputs if sources reference correct tool
            self.update_output_register(list(stp_sources.values()))

            # update task inputs if correct tool
            if step.tool.id() == self.tool.id():
                self.step_count += 1
                self.update_input_register(stp_sources, step)
            
            # recursive for nested workflows
            if isinstance(step.tool, WorkflowBuilder):
                self.collect(step.tool)
    
    def update_output_register(self, sources: list[Any]) -> None:
        for src in sources:
            tracer = StepOutputTracer()
            tracer.trace(src)
            for identifier in tracer.identifiers:
                toolid, outtag = identifier.split(".")
                if toolid == self.tool.id():
                    self.output_register[outtag].sources.append(src)

    def update_input_register(self, sources: dict[str, Any], step: StepNode) -> None:
        # update the record of each TInput's history
        for tinput_id, src in sources.items():

            # add a TaskInputHistory for TInput if not exists
            if tinput_id not in self.input_register:
                tinput = [x for x in step.tool.tool_inputs() if x.id() == tinput_id][0]
                history = TaskInputRegister(tinput)
                self.input_register[tinput_id] = history
            
            # add a value to this TInput's TaskInputHistory
            if src is not None:
                self.input_register[tinput_id].add_value(step.id(), src)
  

