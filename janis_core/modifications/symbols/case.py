
from typing import Any
from enum import Enum, auto

from janis_core import settings
from janis_core import CommandToolBuilder, CodeTool, WorkflowBuilder
from janis_core import ToolInput, ToolOutput
from janis_core.workflow.workflow import InputNode, OutputNode, StepNode


def format_case(entity: Any, text: str) -> str:    
    words = split_words(text)
    new_case = select_case(entity)
    new_text = apply_case(words, new_case)
    return new_text


###############################
### splitting original text ###
###############################

def split_words(text: str) -> list[str]:
    out: list[str] = [text]
    out = split_underscores(out)
    out = split_hyphens(out)
    out = split_lower_upper(out)
    # out = split_camel(out)
    # out = split_pascal(out)
    out = [x.lower() for x in out]
    return out

def split_underscores(words: list[str]) -> list[str]:
    out: list[str] = []
    for word in words:
        out += word.split('_')
    return out

def split_hyphens(words: list[str]) -> list[str]:
    out: list[str] = []
    for word in words:
        out += word.split('-')
    return out

def split_lower_upper(words: list[str]) -> list[str]:
    out: list[str] = []
    for word in words:
        cword = ''
        for i in range(len(word)):
            if i < len(word) - 1:
                cword += word[i]
                if word[i].islower() and word[i+1].isupper():
                    # export current word, reset cword
                    out.append(cword)
                    cword = ''
        out.append(cword + word[-1])
    return out


##########################
### selecting new case ###
##########################

# enum for different supported cases
class CaseFmt(Enum):
    CAMEL = auto()
    KEBAB = auto()
    PASCAL = auto()
    SNAKE_UPPER = auto()
    SNAKE_LOWER = auto()

# language default cases
CWL_DEFAULT_CASE = CaseFmt.SNAKE_LOWER
NXF_DEFAULT_CASE = CaseFmt.SNAKE_LOWER
WDL_DEFAULT_CASE = CaseFmt.CAMEL

# language special cases
cwl_map = {
    "file": CaseFmt.KEBAB,
    "directory": CaseFmt.KEBAB,
}
nxf_map = {
    "file": CaseFmt.SNAKE_LOWER,
    "tool": CaseFmt.SNAKE_UPPER,
    "workflow": CaseFmt.SNAKE_UPPER,
}
wdl_map = {
    "file": CaseFmt.SNAKE_LOWER,
    "directory": CaseFmt.SNAKE_LOWER,
    "tool": CaseFmt.PASCAL,
    "workflow": CaseFmt.PASCAL,
    "struct": CaseFmt.PASCAL,
}

def select_case(entity: Any) -> CaseFmt:
    if settings.translate.DEST == 'cwl':
        case_map = cwl_map
        default_case = CWL_DEFAULT_CASE
    elif settings.translate.DEST == 'nextflow':
        case_map = nxf_map
        default_case = NXF_DEFAULT_CASE
    elif settings.translate.DEST == 'wdl':
        case_map = wdl_map
        default_case = WDL_DEFAULT_CASE
    else:
        raise RuntimeError
    
    # filenames
    if isinstance(entity, str):
        return case_map.get(entity, default_case)
    
    # tool
    if isinstance(entity, CommandToolBuilder | CodeTool):
        return case_map.get('tool', default_case)
    elif isinstance(entity, ToolInput):
        return case_map.get('tool_input', default_case)
    elif isinstance(entity, ToolOutput):
        return case_map.get('tool_output', default_case)
    
    # workflow
    elif isinstance(entity, WorkflowBuilder):
        return case_map.get('workflow', default_case)
    elif isinstance(entity, InputNode):
        return case_map.get('workflow_input', default_case)
    elif isinstance(entity, StepNode):
        return case_map.get('workflow_step', default_case)
    elif isinstance(entity, OutputNode):
        return case_map.get('workflow_output', default_case)
    
    # fallback
    else:
        return default_case
        

#########################
### applying new case ###
#########################

def apply_case(words: list[str], fmt: CaseFmt) -> str:
    if fmt == CaseFmt.CAMEL:
        return as_camel(words)
    elif fmt == CaseFmt.KEBAB:
        return as_kebab(words)
    elif fmt == CaseFmt.PASCAL:
        return as_pascal(words)
    elif fmt == CaseFmt.SNAKE_LOWER:
        return as_snake_lower(words)
    elif fmt == CaseFmt.SNAKE_UPPER:
        return as_snake_upper(words)
    else:
        raise NotImplementedError

def as_camel(words: list[str]) -> str:
    if len(words) == 0:
        return ''
    elif len(words) == 1:
        return words[0]
    else:
        return words[0] + ''.join([x.capitalize() for x in words[1:]])

def as_pascal(words: list[str]) -> str:
    if len(words) == 0:
        return ''
    else:
        return ''.join([x.capitalize() for x in words])

def as_kebab(words: list[str]) -> str:
    return '-'.join(words)

def as_snake_lower(words: list[str]) -> str:
    return '_'.join(words)

def as_snake_upper(words: list[str]) -> str:
    words = [x.upper() for x in words]
    return '_'.join(words)

