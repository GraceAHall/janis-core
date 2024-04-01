
from typing import Any
from collections import defaultdict

from janis_core import CommandToolBuilder, CodeTool, WorkflowBuilder, StringFormatter, Selector
from ..EntityModifier import EntityModifier
from .case import format_case
from .illegals import fix_illegals
from .updates import SelectorUpdater


#####################
### main modifier ###
#####################

class SymbolModifier(EntityModifier): 

    def __init__(self) -> None:
        self.id_map = {}

    # helper methods
    def generate_new_id(self, parent: WorkflowBuilder | CommandToolBuilder, entity: Any, text: str) -> str:
        text = format_case(entity, text)
        text = fix_illegals(parent, entity, text)
        return text
        
    def already_processed(self, entity: Any) -> bool:
        if not isinstance(entity, WorkflowBuilder | CommandToolBuilder):
            raise RuntimeError
        
        if isinstance(entity, WorkflowBuilder):
            if not all([x.uuid in self.id_map for x in entity.input_nodes.values()]):
                return False
            if not all([x.uuid in self.id_map for x in entity.step_nodes.values()]):
                return False
            if not all([x.uuid in self.id_map for x in entity.output_nodes.values()]):
                return False
        
        if isinstance(entity, CommandToolBuilder):
            if not all([x.uuid in self.id_map for x in entity._inputs]):
                return False
            if not all([x.uuid in self.id_map for x in entity._outputs]):
                return False
        
        return True

    def handle_workflow(self, workflow: WorkflowBuilder) -> Any:
        """
        only address inputs/steps/outputs at this stage
        """
        # don't reprocess if already done
        if self.already_processed(workflow):
            return workflow
        
        
        # workflow inputs
        new_inputs = {}
        for winp in sorted(workflow.input_nodes.values(), key=lambda x: x.id()):
            old_id = winp.id()
            new_id = self.generate_new_id(workflow, winp, old_id)
            winp.identifier = new_id
            new_inputs[new_id] = winp
            self.id_map[winp.uuid] = (old_id, new_id)
        workflow.input_nodes = new_inputs

        # workflow steps
        new_steps = {}
        for wstep in sorted(workflow.step_nodes.values(), key=lambda x: x.id()):
            old_id = wstep.id()
            new_id = self.generate_new_id(workflow, wstep, old_id)
            wstep.identifier = new_id
            new_steps[new_id] = wstep
            self.id_map[wstep.uuid] = (old_id, new_id)
        workflow.step_nodes = new_steps
        
        # workflow outputs
        new_outputs = {}
        for wout in sorted(workflow.output_nodes.values(), key=lambda x: x.id()):
            old_id = wout.id()
            new_id = self.generate_new_id(workflow, wout, old_id)
            self.id_map[wout.uuid] = (old_id, new_id)
            wout.identifier = new_id
            new_outputs[new_id] = wout
        workflow.output_nodes = new_outputs

        return workflow

    def handle_cmdtool(self, cmdtool: CommandToolBuilder) -> Any:
        # don't reprocess if already done
        if self.already_processed(cmdtool):
            return cmdtool
        
        # only address inputs/outputs at this stage
        for inp in sorted(cmdtool._inputs, key=lambda x: x.id()):
            old_id = inp.id()
            new_id = self.generate_new_id(cmdtool, inp, old_id)
            inp.tag = new_id
            self.id_map[inp.uuid] = (old_id, new_id)
        
        for out in sorted(cmdtool._outputs, key=lambda x: x.id()):
            old_id = out.id()
            new_id = self.generate_new_id(cmdtool, out, old_id)
            out.tag = new_id
            self.id_map[out.uuid] = (old_id, new_id)

        return cmdtool

    def handle_codetool(self, codetool: CodeTool) -> Any:
        """
        This may be possible, but would need to:
            1. convert the object to string repr
            2. make changes to the string repr
            3. convert back to object
        """
        # tool name
        # tool inputs
        # tool outputs
        return codetool
    
    def do_cleanup(self, entity: WorkflowBuilder | CommandToolBuilder | CodeTool) -> Any:
        """
        handle workflow / cmdtool ids here.
        address the now-invalid InputSelectors and StepOutputSelectors. 
        """
        # codetools ugh
        if isinstance(entity, CodeTool):
            return entity 
        
        # generate & assign ids for workflow / cmdtool
        old_id = entity.id()
        new_id = self.generate_new_id(entity, entity, entity.id())
        if isinstance(entity, WorkflowBuilder):
            entity._identifier = new_id
        elif isinstance(entity, CommandToolBuilder):
            entity._tool = new_id
        self.id_map[entity.uuid] = (old_id, new_id)
        
        # delegate to submethod
        if isinstance(entity, WorkflowBuilder):
            self.do_cleanup_workflow(entity)
        elif isinstance(entity, CommandToolBuilder):
            self.do_cleanup_cmdtool(entity)
        else:
            raise RuntimeError
        return entity
    
    def do_cleanup_cmdtool(self, cmdtool: CommandToolBuilder) -> Any:
        """TODO resource selectors? """

        # ToolInputs can involve Selectors
        for inp in cmdtool._inputs:
            SelectorUpdater(cmdtool, self.id_map).trace(inp)
        
        # ToolArguments can involve Selectors
        if cmdtool._arguments is not None:
            for arg in cmdtool._arguments:
                SelectorUpdater(cmdtool, self.id_map).trace(arg)
        
        # ToolOutputs can involve Selectors
        for out in cmdtool._outputs:
            SelectorUpdater(cmdtool, self.id_map).trace(out)
        
        # files / directories to create can involve Selectors
        if cmdtool._files_to_create is not None:
            assert isinstance(cmdtool._files_to_create, dict)
            for contents in cmdtool._files_to_create.values():
                if isinstance(contents, StringFormatter):
                    SelectorUpdater(cmdtool, self.id_map).trace(contents)
        
        if cmdtool._directories_to_create is not None:
            if isinstance(cmdtool._directories_to_create, list):
                items = cmdtool._directories_to_create
            else:
                items = [cmdtool._directories_to_create]
            for item in items:
                if isinstance(item, Selector):
                    SelectorUpdater(cmdtool, self.id_map).trace(item)

        # Tool resources can involve Selectors
        if cmdtool._cpus is not None:
            SelectorUpdater(cmdtool, self.id_map).trace(cmdtool._cpus)
        if cmdtool._disk is not None:
            SelectorUpdater(cmdtool, self.id_map).trace(cmdtool._disk)
        if cmdtool._memory is not None:
            SelectorUpdater(cmdtool, self.id_map).trace(cmdtool._memory)
        if cmdtool._time is not None:
            SelectorUpdater(cmdtool, self.id_map).trace(cmdtool._time)
    
    def do_cleanup_workflow(self, workflow: WorkflowBuilder) -> Any:
        # invert id_map so we can quickly fetch uuid from old_id
        # old_id -> [possible uuids] -> match uuid -> new_id
        inv_map = defaultdict(list)
        for uuid, (old_id, new_id) in self.id_map.items():
            inv_map[old_id].append(uuid)

        for step in workflow.step_nodes.values():
            self.do_cleanup(step.tool)
        
        # step inputs/when/scatter can involve Selectors
        for step in workflow.step_nodes.values():
            # fix scatter fields
            if step.scatter is not None and not isinstance(step.tool, CodeTool):
                updater = SelectorUpdater(workflow, self.id_map)
                id_map = updater.input_id_map(step.tool)            # type: ignore
                step.scatter.fields = [updater.get_new_id(x, id_map) for x in step.scatter.fields]
            
            # fix steptaginput references
            for source in step.sources.values():
                SelectorUpdater(workflow, self.id_map).trace(source)
            
            # update step inputs dict keys
            new_sources = {}
            for old_id, source in step.sources.items():
                possible_uuids = inv_map[old_id]
                if isinstance(step.tool, WorkflowBuilder):
                    tinp = [x for x in step.tool.input_nodes.values() if x.uuid in possible_uuids][0]
                    new_id = tinp.identifier
                elif isinstance(step.tool, CommandToolBuilder):
                    tinp = [x for x in step.tool._inputs if x.uuid in possible_uuids][0]
                    new_id = tinp.tag
                elif isinstance(step.tool, CodeTool):
                    new_id = old_id
                else:
                    raise RuntimeError
                source.ftag = new_id
                new_sources[new_id] = source
            step.sources = new_sources
            
            # update step when
            if step.when is not None:
                SelectorUpdater(workflow, self.id_map).trace(step.when)
        
        # workflow outputs can involve Selectors
        for wout in workflow.output_nodes.values():
            source = wout.source
            SelectorUpdater(workflow, self.id_map).trace(source)

        

