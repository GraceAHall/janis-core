

import unittest
import os 
import regex as re
import yaml
from typing import Any, Optional

from janis_core import settings
from janis_core.settings.translate import ERenderCmd, ESimplification
from janis_core.messages import configure_logging
from janis_core.messages import load_loglines
from janis_core.messages import ErrorCategory

from janis_core import CommandToolBuilder
from janis_core import WorkflowBuilder
from janis_core import CodeTool
from janis_core import StepOutputSelector
from janis_core import InputNodeSelector

from janis_core.ingestion import ingest
from janis_core.translations import translate
from janis_core.translations import nextflow
from janis_core.translations import WdlTranslator
from janis_core.translations import NextflowTranslator
from janis_core.translations import CwlTranslator

from janis_core.modifications import to_builders
from janis_core.modifications import order_steps_topologically
from janis_core.modifications import ensure_containers
from janis_core.modifications import simplify
from janis_core.modifications import refactor_symbols
from janis_core.modifications import wrap_tool_in_workflow

from janis_core.tests.testtools import FileOutputPythonTestTool
from janis_core.tests.testtools import GridssTestTool
from janis_core.tests.testtools import FastqcTestTool
from janis_core.tests.testtools import OperatorResourcesTestTool
from janis_core.tests.testworkflows import PruneFlatTW
from janis_core.tests.testworkflows import PruneNestedTW
from janis_core.tests.testworkflows import AssemblyTestWF
from janis_core.tests.testworkflows import IllegalSymbolsTestWF
from janis_core.tests.testworkflows import UnwrapTestWF
from janis_core.tests.testworkflows import SubworkflowTestWF
from janis_core.tests.testworkflows import SimplificationScatterTestWF


CWL_TESTDATA_PATH = os.path.join(os.getcwd(), 'janis_core/tests/data/cwl')
GALAXY_TESTTOOL_PATH = os.path.join(os.getcwd(), 'janis_core/tests/data/galaxy/wrappers')
GALAXY_TESTWF_PATH = os.path.join(os.getcwd(), 'janis_core/tests/data/galaxy/workflows')
JANIS_TESTDATA_PATH = os.path.join(os.getcwd(), 'janis_core/tests/data/janis')
WDL_TESTDATA_PATH = os.path.join(os.getcwd(), 'janis_core/tests/data/wdl')


def _reset_global_settings() -> None:
    configure_logging()    # reset the messages logfile
    nextflow.task_inputs.clear()
    nextflow.params.clear()
    settings.ingest.SAFE_MODE = True
    settings.testing.TESTMODE = True
    settings.translate.RENDERCMD = ERenderCmd.ON
    settings.translate.SIMPLIFICATION = ESimplification.OFF
    settings.translate.DEST = ''
    settings.ingest.SOURCE = ''
    settings.ingest.galaxy.GEN_IMAGES = False
    settings.ingest.galaxy.DISABLE_CONTAINER_CACHE = False
    settings.ingest.cwl.INGEST_JAVASCRIPT_EXPRESSIONS = True
    settings.ingest.cwl.REQUIRE_CWL_VERSION = False
    settings.datatypes.ALLOW_UNPARSEABLE_DATATYPES = True
    settings.graph.ALLOW_UNKNOWN_SOURCE = True
    settings.graph.ALLOW_UNKNOWN_SCATTER_FIELDS = True
    settings.graph.ALLOW_INCORRECT_NUMBER_OF_SOURCES = True
    settings.graph.ALLOW_NON_ARRAY_SCATTER_INPUT = True
    settings.graph.ALLOW_INCOMPATIBLE_TYPES = True
    settings.validation.STRICT_IDENTIFIERS = False
    settings.validation.VALIDATE_STRINGFORMATTERS = False
    settings.translate.ALLOW_EMPTY_CONTAINER = True
    settings.translate.nextflow.ENTITY = 'workflow'
    settings.translate.AS_WORKFLOW = False

def _run(filepath: str, srcfmt: str, destfmt: str, mode: Optional[str]=None, simplification: Optional[str]=None) -> Any:
    internal = ingest(filepath, srcfmt)
    return translate(internal, destfmt, mode, simplification, export_path='./translated')

def _is_nf_process(filecontents: str) -> bool:
    pattern = r'process.*?\{'
    if re.findall(pattern, filecontents):
        return True
    return False

def _is_cwl_clt(filecontents: str) -> bool:
    if 'class: CommandLineTool' in filecontents:
        return True
    return False

def _is_wdl_task(filecontents: str) -> bool:
    pattern = r'task.*?\{'
    if re.findall(pattern, filecontents):
        return True
    return False

def _get_cwl_inputs(clt_text: str) -> list[str]:
    spec = yaml.safe_load(clt_text)
    return spec['inputs']

def _get_cwl_outputs(clt_text: str) -> list[str]:
    spec = yaml.safe_load(clt_text)
    return spec['outputs']

def _get_cwl_clt_args(clt_text: str) -> list[str]:
    spec = yaml.safe_load(clt_text)
    return spec['arguments']

def _get_wdl_input_lines(task_text: str) -> list[str]:
    PATTERN = r'input.*?\{([^}{]*)\}'
    match = re.search(PATTERN, task_text)
    if match is None:
        return []
    lines = match.group(1).split('\n')
    lines = [ln.strip() for ln in lines]
    lines = [ln for ln in lines if ln]
    return lines

