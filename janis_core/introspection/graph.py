

import networkx as nx 

from janis_core import WorkflowBuilder, CommandToolBuilder, PythonTool, Filename
from janis_core.workflow.workflow import StepNode, InputNode
from janis_core.translation_utils import get_dtt
from janis_core.translation_utils import DTypeType
import janis_core.translation_utils as utils
from dataclasses import dataclass, field
from .trace import trace_source_nodes

def is_optional(tinput: InputNode) -> bool:
    if isinstance(tinput.datatype, Filename):
        return True
    elif tinput.datatype.optional == True:  # type: ignore
        return True
    return False

"""
each workflow / subworkflow is a graph component. 
the main workflow is marked. 
"""

### HELPERS ###
def get_graph(workflow: WorkflowBuilder) -> nx.DiGraph:
    G = nx.DiGraph()
    G = _populate_nodes(G, workflow)
    G = _populate_edges(G, workflow)
    return G

def _populate_nodes(G: nx.DiGraph, workflow: WorkflowBuilder) -> nx.DiGraph:
    for step in workflow.step_nodes.values():
        G.add_node(step.id(), name=step.id(), ntype='step')
    return G

def _populate_edges(G: nx.DiGraph, workflow: WorkflowBuilder) -> nx.DiGraph:
    for step in workflow.step_nodes.values():
        for src in step.sources.values():
            nodes = trace_source_nodes(src, workflow)
            nodes = [n for n in nodes if isinstance(n, StepNode)]
            for n in nodes:
                G.add_edge(n.id(), step.id())
    return G


### STEP ORDER ###
def get_step_order(workflow: WorkflowBuilder) -> list[str]:
    G = get_graph(workflow)
    assert nx.is_directed_acyclic_graph(G), 'workflow graph must be a DAG'
    return list(nx.lexicographical_topological_sort(G, key=lambda x: len(nx.descendants(G, x))))


### PRIMARY INPUTS ###
@dataclass
class InputCandidate:
    tag: str
    dtype: DTypeType
    optional: bool
    steps: list[str] = field(default_factory=list)
    scatters: list[str] = field(default_factory=list)

def get_primary_workflow_inputs(workflow: WorkflowBuilder) -> list[str]:        
    candidates_all = _get_candidates(workflow)
    candidates_dtype = _filter_dtype(candidates_all)
    candidates_nodes = _filter_nodes(candidates_dtype, workflow)
    candidates_scatter = _filter_scatter(candidates_nodes)

    # priority: scatter > nodes > dtype > all
    if candidates_scatter:
        candidates_final = candidates_scatter
    elif candidates_nodes:
        candidates_final = candidates_nodes
    elif candidates_dtype:
        candidates_final = candidates_dtype
    else:
        candidates_final = candidates_all
    return [inp.tag for inp in candidates_final]

def _get_candidates(workflow: WorkflowBuilder) -> list[InputCandidate]:        
    candidates = _init_candidates(workflow)
    candidates = _annotate_candidates_steps(candidates, workflow)
    candidates = _annotate_candidates_scatter(candidates, workflow)
    return list(candidates.values())

def _init_candidates(workflow: WorkflowBuilder) -> dict[str, InputCandidate]:
    the_dict = {}
    for winp in workflow.input_nodes.values():
        tag = winp.id()
        dtt = get_dtt(winp.datatype)
        the_dict[winp.id()] = InputCandidate(tag, dtt, is_optional(winp))
    return the_dict
    
def _annotate_candidates_steps(the_dict: dict[str, InputCandidate], workflow: WorkflowBuilder) -> dict[str, InputCandidate]:
    # steps
    for step in workflow.step_nodes.values():
        for src in step.sources.values():
            nodes = trace_source_nodes(src, workflow)
            nodes = [n for n in nodes if isinstance(n, InputNode)]
            for node in nodes:
                the_dict[node.id()].steps.append(step.id())
    return the_dict

def _annotate_candidates_scatter(the_dict: dict[str, InputCandidate], workflow: WorkflowBuilder) -> dict[str, InputCandidate]:
    # scatters
    for step in workflow.step_nodes.values():
        if step.scatter is None:
            continue 
        sources = [src for tinput_id, src in step.sources.items() if tinput_id in step.scatter.fields]
        assert len(sources) >= 1
        for src in sources:
            nodes = trace_source_nodes(src, workflow)
            nodes = [n for n in nodes if isinstance(n, InputNode)]
            for node in nodes:
                the_dict[node.id()].scatters.append(step.id())
    return the_dict

