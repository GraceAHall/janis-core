

import regex as re 
from typing import Any
from abc import ABC, abstractmethod
from janis_core import ToolInput, TInput
from janis_core.workflow.workflow import InputNode
from janis_core.types import File, String, Int, Float, Boolean, Array, Directory


### COMMAND TOOL INPUTS ###

class ToolInputOrderingStrategy(ABC):
    @abstractmethod
    def order(self, inputs: list[ToolInput]) -> list[ToolInput]:
        """orders input values and returns ordered list"""
        ...

class DatatypeStrategy(ToolInputOrderingStrategy):
    priorities = {
        'Map': 0,
        'File': 2,
        'String': 3,
        'Int': 4,
        'Float': 5,
        'Boolean': 6,
    }

    def order(self, inputs: list[ToolInput]) -> list[ToolInput]:
        inputs.sort(key=lambda x: self.get_priority(x))
        return inputs
    
    def get_priority(self, inp: ToolInput) -> int:
        dtype_str: str = inp.input_type.wdl().get_string()
        dtype_str = re.sub(r'\?', '', dtype_str)
        dtype_str = re.sub(r'\[', '', dtype_str)
        dtype_str = re.sub(r'\]', '', dtype_str)
        dtype_str = re.sub(r'Array', '', dtype_str)
        
        priority = 0 
        # make arrays come first 
        if 'Array' in dtype_str:
            priority -= 10
        # use priority map or fallback
        if dtype_str in self.priorities:
            priority += self.priorities[dtype_str]
        else:
            priority += 7

        return priority 

class AlphabeticalStrategy(ToolInputOrderingStrategy):
    def order(self, inputs: list[ToolInput]) -> list[ToolInput]:
        inputs.sort(key=lambda x: x.tag)
        return inputs

class MandatoryStrategy(ToolInputOrderingStrategy):
    def order(self, inputs: list[ToolInput]) -> list[ToolInput]:
        inputs.sort(key=lambda x: x.input_type.optional and x.default is not None)
        return inputs

class ExpressionStrategy(ToolInputOrderingStrategy):
    primitives = (bool, str, int, float, type(None))

    def order(self, inputs: list[ToolInput]) -> list[ToolInput]:
        inputs.sort(key=lambda x: self.is_expression(x.default))
        return inputs

    def is_expression(self, default: Any) -> bool:
        if default is not None:
            if not isinstance(default, self.primitives):
                return True
        return False


# class PositionToolInputStrategy(ToolInputOrderingStrategy):
#     def order(self, inputs: list[ToolInput]) -> list[ToolInput]:
#         inputs.sort(key=lambda x: x.position if x.position else 0)
#         return inputs


tool_input_strategies = [
    AlphabeticalStrategy(),
    DatatypeStrategy(),
    MandatoryStrategy(),
    ExpressionStrategy(),
]

def order_tool_inputs(inputs: list[ToolInput]) -> list[ToolInput]:
    for strategy in tool_input_strategies:
        inputs = strategy.order(inputs)
    return inputs

def get_tool_input_positions_cmdtool(inputs: list[ToolInput]) -> dict[str, int]:
    inputs = order_tool_inputs(inputs)
    order_map = {inp.id(): i for i, inp in enumerate(inputs)}
    return order_map

def get_tool_input_positions_codetool(inputs: list[TInput]) -> dict[str, int]:
    order_map = {inp.id(): i for i, inp in enumerate(inputs)}
    return order_map




### WORKFLOW INPUTS ###

class WFInputOrderingStrategy(ABC):
    @abstractmethod
    def order(self, inputs: list[InputNode]) -> list[InputNode]:
        """orders input values and returns ordered list"""
        ...

class AlphabeticalWFInputStrategy(WFInputOrderingStrategy):
    def order(self, inputs: list[InputNode]) -> list[InputNode]:
        inputs.sort(key=lambda x: x.id())
        return inputs

class MandatoryPriorityWFInputStrategy(WFInputOrderingStrategy):
    def order(self, inputs: list[InputNode]) -> list[InputNode]:
        inputs.sort(key=lambda x: x.datatype.optional)
        return inputs


workflow_input_strategies = [
    AlphabeticalWFInputStrategy(),
    MandatoryPriorityWFInputStrategy(),
]

def order_workflow_inputs(inputs: list[InputNode]) -> list[InputNode]:
    for strategy in workflow_input_strategies:
        inputs = strategy.order(inputs)
    return inputs

def get_workflow_input_positions(inputs: list[InputNode]) -> dict[str, int]:
    inputs = order_workflow_inputs(inputs)
    return {inp.id(): i for i, inp in enumerate(inputs)}
        
        