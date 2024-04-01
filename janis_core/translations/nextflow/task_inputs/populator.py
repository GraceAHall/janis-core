

import os
from typing import Any, Optional

from janis_core import translation_utils as utils
from janis_core import Tool, CommandToolBuilder, PythonTool, WorkflowBuilder
from janis_core import settings
from janis_core.types import File

from janis_core.translation_utils import DTypeType
from janis_core.introspection.workflow_inputs import get_true_workflow_inputs

from janis_core.translations.nextflow import naming
from janis_core.translations.nextflow import params
from janis_core.translations.nextflow.model import VariableType
from . import main as ti


# main module funcs
def populate_task_inputs(tool: Tool, main_wf: Optional[WorkflowBuilder]=None) -> None:
    assert(isinstance(tool, CommandToolBuilder | PythonTool | WorkflowBuilder))
    if settings.translate.nextflow.ENTITY == 'tool' and isinstance(tool, CommandToolBuilder | PythonTool):
        _populate_task_inputs_toolmode(tool)
    elif settings.translate.nextflow.ENTITY == 'workflow' and isinstance(main_wf, WorkflowBuilder):
        _populate_task_inputs_workflowmode(main_wf, main_wf)
    else:
        raise RuntimeError(f"{tool.id()}: {type(tool)}")
    ti.report()

# TOOL MODE 
def _populate_task_inputs_toolmode(tool: CommandToolBuilder | PythonTool) -> None:
    """how to populate task inputs when doing tool translation (toolmode)"""
    if isinstance(tool, CommandToolBuilder):
        _populate_task_inputs_commandtool(tool)
    elif isinstance(tool, PythonTool):
        _populate_task_inputs_pythontool(tool)
    else:
        raise RuntimeError
    
# WORKFLOW MODE
def _populate_task_inputs_workflowmode(subwf: WorkflowBuilder, main_wf: WorkflowBuilder) -> None:
    """how to populate task inputs when doing workflow translation (workflowmode)"""
    for step in subwf.step_nodes.values():
        
        # if not already done, formulate task inputs for step task
        if not ti.existsall(step.tool): # type: ignore
            if isinstance(step.tool, CommandToolBuilder):
                _populate_task_inputs_commandtool(step.tool)
            elif isinstance(step.tool, PythonTool):
                _populate_task_inputs_pythontool(step.tool)
            elif isinstance(step.tool, WorkflowBuilder):
                _populate_task_inputs_subwf(step.tool)
        
        # if subworkflow, do recursively for subworkflow
        if isinstance(step.tool, WorkflowBuilder):
            _populate_task_inputs_workflowmode(step.tool, main_wf)

    # final task is the main workflow
    if subwf.id() == main_wf.id():
        assert(not ti.existsall(main_wf))
        _populate_task_inputs_mainwf(main_wf)

# WORKFLOW MODE: COMMANDTOOL SUBTASK
def _populate_task_inputs_commandtool(tool: CommandToolBuilder) -> None:
    # if settings.translate.SIMPLIFICATION in [ESimplification.AGGRESSIVE, ESimplification.OFF]:
    populate_scripts(tool)
    for tinput in tool.tool_inputs(): # and check DataTypeType? utils.get_dtt(tinput.intype)
        if tinput.default is not None:
            ti_value = tinput.default
            ti.update(tool.id(), tinput.id(), VariableType.STATIC, ti_value)
        else:
            ti_value = gen_task_input_value_process(tool, tinput.id())
            ti.update(tool.id(), tinput.id(), VariableType.INPUT, ti_value)

# WORKFLOW MODE: PYTHONTOOL SUBTASK
def _populate_task_inputs_pythontool(tool: PythonTool) -> None:
    populate_code_file(tool)
    for tinput in tool.tool_inputs():
        ti_value = gen_task_input_value_process(tool, tinput.id())
        ti.update(tool.id(), tinput.id(), VariableType.INPUT, ti_value)

# WORKFLOW MODE: WORKFLOW SUBTASK
def _populate_task_inputs_subwf(subwf: WorkflowBuilder) -> None:
    for tinput in subwf.tool_inputs():
        ti_value = gen_task_input_value_workflow(subwf, tinput.id())
        ti.update(subwf.id(), tinput.id(), VariableType.INPUT, ti_value)

