
from networkx.drawing.nx_agraph import write_dot, graphviz_layout
import matplotlib.pyplot as plt
import networkx as nx
import unittest
import os 

from janis_core import settings
from janis_core.settings.translate import ERenderCmd, ESimplification
from janis_core.messages import configure_logging

from janis_core import WorkflowBuilder
from janis_core.ingestion import ingest
from janis_core.translations import nextflow
from janis_core.modifications import to_builders

from janis_core.tests.testworkflows import PruneFlatTW
from janis_core.tests.testworkflows import PruneNestedTW
from janis_core.tests.testworkflows import AssemblyTestWF
from janis_core.tests.testworkflows import IllegalSymbolsTestWF
from janis_core.tests.testworkflows import UnwrapTestWF
from janis_core.tests.testworkflows import SubworkflowTestWF
from janis_core.tests.testworkflows import SimplificationScatterTestWF

from janis_core.introspection.graph import get_graph
from janis_core.introspection.graph import get_primary_workflow_inputs
from janis_core.introspection.graph import get_step_order

CWL_TESTDATA_PATH = os.path.join(os.getcwd(), 'janis_core/tests/data/cwl')
GALAXY_TESTTOOL_PATH = os.path.join(os.getcwd(), 'janis_core/tests/data/galaxy/wrappers')
GALAXY_TESTWF_PATH = os.path.join(os.getcwd(), 'janis_core/tests/data/galaxy/workflows')
JANIS_TESTDATA_PATH = os.path.join(os.getcwd(), 'janis_core/tests/data/janis')
WDL_TESTDATA_PATH = os.path.join(os.getcwd(), 'janis_core/tests/data/wdl')
OUTPUT_DIR = os.path.join(os.getcwd(), "janis_core/tests/outputs")

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


def render_graph(graph: nx.DiGraph, filepath: str) -> None:
    fig = plt.figure(1, figsize=(10, 10), dpi=60)
    pos = graphviz_layout(graph, prog='dot')
    # pos = nx.spring_layout(graph)
    nx.draw_networkx(graph, pos, with_labels=True, node_size=1200, node_color='pink', alpha=0.9)
    # nx.draw_networkx_edges(graph, pos, width=0.7, arrows=True, arrowstyle='-|>', arrowsize=10, min_source_margin=25, min_target_margin=25)
    # nx.draw_networkx_labels(graph, pos, font_size=9, font_family="sans-serif")
    # nx.draw_networkx_edge_labels(
    #     graph, pos, font_color='red', font_size=8, 
    #     edge_labels={e: graph.edges[e]['label'] for e in graph.edges}
    # )
    plt.tight_layout()
    plt.savefig(filepath)
    plt.close(fig)


class TestNetworkxGraphs(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()

    def test_flat_workflow(self) -> None:
        wf = PruneFlatTW()
        wf = to_builders(wf)
        assert isinstance(wf, WorkflowBuilder)
        graph = get_graph(wf)
        outfile = os.path.join(OUTPUT_DIR, wf.id() + ".png")
        render_graph(graph, outfile)
    
    def test_from_cwl(self) -> None:
        infile = f'{CWL_TESTDATA_PATH}/workflows/super_enhancer_wf.cwl'
        wf = ingest(infile, 'cwl')
        wf = to_builders(wf)
        assert isinstance(wf, WorkflowBuilder)
        graph = get_graph(wf)
        outfile = os.path.join(OUTPUT_DIR, wf.id() + ".png")
        render_graph(graph, outfile)

        expected_nodes = [
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
        actual_nodes = list(graph.nodes.keys())
        self.assertSetEqual(set(expected_nodes), set(actual_nodes))
        
        expected_edges = [
            'make_gff|run_rose',
            'run_rose|rename_png',
            'run_rose|sort_bed',
            'sort_bed|add_island_names',
            'sort_bed|bed_to_macs',
            'sort_bed|reduce_bed',
            'bed_to_macs|assign_genes',
            'assign_genes|add_island_names',
            'reduce_bed|bed_to_bigbed',
        ]
        actual_edges = [f'{u}|{v}' for u, v in graph.edges]
        self.assertSetEqual(set(expected_edges), set(actual_edges))



class TestStepOrdering(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()

    def test_from_cwl(self) -> None:
        infile = f'{CWL_TESTDATA_PATH}/workflows/super_enhancer_wf.cwl'
        wf = ingest(infile, 'cwl')
        wf = to_builders(wf)
        assert isinstance(wf, WorkflowBuilder)
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
        actual_order = get_step_order(wf)
        self.assertListEqual(expected_order, actual_order)


class TestPrimaryWorkflowInputs(unittest.TestCase):

    def setUp(self) -> None:
        _reset_global_settings()

    def test_from_cwl(self) -> None:
        infile = f'{CWL_TESTDATA_PATH}/workflows/super_enhancer_wf.cwl'
        wf = ingest(infile, 'cwl')
        wf = to_builders(wf)
        assert isinstance(wf, WorkflowBuilder)
        actual_inputs = get_primary_workflow_inputs(wf)
        expected_inputs = ['islands_file']
        self.assertSetEqual(set(expected_inputs), set(actual_inputs))



