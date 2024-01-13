

import unittest
import os 
import regex as re
import yaml
from typing import Any

from janis_core import settings
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
from janis_core.modifications import ensure_containers
from janis_core.modifications import simplify
from janis_core.modifications import refactor_symbols
from janis_core.modifications import wrap_tool_in_workflow

from janis_core.tests.testtools import FileOutputPythonTestTool
from janis_core.tests.testtools import GridssTestTool
from janis_core.tests.testtools import FastqcTestTool
from janis_core.tests.testworkflows import PruneFlatTW
from janis_core.tests.testworkflows import PruneNestedTW
from janis_core.tests.testworkflows import AssemblyTestWF
from janis_core.tests.testworkflows import IllegalSymbolsTestWF
from janis_core.tests.testworkflows import UnwrapTestWF
from janis_core.tests.testworkflows import SubworkflowTestWF


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
    settings.translate.MODE = 'extended'
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

def _run(filepath: str, srcfmt: str, destfmt: str) -> Any:
    internal = ingest(filepath, srcfmt)
    return translate(internal, destfmt, export_path='./translated')

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

def _get_cwl_clt_inputs(clt_text: str) -> list[str]:
    spec = yaml.safe_load(clt_text)
    return spec['inputs']

def _get_cwl_clt_args(clt_text: str) -> list[str]:
    spec = yaml.safe_load(clt_text)
    return spec['arguments']

def _get_wdl_task_command_lines(task_text: str) -> list[str]:
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