def _filter_dtype(candidates: list[InputCandidate]) -> list[InputCandidate]:
    file_types = [
        DTypeType.FILENAME,
        DTypeType.FILE,
        DTypeType.FILE_ARRAY,
        DTypeType.FILE_PAIR,
        DTypeType.FILE_PAIR_ARRAY,
        DTypeType.SECONDARY,
        DTypeType.SECONDARY_ARRAY,
    ]
    candidates = [inp for inp in candidates if not inp.optional]
    candidates = [inp for inp in candidates if inp.dtype in file_types]
    return candidates

def _filter_nodes(candidates: list[InputCandidate], workflow: WorkflowBuilder) -> list[InputCandidate]:
    G = get_graph(workflow)
    head_nodes = [n for n in G.nodes if G.in_degree(n) == 0]
    new_candidates = [] 

    for candidate in candidates:
        isteps = set(candidate.steps) & set(head_nodes)
        # only appears in head nodes
        if len(isteps) >= 1:
            if set(isteps) == set(candidate.steps):
                new_candidates.append(candidate)
    return new_candidates

def _filter_scatter(candidates: list[InputCandidate]) -> list[InputCandidate]:
    # has scatter? 
    has_scatter = False 
    for c in candidates:
        if c.scatters:
            has_scatter = True
            break

    if not has_scatter:
        return candidates 
    return [n for n in candidates if len(n.scatters) >= 1]




"""

def _populate_nodes(G: nx.DiGraph, workflow: WorkflowBuilder) -> nx.DiGraph:
    for winp in workflow.input_nodes.values():
        G.add_node(winp.id(), name=winp.id(), ntype='input')
    for step in workflow.step_nodes.values():
        G.add_node(step.id(), name=step.id(), ntype='step')
    for wout in workflow.output_nodes.values():
        G.add_node(wout.id(), name=wout.id(), ntype='output')
    return G

def _populate_nodes_io(G: nx.DiGraph, workflow: WorkflowBuilder) -> nx.DiGraph:
    for winp in workflow.input_nodes.values():
        G.nodes[winp.id()]['inputs'] = {}
        G.nodes[winp.id()]['outputs'] = {winp.id(): get_dtt(winp.datatype)}
    for step in workflow.step_nodes.values():
        G.nodes[step.id()]['inputs'] = _get_step_inputs(step)
        G.nodes[step.id()]['outputs'] = _get_step_outputs(step)
    for wout in workflow.output_nodes.values():
        G.nodes[wout.id()]['inputs'] = {wout.id(): get_dtt(wout.datatype)}
        G.nodes[wout.id()]['outputs'] = {}
    return G

def _get_step_inputs(step: StepNode) -> dict[str, DTypeType]:
    inputs = {}
    for tinput_id, src in step.sources.items():
        if isinstance(step.tool, WorkflowBuilder):
            tinput = step.tool.input_nodes[tinput_id]
            dtype = get_dtt(tinput.datatype)
        elif isinstance(step.tool, CommandToolBuilder):
            tinput = [x for x in step.tool._inputs if x.id() == tinput_id][0]
            dtype = get_dtt(tinput.input_type) # type: ignore
        elif isinstance(step.tool, PythonTool):
            tinput = [x for x in step.tool.inputs() if x.id() == tinput_id][0]
            dtype = get_dtt(tinput.intype)
        inputs[tinput_id] = dtype
    return inputs

def _get_step_outputs(step: StepNode) -> dict[str, DTypeType]:
    outputs = {}
    if isinstance(step.tool, WorkflowBuilder):
        for output in step.tool.output_nodes.values():
            outputs[output.id()] = get_dtt(output.datatype)
    elif isinstance(step.tool, CommandToolBuilder):
        for output in step.tool._outputs:
            outputs[output.id()] = get_dtt(output.output_type)  # type: ignore
    elif isinstance(step.tool, PythonTool):
        for output in step.tool.outputs():
            outputs[output.id()] = get_dtt(output.outtype)
    return outputs


"""