# WORKFLOW MODE: MAIN WORKFLOW
def _populate_task_inputs_mainwf(main_wf: WorkflowBuilder) -> None:
    """
    how to populate task inputs for main wf.
    all the valid workflow inputs start as a param.
    """
    all_tinput_ids = set([x.id() for x in main_wf.tool_inputs()])
    param_tinput_ids = get_true_workflow_inputs(main_wf)
    ignored_tinput_ids = all_tinput_ids - param_tinput_ids

    # param inputs
    for tinput_id in param_tinput_ids:
        tinput = [x for x in main_wf.tool_inputs() if x.id() == tinput_id][0]
        param = params.register(tinput, task_id=main_wf.id(), subtype='main_workflow')
        value = f'params.{param.name}'
        ti.update(main_wf.id(), tinput_id, VariableType.PARAM, value)
    
    # ignored inputs
    for tinput_id in ignored_tinput_ids:
        ti.update(main_wf.id(), tinput_id, VariableType.IGNORED, None)
    

### HELPER METHODS ###

def populate_code_file(tool: PythonTool) -> None:
    if not isinstance(tool, PythonTool):
        return 
    
    path = f'{settings.translate.nextflow.TEMPLATES_OUTDIR}{os.sep}{tool.id()}.py'
    params.add(
        task_id=tool.id(),
        tinput_id=settings.translate.nextflow.PYTHON_CODE_FILE,
        subtype='sub_tool',
        janis_dtype=File(),
        default=path
    )

    # update task inputs
    ti.update(
        tool_id=tool.id(),
        tinput_id=settings.translate.nextflow.PYTHON_CODE_FILE,
        ttype=VariableType.INPUT, 
        value=settings.translate.nextflow.PYTHON_CODE_FILE
    )

def populate_scripts(tool: CommandToolBuilder) -> None:
    # for CommandTools, need to have a task input for each script in files_to_create.
    # *unless translation is from Galaxy, where these will already be inputs. 
    if settings.ingest.SOURCE == 'galaxy' or not tool._files_to_create:
        return 
    
    for filename in tool._files_to_create.keys():  # type: ignore
        # get the file path to where the script will appear in the translation
        assert(isinstance(filename, str))

        # ignoring shell script parsed from WDL
        if tool.is_shell_script and filename == 'script.sh':
            continue 

        path = os.path.join(settings.translate.nextflow.TEMPLATES_OUTDIR, filename)
        
        # generate a name for this input
        if len(tool._files_to_create) == 1:        # type: ignore
            name = 'script'
        else:
            name = naming.process.files_to_create_script(filename)

        # create param for nextflow.config & so we can get the param for process calls
        params.add(
            task_id=tool.id(),
            tinput_id=name,
            subtype='sub_tool',
            janis_dtype=File(),
            default=path
        )

        # update task inputs
        ti.update(
            tool_id=tool.id(), 
            tinput_id=name, 
            ttype=VariableType.INPUT, 
            value=name
        )

def gen_task_input_value_process(tool: CommandToolBuilder | PythonTool, tinput_id: str) -> Any:
    tinput = [x for x in tool.tool_inputs() if x.id() == tinput_id][0]
    # is_duplicate = self.duplicate_datatype_exists(tinput)
    dtt = utils.get_dtt(tinput.intype)

    if dtt == DTypeType.SECONDARY_ARRAY:
        value = naming.process.secondaries_array(tinput)
    elif dtt == DTypeType.SECONDARY:
        value = naming.process.generic(tinput)
    elif dtt == DTypeType.FILE_PAIR_ARRAY:
        value = naming.process.file_pair_array(tinput)
    elif dtt == DTypeType.FILE_PAIR:
        value = naming.process.file_pair(tinput)
    else:
        value = naming.process.generic(tinput)
    
    return value

def gen_task_input_value_workflow(tool: WorkflowBuilder, tinput_id: str) -> Any:
    tinput = [x for x in tool.tool_inputs() if x.id() == tinput_id][0]
    value = naming.process.generic(tinput)
    value = f'ch_{value}'
    return value

                

# class TaskInputsPopulator(ABC):
    
