

import wdlgen as wdl
from typing import Any
from janis_core import settings
from janis_core.messages import load_loglines

from janis_core.tool.commandtool import ToolInput
from janis_core.types.common_data_types import (
    Array,
    Boolean,
    File,
    Directory,
    String,
)

from . import utils

# if not utils.is_defined(inp):
#     expr = f'if defined({inp.id()}) then {expr} else "generated"'

def translate_command_input(tool_input: ToolInput, inputsdict=None):
    # make sure it has some essence of a command line binding, else we'll skip it
    if not (tool_input.position is not None or tool_input.prefix):
        return None

    if tool_input.localise_file and tool_input.presents_as:
        return wdl.Task.Command.CommandInput(
            value=tool_input.presents_as, position=tool_input.position
        )
    
    expr = utils.resolve_tool_input_value(tool_input)

    if _is_boolean(tool_input):
        expr = _format_boolean(expr, tool_input) 
    elif _is_array(tool_input):
        expr = _format_array(expr, tool_input) 
    elif _is_file(tool_input):
        expr = _format_file(expr, tool_input) 
    else:
        expr = _format_generic(expr, tool_input) 

    # there used to be a whole lot of login in the wdl.Task.Command.CommandInput but it's been moved to here now
    return wdl.Task.Command.CommandInput(value=expr, position=tool_input.position)

def _is_boolean(tool_input: ToolInput):
    if isinstance(tool_input.input_type, Boolean) and tool_input.prefix:
        return True 
    return False 

def _is_array(tool_input: ToolInput):
    return tool_input.input_type.is_array()

def _is_file(tool_input: ToolInput):
    if isinstance(tool_input.input_type, (File, String, Directory)):
        if tool_input.shell_quote is not False:
            return True
    return False

def _format_boolean(expr: str, tool_input: ToolInput):
    return f'~{{true="{tool_input.prefix}" false="" {expr}}}'

def _format_array(expr: str, tool_input: ToolInput):
    
    ### helper attributes ###
    datatype = tool_input.input_type
    basetype = datatype.subtype()
    while isinstance(basetype, Array):
        basetype = basetype.subtype()
    prefix = _prefix(tool_input)
    defined = utils.is_defined(tool_input)
    should_quote = _should_quote(tool_input, basetype)

    ### condition ###
    condition_for_binding = None
    
    # check if defined, check at least 1 non-null element
    if not defined and basetype.optional:   
        non_null = f"select_all({expr})"
        condition_for_binding = f"(defined({expr}) && length({non_null}) > 0)"
        expr = non_null
    
    # check if defined
    elif not defined:                       
        condition_for_binding = f"defined({expr})"
    
    # check at least 1 non-null element
    elif basetype.optional:                 
        non_null = f"select_all({expr})"
        condition_for_binding = f"(length({non_null}) > 0)"
        expr = non_null

    ### should quote ###
    if tool_input.prefix_applies_to_all_elements and should_quote:
        expr = f'\'"\' + sep(\'" {prefix} "\', {expr}) + \'"\''
    elif should_quote:
        expr = f'\'"\' + sep(\'" "\', {expr})" + \'"\''

    ### final formatting ###
    # wrap in conditional if necessary
    if condition_for_binding is not None:
        expr = f'~{{if {condition_for_binding} then {expr} else ""}}'
    else:
        expr = f'~{{{expr}}}'
    # prefix before WDL.Part
    if prefix:
        expr = f'{prefix}{expr}'

    return expr

def _format_file(expr: str, tool_input: ToolInput):
    prefix = _prefix(tool_input)
    defined = utils.is_defined(tool_input)

    if prefix and not defined:
        expr = f'~{{if defined({expr}) then ("{prefix}\'" + {expr} + "\'") else ""}}'
    elif prefix:
        expr = f"{prefix}'~{{{expr}}}'"
    elif not defined:
        expr = f'~{{if defined({expr}) then ("\'" + {expr} + "\'") else ""}}'
    else:
        expr = f"'~{{{expr}}}'"
    return expr

def _format_generic(expr: str, tool_input: ToolInput):
    prefix = _prefix(tool_input)
    defined = utils.is_defined(tool_input)

    if prefix and not defined:
        expr = f"~{{if defined({expr}) then (\"{prefix}\" + {expr}) else ''}}"
    elif prefix:
        expr = f"{prefix}~{{{expr}}}"
    else:
        expr = f"~{{{expr}}}"
    return expr 

def _prefix(tool_input: ToolInput) -> str:
    prefix = tool_input.prefix if tool_input.prefix else ""
    if prefix and tool_input.separate_value_from_prefix != False:
        prefix += " "
    return prefix 

def _separator(tool_input: ToolInput) -> str:
    return tool_input.separator if tool_input.separator is not None else " "

def _should_quote(tool_input: ToolInput, basetype: Any) -> bool:
    if isinstance(basetype, (String, File, Directory)):
        if tool_input.shell_quote is not False:
            return True 
    return False
    
