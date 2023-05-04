

from typing import Any, Optional

from janis_core.ingestion.galaxy import expressions
from janis_core.ingestion.galaxy.expressions.patterns import (
    FUNCTION_CALL_FMT1,
    FUNCTION_CALL_FMT2,
    BACKTICK_SECTION,
    QUOTED_SECTION,
    GX_DYNAMIC_KEYWORDS,
    PYTHON_STR_FUNC,
    GX_ATTRIBUTE
    # GX_STATIC_KEYWORDS,
)

from .. import utils
from ...tool import XMLToolDefinition

def remove_dataset_attributes(cmdstr: str, xmltool: XMLToolDefinition, inputs_dict: Optional[dict[str, Any]]) -> str:
    known_attributes = [
        # properties
        'ext',
        'element_identifier',
        'extra_files_path',
        # attributes
        'name',
        'extension',
        'id',
    ]
    for attr in known_attributes:
        expr = GX_ATTRIBUTE.format(attribute=attr)
        matches = expressions.get_matches(cmdstr, expr)
        for match in reversed(matches):
            # logging.has_backtick_statement()
            top = cmdstr[:match.start()]
            middle = match.groups()[0]
            bottom = cmdstr[match.end():]
            cmdstr = top + middle + bottom
    return cmdstr

def remove_dataset_methods(cmdstr: str, xmltool: XMLToolDefinition, inputs_dict: Optional[dict[str, Any]]) -> str:
    known_methods = [
        'is_of_type'
    ]
    return cmdstr

def deindent(cmdstr: str, xmltool: XMLToolDefinition, inputs_dict: Optional[dict[str, Any]]) -> str:
    textlines = cmdstr.split('\n')
    textlines = [ln.strip() for ln in textlines]
    return '\n'.join(textlines)

def remove_blank_lines(cmdstr: str, xmltool: XMLToolDefinition, inputs_dict: Optional[dict[str, Any]]) -> str:
    textlines = cmdstr.split('\n')
    textlines = [ln for ln in textlines if ln.strip() != '']
    return '\n'.join(textlines)

def replace_python_str_functions(cmdstr: str, xmltool: XMLToolDefinition, inputs_dict: Optional[dict[str, Any]]) -> str:
    matches = expressions.get_matches(cmdstr, PYTHON_STR_FUNC)
    for match in matches:
        # logging.has_python_str_function()
        old_section = match[0]
        new_section = match[1]
        cmdstr = cmdstr.replace(old_section, new_section)
    return cmdstr

def replace_function_calls(cmdstr: str, xmltool: XMLToolDefinition, inputs_dict: Optional[dict[str, Any]]) -> str:
    cmdlines = utils.split_lines(cmdstr)
    out: list[str] = []
    for line in cmdlines:
        matches = expressions.get_matches(line, FUNCTION_CALL_FMT1)
        matches += expressions.get_matches(line, FUNCTION_CALL_FMT2)
        for match in matches:
            # logging.has_cheetah_function()
            old_section = match[0]
            new_section = '__FUNCTION_CALL__'
            line = line.replace(old_section, new_section)
        out.append(line)
    return utils.join_lines(out)

def replace_backticks(cmdstr: str, xmltool: XMLToolDefinition, inputs_dict: Optional[dict[str, Any]]) -> str:
    matches = expressions.get_matches(cmdstr, BACKTICK_SECTION)
    for match in matches:
        # logging.has_backtick_statement()
        old_section = match[0]
        new_section = '__BACKTICK_SHELL_STATEMENT__'
        cmdstr = cmdstr.replace(old_section, new_section)
    return cmdstr

def interpret_raw(cmdstr: str, xmltool: XMLToolDefinition, inputs_dict: Optional[dict[str, Any]]) -> str:
    return cmdstr.replace('\\', '')  # ? why

def flatten_multiline_strings(cmdstr: str, xmltool: XMLToolDefinition, inputs_dict: Optional[dict[str, Any]]) -> str:
    matches = expressions.get_matches(cmdstr, QUOTED_SECTION)
    for match in matches:
        if '\n' in match[0]:
            # logging.has_multiline_str()
            old_section = match[0]
            new_section = match[0].replace('\n', ' ')
            cmdstr = cmdstr.replace(old_section, new_section)
    return cmdstr

def translate_variable_markers(cmdstr: str, xmltool: XMLToolDefinition, inputs_dict: Optional[dict[str, Any]]) -> str:
    return cmdstr.replace("gxparam_", "$")

def standardise_variable_format(cmdstr: str, xmltool: XMLToolDefinition, inputs_dict: Optional[dict[str, Any]]) -> str:
    """standardises different forms of a galaxy variable ${var}, $var etc"""
    cmdlines: list[str] = utils.split_lines(cmdstr)
    outlines: list[str] = [remove_var_braces(line) for line in cmdlines]
    return utils.join_lines(outlines)

def remove_var_braces(cmdstr: str, xmltool: XMLToolDefinition) -> str:
    """
    modifies cmd word to ensure the $var format is present, rather than ${var}
    takes a safe approach using regex and resolving all vars one by one
    """
    return cmdstr
    # if text == '':
    #     return text
    # matches = scanners.get_variables_fmt2(text)
    # if len(matches) > 0:
    #     m = matches[0]
    #     # this is cursed but trust me it removes the curly braces for the match span
    #     old_segment = text[m.start(): m.end()]
    #     new_segment = old_segment[0] + old_segment[2: -1]
    #     new_segment = new_segment.replace(' ', '')
    #     text = text.replace(old_segment, new_segment)
    #     text = remove_var_braces(text)
    # return text  

def remove_empty_quotes(cmdstr: str, xmltool: XMLToolDefinition, inputs_dict: Optional[dict[str, Any]]) -> str:
    cmdstr = cmdstr.replace('""', '')
    cmdstr = cmdstr.replace("''", '')
    return cmdstr

def simplify_sh_constructs(cmdstr: str, xmltool: XMLToolDefinition, inputs_dict: Optional[dict[str, Any]]) -> str:
    """
    this function standardises the different equivalent 
    forms of linux operations into a single common form
    """
    cmdstr = cmdstr.replace("&amp;", "&")
    cmdstr = cmdstr.replace("&lt;", "<")
    cmdstr = cmdstr.replace("&gt;", ">")
    cmdstr = cmdstr.replace("|&", "2>&1 |")
    cmdstr = cmdstr.replace("| tee", "|tee")
    cmdstr = cmdstr.replace("1>", ">")
    return cmdstr 

def simplify_galaxy_dynamic_vars(cmdstr: str, xmltool: XMLToolDefinition, inputs_dict: Optional[dict[str, Any]]) -> str:
    """  ${GALAXY_SLOTS:-2} -> 2   etc """
    matches = expressions.get_matches(cmdstr, GX_DYNAMIC_KEYWORDS)
    for match in matches:
        cmdstr = cmdstr.replace(match[0], match.group(1)) 
    return cmdstr

def remove_cheetah_comments(cmdstr: str, xmltool: XMLToolDefinition, inputs_dict: Optional[dict[str, Any]]) -> str:
    """
    removes cheetah comments from shellparser lines
    comments can be whole line, or part way through
    """
    cmdlines: list[str] = utils.split_lines(cmdstr)
    outlines: list[str] = []

    for line in cmdlines:
        comment_start, _ = expressions.find_unquoted(line, '##')
        if comment_start != -1:
            # override line with comment removed
            line = line[:comment_start].strip()
        # make sure we didnt trim a full line comment and now its an empty string
        if line != '':
            outlines.append(line)
    return utils.join_lines(outlines)


