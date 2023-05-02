

from typing import Any

from janis_core.ingestion.galaxy.model.tool import Tool
from janis_core.ingestion.galaxy.model.workflow import StepMetadata
from janis_core.ingestion.galaxy.model.workflow import Workflow

from janis_core.ingestion.galaxy.startup import tool_setup
from janis_core.ingestion.galaxy.ingest import ingest_tool
from janis_core.ingestion.galaxy.gx.gxworkflow.parsing.tool_state import load_tool_state
from janis_core.ingestion.galaxy.gx.wrappers.downloads.main import get_builtin_tool_path

from janis_core.ingestion.galaxy import mapping
from janis_core.ingestion.galaxy import settings


def ingest_workflow_tools(janis: Workflow, galaxy: dict[str, Any]) -> None:
    for g_step in galaxy['steps'].values():
        if g_step['type'] == 'tool':
            j_step = mapping.step(g_step['id'], janis, galaxy)
            tool = parse_step_tool(j_step.metadata)
            j_step.set_tool(tool)
            g_step['tool_state'] = load_tool_state(g_step)
            # g_step['tool_state'] = load_tool_state(g_step)

def parse_step_tool(metadata: StepMetadata) -> Tool:
    args = create_tool_settings_for_step(metadata)
    tool_setup(args)
    return ingest_tool(settings.tool.tool_path)

def create_tool_settings_for_step(metadata: StepMetadata) -> dict[str, Any]:
    tool_id = metadata.wrapper.tool_id
    if metadata.wrapper.inbuilt:
        xml_path = get_builtin_tool_path(tool_id)
        assert(xml_path)
        return {
            'infile': xml_path,
            'remote': None,
            'outdir': None
            #'outdir': f'{paths.wrapper(tool_id, tool_id)}'
        }
    else:
        revision = metadata.wrapper.revision
        owner = metadata.wrapper.owner
        repo = metadata.wrapper.repo
        return {
            'infile': None,
            'remote': f'{owner},{repo},{tool_id},{revision}',
            'outdir': None
            #'outdir': f'{paths.wrapper(tool_id, revision)}'
        }
