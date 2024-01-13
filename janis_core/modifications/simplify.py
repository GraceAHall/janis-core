
from typing import Any
from janis_core import CommandToolBuilder, CodeTool, WorkflowBuilder
from .EntityModifier import EntityModifier




class SimplifyModifier(EntityModifier): 

    def handle_workflow(self, workflow: WorkflowBuilder) -> Any:
        raise NotImplementedError
    
    def handle_cmdtool(self, cmdtool: CommandToolBuilder) -> Any:
        raise NotImplementedError
    
    def handle_codetool(self, codetool: CodeTool) -> Any:
        raise NotImplementedError