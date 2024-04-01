

from typing import Optional

from janis_core import DataType
from janis_core import settings

from ..casefmt import to_case


### GENERAL

def gen_varname_workflow(basename: str) -> str:
    return to_case(basename, settings.translate.nextflow.NF_PROCESS_CASE)

def gen_varname_process(basename: str) -> str:
    return to_case(basename, settings.translate.nextflow.NF_PROCESS_CASE)

def gen_varname_channel(janis_tag: str, name_override: Optional[str]=None, dtype: Optional[DataType]=None) -> str:
    basename = name_override if name_override else janis_tag
    # basename = _handle_plurals(basename, dtype)
    name = to_case(basename, settings.translate.nextflow.NF_CHANNEL_CASE)
    name = f'ch_{name}'
    return name

def gen_varname_file(janis_tag: str, name_override: Optional[str]=None, dtype: Optional[DataType]=None) -> str:
    basename = name_override if name_override else janis_tag
    # basename = _handle_plurals(basename, dtype)
    name = to_case(basename, settings.translate.nextflow.NF_CHANNEL_CASE)
    return name

def gen_varname_param(
    task_id: str, 
    subtype: str,
    tinput_id: Optional[str]=None, 
    name_override: Optional[str]=None, 
    ) -> str:
    assert(tinput_id or name_override)
    basename = name_override if name_override else tinput_id
    basename = to_case(basename, settings.translate.nextflow.NF_PARAM_CASE)
    if task_id and subtype not in  ['main_workflow', 'defaults']:
        task_id = to_case(task_id, settings.translate.nextflow.NF_PARAM_CASE)
        name = f'{task_id}.{basename}'
    else:
        name = basename
    return name
