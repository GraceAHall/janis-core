

from typing import Any

from janis_core import Workflow, WorkflowBuilder
from janis_core import CommandTool, CommandToolBuilder
from janis_core import CodeTool

from .builders import BuilderModifier
from .symbols import SymbolModifier
from .containers import ContainerModifier
from .simplify import SimplifyModifier
from .wrap import WrapToolModifier
from .prune import prune_workflow

BaseClass    = Workflow | CommandTool | CodeTool
BuilderClass = WorkflowBuilder | CommandToolBuilder | CodeTool


def to_builders(entity: BaseClass) -> BuilderClass:
    return BuilderModifier().modify(entity)

def ensure_containers(entity: BuilderClass) -> BuilderClass:
    return ContainerModifier().modify(entity)

def simplify(entity: BuilderClass) -> BuilderClass:
    if isinstance(entity, WorkflowBuilder):
        prune_workflow(entity)
    return entity
    # return SimplifyModifier().modify(entity)

def refactor_symbols(entity: BuilderClass) -> BuilderClass:
    return SymbolModifier().modify(entity)

def wrap_tool_in_workflow(entity: BuilderClass) -> BuilderClass:
    return WrapToolModifier().modify(entity)