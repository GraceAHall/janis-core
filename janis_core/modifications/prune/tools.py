

from collections import defaultdict
from typing import Tuple

from janis_core import WorkflowBuilder, CommandToolBuilder, ToolInput, ToolArgument
from janis_core.workflow.workflow import StepNode
from janis_core.operators.selectors import InputSelector
from janis_core.translations.common import trace
from janis_core import translation_utils as utils
from janis_core.translation_utils import DTypeType
from janis_core import settings
from janis_core.settings.translate import ESimplification
from .history import TaskIOCollector

def prune_tools_and_sources(main_wf: WorkflowBuilder, tools: dict[str, CommandToolBuilder]) -> None:
    for tool in tools.values():
        prune(main_wf, tool)

def prune(main_wf: WorkflowBuilder, tool: CommandToolBuilder) -> None:
    """
    1. identify set of valid inputs / outputs
    2. prune invalid tool inputs, arguments, outputs, and step sources
    """

    if settings.translate.SIMPLIFICATION == ESimplification.ON:
        collector = TaskIOCollector(tool)
        collector.collect(main_wf)
        valid_inp_ids = _get_valid_inputs_normal(main_wf, tool, collector)
        valid_out_ids = _get_valid_outputs_normal(main_wf, tool, collector)
    
    elif settings.translate.SIMPLIFICATION == ESimplification.AGGRESSIVE:
        valid_inp_ids = _get_valid_inputs_aggr(tool)
        valid_out_ids = _get_valid_outputs_aggr(tool)

    # prune tool inputs, arguments, outputs, and step sources feeding tool inputs
    _prune_tool(main_wf, tool.id(), valid_inp_ids, valid_out_ids)

def _get_valid_inputs_aggr(tool: CommandToolBuilder) -> set[str]:
    return set([x.id() for x in tool._inputs if not x.input_type.optional or x.default is not None])

def _get_valid_outputs_aggr(tool: CommandToolBuilder) -> set[str]:
    return set([x.id() for x in tool._outputs if not x.output_type.optional])

def _get_valid_inputs_normal(main_wf: WorkflowBuilder, tool: CommandToolBuilder, collector: TaskIOCollector) -> set[str]:
    """get the tinputs which are needed for this simplification mode. """

    ### TINPUTS FED VIA DYNAMIC VALUES ###
    # identifying which tinputs need to be fed via step.sources
    valid_tinput_ids: set[str] = set() 
    # identify tinputs which need to be kept based on step.sources
    valid_tinput_ids = valid_tinput_ids | _get_step_referenced_tinputs(collector)
    # identify tinputs which optional files with default referencing another input
    valid_tinput_ids = valid_tinput_ids | _get_optional_file_inputs_w_default(tool)
    # identify tinputs which are referenced in tool outputs
    valid_tinput_ids = valid_tinput_ids | _get_output_referenced_tinputs(main_wf, tool)

    ### TINPUTS FED VIA STATIC VALUES ###
    # identify tinputs which have a single static value as source & migrate the source to tool default
    _migrate_single_statics_to_defaults(valid_tinput_ids, collector, tool)
    _prune_sources(main_wf, tool.id(), valid_tinput_ids)

    ### TINPUTS NOT FED IN WORKFLOW BUT REFER TO VALID TINPUTS ###
    # add tinputs which reference a previously validated tinput
    valid_tinput_ids = valid_tinput_ids | _get_tinput_reference_tinputs(tool, valid_tinput_ids)
    # add tinputs which have a non-null default
    valid_tinput_ids = valid_tinput_ids | _get_default_tinputs(tool, valid_tinput_ids)
    
    return valid_tinput_ids

def _get_valid_outputs_normal(main_wf: WorkflowBuilder, tool: CommandToolBuilder, collector: TaskIOCollector) -> set[str]:
    """
    get the toutputs which are needed for this simplification mode. 
    """
    filtered_toutputs: set[str] = set()

    for toutput_id, history in collector.output_register.items():
        if not history.is_optional:
            filtered_toutputs.add(toutput_id)
        elif len(history.sources) >= 1:
            filtered_toutputs.add(toutput_id)
        else:
            continue 

    return filtered_toutputs

