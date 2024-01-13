

from janis_core.utils.secondary import split_secondary_file_carats
import wdlgen as wdl
from typing import Optional

from janis_core.code.codetool import CodeTool
from janis_core.operators import InputSelector
from janis_core.tool.commandtool import CommandToolBuilder, ToolInput, ToolOutput
from janis_core.workflow.workflow import InputNode, OutputNode
from janis_core.tool.tool import Tool, TInput
from janis_core.types.common_data_types import (
    File,
    Directory,
    Array,
    Boolean,
    Filename,
    DataType,
)
from janis_core.utils.logger import Logger



SED_REMOVE_EXTENSION = "| sed 's/\\.[^.]*$//'"
REMOVE_EXTENSION = (
    lambda x, iterations: f"$(echo '{x}' {iterations * SED_REMOVE_EXTENSION})"
)


TypedEntity = ToolInput | ToolOutput | InputNode | OutputNode | TInput


def is_defined(entity: TypedEntity) -> bool:
    dtype = get_datatype(entity)
    return True if has_default(entity) or not dtype.optional else False

def get_datatype(entity: TypedEntity) -> DataType:
    if isinstance(entity, InputNode | OutputNode):
        dtype = entity.datatype
    elif isinstance(entity, TInput):
        dtype = entity.intype
    elif isinstance(entity, ToolInput):
        dtype = entity.input_type
    elif isinstance(entity, ToolOutput):
        dtype = entity.output_type
    return dtype

def has_default(entity: TypedEntity) -> bool:
    if isinstance(entity, ToolOutput | OutputNode):
        return False
    
    # entity default
    if entity.default is not None:
        return True 
    
    # get boolean and filename always have defaults
    dtype = get_datatype(entity)
    while isinstance(dtype, Array):
        dtype = dtype.subtype()
    if isinstance(dtype, Boolean | Filename):
        return True
     
    return False
    

def resolve_tool_input_value(tool_input: ToolInput) -> str:
    name = tool_input.id()
    # indefault = (
    #     tool_input.input_type
    #     if isinstance(tool_input.input_type, Filename)
    #     else tool_input.default
    # )

    # default = None
    # if isinstance(indefault, ResourceSelector):

    #     if indefault.default:
    #         default = (
    #             f"select_first([{indefault.input_to_select}, {str(indefault.default)}])"
    #         )
    #     else:
    #         default = indefault.input_to_select

    # elif isinstance(indefault, InputSelector):
    #     Logger.critical(
    #         f"WDL does not support command line level defaults that select a different input, this will remove the "
    #         f"value: '{indefault}' for tool_input '{tool_input.id()}'"
    #     )

    # elif indefault is not None:
    #     default = unwrap_expression(
    #         indefault,
    #         inputsdict=inputsdict,
    #         string_environment=string_environment,
    #         **debugkwargs,
    #     )

    # default now being handled in task inputs section
    # if default is not None:
    #     # Default should imply optional input
    #     name = f"select_first([{name}, {default}])"

    if tool_input.localise_file:
        if tool_input.input_type.is_array():
            raise Exception(
                "Localising files through `basename(x)` is unavailable for arrays of files: https://github.com/openwdl/wdl/issues/333"
            )
        if tool_input.presents_as:
            return (
                tool_input.presents_as
                if self.string_environment
                else f'"{tool_input.presents_as}"'
            )
        else:
            name = "basename(%s)" % name
    
    return name

def value_or_default(ar, default):
    """
    default is ar is None, else return the value of ar, returns ar even if ar is FALSEY
    :param ar:
    :param default:
    :return:
    """
    return default if ar is None else ar


def build_aliases(steps2):
    """
    From a list of stepNodes, generate the toolname alias (tool name to unique import alias)
    and the step alias, which
    :param steps: list of step nodes
    :return:
    """
    from janis_core.workflow.workflow import StepNode

    steps: list[StepNode] = steps2

    get_alias = lambda t: t[0] + "".join([c for c in t[1:] if c.isupper()])
    aliases: set[str] = set()

    tools: list[Tool] = [s.tool for s in steps]
    tool_name_to_tool: dict[str, Tool] = {t.versioned_id().lower(): t for t in tools}
    tool_name_to_alias = {}
    steps_to_alias: dict[str, str] = {
        s.id().lower(): get_alias(s.id()).lower() for s in steps
    }

    for tool in tool_name_to_tool:
        a = get_alias(tool).upper()
        s = a
        idx = 2
        while s in aliases:
            s = a + str(idx)
            idx += 1
        aliases.add(s)
        tool_name_to_alias[tool] = s

    return tool_name_to_alias, steps_to_alias


def get_secondary_tag_from_original_tag(original, secondary) -> str:
    secondary_without_punctuation = secondary.replace(".", "").replace("^", "")
    return original + "_" + secondary_without_punctuation


