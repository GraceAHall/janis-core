



import json
from typing import Any

# from .expand import expand_tool_state
# from .flatten import get_flattened_tool_state
# from .resolve import resolve_values
# from .standardisation import standardise_tool_state

from janis_core.ingestion.galaxy.gx.gxtool import load_xmltool
from janis_core.ingestion.galaxy import settings
from .resolve import resolve_values
from .flatten import flatten


# MODULE ENTRY
def load_tool_state(step: dict[str, Any], flat: bool=False) -> dict[str, Any]:
    xmltool = load_xmltool(settings.tool.tool_path)
    step['tool_state'] = json.loads(step['tool_state'])
    step['tool_state'] = resolve_values(step, xmltool)
    if flat:
        step['tool_state'] = flatten(step['tool_state'])
    return step['tool_state']


# def load_tool_state_flat(step: dict[str, Any]) -> dict[str, Any]:
#     step['tool_state'] = expand_tool_state(step)  # string -> json object
#     step['tool_state'] = get_flattened_tool_state(step)
#     step['tool_state'] = resolve_values(step)
#     step['tool_state'] = standardise_tool_state(step)
#     return step['tool_state']