def _get_step_referenced_tinputs(collector: TaskIOCollector) -> set[str]:
    """
    get the tinputs which are needed based on step inputs
    """
    filtered_tinputs: set[str] = set()
    
    for tinput_id, history in collector.input_register.items():
        # RULE 1: mandatory tool inputs are always kept
        if not history.is_optional:  
            filtered_tinputs.add(tinput_id)
        # RULE 2: tool inputs which are fed by mandatory types are kept
        elif len(history.mandatory_input_sources) >= 1:
            filtered_tinputs.add(tinput_id)
        # RULE 3: if has multiple sources, keep
        elif len(history.sources) >= 2:
            filtered_tinputs.add(tinput_id)
        # RULE 4: if has step connections, keep
        elif len(history.connection_sources) >= 1:
            filtered_tinputs.add(tinput_id)
        # RULE 5: if weird sources, keep
        elif len(history.other_sources) >= 1:
            filtered_tinputs.add(tinput_id)
        # RULE 6: (edge case) if tool used in 2+ steps, but tinput has only 1 source, keep.
        #         this is needed because if we are driving the tinput's value from a source in 
        #         one step, then it's value is driven by its default in another. they could be different. 
        elif len(history.sources) == 1 and collector.step_count >= 2:
            filtered_tinputs.add(tinput_id)
        else:
            continue
        # # RULE 5: if only has single placeholder source, ignore
        # elif len(history.sources) == 1 and len(history.placeholder_sources) == 1:
        #     continue
        # # RULE 6: if has 1+ sources which are workflow inputs, keep
        # elif len(history.input_sources) >= 1:
        #     tinputs_to_keep.add(tinput_id)
        # else:
        #     continue
    
    return filtered_tinputs

def _get_optional_file_inputs_w_default(tool: CommandToolBuilder) -> set[str]:
    filtered_tinputs: set[str] = set()
    for tinput in tool._inputs:
        dtt = utils.get_dtt(tinput.input_type) # type: ignore
        if dtt == DTypeType.FILE:
            if tinput.input_type.optional and tinput.default is not None:
                filtered_tinputs.add(tinput.id())
    return filtered_tinputs

def _get_output_referenced_tinputs(main_wf: WorkflowBuilder, tool: CommandToolBuilder) -> set[str]:
    # TODO check if the output is consumed as a source somewhere else in the workflow. 
    # if not we can remove it. 
    filtered_tinputs: set[str] = set()
    for tout in tool._outputs:
        ref_vars = trace.trace_referenced_variables(tout, tool)
        filtered_tinputs = filtered_tinputs | ref_vars
    return filtered_tinputs

def _migrate_single_statics_to_defaults(
    valid_tinput_ids: set[str], 
    collector: TaskIOCollector, 
    tool: CommandToolBuilder
    ) -> None:
    """
    moves static values to tool input defaults. 
    returns list of respective input nodes so these can be removed from step sources (and therefore workflow). 
    """
    for tinput_id, history in collector.input_register.items():
        if tinput_id in valid_tinput_ids:
            continue
        if len(history.sources) == 1 and len(history.placeholder_sources) == 1:
            node = history.input_sources[0].value.input_node
            tinput = [x for x in tool._inputs if x.id() == tinput_id][0] 
            tinput.default = node.default

def _get_default_tinputs(tool: CommandToolBuilder, valid_tinput_ids: set[str]) -> set[str]:
    extra_tinput_ids: set[str] = set()
    for tinput in tool._inputs:
        if tinput.id() not in valid_tinput_ids and tinput.default is not None:
            extra_tinput_ids.add(tinput.id())
    return extra_tinput_ids

def _get_tinput_reference_tinputs(tool: CommandToolBuilder, valid_tinput_ids: set[str]) -> set[str]:
    """
    Gets the tinputs which have a reference to step input tinputs
    eg: 
        step_input_ids = {'myfile'}
        tool inputs = [
        ToolInput("myfile", File()),
        ToolInput("myfilename", Filename(prefix=InputSelector("myfile"), extension=""))
        ]
    we should keep "myfilename" because it references "myfile"
    """
    extra_tinput_ids: set[str] = set()
    for tinput in tool._inputs:
        # early exit for previously validated tinputs
        if tinput.id() in valid_tinput_ids:
            continue
        
        # reference tracing for unvalidated tinputs - do they link to a validated tinput?
        refs = trace.trace_referenced_variables(tinput, tool)
        for ref in refs:
            if ref in valid_tinput_ids:
                extra_tinput_ids.add(tinput.id())
                break
    return extra_tinput_ids

def _prune_sources(
    local_wf: WorkflowBuilder, 
    tool_id: str, 
    valid_tinput_ids: set[str],
    ) -> None:
    for step in local_wf.step_nodes.values():
        if isinstance(step.tool, WorkflowBuilder):
            _prune_sources(step.tool, tool_id, valid_tinput_ids)
        elif isinstance(step.tool, CommandToolBuilder) and step.tool.id() == tool_id:
            _do_prune_tool_sources(step, valid_tinput_ids)
        else:
            continue

def _do_prune_tool_sources(step: StepNode, valid_tinput_ids: set[str]) -> None:
    # remove sources which are not needed
    invalid_sources = set(step.sources.keys()) - valid_tinput_ids
    for tinput_id in invalid_sources:
        del step.sources[tinput_id]

