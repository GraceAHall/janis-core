
from typing import Any
from janis_core import CommandTool, Workflow, WorkflowBuilder
from .EntityModifier import EntityModifier


class BuilderModifier(EntityModifier): 

    def handle_workflow(self, workflow: Workflow) -> Any:
        builder = WorkflowBuilder(
            identifier=workflow.id(),
            friendly_name=workflow.friendly_name(),
            version=workflow.version(),
            metadata=workflow.metadata,
            tool_provider=workflow.tool_provider(),
            tool_module=workflow.tool_module(),
            doc=workflow.doc()
        )

        # Add Workflow attributes
        builder.nodes = workflow.nodes
        builder.input_nodes = workflow.input_nodes
        builder.step_nodes = workflow.step_nodes
        builder.output_nodes = workflow.output_nodes
        builder.has_scatter = workflow.has_scatter
        builder.has_subworkflow = workflow.has_subworkflow
        builder.has_multiple_inputs = workflow.has_multiple_inputs

        # Add Tool attributes
        builder.uuid = workflow.uuid
        builder.connections = workflow.connections
        return builder
    
    def handle_cmdtool(self, cmdtool: CommandTool) -> Any:
        builder = cmdtool.to_command_tool_builder()
        builder.uuid = cmdtool.uuid
        return builder
    