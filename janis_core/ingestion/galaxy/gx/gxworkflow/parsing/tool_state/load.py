



from typing import Any
import json

from .expand import expand_tool_state
from .flatten import get_flattened_tool_state
from .resolve import resolve_values
from .standardisation import standardise_tool_state
from janis_core.ingestion.galaxy.gx.gxtool import XMLToolDefinition

# MODULE ENTRY
def load_tool_state(step: dict[str, Any], xmltool: XMLToolDefinition) -> dict[str, Any]:
    step['tool_state'] = to_json(step)
    step['tool_state'] = get_flattened_tool_state(step, xmltool)
    # step['tool_state'] = resolve_values(step)
    # step['tool_state'] = standardise_tool_state(step)
    return step['tool_state']

def load_tool_state_old(step: dict[str, Any]) -> dict[str, Any]:
    step['tool_state'] = expand_tool_state(step)  # string -> json object
    step['tool_state'] = get_flattened_tool_state(step)
    step['tool_state'] = resolve_values(step)
    step['tool_state'] = standardise_tool_state(step)
    return step['tool_state']


def to_json(step: dict[str, Any]) -> dict[str, Any]:
    return json.loads(step['tool_state'])





