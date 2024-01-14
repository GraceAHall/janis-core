

from typing import Any

from janis_core import Workflow, WorkflowBuilder
from janis_core import CommandTool, CommandToolBuilder
from janis_core import CodeTool
from janis_core import settings
from janis_core.settings.translate import ESimplification

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
    if settings.translate.SIMPLIFICATION in [ESimplification.AGGRESSIVE, ESimplification.ON]:
        if isinstance(entity, WorkflowBuilder):
            prune_workflow(entity)
    return entity
    # return SimplifyModifier().modify(entity)

def refactor_symbols(entity: BuilderClass) -> BuilderClass:
    return SymbolModifier().modify(entity)

def wrap_tool_in_workflow(entity: BuilderClass) -> BuilderClass:
    if settings.translate.AS_WORKFLOW and isinstance(entity, CommandToolBuilder):
        return WrapToolModifier().modify(entity)
    return entity 