def _prune_tool(
    local_wf: WorkflowBuilder, 
    tool_id: str, 
    valid_tinput_ids: set[str],
    valid_toutput_ids: set[str]
    ) -> None:
    for step in local_wf.step_nodes.values():
        if isinstance(step.tool, WorkflowBuilder):
            _prune_tool(step.tool, tool_id, valid_tinput_ids, valid_toutput_ids)
        elif isinstance(step.tool, CommandToolBuilder) and step.tool.id() == tool_id:
            _do_prune_tool_inputs(step.tool, valid_tinput_ids)
            _do_prune_tool_arguments(step.tool, valid_tinput_ids)
            _do_prune_tool_outputs(step.tool, valid_toutput_ids)
        else:
            continue

def _do_prune_tool_inputs(tool: CommandToolBuilder, valid_tinput_ids: set[str]) -> None:
    # early exit
    if not tool._inputs:
        return 
    
    items_to_delete: list[int] = []
    for i, tinput in enumerate(tool._inputs):     # type: ignore
        if tinput.id() not in valid_tinput_ids:
            items_to_delete.append(i)
    
    for i in sorted(items_to_delete, reverse=True):
        del tool._inputs[i]     # type: ignore

def _do_prune_tool_arguments(tool: CommandToolBuilder, valid_tinput_ids: set[str]) -> None:
    """
    S1 ---
    [DLTE] arg: -p
    [DLTE] arg: InputSelector("not exists")
    
    S2 ---
    [KEEP] arg: -p
    [DLTE] arg: prefix="-p", InputSelector("not exists")
    
    S3 ---
    [DLTE] arg: InputSelector("not exists")
    [DLTE] arg: InputSelector("not exists")

    if has prefix and not exists, delete
    if no prefix and not exists
    """
    # early exit
    if not tool._arguments:
        return 
    
    items_to_delete: list[int] = []
    inputs_args = _ordered_tool_inputs_args(tool)
    
    for i, (idx, entity) in enumerate(inputs_args):
        if isinstance(entity, ToolArgument):
            should_delete = _has_invalid_input_ref(entity, tool, valid_tinput_ids)
            if should_delete:
                
                # should the preceeding arg also be deleted? 
                if entity.prefix is None:  # S2 above
                    preceeding = [(idx, entity) for idx, entity in inputs_args[:i] if isinstance(entity, ToolArgument)]
                    if preceeding:
                        prev_idx, prev_arg = preceeding[-1]
                        if prev_idx not in items_to_delete:
                            if prev_arg.prefix is not None:  # S1 / S3 above
                                items_to_delete.append(prev_idx)
                
                # add this arg to delete pool
                items_to_delete.append(idx)

    # do deletes
    for idx in sorted(items_to_delete, reverse=True):
        del tool._arguments[idx]     # type: ignore
    
def _do_prune_tool_outputs(tool: CommandToolBuilder, valid_toutput_ids: set[str]) -> None:
    # early exit
    if not tool._outputs:
        return 
    
    items_to_delete: list[int] = []
    for i, toutput in enumerate(tool._outputs):     # type: ignore
        if toutput.id() not in valid_toutput_ids:
            items_to_delete.append(i)
    
    for i in sorted(items_to_delete, reverse=True):
        del tool._inputs[i]     # type: ignore

def _has_invalid_input_ref(targ: ToolArgument, tool: CommandToolBuilder, valid_tinput_ids: set[str]) -> bool:
    refs = trace.trace_entities(targ, tool)
    input_refs = [ref for ref in refs if isinstance(ref, InputSelector)]
    if not input_refs:
        return False
    if not all([ref.input_to_select in valid_tinput_ids for ref in input_refs]):
        return True 
    return False
        
def _ordered_tool_inputs_args(tool: CommandToolBuilder) -> list[Tuple[int, ToolInput | ToolArgument]]:
    """
    orders tool inputs and args as they should appear in a shell cmd.
    adds the index of each Input / Argument in tool._arguments / tool._inputs so can access them later. 
    """

    def _extract_pos(entity: ToolInput | ToolArgument) -> int:
        return 0 if entity.position is None else entity.position
    
    # group inps / args by position (args have priority)
    positions: dict[int, list[Tuple[int, ToolInput | ToolArgument]]] = defaultdict(list)
    if tool._arguments is not None:
        for i, arg in enumerate(tool._arguments):
            positions[_extract_pos(arg)].append((i, arg))
    if tool._inputs is not None:
        for i, inp in enumerate(tool._inputs):
            positions[_extract_pos(inp)].append((i, arg))
    
    # order by position & return
    ordered: list[Tuple[int, ToolInput | ToolArgument]] = []
    for pos in sorted(positions.keys()):
        ordered.extend(positions[pos])
    return ordered




    

