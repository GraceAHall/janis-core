


from typing import Any
from janis_core import CommandTool, CommandToolBuilder, Workflow, WorkflowBuilder, CodeTool
from abc import ABC
 

class EntityModifier(ABC): 
    """
    base class for something which modifies a tool or workflow in-place. 
    for example, renaming all the steps in a workflow.
    returns the modified entity.
    
    """

    def _ensure_builders(self, entity: Workflow | CommandTool | CodeTool) -> Any:
        # do nothing for BuilderModifier
        if self.__class__.__name__ == "BuilderModifier":
            return 
        # assert everything is builder class variants
        assert isinstance(entity, WorkflowBuilder | CommandToolBuilder | CodeTool)

    def modify(self, entity: Workflow | CommandTool | CodeTool) -> Any:
        entity = self.do_modify(entity)
        entity = self.do_cleanup(entity)
        return entity
    
    def do_modify(self, entity: Workflow | CommandTool | CodeTool) -> Any:
        # ensure everything is a builder
        self._ensure_builders(entity)
        
        # workflow
        if isinstance(entity, Workflow):
            for step in entity.step_nodes.values():
                step.tool = self.do_modify(step.tool)
            # workflow itself
            return self.handle_workflow(entity)
        
        # cmdtool
        elif isinstance(entity, CommandTool):
            return self.handle_cmdtool(entity)
        
        # codetool
        elif isinstance(entity, CodeTool):
            return self.handle_codetool(entity)
        
        else:
            raise RuntimeError()
    
    # Override these methods in inheriting classes
    def handle_workflow(self, workflow: Workflow) -> Any:
        """apply modifications to a workflow in-place"""
        return workflow
    
    def handle_cmdtool(self, cmdtool: CommandTool) -> Any:
        """apply modifications to a cmdtool in-place"""
        return cmdtool
    
    def handle_codetool(self, codetool: CodeTool) -> Any:
        """apply modifications to a codetool in-place"""
        return codetool
    
    def do_cleanup(self, entity: Workflow | CommandTool | CodeTool) -> Any:
        """
        apply final necessary modifications to main entity 
        (if modifications have made it invalid)
        """
        return entity