#     @abstractmethod
#     def populate(self) -> None:
#         ...


# class TaskInputsPopulatorMainWorkflow(TaskInputsPopulator):
    
#     def __init__(self, main_wf: WorkflowBuilder) -> None:
#         self.main_wf = main_wf

#     def populate(self) -> None:
#         if settings.translate.SIMPLIFICATION == ESimplification.OFF:
#             self.populate_task_inputs_extended()
#         elif settings.translate.SIMPLIFICATION in [ESimplification.AGGRESSIVE, ESimplification.ON]:
#             self.populate_task_inputs_pruned()
#         else:
#             raise RuntimeError

#     def populate_task_inputs_extended(self) -> None:
#         all_tinput_ids = set([x.id() for x in self.main_wf.tool_inputs()])
#         for tinput_id in all_tinput_ids:
#             ti_type = 'param'
#             tinput = [x for x in self.main_wf.tool_inputs() if x.id() == tinput_id][0]
#             subtype = 'main_workflow'
#             param = params.register(tinput, task_id=self.main_wf.id(), subtype=subtype)
#             value = f'params.{param.name}' 
#             task_inputs.update(self.main_wf.id(), ti_type, tinput_id, value)

#     def populate_task_inputs_pruned(self) -> None:
#         all_tinput_ids = set([x.id() for x in self.main_wf.tool_inputs()])
#         param_tinput_ids = get_true_workflow_inputs(self.main_wf)
#         ignored_tinput_ids = all_tinput_ids - param_tinput_ids

#         # param inputs
#         for tinput_id in param_tinput_ids:
#             ti_type = 'param'
#             tinput = [x for x in self.main_wf.tool_inputs() if x.id() == tinput_id][0]
#             subtype = 'main_workflow'
#             param = params.register(tinput, task_id=self.main_wf.id(), subtype=subtype)
#             value = f'params.{param.name}'
#             task_inputs.update(self.main_wf.id(), ti_type, tinput_id, value)
        
#         # ignored inputs
#         for tinput_id in ignored_tinput_ids:
#             ti_type = 'ignored'
#             value = None
#             task_inputs.update(self.main_wf.id(), ti_type, tinput_id, value)
    







# ### TASK INPUT POPULATION CLASSES ###


#     def categorise(self) -> None:
#         for tinput_id, history in self.histories.items():

#             ### file types
#             # RULE 0: anything passed via step output must be a task input
#             if history.supplied_value_via_connection:
#                 self.task_inputs.add(tinput_id)

#             # RULE 1: files (mandatory) are always task inputs
#             elif history.is_file and not history.is_optional:  
#                 self.task_inputs.add(tinput_id)
            
#             elif history.is_file:
#                 # RULE 2: files (optional) will be task inputs if 1+ values supplied
#                 if len(history.non_null_unique_values) >= 1:
#                     self.task_inputs.add(tinput_id)

#                 # RULE 3: files (optional) will be ignored if unused
#                 elif len(history.non_null_unique_values) == 0:
#                     self.ignored_inputs.add(tinput_id)
                
#                 else:
#                     raise RuntimeError

#             ### non-file types
#             else:
#                 # RULE 4: non-files will be task inputs if 2+ values supplied
#                 if len(history.non_null_unique_values) >= 2:
#                     self.task_inputs.add(tinput_id)
                
#                 elif len(history.unique_values) == 1 and len(history.non_null_unique_values) == 1:
#                     # RULE 5: non-files with single invariant InputNode value can be hardcoded param in task
#                     # TODO this is a weak check
#                     if list(history.non_null_unique_values)[0].startswith('Input:'):
#                         self.param_inputs.add(tinput_id)
                    
#                     # RULE 6: non-files with single invariant static value can be hardcoded static in task
#                     else:
#                         self.static_inputs.add(tinput_id)

#                 # RULE 7: non-files with single null value and single InputNode value must be task inputs
#                 elif len(history.unique_values) == 2 and len(history.non_null_unique_values) == 1:
#                     self.task_inputs.add(tinput_id)

#                 # RULE 8: non-files will be ignored if unused
#                 elif len(history.non_null_unique_values) == 0:
#                     self.ignored_inputs.add(tinput_id)
                
#                 else:
#                     raise RuntimeError