class TestValidContainers(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()

    def test_echo_single(self):
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
            base_command=["echo", "hello"],
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
        self.assertEqual(cmdtool._container, 'quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0')
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
        self.assertEqual(cmdtool._container, "quay.io/biocontainers/bwa-mem2:2.2.1--hd03093a_5")
        msgs = load_loglines(entity_uuids=set([cmdtool.uuid]))
        msgs = [x.message for x in msgs]
        self.assertIn('tool did not specify container or software requirement, guessed from command.', msgs)
    



class TestWrapTool(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()

    def test_tool_fastqc(self):
        tool: CommandToolBuilder = FastqcTestTool()
        wf = wrap_tool_in_workflow(tool)

        # basics
        assert isinstance(wf, WorkflowBuilder)
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




class TestModes(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()




class TestSimplification(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()
        self.flat_wf: WorkflowBuilder = PruneFlatTW()               # type: ignore
        self.flat_wf: WorkflowBuilder = to_builders(self.flat_wf)   # type: ignore
        simplify(self.flat_wf)
        self.nested_wf: WorkflowBuilder = PruneNestedTW()               # type: ignore
        self.nested_wf: WorkflowBuilder = to_builders(self.nested_wf)   # type: ignore
        simplify(self.nested_wf)

    ### workflow inputs ###
    
    def test_flat_wf_inputs(self) -> None:
        actual_inputs = set(list(self.flat_wf.input_nodes.keys()))
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
    
    def test_nested_wf_inputs(self) -> None:
        actual_inputs = set(list(self.nested_wf.input_nodes.keys()))
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
        
    ### migrating statics ###

    def test_migrate_single_statics(self) -> None:
        tool = self.flat_wf.step_nodes['stp4'].tool
        assert isinstance(tool, CommandToolBuilder)
        
        # checking num inputs
        num_actual_inputs = len(tool._inputs)
        num_expected_inputs = 4
        self.assertEqual(num_actual_inputs, num_expected_inputs)
        
        tool = self.flat_wf.step_nodes['stp6'].tool
        assert isinstance(tool, CommandToolBuilder)
        
        # checking num inputs
        num_actual_inputs = len(tool._inputs)
        num_expected_inputs = 3
        self.assertEqual(num_actual_inputs, num_expected_inputs)
        
        # checking default values
        for tinput in tool._inputs:
            if tinput.id() == 'inStrOpt1':
                self.assertEqual(tinput.default, 'hello')
            elif tinput.id() == 'inStrOpt2':
                self.assertEqual(tinput.default, 'there')
            elif tinput.id() == 'inStrOpt3':
                self.assertEqual(tinput.default, 'friend')
            else:
                self.assertEqual(tinput.default, None)
        
    def test_remove_sources(self) -> None:
        step = self.flat_wf.step_nodes['stp4']
        actual_sources = set(list(step.sources.keys()))
        expected_sources = set(['inFileOpt1', 'inStrOpt1'])
        self.assertEqual(actual_sources, expected_sources)
        
        step = self.flat_wf.step_nodes['stp5']
        actual_sources = set(list(step.sources.keys()))
        expected_sources = set(['inFileOpt2', 'inStrOpt2'])
        self.assertEqual(actual_sources, expected_sources)
        
        step = self.flat_wf.step_nodes['stp6']
        actual_sources = set(list(step.sources.keys()))
        expected_sources = set()
        self.assertEqual(actual_sources, expected_sources)


    ### tool inputs: flat wf ###

    def test_mandatory_tinputs(self) -> None:
        tool = self.flat_wf.step_nodes['stp1'].tool
        assert isinstance(tool, CommandToolBuilder)
        actual_tinputs = set([x.id() for x in tool._inputs])
        expected_tinputs = set([
            'inFile1', 'inFile2', 'inStr1', 'inStr2'
        ])
        self.assertEqual(actual_tinputs, expected_tinputs)

    def test_connection_sources(self) -> None:
        tool = self.flat_wf.step_nodes['stp4'].tool
        assert isinstance(tool, CommandToolBuilder)
        actual_tinputs = set([x.id() for x in tool._inputs])
        expected_tinputs = set(['inFileOpt1', 'inStrOpt1'])
        for tinput_id in expected_tinputs:
            self.assertIn(tinput_id, actual_tinputs)
    
    def test_inputnode_sources(self) -> None:
        tool = self.flat_wf.step_nodes['stp5'].tool
        assert isinstance(tool, CommandToolBuilder)
        actual_tinputs = set([x.id() for x in tool._inputs])
        expected_tinputs = set(['inFileOpt2', 'inStrOpt2'])
        for tinput_id in expected_tinputs:
            self.assertIn(tinput_id, actual_tinputs)
    
    def test_static_sources(self) -> None:
        tool = self.flat_wf.step_nodes['stp6'].tool
        assert isinstance(tool, CommandToolBuilder)
        actual_tinputs = set([x.id() for x in tool._inputs])
        expected_tinputs = set(['inStrOpt3'])
        for tinput_id in expected_tinputs:
            self.assertIn(tinput_id, actual_tinputs)
    
    def test_optional_tinputs(self) -> None:
        tool = self.flat_wf.step_nodes['stp4'].tool
        assert isinstance(tool, CommandToolBuilder)
        actual_tinputs = set([x.id() for x in tool._inputs])
        expected_tinputs = set([
            'inFileOpt1', 
            'inFileOpt2', 
            'inStrOpt1', 
            'inStrOpt2', 
        ])
        self.assertEqual(actual_tinputs, expected_tinputs)
    
    def test_inputref_tinputs(self) -> None:
        tool = self.flat_wf.step_nodes['stp2'].tool
        assert isinstance(tool, CommandToolBuilder)
        actual_tinputs = set([x.id() for x in tool._inputs])
        expected_tinputs = set(['inFile1', 'OutputName'])
        self.assertEqual(actual_tinputs, expected_tinputs)
    
    def test_outputref_tinputs(self) -> None:
        tool = self.flat_wf.step_nodes['stp3'].tool
        assert isinstance(tool, CommandToolBuilder)
        actual_tinputs = set([x.id() for x in tool._inputs])
        expected_tinputs = set(['inFileOpt1', 'inStrOpt1'])
        self.assertEqual(actual_tinputs, expected_tinputs)
    
    ### tool inputs: nested wf ###
    
    def test_nested_tool(self) -> None:
        tool = self.nested_wf.step_nodes['stp1'].tool
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
    
    def test_nested_wf1(self) -> None:
        tool = self.nested_wf.step_nodes['stp2'].tool
        assert isinstance(tool, WorkflowBuilder)
        actual_tinputs = set([x for x in tool.input_nodes.keys()])
        expected_tinputs = set([
            'inFileOpt2', 
            'inFileOpt3', 
            'inStrOpt2', 
            'inStrOpt3', 
        ])
        self.assertEqual(actual_tinputs, expected_tinputs)

    def test_nested_wf2(self) -> None:
        tool = self.nested_wf.step_nodes['stp2'].tool.step_nodes['stp2'].tool
        assert isinstance(tool, WorkflowBuilder)
        actual_tinputs = set([x for x in tool.input_nodes.keys()])
        expected_tinputs = set([
            'inFileOpt3', 
            'inStrOpt3', 
        ])
        self.assertEqual(actual_tinputs, expected_tinputs)

    def test_skeleton_nextflow(self) -> None:
        settings.translate.MODE = 'skeleton'
        filepath = f'{CWL_TESTDATA_PATH}/workflows/subworkflow_test/main.cwl'
        _, _, subwfs, processes = _run(filepath, srcfmt='cwl', destfmt='nextflow')
        expected_task_input_count = {
            'basic.nf': 3,
            'mandatory_input_types.nf': 6,
            'optional_input_types.nf': 5,
        }
        expected_subwf_input_count = {
            'subworkflow.nf': 6,
        }
        expected_script_lengths = {
            'basic.nf': 5,
            'mandatory_input_types.nf': 7,
            'optional_input_types.nf': 6,
        }
        for filepath, filecontents in subwfs:
            actual_lines = _get_nf_subworkflow_input_lines(filecontents)
            expected = expected_subwf_input_count[filepath]
            self.assertEqual(len(actual_lines), expected)
        for filepath, filecontents in processes:
            print(filecontents)
            actual_input_lines = _get_nf_process_input_lines(filecontents)
            actual_script_lines = _get_nf_process_script_lines(filecontents)
            self.assertEqual(len(actual_input_lines), expected_task_input_count[filepath])
            self.assertEqual(len(actual_script_lines), expected_script_lengths[filepath])

    def test_regular_nextflow(self) -> None:
        settings.translate.MODE = 'regular'
        filepath = f'{CWL_TESTDATA_PATH}/workflows/subworkflow_test/main.cwl'
        maintask, _, subwfs, processes = _run(filepath, srcfmt='cwl', destfmt='nextflow')
        print(maintask)
        expected_inputs_count = {
            'basic.nf': 3,
            'mandatory_input_types.nf': 6,
            'optional_input_types.nf': 5,
        }
        expected_subwf_input_count = {
            'subworkflow.nf': 6,
        }
        expected_script_lengths = {
            'basic.nf': 6,
            'mandatory_input_types.nf': 7,
            'optional_input_types.nf': 6
        }
        for filepath, filecontents in subwfs:
            actual_lines = _get_nf_subworkflow_input_lines(filecontents)
            expected = expected_subwf_input_count[filepath]
            self.assertEqual(len(actual_lines), expected)
        for filepath, filecontents in processes:
            if _is_nf_process(filecontents):
                print(filecontents)
                actual_input_lines = _get_nf_process_input_lines(filecontents)
                actual_script_lines = _get_nf_process_script_lines(filecontents)
                self.assertEqual(len(actual_input_lines), expected_inputs_count[filepath])
                self.assertEqual(len(actual_script_lines), expected_script_lengths[filepath])

    def test_extended_nextflow(self) -> None:
        settings.translate.MODE = 'extended'
        filepath = f'{CWL_TESTDATA_PATH}/workflows/subworkflow_test/main.cwl'
        _, _, subwfs, sub_tasks = _run(filepath, srcfmt='cwl', destfmt='nextflow')
        expected_inputs_count = {
            'basic.nf': 7,
            'mandatory_input_types.nf': 6,
            'optional_input_types.nf': 6,
        }
        expected_subwf_input_count = {
            'subworkflow.nf': 6,
        }
        expected_script_lengths = {
            'basic.nf': 9,
            'mandatory_input_types.nf': 7,
            'optional_input_types.nf': 7,
        }
        for filepath, filecontents in subwfs:
            actual_lines = _get_nf_subworkflow_input_lines(filecontents)
            expected = expected_subwf_input_count[filepath]
            self.assertEqual(len(actual_lines), expected)
        for filepath, filecontents in sub_tasks:
            if _is_nf_process(filecontents):
                print(filecontents)
                actual_input_lines = _get_nf_process_input_lines(filecontents)
                actual_script_lines = _get_nf_process_script_lines(filecontents)
                self.assertEqual(len(actual_input_lines), expected_inputs_count[filepath])
                self.assertEqual(len(actual_script_lines), expected_script_lengths[filepath])

    @unittest.skip('not implemented')
    def test_skeleton_cwl(self) -> None:
        settings.translate.MODE = 'skeleton'
        filepath = f'{CWL_TESTDATA_PATH}/workflows/subworkflow_test/main.cwl'
        maintask, _, sub_tasks = _run(filepath, srcfmt='cwl', destfmt='cwl')

        # main
        expected_num_clt_inputs = 11
        clt_inputs = _get_cwl_clt_inputs(maintask)
        self.assertEqual(len(clt_inputs), expected_num_clt_inputs)

        # subtasks
        expected_num_clt_inputs = {
            'tools/basic_v0_1_0.cwl': 4,
            'tools/mandatory_input_types_v0_1_0.cwl': 6,
            'tools/optional_input_types_v0_1_0.cwl': 5,
            'tools/subworkflow.cwl': 6,
        }
        for filepath, filecontents in sub_tasks:
            if _is_cwl_clt(filecontents):
                clt_inputs = _get_cwl_clt_inputs(filecontents)
                
                # checking expected number of clt inputs
                self.assertEqual(len(clt_inputs), expected_num_clt_inputs[filepath])

                # checking clt inputs have inputBindings
                for inp in clt_inputs:
                    self.assertNotIn('inputBinding', inp)
    
    @unittest.skip('not implemented')
    def test_skeleton_wdl(self) -> None:
        # TODO
        settings.translate.MODE = 'skeleton'
        filepath = f'{CWL_TESTDATA_PATH}/workflows/subworkflow_test/main.cwl'
        _, _, subwfs, sub_tasks = _run(filepath, srcfmt='cwl', destfmt='wdl')
        for filepath, filecontents in sub_tasks:
            if _is_wdl_task(filecontents):
                command_lines = _get_wdl_task_command_lines(filecontents)
                self.assertEqual(len(command_lines), 2)
    
    @unittest.skip('not implemented')
    def test_regular_cwl1(self) -> None:
        settings.translate.MODE = 'regular'
        filepath = f'{CWL_TESTDATA_PATH}/workflows/subworkflow_test/main.cwl'
        maintask, _, sub_tasks = _run(filepath, srcfmt='cwl', destfmt='cwl')

        # main
        expected_num_clt_inputs = 12
        clt_inputs = _get_cwl_clt_inputs(maintask)
        self.assertEqual(len(clt_inputs), expected_num_clt_inputs)

        # subtasks
        expected_num_clt_inputs = {
            'tools/basic_v0_1_0.cwl': 6,
            'tools/mandatory_input_types_v0_1_0.cwl': 6,
            'tools/optional_input_types_v0_1_0.cwl': 5,
            'tools/subworkflow.cwl': 6,
        }
        for filepath, filecontents in sub_tasks:
            if _is_cwl_clt(filecontents):
                clt_inputs = _get_cwl_clt_inputs(filecontents)
                
                # checking expected number of clt inputs
                self.assertEqual(len(clt_inputs), expected_num_clt_inputs[filepath])

                # checking clt inputs have inputBindings
                for inp in clt_inputs:
                    self.assertIn('inputBinding', inp)
    
    @unittest.skip('not implemented')
    def test_regular_cwl2(self) -> None:
        settings.translate.MODE = 'regular'
        filepath = f'{CWL_TESTDATA_PATH}/workflows/m-unlock/workflows/ngtax.cwl'
        _, _, subwfs, sub_tasks = _run(filepath, srcfmt='cwl', destfmt='cwl')
        expected_num_clt_inputs = {
            'tools/fastqc_v0_1_0.cwl': 2,
            'tools/files_to_folder_v0_1_0.cwl': 2,
            'tools/ngtax_v0_1_0.cwl': 9,
            'tools/ngtax_to_tsv_fasta_v0_1_0.cwl': 4,
        }
        expected_input_binding_absence = {
            'tools/fastqc_v0_1_0.cwl': [],
            'tools/files_to_folder_v0_1_0.cwl': ['files', 'folders', 'destination'],
            'tools/ngtax_v0_1_0.cwl': ['sample', 'fragment'],
            'tools/ngtax_to_tsv_fasta_v0_1_0.cwl': ['metadata', 'input', 'identifier', 'fragment'],
        }
        expected_num_clt_args = {
            'tools/fastqc_v0_1_0.cwl': 2,
            'tools/files_to_folder_v0_1_0.cwl': 1,
            'tools/ngtax_v0_1_0.cwl': 4,
            'tools/ngtax_to_tsv_fasta_v0_1_0.cwl': 8,
        }
        for filepath, filecontents in sub_tasks:
            if _is_cwl_clt(filecontents):
                clt_inputs = _get_cwl_clt_inputs(filecontents)
                clt_args = _get_cwl_clt_args(filecontents)
                
                # checking expected number of clt inputs
                self.assertEqual(len(clt_inputs), expected_num_clt_inputs[filepath])
                # checking expected number of clt args
                self.assertEqual(len(clt_args), expected_num_clt_args[filepath])

                # checking clt inputs have or do not have inputBindings
                for inp in clt_inputs:
                    if inp['id'] not in expected_input_binding_absence[filepath]:
                        self.assertIn('inputBinding', inp)
                    else:
                        self.assertNotIn('inputBinding', inp)
    
    @unittest.skip('implement me')
    def test_regular_wdl(self) -> None:
        settings.translate.MODE = 'regular'
        filepath = f'{CWL_TESTDATA_PATH}/workflows/subworkflow_test/main.cwl'
        _, _, subwfs, sub_tasks = _run(filepath, srcfmt='cwl', destfmt='wdl')
        expected_num_clt_inputs = {
            'align_and_tag_v0_1_0': 3,
            'index_bam_v0_1_0': 1,
            'mark_duplicates_and_sort_v0_1_0': 3,
            'merge_bams_samtools_v0_1_0': 2,
            'name_sort_v0_1_0': 1,
        }
        expected_input_binding_absence = {
            'align_and_tag_v0_1_0': [],
            'index_bam_v0_1_0': ['bam'],
            'mark_duplicates_and_sort_v0_1_0': [],
            'merge_bams_samtools_v0_1_0': ['name'],
            'name_sort_v0_1_0': [],
        }
        for filepath, filecontents in sub_tasks:
            if _is_wdl_task(filecontents):
                command_lines = _get_wdl_task_command_lines(filecontents)
                raise NotImplementedError

    @unittest.skip('not implemented')
    def test_extended_cwl(self) -> None:
        settings.translate.MODE = 'extended'
        filepath = f'{CWL_TESTDATA_PATH}/workflows/subworkflow_test/main.cwl'
        _, _, subwfs, sub_tasks = _run(filepath, srcfmt='cwl', destfmt='cwl')
        expected_num_clt_inputs = {
            'tools/basic_v0_1_0.cwl': 7,
            'tools/mandatory_input_types_v0_1_0.cwl': 6,
            'tools/optional_input_types_v0_1_0.cwl': 6,
        }
        for filepath, filecontents in sub_tasks:
            if _is_cwl_clt(filecontents):
                clt_inputs = _get_cwl_clt_inputs(filecontents)
                
                # checking expected number of clt inputs
                self.assertEqual(len(clt_inputs), expected_num_clt_inputs[filepath])

                # checking clt inputs have inputBindings
                for inp in clt_inputs:
                    self.assertIn('inputBinding', inp)

    @unittest.skip('implement me')
    def test_extended_wdl(self) -> None:
        settings.translate.MODE = 'extended'
        filepath = f'{CWL_TESTDATA_PATH}/workflows/subworkflow_test/main.cwl'
        _, _, subwfs, sub_tasks = _run(filepath, srcfmt='cwl', destfmt='wdl')
        expected_num_clt_inputs = {
            'align_and_tag_v0_1_0': 3,
            'index_bam_v0_1_0': 1,
            'mark_duplicates_and_sort_v0_1_0': 3,
            'merge_bams_samtools_v0_1_0': 2,
            'name_sort_v0_1_0': 1,
        }
        expected_input_binding_absence = {
            'align_and_tag_v0_1_0': [],
            'index_bam_v0_1_0': ['bam'],
            'mark_duplicates_and_sort_v0_1_0': [],
            'merge_bams_samtools_v0_1_0': ['name'],
            'name_sort_v0_1_0': [],
        }
        for filepath, filecontents in sub_tasks:
            if _is_wdl_task(filecontents):
                raise NotImplementedError




class TestCaseFormatting(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()
        wf = AssemblyTestWF()
        self.wf = to_builders(wf)

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
        expected = set(['the_file'])
        actual = set([x.id() for x in wf.output_nodes.values()])
        self.assertSetEqual(expected, actual)
        
        # tool inputs
        tool = wf.step_nodes['cwl'].tool
        assert isinstance(tool, CommandToolBuilder)
        expected = set([
            'in_filename',
            'inp',
            'input',
            'out',
            'output',
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
            'theFile','theFileOpt','theFileArr','theFilenamePath','theBam',
            'theBamBai','theBamBaiArr','theStr','theStrOpt','theInt',
            'theIntOpt','theFloat','theFloatOpt','theBool',
        ])
        actual = set([x.id() for x in wf.input_nodes.values()])
        self.assertSetEqual(expected, actual)

        # workflow outputs
        expected = set(['outTheFile'])
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