def prepare_move_statements_for_input(ti: ToolInput):
    """
    Update 2019-12-16:

        ToolInput introduces 'presents_as' and 'secondaries_present_as' fields (in addition to 'localise').
        This allows you to present a file as a specific filename, or change how the secondary files present to the tool.

        Additional considerations:
            - we MUST ensure that the secondary file is in the same directory as the base
            - if something is unavailable for an array, we must let the user know

        This is the logic that should be applied:

            - localise=True :: Moves the file into the execution directory ('.')
            - presents_as :: rewrites the input file to be the requires name (in the same directory).
                             This should also rewrite the secondary files per the original rules
            - secondaries_present_as :: rewrites the extension of the secondary files

        Combinations of these can be used

            - presents_as + localise :: should move the file into the execution directory as the new name
            - secondaries_present_as + presents as :: should rewrite the secondary

        The easiest way to do this is:

            - if localise or presents_as is given, generate the new filename
            - apply the secondary file naming rules to all the others (ensures it's in the same directory for free).

    """

    it = ti.input_type
    commands: list[wdl.Task.Command] = []

    if not (ti.localise_file or ti.presents_as or ti.secondaries_present_as):
        return commands

    if not it.is_base_type(File):   # type: ignore
        Logger.critical(
            "Janis has temporarily removed support for localising array types"
        )
        return commands

    base = f"~{{{ti.id()}}}"

    if ti.localise_file or ti.presents_as:
        newlocation = None

        if ti.localise_file and not ti.presents_as:
            newlocation = "."
        elif not ti.localise_file and ti.presents_as:
            newlocation = f"`dirname ~{{{ti.id()}}}`/{ti.presents_as}"
            base = newlocation
        else:
            newlocation = ti.presents_as
            base = ti.presents_as

        commands.append(wdl.Task.Command(f"cp -f '~{{{ti.id()}}}' '{newlocation}'"))

    if it.secondary_files():            # type: ignore
        sec_presents_as = ti.secondaries_present_as or {}

        for s in it.secondary_files():  # type: ignore
            sectag = get_secondary_tag_from_original_tag(ti.id(), s)
            if ti.localise_file and not ti.presents_as:
                # move into the current directory
                dest = "."
            else:
                newext, iters = split_secondary_file_carats(sec_presents_as.get(s, s))
                dest = REMOVE_EXTENSION(base, iters) + newext

            commands.append(wdl.Task.Command(f"cp -f '~{{{sectag}}}' {dest}"))

    return commands


def prepare_move_statements_for_output(
    to: ToolOutput, baseexpression
) -> list[wdl.Task.Command]:
    """
    Update 2019-12-16:

            - presents_as :: rewrites the output file to be the requires name (in the same directory).
                             This should also rewrite the secondary files per the original rules
            - secondaries_present_as :: rewrites the extension of the secondary files

        Combinations of these can be used

            - presents_as + localise :: should move the file into the execution directory as the new name
            - secondaries_present_as + presents as :: should rewrite the secondary
    """

    ot = to.output_type
    commands = []

    if not (to.presents_as or to.secondaries_present_as):
        return commands

    if not issubclass(type(ot), File):
        Logger.critical(
            f"Janis has temporarily removed support for localising '{type(ot)}' types"
        )
        return commands

    base = f"~{{{baseexpression}}}"

    if to.presents_as:
        newlocation = to.presents_as
        base = f'"{to.presents_as}"'

        commands.append(wdl.Task.Command(f"ln -f ~{{{to.id()}}} {newlocation}"))

    if to.secondaries_present_as and ot.secondary_files():  # type: ignore
        for s in ot.secondary_files():                      # type: ignore
            if s not in to.secondaries_present_as:
                continue

            newextvalues = split_secondary_file_carats(s)
            oldextvalues = split_secondary_file_carats(to.secondaries_present_as[s])

            oldpath = REMOVE_EXTENSION(base, oldextvalues[1]) + oldextvalues[0]
            newpath = REMOVE_EXTENSION(base, newextvalues[1]) + newextvalues[0]

            commands.append(
                wdl.Task.Command(
                    f"if [ -f {oldpath} ]; then ln -f {oldpath} {newpath}; fi"
                )
            )

    return commands


def build_resource_override_maps_for_tool(tool, prefix=None) -> list[wdl.Input]:
    inputs = []

    if not prefix:
        prefix = ""  # wf.id() + "."
    else:
        prefix += "_"

    if isinstance(tool, (CommandToolBuilder, CodeTool)):
        inputs.extend(
            [
                wdl.Input(wdl.WdlType.parse_type("Int?"), prefix + "runtime_memory"),   # type: ignore   
                wdl.Input(wdl.WdlType.parse_type("Int?"), prefix + "runtime_cpu"),      # type: ignore
                wdl.Input(wdl.WdlType.parse_type("Int?"), prefix + "runtime_disk"),     # type: ignore
                # Note: commented this out because seems runtime.duration no longer supported in WDL
                # wdl.Input(wdl.WdlType.parse_type("Int?"), prefix + "runtime_seconds"),
            ]
        )
    else:
        inputs.extend(build_resource_override_maps_for_workflow(tool, prefix=prefix))

    return inputs


def build_resource_override_maps_for_workflow(wf, prefix=None) -> list[wdl.Input]:

    # returns a list of key, value pairs
    inputs = []

    for s in wf.step_nodes.values():
        tool: Tool = s.tool

        tool_pre = (prefix or "") + s.id()
        inputs.extend(build_resource_override_maps_for_tool(tool, prefix=tool_pre))

    return inputs


def prepare_filename_replacements_for(
    sel: Optional[InputSelector], inputsdict: Optional[dict[str, ToolInput]]
) -> Optional[str]:
    
    # ^^^ what is the purpose of this func? 
    if not (sel is not None and isinstance(sel, InputSelector)):
        return None

    if not inputsdict:
        raise Exception(
            f"Couldn't generate filename as an internal error occurred (inputsdict did not contain {sel.input_to_select})"
        )

    if sel.input_to_select not in inputsdict:
        raise Exception(
            f"The InputSelector '{sel.input_to_select}' did not select a valid input"
        )

    tinp = inputsdict.get(sel.input_to_select)
    intype = tinp.input_type

    if isinstance(intype, (File, Directory)):
        if isinstance(intype, File) and intype.extension:
            base = f'basename({tinp.id()}, "{intype.extension}")'
        else:
            base = f"basename({tinp.id()})"
    else:
        base = tinp.id()

    if intype.optional:
        base = f'if defined({tinp.id()}) then {base} else "generated"'

    return base
