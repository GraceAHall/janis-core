

from typing import Any, Optional, Callable
from .common.filters import (
    deindent,
    remove_blank_lines,
    flatten_multiline_strings,
    # translate_variable_markers,
    # standardise_variable_format,
    simplify_sh_constructs,
    simplify_galaxy_dynamic_vars,
    remove_cheetah_comments,
    replace_python_str_functions,
    replace_function_calls,
    replace_backticks,
    remove_dataset_attributes,
    remove_dataset_methods,
    remove_empty_quotes,

)

from ..tool import XMLToolDefinition

# from ..load import load_xmltool
# from .common.aliases import resolve_aliases
# from .common.simplify import simplify_cmd
# from janis_core.ingestion.galaxy import settings

filter_funcs = [
    deindent,
    remove_dataset_attributes,
    remove_dataset_methods,
    remove_blank_lines,
    remove_cheetah_comments,
    flatten_multiline_strings,
    replace_python_str_functions,
    replace_function_calls,
    replace_backticks,
    simplify_sh_constructs,
    simplify_galaxy_dynamic_vars,
    remove_empty_quotes,
]

def simplify_xmltool_command(
    xmltool: XMLToolDefinition, 
    inputs_dict: Optional[dict[str, Any]]=None,
    additional_filters: list[str]=[]
    ) -> str: 
    """ 
    simplifies the <command> section (cmdstr) of a galaxy tool. 
    if inputs_dict is present, will simplify the command using supplied inputs.
    returns a list of strings. each string is a line of the simplified command.
    """
    default_filters = [
        'simplify_galaxy_dynamic_vars',
        'simplify_sh_constructs',
        'remove_cheetah_comments',
        'remove_blank_lines'
    ]
    filter_names = set(default_filters + additional_filters)
    filters_to_apply: list[Callable[[str, XMLToolDefinition, Optional[dict[str, str]]], str]] = []
    # (lol python type hints)
    
    global filter_funcs
    for func in filter_funcs:
        if func.__name__ in filter_names:
            filters_to_apply.append(func)

    cmdstr = xmltool.raw_command
    for func in filters_to_apply:
        cmdstr = func(cmdstr, xmltool, inputs_dict)
    return cmdstr


# def do_general_simplification(cmdstr: str) -> str:
#     filters: list[Callable[[str], str]] = [
#         deindent,
#         remove_blank_lines,
#         remove_cheetah_comments,
#         flatten_multiline_strings,
#         replace_python_str_functions,
#         replace_function_calls,
#         replace_backticks,
#         # standardise_variable_format,  # ?
#         simplify_sh_constructs,
#         simplify_galaxy_dynamic_vars,
#         # remove_empty_quotes,
#         interpret_raw  # ?
#     ]
#     for func in filters:
#         cmdstr = func(cmdstr)
#     return cmdstr

# def do_evaluation_simplification(cmdstr: str, inputs_dict: dict[str, Any]) -> str:
#     textlines = cmdstr.split('\n')
#     textlines = cheetah_evaulate(textlines, inputs_dict)
#     # evaluator = PartialCheetahEvaluator(textlines, inputs_dict)
#     # textlines = evaluator.evaluate()
#     textlines = '\n'.join(textlines)
#     return textlines


# def load_command_workflowmode(xmltool: XMLToolDefinition, inputs_dict: dict[str, Any]) -> str:
#     pass

# def load_command_toolmode(xmltool: XMLToolDefinition) -> str:
#     text = simplify_cmd(xmltool.raw_command, 'xml')
#     # text = resolve_aliases(text)
#     return text

# def load_partial_cheetah_command(xmltool: XMLToolDefinition, inputs_dict: dict[str, Any]) -> str:
#     text = xmltool.raw_command
#     text = simplify_cmd(text, 'cheetah')
#     text = sectional_evaluate(text, inputs=inputs_dict)
#     # text = resolve_aliases(text)
#     return text