def _get_wdl_output_lines(task_text: str) -> list[str]:
    PATTERN = r'output.*?\{([^}{]*)\}'
    match = re.search(PATTERN, task_text)
    if match is None:
        return []
    lines = match.group(1).split('\n')
    lines = [ln.strip() for ln in lines]
    lines = [ln for ln in lines if ln]
    return lines

def _get_wdl_command_lines(task_text: str) -> list[str]:
    """Returns the lines of the process script"""
    out: list[str] = []
    lines = task_text.split('\n')
    within_script: bool = False
    
    for i in range(len(lines)):
        if lines[i].strip() == 'command <<<':
            within_script = True
            continue
        if lines[i].strip() == '>>>' and within_script:
            within_script = False
            continue
        if within_script:
            out.append(lines[i])
    
    return out

def _get_nf_subworkflow_input_lines(text: str) -> list[str]:
    pattern = r'take:([\s\S]*)main:'
    match = list(re.finditer(pattern, text))[0]
    lines = match.group(1).split('\n')
    lines = [ln.strip() for ln in lines]
    lines = [ln for ln in lines if ln != '']
    return lines

def _get_nf_process_input_lines(process_text: str) -> list[str]:
    """Returns the lines of the process script"""
    out: list[str] = []
    lines = process_text.split('\n')
    within_inputs: bool = False
    
    for i in range(len(lines)):
        if lines[i].strip() == 'input:':
            within_inputs = True
            continue
        if lines[i].strip() == 'output:' and within_inputs:
            within_inputs = False
            continue
        if within_inputs and lines[i].strip() != '':
            out.append(lines[i])
    
    return out

def _get_nf_process_output_lines(process_text: str) -> list[str]:
    """Returns the lines of the process script"""
    out: list[str] = []
    lines = process_text.split('\n')
    within_outputs: bool = False
    
    for i in range(len(lines)):
        if lines[i].strip() == 'output:':
            within_outputs = True
            continue
        if lines[i].strip() == 'script:' and within_outputs:
            within_outputs = False
            continue
        if within_outputs and lines[i].strip() != '':
            out.append(lines[i])
    
    return out

def _get_nf_process_script_lines(process_text: str) -> list[str]:
    """Returns the lines of the process script"""
    out: list[str] = []
    lines = process_text.split('\n')
    within_script: bool = False
    
    for i in range(len(lines)):
        if lines[i].strip() == '"""' and not within_script:
            within_script = True
            continue
        if lines[i].strip() == '"""' and within_script:
            within_script = False
            continue
        if within_script:
            out.append(lines[i])
    
    return out

def _is_camel(text: str) -> bool:
    PATTERN = r'^([a-z\d]+)([A-Z\d]+[a-z\d]+)*([A-Z\d]?)?$'
    matches = re.findall(PATTERN, text)
    return len(matches) == 1

def _is_kebab(text: str) -> bool:
    PATTERN = r'^([a-z\d]+)?(-[a-z\d]+)*$'
    matches = re.findall(PATTERN, text)
    return len(matches) == 1

def _is_pascal(text: str) -> bool:
    PATTERN = r'^(?<!=[a-z\d])([A-Z\d]+[a-z\d]+)*([A-Z\d].*)?$'
    matches = re.findall(PATTERN, text)
    return len(matches) == 1

def _is_snake_lower(text: str) -> bool:
    PATTERN = r'^([a-z\d]+)?(_[a-z\d]+)*$'
    matches = re.findall(PATTERN, text)
    return len(matches) == 1

def _is_snake_upper(text: str) -> bool:
    PATTERN = r'^([A-Z\d]+)?(_[A-Z\d]+)*$'
    matches = re.findall(PATTERN, text)
    return len(matches) == 1

def _janis_pipelines_installed() -> bool:
    # ensuring janis pipelines for janis translate tests
    try:
        import janis_pipelines      # type: ignore
        import janis_bioinformatics # type: ignore
        return True
    except:
        return False
    


class TestBuilders(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()

    def test_commandtool_to_builders(self) -> None:
        entity = GridssTestTool()
        entity = to_builders(entity)
        self.assertIsInstance(entity, CommandToolBuilder)
    
    def test_codetool_to_builders(self) -> None:
        entity = FileOutputPythonTestTool()
        entity = to_builders(entity)
        self.assertIsInstance(entity, CodeTool)

    def test_workflow_to_builders(self) -> None:
        entity = AssemblyTestWF()
        entity = to_builders(entity)
        self.assertIsInstance(entity, WorkflowBuilder)
        assert(isinstance(entity, WorkflowBuilder))
        for step in entity.step_nodes.values():
            self.assertIsInstance(step.tool, CommandToolBuilder)


class TestStepOrdering(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()

    def test_wf_super_enhancer(self):
        infile = f'{CWL_TESTDATA_PATH}/workflows/super_enhancer_wf.cwl'
        wf = ingest(infile, 'cwl')
        wf = to_builders(wf)
        assert isinstance(wf, WorkflowBuilder)
        wf = order_steps_topologically(wf)
        expected_order = [
            'make_gff',
            'run_rose',
            'rename_png',
            'sort_bed',
            'reduce_bed',
            'bed_to_bigbed',
            'bed_to_macs',
            'assign_genes',
            'add_island_names',
        ]
        actual_order = [step.id() for step in wf.step_nodes.values()]
        self.assertListEqual(expected_order, actual_order)


class TestValidContainers(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()

    def test_echo(self):
        """Test tools calling linux binaries"""
        cmdtool = CommandToolBuilder(
            tool="test",
            base_command=["echo"],
            inputs=[],
            outputs=[],
            container=None, # type: ignore
            version="1.0"
        )
        cmdtool = ensure_containers(cmdtool)
        assert isinstance(cmdtool, CommandToolBuilder)
        self.assertEqual(cmdtool._container, "ubuntu:latest")
        msgs = load_loglines(entity_uuids=set([cmdtool.uuid]))
        msgs = [x.message for x in msgs]
        self.assertIn('tool did not specify container or software requirement, guessed from command.', msgs)

    def test_echo_multi(self):
        """Test tools calling linux binaries"""
        cmdtool = CommandToolBuilder(
            tool="test",
            base_command=["echo", '"hello"'],
            inputs=[],
            outputs=[],
            container=None, # type: ignore
            version="1.0"
        )
        cmdtool = ensure_containers(cmdtool)
        assert isinstance(cmdtool, CommandToolBuilder)
        self.assertEqual(cmdtool._container, "ubuntu:latest")
        msgs = load_loglines(entity_uuids=set([cmdtool.uuid]))
        msgs = [x.message for x in msgs]
        self.assertIn('tool did not specify container or software requirement, guessed from command.', msgs)
     
    def test_fastqc(self):
        """Test tools calling bioinformatics software"""
        cmdtool = CommandToolBuilder(
            tool="test",
            base_command="fastqc",
            inputs=[],
            outputs=[],
            container=None,  # type: ignore
            version="1.0"
        )
        cmdtool = ensure_containers(cmdtool)
        assert isinstance(cmdtool, CommandToolBuilder)
        self.assertIn('quay.io/biocontainers/fastqc:', cmdtool._container)
        msgs = load_loglines(entity_uuids=set([cmdtool.uuid]))
        msgs = [x.message for x in msgs]
        self.assertIn('tool did not specify container or software requirement, guessed from command.', msgs)
    
    def test_samtools_sort(self):
        """Test tools calling linux binaries"""
        cmdtool = CommandToolBuilder(
            tool="test",
            base_command=["samtools", "sort"],
            inputs=[],
            outputs=[],
            container=None, # type: ignore
            version="1.0"
        )
        cmdtool = ensure_containers(cmdtool)
        assert isinstance(cmdtool, CommandToolBuilder)
        self.assertIn('quay.io/biocontainers/samtools:', cmdtool._container)
        msgs = load_loglines(entity_uuids=set([cmdtool.uuid]))
        msgs = [x.message for x in msgs]
        self.assertIn('tool did not specify container or software requirement, guessed from command.', msgs)
   
    def test_bwa_mem(self):
        """Test tools calling bioinformatics software (multi)"""
        cmdtool = CommandToolBuilder(
            tool="test",
            base_command=["bwa", "mem"],
            inputs=[],
            outputs=[],
            container=None,  # type: ignore
            version="1.0"
        )
        cmdtool = ensure_containers(cmdtool)
        assert isinstance(cmdtool, CommandToolBuilder)
        self.assertIn("quay.io/biocontainers/bwa:", cmdtool._container)
        msgs = load_loglines(entity_uuids=set([cmdtool.uuid]))
        msgs = [x.message for x in msgs]
        self.assertIn('tool did not specify container or software requirement, guessed from command.', msgs)
    
    def test_bwamem2(self):
        """Test tools calling bioinformatics software (multi)"""
        cmdtool = CommandToolBuilder(
            tool="test",
            base_command=["./bwa-mem2"],
            inputs=[],
            outputs=[],
            container=None,  # type: ignore
            version="1.0"
        )
        cmdtool = ensure_containers(cmdtool)
        assert isinstance(cmdtool, CommandToolBuilder)
        self.assertIn("quay.io/biocontainers/bwa-mem2:", cmdtool._container)
    
    def test_ebi_fraggenescan(self):
        """Test tools calling bioinformatics software (multi)"""
        filepath = f'{CWL_TESTDATA_PATH}/workflows/ebi-metagenomics/tools/Combined_gene_caller/FGS.cwl'
        cmdtool = ingest(filepath, 'cwl')
        cmdtool = ensure_containers(cmdtool)
        assert isinstance(cmdtool, CommandToolBuilder)
        self.assertIn("quay.io/biocontainers/fraggenescan:", cmdtool._container)
        msgs = load_loglines(entity_uuids=set([cmdtool.uuid]))
        msgs = [x.message for x in msgs]
        self.assertIn('tool did not specify container or software requirement, guessed from command.', msgs)
    
    def test_ebi_interproscan(self):
        filepath = f'{CWL_TESTDATA_PATH}/workflows/ebi-metagenomics/tools/InterProScan/InterProScan-v5-none_docker.cwl'
        cmdtool = ingest(filepath, 'cwl')
        cmdtool = ensure_containers(cmdtool)
        assert isinstance(cmdtool, CommandToolBuilder)
        self.assertIn("quay.io/biocontainers/interproscan:", cmdtool._container)
        msgs = load_loglines(entity_uuids=set([cmdtool.uuid]))
        msgs = [x.message for x in msgs]
        self.assertIn('tool did not specify container or software requirement, guessed from command.', msgs)
    



class TestWrapTool(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()

    def test_tool_fastqc(self):
        settings.translate.AS_WORKFLOW = True
        tool = FastqcTestTool()
        
        tool = to_builders(tool)
        assert isinstance(tool, CommandToolBuilder)

        wf = wrap_tool_in_workflow(tool)
        assert isinstance(wf, WorkflowBuilder)

        # basics
        self.assertEqual(len(wf.input_nodes), 11)
        self.assertEqual(len(wf.step_nodes), 1)
        self.assertEqual(len(wf.output_nodes), 2)
        
        # checking step input sources
        step = wf.step_nodes['fastqc_step']
        for inp in tool._inputs:
            self.assertIn(inp.id(), step.sources)
            source = step.sources[inp.id()].source_map[0].source
            self.assertIsInstance(source, InputNodeSelector)
            self.assertEqual(source.input_node, wf.input_nodes[inp.id()])

        # checking workflow output sources
        for out in tool._outputs:
            self.assertIn(out.id(), wf.output_nodes)
            source = wf.output_nodes[out.id()].source
            assert isinstance(source, StepOutputSelector)
            self.assertEqual(source.node, step)
            self.assertEqual(source.tag, out.id())




class TestRenderCmd(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()
        self.flat_wf: WorkflowBuilder = PruneFlatTW()
    
    def test_render_cwl(self) -> None:
        mainstr, _, _, subtools = translate(self.flat_wf, 'cwl', nocmd=False)
        toolstr = subtools[0][1]
        self.assertIn('inputBinding', toolstr)
    
    def test_render_nxf(self) -> None:
        mainstr, _, _, subtools = translate(self.flat_wf, 'nextflow', nocmd=False)
        toolstr = subtools[0][1]
        script_lines = _get_nf_process_script_lines(toolstr)
        self.assertGreater(len(script_lines), 1)
    
    def test_render_wdl(self) -> None:
        mainstr, _, _, subtools = translate(self.flat_wf, 'wdl', nocmd=False)
        toolstr = subtools[0][1]
        script_lines = _get_wdl_command_lines(toolstr)
        self.assertGreater(len(script_lines), 2)
    
    def test_norender_cwl(self) -> None:
        mainstr, _, _, subtools = translate(self.flat_wf, 'cwl', nocmd=True)
        toolstr = subtools[0][1]
        self.assertNotIn('inputBinding', toolstr)
    
    def test_norender_nxf(self) -> None:
        mainstr, _, _, subtools = translate(self.flat_wf, 'nextflow', nocmd=True)
        toolstr = subtools[0][1]
        script_lines = _get_nf_process_script_lines(toolstr)
        self.assertEqual(len(script_lines), 1)
    
    def test_norender_wdl(self) -> None:
        mainstr, _, _, subtools = translate(self.flat_wf, 'wdl', nocmd=True)
        toolstr = subtools[0][1]
        script_lines = _get_wdl_command_lines(toolstr)
        self.assertEqual(len(script_lines), 2)




class TestSimplification(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()
        self.flat_wf: WorkflowBuilder = PruneFlatTW()               # type: ignore
        self.flat_wf: WorkflowBuilder = to_builders(self.flat_wf)   # type: ignore
        self.nested_wf: WorkflowBuilder = PruneNestedTW()               # type: ignore
        self.nested_wf: WorkflowBuilder = to_builders(self.nested_wf)   # type: ignore

    ### BASICS ###
    
    def test_wf_inputs(self) -> None:
        settings.translate.SIMPLIFICATION = ESimplification.ON
        wf: WorkflowBuilder = simplify(self.flat_wf)        # type: ignore
        actual_inputs = set(list(wf.input_nodes.keys()))
        expected_inputs = set([
            'inFile1',
            'inFile2',
            'inFile3',
            
            'inStr1',
            'inStr2',
            'inStr3',
            
            'inFileOpt1',
            'inFileOpt2',
            
            'inStrOpt1',
            'inStrOpt2',

        ])
        self.assertSetEqual(actual_inputs, expected_inputs)
    
    def test_dynamic_tinputs(self) -> None:
        """
        checks whether tool inputs with dynamic sources: 
        - are kept in the simplified workflow 
        - have sources preserved in stp.sources
        """
        settings.translate.SIMPLIFICATION = ESimplification.ON
        wf: WorkflowBuilder = simplify(self.flat_wf)        # type: ignore

        tool = wf.step_nodes['stp4'].tool
        assert isinstance(tool, CommandToolBuilder)
        
        # checking optional inputs with dynamic sources are kept
        num_actual_inputs = len(tool._inputs)
        num_expected_inputs = 4
        self.assertEqual(num_actual_inputs, num_expected_inputs)
        
        # checking sources are kept
        step = wf.step_nodes['stp4']
        actual_sources = set(list(step.sources.keys()))
        expected_sources = set(['inFileOpt1', 'inStrOpt1'])
        self.assertEqual(actual_sources, expected_sources)
        
        # checking sources are kept
        step = wf.step_nodes['stp5']
        actual_sources = set(list(step.sources.keys()))
        expected_sources = set(['inFileOpt2', 'inStrOpt2'])
        self.assertEqual(actual_sources, expected_sources)

    def test_static_tinputs(self) -> None:
        """
        checks whether static values are 
        - moved to input defaults
        - corresponding inputs are removed from stp.sources 
        """
        settings.translate.SIMPLIFICATION = ESimplification.ON
        wf: WorkflowBuilder = simplify(self.flat_wf)        # type: ignore

        # checking unused tool inputs are removed
        tool = wf.step_nodes['stp6'].tool
        assert isinstance(tool, CommandToolBuilder)
        num_actual_inputs = len(tool._inputs)
        num_expected_inputs = 3
        self.assertEqual(num_actual_inputs, num_expected_inputs)
        
        # checking static values moved to tool input defaults
        for tinput in tool._inputs:
            if tinput.id() == 'inStrOpt1':
                self.assertEqual(tinput.default, 'hello')
            elif tinput.id() == 'inStrOpt2':
                self.assertEqual(tinput.default, 'there')
            elif tinput.id() == 'inStr3':
                self.assertEqual(tinput.default, 'friend')
            else:
                self.assertEqual(tinput.default, None)
        
        # checking static values removed from stp.sources
        step = wf.step_nodes['stp6']
        self.assertEqual(len(step.sources), 0)
        
    def test_internal_reference_tinputs(self) -> None:
        """
        checks whether unnecessary tool inputs (which would usually be removed)
        are not removed if 
        - they refer to necessary tool inputs, or
        - an output refers to them
        """
        settings.translate.SIMPLIFICATION = ESimplification.ON
        wf: WorkflowBuilder = simplify(self.flat_wf)        # type: ignore

        # tool input -> tool input
        tool = wf.step_nodes['stp2'].tool
        assert isinstance(tool, CommandToolBuilder)
        actual_tinputs = set([x.id() for x in tool._inputs])
        expected_tinputs = set(['inFile1', 'OutputName'])
        self.assertEqual(actual_tinputs, expected_tinputs)
    
        # tool output -> tool input
        tool = wf.step_nodes['stp3'].tool
        assert isinstance(tool, CommandToolBuilder)
        actual_tinputs = set([x.id() for x in tool._inputs])
        expected_tinputs = set(['inFileOpt1', 'inStrOpt1'])
        self.assertEqual(actual_tinputs, expected_tinputs)
    
    def test_scattered_tinputs(self) -> None:
        """tinputs which are scattered on should not be removed"""
        settings.translate.SIMPLIFICATION = ESimplification.ON
        wf = SimplificationScatterTestWF()              # type: ignore
        wf = to_builders(wf)                            # type: ignore
        wf: WorkflowBuilder = simplify(wf)              # type: ignore

        # tool input -> tool input
        tool = wf.step_nodes['stp1'].tool
        assert isinstance(tool, CommandToolBuilder)
        actual_tinputs = set([x.id() for x in tool._inputs])
        expected_tinputs = set(['inIntOpt'])
        self.assertEqual(actual_tinputs, expected_tinputs)
    
    def test_toutputs(self) -> None:
        """
        checks whether unnecessary tool outputs are removed. Tool outputs are kept when:
        - they are referenced in step input sources (connection)
        - they are referenced in workflow output sources (workflow output)
        """
        settings.translate.SIMPLIFICATION = ESimplification.ON
        wf: WorkflowBuilder = simplify(self.flat_wf)        # type: ignore

        # tool input -> tool input
        tool = wf.step_nodes['stp0'].tool
        assert isinstance(tool, CommandToolBuilder)
        actual_toutputs = set([x.id() for x in tool._outputs])
        expected_toutputs = set(['outFile', 'outFileOpt1', 'outStr', 'outStrOpt1'])
        self.assertEqual(actual_toutputs, expected_toutputs)

    ### NESTED ###
        
    def test_nested_wf_inputs(self) -> None:
        settings.translate.SIMPLIFICATION = ESimplification.ON
        wf: WorkflowBuilder = simplify(self.nested_wf)        # type: ignore
        actual_inputs = set(list(wf.input_nodes.keys()))
        expected_inputs = set([
            'inFile1',
            'inFile2',
            'inFile3',
            
            'inStr1',
            'inStr2',
            'inStr3',
            
            'inFileOpt1',
            'inFileOpt2',
            'inFileOpt3',
            
            'inStrOpt1',
            'inStrOpt2',
            'inStrOpt3',
        ])
        self.assertSetEqual(actual_inputs, expected_inputs)
    
    def test_nested_tool(self) -> None:
        settings.translate.SIMPLIFICATION = ESimplification.ON
        wf: WorkflowBuilder = simplify(self.nested_wf)        # type: ignore

        tool = wf.step_nodes['stp1'].tool
        assert isinstance(tool, CommandToolBuilder)
        actual_tinputs = set([x.id() for x in tool._inputs])
        expected_tinputs = set([
            'inFileOpt1', 
            'inFileOpt2', 
            'inFileOpt3', 
            'inStrOpt1', 
            'inStrOpt2', 
            'inStrOpt3', 
        ])
        self.assertEqual(actual_tinputs, expected_tinputs)
    
    def test_nested_wf(self) -> None:
        settings.translate.SIMPLIFICATION = ESimplification.ON
        wf: WorkflowBuilder = simplify(self.nested_wf)        # type: ignore

        tool = wf.step_nodes['stp2'].tool
        assert isinstance(tool, WorkflowBuilder)
        actual_tinputs = set([x for x in tool.input_nodes.keys()])
        expected_tinputs = set([
            'inFileOpt2', 
            'inFileOpt3', 
            'inStrOpt2', 
            'inStrOpt3', 
        ])
        self.assertEqual(actual_tinputs, expected_tinputs)

        tool = wf.step_nodes['stp2'].tool.step_nodes['stp2'].tool
        assert isinstance(tool, WorkflowBuilder)
        actual_tinputs = set([x for x in tool.input_nodes.keys()])
        expected_tinputs = set([
            'inFileOpt3', 
            'inStrOpt3', 
        ])
        self.assertEqual(actual_tinputs, expected_tinputs)

    ### integration tests ###
        
    def test_simplification_off_tool(self) -> None:
        _, _, _, cwltools = translate(PruneFlatTW(), dest_fmt='cwl', simplification='off')
        _, _, _, nxftools = translate(PruneFlatTW(), dest_fmt='nextflow', simplification='off')
        _, _, _, wdltools = translate(PruneFlatTW(), dest_fmt='wdl', simplification='off')
        expected_tool_io = [
            # (num_inputs, num_outputs)  
            (2, 6), # PruneOutputTT
            (4, 2), # PruneMandatoryTT
            (2, 1), # PruneInputRefTT
            (2, 2), # PruneOutputRefTT
            (6, 3), # PruneOptionalTT
            (6, 3), # PruneOptional2TT
        ]
        for expected_io, cwltool, nxftool, wdltool in zip(expected_tool_io, cwltools, nxftools, wdltools):
            # cwl
            self.assertEqual(len(_get_cwl_inputs(cwltool[1])), expected_io[0])
            self.assertEqual(len(_get_cwl_outputs(cwltool[1])), expected_io[1])
            # nxf
            self.assertEqual(len(_get_nf_process_input_lines(nxftool[1])), expected_io[0])
            self.assertEqual(len(_get_nf_process_output_lines(nxftool[1])), expected_io[1])
            # wdl
            self.assertEqual(len(_get_wdl_input_lines(wdltool[1])), expected_io[0])
            self.assertEqual(len(_get_wdl_output_lines(wdltool[1])), expected_io[1])
    
    def test_simplification_on_tool(self) -> None:
        _, _, _, cwltools = translate(PruneFlatTW(), dest_fmt='cwl', simplification='on')
        _, _, _, nxftools = translate(PruneFlatTW(), dest_fmt='nextflow', simplification='on')
        _, _, _, wdltools = translate(PruneFlatTW(), dest_fmt='wdl', simplification='on')
        expected_tool_io = [
            (2, 4), # PruneOutputTT
            (4, 2), # PruneMandatoryTT
            (2, 1), # PruneInputRefTT
            (2, 2), # PruneOutputRefTT
            (4, 3), # PruneOptionalTT
            (3, 3), # PruneOptional2TT
        ]
        for expected_io, cwltool, nxftool, wdltool in zip(expected_tool_io, cwltools, nxftools, wdltools):
            # cwl
            self.assertEqual(len(_get_cwl_inputs(cwltool[1])), expected_io[0])
            self.assertEqual(len(_get_cwl_outputs(cwltool[1])), expected_io[1])
            # nxf
            self.assertEqual(len(_get_nf_process_input_lines(nxftool[1])), expected_io[0])
            self.assertEqual(len(_get_nf_process_output_lines(nxftool[1])), expected_io[1])
            # wdl
            self.assertEqual(len(_get_wdl_input_lines(wdltool[1])), expected_io[0])
            self.assertEqual(len(_get_wdl_output_lines(wdltool[1])), expected_io[1])
    
    def test_simplification_aggr_tool(self) -> None:
        _, _, _, cwltools = translate(PruneFlatTW(), dest_fmt='cwl', simplification='aggressive')
        _, _, _, nxftools = translate(PruneFlatTW(), dest_fmt='nextflow', simplification='aggressive')
        _, _, _, wdltools = translate(PruneFlatTW(), dest_fmt='wdl', simplification='aggressive')
        expected_tool_io = [
            (2, 4), # PruneOutputTT
            (4, 2), # PruneMandatoryTT
            (1, 1), # PruneInputRefTT
            (0, 2), # PruneOutputRefTT
            (1, 3), # PruneOptionalTT
            (1, 3), # PruneOptional2TT
        ]
        for expected_io, cwltool, nxftool, wdltool in zip(expected_tool_io, cwltools, nxftools, wdltools):
            # cwl
            self.assertEqual(len(_get_cwl_inputs(cwltool[1])), expected_io[0])
            self.assertEqual(len(_get_cwl_outputs(cwltool[1])), expected_io[1])
            # nxf
            self.assertEqual(len(_get_nf_process_input_lines(nxftool[1])), expected_io[0])
            self.assertEqual(len(_get_nf_process_output_lines(nxftool[1])), expected_io[1])
            # wdl
            self.assertEqual(len(_get_wdl_input_lines(wdltool[1])), expected_io[0])
            self.assertEqual(len(_get_wdl_output_lines(wdltool[1])), expected_io[1])



    



class TestCaseFormatting(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()
        wf = AssemblyTestWF()
        self.wf = to_builders(wf)

    def test_resources(self):
        """
        checks that InputSelectors in tool.cpu/memory/disk/time 
        are updated to match the new input name formatting (will throw error if not)
        """
        tool = OperatorResourcesTestTool()
        from janis_core import settings
        settings.translate.WITH_RESOURCE_OVERRIDES = True
        toolstr = translate(tool, 'cwl')

    def test_cwl_entities(self) -> None:
        settings.translate.DEST = 'cwl'
        wf = refactor_symbols(self.wf)
        assert isinstance(wf, WorkflowBuilder)
        
        self.assertTrue(_is_snake_lower(wf.id()))
        for winp in wf.input_nodes.values():
            self.assertTrue(_is_snake_lower(winp.id()))
        for wstep in wf.step_nodes.values():
            self.assertTrue(_is_snake_lower(wstep.id()))
        for wout in wf.output_nodes.values():
            self.assertTrue(_is_snake_lower(wout.id()))
        
        # subtools
        for wstep in wf.step_nodes.values():
            tool = wstep.tool
            assert isinstance(tool, CommandToolBuilder)
            self.assertTrue(_is_snake_lower(tool.id()))
            for tinp in tool._inputs:
                self.assertTrue(_is_snake_lower(tinp.id()))
            for tout in tool._outputs:
                self.assertTrue(_is_snake_lower(tout.id()))
        
    def test_cwl_filenames(self) -> None:
        settings.translate.DEST = 'cwl'
        self.assertEqual('unicycler-assembly.cwl', CwlTranslator.workflow_filename(self.wf))
        self.assertEqual('unicycler-assembly-inp.yml', CwlTranslator.inputs_filename(self.wf))
        self.assertEqual('fastqc.cwl', CwlTranslator.tool_filename(self.wf.step_nodes['fastqc1'].tool))
        
    def test_nxf_entities(self) -> None:
        settings.translate.DEST = 'nextflow'
        wf = refactor_symbols(self.wf)
        assert isinstance(wf, WorkflowBuilder)
        
        self.assertTrue(_is_snake_upper(wf.id()))
        for winp in wf.input_nodes.values():
            self.assertTrue(_is_snake_lower(winp.id()))
        for wstep in wf.step_nodes.values():
            self.assertTrue(_is_snake_lower(wstep.id()))
        for wout in wf.output_nodes.values():
            self.assertTrue(_is_snake_lower(wout.id()))
        
        # subtools
        for wstep in wf.step_nodes.values():
            tool = wstep.tool
            assert isinstance(tool, CommandToolBuilder)
            self.assertTrue(_is_snake_upper(tool.id()))
            for tinp in tool._inputs:
                self.assertTrue(_is_snake_lower(tinp.id()))
            for tout in tool._outputs:
                self.assertTrue(_is_snake_lower(tout.id()))
        
    def test_nxf_filenames(self) -> None:
        settings.translate.DEST = 'nextflow'
        self.assertEqual('main.nf', NextflowTranslator.workflow_filename(self.wf, is_main=True))
        self.assertEqual('unicycler_assembly.nf', NextflowTranslator.workflow_filename(self.wf))
        self.assertEqual('nextflow.config', NextflowTranslator.inputs_filename(self.wf))
        self.assertEqual('fastqc.nf', NextflowTranslator.tool_filename(self.wf.step_nodes['fastqc1'].tool))
    
    def test_wdl_entities(self) -> None:
        settings.translate.DEST = 'wdl'
        wf = refactor_symbols(self.wf)
        assert isinstance(wf, WorkflowBuilder)
        
        self.assertTrue(_is_pascal(wf.id()))
        for winp in wf.input_nodes.values():
            self.assertTrue(_is_camel(winp.id()))
        for wstep in wf.step_nodes.values():
            self.assertTrue(_is_camel(wstep.id()))
        for wout in wf.output_nodes.values():
            self.assertTrue(_is_camel(wout.id()))
        
        # subtools
        for wstep in wf.step_nodes.values():
            tool = wstep.tool
            assert isinstance(tool, CommandToolBuilder)
            self.assertTrue(_is_pascal(tool.id()))
            for tinp in tool._inputs:
                self.assertTrue(_is_camel(tinp.id()))
            for tout in tool._outputs:
                self.assertTrue(_is_camel(tout.id()))

    def test_wdl_filenames(self) -> None:
        settings.translate.DEST = 'wdl'
        self.assertEqual('unicycler_assembly.wdl', WdlTranslator.workflow_filename(self.wf))
        self.assertEqual('unicycler_assembly.json', WdlTranslator.inputs_filename(self.wf))
        self.assertEqual('fastqc.wdl', WdlTranslator.tool_filename(self.wf.step_nodes['fastqc1'].tool))
        
    def test_subworkflows(self) -> None:
        settings.translate.DEST = 'nextflow'
        wf = SubworkflowTestWF()
        wf = to_builders(wf)
        wf = refactor_symbols(wf)
        
        # main wf
        assert isinstance(wf, WorkflowBuilder)
        self.assertTrue(_is_snake_upper(wf.id()))
        for winp in wf.input_nodes.values():
            self.assertTrue(_is_snake_lower(winp.id()))
        for wstep in wf.step_nodes.values():
            self.assertTrue(_is_snake_lower(wstep.id()))
        for wout in wf.output_nodes.values():
            self.assertTrue(_is_snake_lower(wout.id()))
        
        # subworkflow
        subwf = wf.step_nodes['apples_subworkflow'].tool
        assert isinstance(subwf, WorkflowBuilder)
        for winp in subwf.input_nodes.values():
            self.assertTrue(_is_snake_lower(winp.id()))
        for wstep in subwf.step_nodes.values():
            self.assertTrue(_is_snake_lower(wstep.id()))
        for wout in subwf.output_nodes.values():
            self.assertTrue(_is_snake_lower(wout.id()))
        self.assertEqual('apples_workflow.nf', NextflowTranslator.workflow_filename(subwf))
        
        # subtool
        tool = wf.step_nodes['file_tool'].tool
        assert isinstance(tool, CommandToolBuilder)
        self.assertTrue(_is_snake_upper(tool.id()))
        for tinp in tool._inputs:
            self.assertTrue(_is_snake_lower(tinp.id()))
        for tout in tool._outputs:
            self.assertTrue(_is_snake_lower(tout.id()))



class TestIllegalSymbolRefactor(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()
        wf = IllegalSymbolsTestWF()
        self.wf = to_builders(wf)

    def test_selector_updates(self) -> None:
        settings.translate.DEST = 'wdl'
        wf = UnwrapTestWF()
        wf = to_builders(wf)
        wf = refactor_symbols(wf)
        assert isinstance(wf, WorkflowBuilder)

        # tool inputs
        tool = wf.step_nodes['basicsStep'].tool
        assert isinstance(tool, CommandToolBuilder)
        expected = set([
            'reads1',
            'inFilenamePath',
            'bamSorted',
        ])
        actual = set([x.id() for x in tool._inputs])
        self.assertSetEqual(expected, actual)
        
        # selectors
        for out in tool._outputs:
            if out.id() == 'bamSortedIndexed':
                expected = 'inputs.bamSorted.basename'
                actual = str(out.selector)
                self.assertEqual(actual, expected)
            elif out.id() == 'trimmedReads1':
                expected = '{inputs.reads1.basename}.trimmed{inputs.reads1.nameext}'
                actual = str(out.selector)
                self.assertEqual(actual, expected)
            else:
                raise RuntimeError('unexpected output')

    def test_dict_keys(self) -> None:
        settings.translate.DEST = 'wdl'
        wf = refactor_symbols(self.wf)
        assert isinstance(wf, WorkflowBuilder)

        # check step input source keys
        expected = set([
            'bamPath',
            'inFile',
            'inp',
            'inputFile',
            'inCommand',
            'container',
            'int',
            'inDefined',
        ])
        actual_source_ids = set(wf.step_nodes['wdl'].sources.keys())
        actual_tinput_ids = set([x.id() for x in wf.step_nodes['wdl'].tool._inputs])
        for ident in expected:
            self.assertIn(ident, actual_source_ids)
            self.assertIn(ident, actual_tinput_ids)

    def test_cwl(self) -> None:
        settings.translate.DEST = 'cwl'
        wf = refactor_symbols(self.wf)
        assert isinstance(wf, WorkflowBuilder)

        # workflow inputs
        expected = set([
            'the_file','the_file_opt','the_file_arr','the_filename','the_bam',
            'the_bam_bai','the_bam_bai_arr','the_str','the_str_opt','the_int',
            'the_int_opt','the_float','the_float_opt','the_bool',
        ])
        actual = set([x.id() for x in wf.input_nodes.values()])
        self.assertSetEqual(expected, actual)

        # workflow outputs
        expected = set(['out_the_file'])
        actual = set([x.id() for x in wf.output_nodes.values()])
        self.assertSetEqual(expected, actual)
        
        # tool inputs
        tool = wf.step_nodes['cwl'].tool
        assert isinstance(tool, CommandToolBuilder)
        expected = set([
            'in_filename',
            'inp',
            'input',
            'in_out',
            'in_output',
        ])
        actual = set([x.id() for x in tool._inputs])
        self.assertSetEqual(expected, actual)

        # tool outputs
        expected = set(['out_file', 'out', 'output'])
        actual = set([x.id() for x in tool._outputs])
        self.assertSetEqual(expected, actual)

    def test_nxf(self) -> None:
        settings.translate.DEST = 'nextflow'
        wf = refactor_symbols(self.wf)
        assert isinstance(wf, WorkflowBuilder)

        # workflow inputs
        expected = set([
            'the_file','the_file_opt','the_file_arr','the_filename','the_bam',
            'the_bam_bai','the_bam_bai_arr','the_str','the_str_opt','the_int',
            'the_int_opt','the_float','the_float_opt','the_bool',
        ])
        actual = set([x.id() for x in wf.input_nodes.values()])
        self.assertSetEqual(expected, actual)

        # workflow outputs
        expected = set(['out_the_file'])
        actual = set([x.id() for x in wf.output_nodes.values()])
        self.assertSetEqual(expected, actual)
        
        # tool inputs
        tool = wf.step_nodes['nextflow_task'].tool
        assert isinstance(tool, CommandToolBuilder)
        expected = set([
            'in_file',
            'inp',
            'input_filename',
            'in_container',
            'in_path',
            'in_val',
        ])
        actual = set([x.id() for x in tool._inputs])
        self.assertSetEqual(expected, actual)

        # tool outputs
        expected = set(['out_file', 'out', 'output_file'])
        actual = set([x.id() for x in tool._outputs])
        self.assertSetEqual(expected, actual)
    
    def test_wdl(self) -> None:
        settings.translate.DEST = 'wdl'
        wf = refactor_symbols(self.wf)
        assert isinstance(wf, WorkflowBuilder)
        
        # workflow inputs
        expected = set([
            'inTheFile','theFileOpt','theFileArr','theFilenamePath','theBam',
            'theBamBai','theBamBaiArr','theStr','theStrOpt','theInt',
            'theIntOpt','theFloat','theFloatOpt','theBool',
        ])
        actual = set([x.id() for x in wf.input_nodes.values()])
        self.assertSetEqual(expected, actual)

        # workflow outputs
        expected = set(['theFile'])
        actual = set([x.id() for x in wf.output_nodes.values()])
        self.assertSetEqual(expected, actual)
        
        # tool inputs
        tool = wf.step_nodes['wdl'].tool
        assert isinstance(tool, CommandToolBuilder)
        expected = set([
            'bamPath',
            'inFile',
            'inp',
            'inputFile',
            'inCommand',
            'container',
            'int',
            'inDefined',
        ])
        actual = set([x.id() for x in tool._inputs])
        self.assertSetEqual(expected, actual)

        # tool outputs
        expected = set(['outFile', 'out', 'outputFile'])
        actual = set([x.id() for x in tool._outputs])
        self.assertSetEqual(expected, actual)

