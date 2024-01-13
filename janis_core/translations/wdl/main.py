"""
WDL

This is one of the more complicated classes, it takes the janis in-memory representation of a tool,
and converts it into the equivalent WDL objects. Python-wdlgen distances us from the memory representation
and the actual string-specification.

This file is logically structured similar to the cwl equiv:

- Imports
- dump_wdl
- translate_workflow
- translate_tool (command tool)
- other translate methods
- selector helpers (InputSelector, WildcardSelector, CpuSelector, MemorySelector)
- helper methods
"""

import json
import wdlgen as wdl
from typing import Any, Optional

from .unwrap import unwrap_expression

from janis_core import settings
from janis_core.messages import load_loglines
from janis_core.code.codetool import CodeTool
from janis_core.modifications import format_case

from janis_core.graph.steptaginput import Edge, StepTagInput
from janis_core.operators import (
    InputSelector,
    WildcardSelector,
    CpuSelector,
    StringFormatter,
    Selector,
    StepOutputSelector,
    InputNodeSelector,
)
from janis_core.tool.commandtool import CommandToolBuilder, ToolInput, ToolArgument, ToolOutput, TInput
from janis_core import WorkflowBuilder
from janis_core.tool.tool import Tool, ToolType
from janis_core.translation_deps.supportedtranslations import SupportedTranslation
from janis_core.translations.translationbase import (
    TranslatorBase,
    TranslatorMeta,
    try_catch_translate,
)
from janis_core.types import get_instantiated_type, DataType
from janis_core.types.common_data_types import (
    Stdout,
    Array,
    Boolean,
    Filename,
    File,
    Directory,
    String,
    Int,
)
from janis_core.utils import (
    first_value,
    recursive_2param_wrap,
    find_duplicates,
    generate_cat_command_from_statements,
)
from janis_core.utils.generators import generate_new_id_from
from janis_core.utils.logger import Logger
from janis_core.utils.scatter import ScatterDescription, ScatterMethod
from janis_core.utils.secondary import (
    apply_secondary_file_format_to_filename,
)
# from janis_core.utils.validators import Validators
from janis_core.workflow.workflow import StepNode

from . import utils
from .command import translate_command_input
from .ordering import get_workflow_input_positions
from .ordering import order_tool_inputs
from .ordering import get_tool_input_positions_cmdtool
from .ordering import get_tool_input_positions_codetool

primitives = (bool, str, int, float, type(None))

## PRIMARY TRANSLATION METHODS


class CustomGlob(Selector):
    def __init__(self, expression):
        self.expression = expression

    def returntype(self):
        return Array(File)

    def to_string_formatter(self):
        raise Exception("Not supported for CustomGlob")


class WdlTranslator(TranslatorBase, metaclass=TranslatorMeta):
    
    OUTDIR_STRUCTURE: dict[str, str | None] = {
        'subworkflows': 'subworkflows',
        'tools': 'tasks',
        'helpers': 'scripts',
    }

    def __init__(self):
        super().__init__(name="wdl")

    ### JANIS -> OUTPUT MODEL MAPPING ###
    
    @classmethod
    def unwrap_expression(
        cls,
        expr,
        inputsdict=None,
        string_environment=False,
        tool=None,
        for_output=False,
        **debugkwargs,
    ):  
        return unwrap_expression(
            expr,
            inputsdict=inputsdict,
            string_environment=string_environment,
            tool=tool,
            for_output=for_output,
        )

    #@try_catch_translate(type="workflow")
    def translate_workflow_internal(self, wf: WorkflowBuilder, is_nested_tool: bool=False) -> None:
        """
        Translate the workflow into wdlgen classes!
        :param with_resource_overrides:
        :param with_container:
        :param is_nested_tool:
        :return:
        """
        # check we haven't already translated this
        if self.get_subworkflow(wf) is not None:
            return

        # Import needs to be here, otherwise we end up circularly importing everything
        # I need the workflow for type comparison
        # ^you could have used TYPE_CHECKING, or fixed the larger architecture issues. - GH

        # wf: WorkflowBuilder = wf

        # Notes:
        #       All wdlgen classes have a .get_string(**kwargs) function
        #       The wdlgen Workflow class requires a

        # As of 2019-04-16: we use development (Biscayne) features
        # like Directories and wdlgen uses the new input {} syntax
        w = wdl.Workflow(wf.id(), version="development")
        tools: list[Tool] = [s.tool for s in wf.step_nodes.values()]

        inputs = list(wf.input_nodes.values())
        steps = list(wf.step_nodes.values())
        outputs = list(wf.output_nodes.values())

        inputsdict = {t.id(): ToolInput(t.id(), t.intype) for t in wf.tool_inputs()}

        wtools = {}  # Store all the tools by their name in this dictionary
        tool_aliases, step_aliases = utils.build_aliases(
            wf.step_nodes.values()
        )  # Generate call and import aliases

        # Convert self._inputs -> wdl.Input
        for i in inputs:
            dt = i.datatype
            expr = None
            if isinstance(i.datatype, Filename):
                # expr = f'"{i.datatype.generated_filename()}"'
                dt = String(optional=True)

            if i.default is not None:
                expr = unwrap_expression(i.default, inputsdict=inputsdict)

            wd = dt.wdl(has_default=utils.has_default(i))

            w.inputs.append(
                wdl.Input(
                    data_type=wd, name=i.id(), expression=expr, requires_quotes=False
                )
            )

            is_array = i.datatype.is_array()
            if i.datatype.secondary_files() or (
                is_array and i.datatype.subtype().secondary_files()
            ):
                secs = (
                    i.datatype.secondary_files()
                    if not is_array
                    else i.datatype.subtype().secondary_files()
                )

                w.inputs.extend(
                    wdl.Input(wd, utils.get_secondary_tag_from_original_tag(i.id(), s))
                    for s in secs
                )

        resource_inputs = []
        if settings.translate.WITH_RESOURCE_OVERRIDES:
            resource_inputs = utils.build_resource_override_maps_for_workflow(wf)
            w.inputs.extend(resource_inputs)

        # Convert self._outputs -> wdl.Output
        # NOTE: passing wf and output node to unwrap for some reason? 
        for o in outputs:
            outtag = None

            if isinstance(o.source, list):
                outtag = unwrap_expression(
                    o.source,
                    inputsdict=None,
                    string_environment=False,
                    tool=wf,
                    entity=o
                )

            else:
                outtag = unwrap_expression(
                    o.source,
                    inputsdict=None,
                    string_environment=False,
                    tool=wf,
                    entity=o
                )

            w.outputs.append(wdl.Output(o.datatype.wdl(), o.id(), outtag))

            fundamental_outtype = o.datatype
            if fundamental_outtype.is_array():
                fundamental_outtype = fundamental_outtype.fundamental_type()
            if fundamental_outtype.secondary_files():
                if isinstance(o.source, InputNodeSelector):
                    src = [o.source.id()]
                elif isinstance(o.source, StepOutputSelector):
                    src = [o.source.node.id(), o.source.tag]
                else:
                    raise Exception(
                        f"Unsupported type for output with secondary files: {type(o.source)}"
                    )
                w.outputs.extend(
                    wdl.Output(
                        o.datatype.wdl(),
                        utils.get_secondary_tag_from_original_tag(o.id(), s),
                        ".".join(
                            [*src[:-1], utils.get_secondary_tag_from_original_tag(src[-1], s)]
                        ),
                    )
                    for s in fundamental_outtype.secondary_files()
                )

        # Generate import statements (relative tool dir is later?)
        uniquetoolmap: dict[str, Tool] = {t.versioned_id(): t for t in tools}
        w.imports = [
            wdl.Workflow.WorkflowImport(
                t.versioned_id(),
                tool_aliases[t.versioned_id().lower()].upper(),
                None if is_nested_tool else "tools/",
            )
            for t in uniquetoolmap.values()
        ]

        # Step[] -> (wdl.Task | wdl.Workflow)[]
        forbiddenidentifiers = set(
            [i.id() for i in inputs]
            + list(tool_aliases.keys())
            + list(s.id() for s in steps)
        )
        for s in steps:
            t = s.tool

            if t.versioned_id() not in wtools:
                if t.type() == ToolType.Workflow:
                    self.translate_workflow_internal(t, is_nested_tool=True)
                elif isinstance(t, CommandToolBuilder):
                    self.translate_tool_internal(t)
                elif isinstance(t, CodeTool):
                    self.translate_code_tool_internal(t)

            resource_overrides = {}

            if settings.translate.WITH_RESOURCE_OVERRIDES:
                toolroverrides = utils.build_resource_override_maps_for_tool(t)
                for r in toolroverrides:
                    resource_overrides[r.name] = s.id() + "_" + r.name

            call = translate_step_node(
                step=s,
                step_identifier=tool_aliases[t.versioned_id().lower()].upper() + "." + t.id(),
                resource_overrides=resource_overrides,
                invalid_identifiers=forbiddenidentifiers,
                inputsdict=inputsdict,
            )

            w.calls.append(call)

        # add the translated workflow
        if is_nested_tool:
            self.add_subworkflow(wf, w)
        else:
            assert self.main is None
            self.main = (wf, w)

    # @try_catch_translate(type="command tool")
    def translate_tool_internal(self, tool: CommandToolBuilder) -> None:
        # check we haven't already translated this
        if self.get_tool(tool) is not None:
            return

        # get inputs
        tinputs = tool.inputs()
        tinputs = tinputs + self.ordered_resource_inputs(tool)
        tinputs_map = {i.id(): i for i in tinputs}
        if len(tinputs) != len(tinputs_map):    # check dups? why? 
            dups = ", ".join(find_duplicates(list(tinputs_map.keys())))
            raise Exception(
                f"There are {len(dups)} duplicate values in  {tool.id()}'s inputs: {dups}"
            )

        # get outputs
        toutputs = tool.outputs()
        outdups = find_duplicates([o.id() for o in toutputs])
        if len(outdups) > 0:    # check dups? why? 
            raise Exception(
                f"There are {len(outdups)} duplicate values in  {tool.id()}'s outputs: {outdups}"
            )

        ins: list[wdl.Input] = self.translate_tool_inputs(tinputs, tinputs_map, tool=tool)
        outs: list[wdl.Output] = self.translate_tool_outputs(toutputs, tinputs_map, tool=tool)
        command_args = self.translate_tool_args(tool.arguments(), tinputs_map, tool=tool, toolId=tool.id())
        command_ins = self.build_command_from_inputs(tool.inputs())

        commands = [wdl.Task.Command("set -e")]

        # generate directories / file to create commands
        commands.extend(self.build_commands_for_file_to_create(tool))

        env = tool.env_vars()
        if env:
            commands.extend(
                prepare_env_var_setters(env, inputsdict=tinputs_map, toolid=tool.id())
            )

        for ti in tool.inputs():
            commands.extend(utils.prepare_move_statements_for_input(ti))

        rbc = tool.base_command()
        bc = " ".join(rbc) if isinstance(rbc, list) else rbc

        # run mode skeleton: only base command in command
        if settings.translate.MODE == 'skeleton':
            pass
            # commands.append(wdl.Task.Command(bc))
        # run mode minimal | full: base command + inputs + args in command
        else:
            commands.append(wdl.Task.Command(bc, command_ins, command_args))

        namedwdlouts = {t.name: t for t in outs}
        for to in toutputs:
            commands.extend(
                utils.prepare_move_statements_for_output(to, namedwdlouts[to.id()].expression)
            )

        
        # if settings.translate.WITH_CONTAINER:
        #     container = (
        #         WdlTranslator.get_container_override_for_tool(tool)
        #         or tool.container()
        #     )
        #     if container is not None:
        #         r.add_docker(container)

        rt = self.gen_runtime_block(
            tool=tool,
            inmap=tinputs_map,
        )
        tool_wdl = wdl.Task(tool.id(), ins, outs, commands, rt, version="development")
        self.add_tool(tool, tool_wdl)

    @try_catch_translate(type="code tool")
    def translate_code_tool_internal(self, tool: CodeTool) -> Any:
        # check we haven't already translated this
        if self.get_tool(tool) is not None:
            return
        
        # if not Validators.validate_identifier(tool.id()):
        #     raise Exception(
        #         f"The identifier '{tool.id()}' for class '{tool.__class__.__name__}' was not validated by "
        #         f"'{Validators.identifier_regex}' (must start with letters, and then only contain letters, "
        #         f"numbers or an underscore)"
        #     )

        ins = self.get_resource_override_inputs() + [
            ToolInput(
                t.id(),
                input_type=t.intype,
                prefix=f"--{t.id()}",
                default=t.default,
                doc=t.doc,
            )
            for t in tool.tool_inputs()
        ]

        tr_ins = self.translate_tool_inputs(ins)

        outs = []
        for t in tool.tool_outputs():
            if isinstance(t.outtype, Stdout):
                outs.append(ToolOutput(t.id(), output_type=t.outtype))
                continue

            outs.append(
                ToolOutput(
                    t.id(),
                    output_type=t.outtype,
                    glob=CustomGlob(f'read_json(stdout())["{t.id()}"]'),
                )
            )

        tr_outs = self.translate_tool_outputs(outs, {}, tool=tool)

        commands = []

        scriptname = tool.script_name()

        commands.append(
            wdl.Task.Command(
                f"""
cat <<EOT >> {scriptname}
    {tool.prepared_script(SupportedTranslation.WDL)}
EOT"""
            )
        )

        command_ins = self.build_command_from_inputs(ins)
        bc = tool.base_command()
        bcs = " ".join(bc) if isinstance(bc, list) else bc
        commands.append(wdl.Task.Command(bcs, command_ins, []))

        inmap = {t.id(): t for t in ins}
        rt = self.gen_runtime_block(tool=tool, inmap=inmap)

        tool_wdl = wdl.Task(tool.id(), tr_ins, tr_outs, commands, rt, version="development")
        self.add_tool(tool, tool_wdl)

    @classmethod
    def translate_tool_inputs(cls, toolinputs: list[ToolInput], inputsmap: dict[str, ToolInput], tool: CommandToolBuilder) -> list[wdl.Input]:
        ins = []
        toolinputs = order_tool_inputs(toolinputs)
        for i in toolinputs:
            # map default value 
            if isinstance(i.input_type, Filename):
                expr = None
            elif isinstance(i.input_type, Boolean) and i.default is None:
                expr = 'false'
            elif i.default is not None:
                expr = unwrap_expression(i.default, inputsdict=inputsmap, tool=tool)
            else:
                expr = None
            
            # map datatype
            dtype = i.input_type.wdl(has_default=utils.has_default(i))

            # map input
            if isinstance(dtype, list):
                ins.extend(wdl.Input(w, i.id()) for w in dtype)
            else:
                ins.append(wdl.Input(dtype, i.id(), expr, requires_quotes=False))
                sec = utils.value_or_default(
                    i.input_type.subtype().secondary_files()
                    if i.input_type.is_array()
                    else i.input_type.secondary_files(),
                    default=[],
                )
                ins.extend(
                    wdl.Input(dtype, utils.get_secondary_tag_from_original_tag(i.id(), s))
                    for s in sec
                )
        return ins

    @classmethod
    def translate_tool_outputs(
        cls, tooloutputs: list[ToolOutput], inputsmap: dict[str, ToolInput], tool
    ):
        outs: list[wdl.Output] = []

        for o in tooloutputs:
            wdl_type = o.output_type.wdl()
            
            if isinstance(o.selector, WildcardSelector):
                is_single = not o.output_type.is_array()
                is_single_optional = o.output_type.optional if is_single else None
                select_first = True if is_single and not o.selector.select_first else None
                # if not o.selector.select_first:
                    # Logger.info(
                    #     f"The command tool ({debugkwargs}).{output.id()}' used a star-bind (*) glob to find the output, "
                    #     f"but the return type was not an array. For WDL, the first element will be used, "
                    #     f"ie: 'glob(\"{expression.wildcard}\")[0]'"
                    # )
                expression = translate_wildcard_selector(
                    selector=o.selector,
                    output=o,
                    override_select_first=select_first,
                    is_optional=is_single_optional,
                    inputsdict=inputsmap,
                )
            else:
                expression = unwrap_expression(
                    o.selector,
                    tool=tool,
                    toolid=tool.id(),
                    entity=o,
                    inputsdict=inputsmap,
                    for_output=True
                )

            outs.append(wdl.Output(wdl_type, o.id(), expression))
            outs.extend(
                cls.prepare_secondary_tool_outputs(
                    out=o,
                    original_expression=o.selector,
                    expression=expression,
                    toolid=tool.id(),
                    inputsdict=inputsmap,
                )
            )

        return outs

    @classmethod
    def prepare_secondary_tool_outputs(
        cls,
        out: ToolOutput,
        original_expression: any,
        expression: str,
        toolid: str,
        inputsdict,
    ) -> list[wdl.Output]:
        if not (
            isinstance(out.output_type, File) and out.output_type.secondary_files()
        ):
            return []

        islist = isinstance(expression, list)

        if (
            out.output_type.is_array()
            and isinstance(out.output_type.subtype(), File)
            and out.output_type.subtype().secondary_files()
        ):
            if isinstance(original_expression, WildcardSelector):
                # do custom override for wildcard selector
                is_single = not out.output_type.is_array()
                select_first = None
                is_single_optional = None
                if is_single and not original_expression.select_first:
                    select_first = True
                    is_single_optional = out.output_type.optional
                ftype = out.output_type.subtype().wdl()
                return [
                    wdl.Output(
                        ftype,
                        utils.get_secondary_tag_from_original_tag(out.id(), s),
                        translate_wildcard_selector(
                            output=out,
                            selector=original_expression,
                            secondary_format=s,
                            override_select_first=select_first,
                            is_optional=is_single_optional,
                            inputsdict=inputsdict,
                        ),
                    )
                    for s in out.output_type.subtype().secondary_files()
                ]
            elif islist:
                Logger.info(
                    "Special handling for an Array return type with a list expressions"
                )
            else:
                raise Exception(
                    "Janis isn't sure how to collect secondary files for an array yet"
                )

        outs = []
        if isinstance(out.output_type, File) and out.output_type.secondary_files():
            # eep we have secondary files
            ot = get_instantiated_type(out.output_type)
            ftype = ot.wdl()
            for s in ot.secondary_files():
                tag = utils.get_secondary_tag_from_original_tag(out.id(), s)
                ar_exp = expression if islist else [expression]
                potential_extensions = ot.get_extensions()
                if "^" not in s:
                    exp = [(ex + f' + "{s}"') for ex in ar_exp]
                elif potential_extensions:
                    exp = []
                    for ex in ar_exp:
                        inner_exp = ex
                        for ext in potential_extensions:
                            inner_exp = (
                                'sub({inp}, "\\\\{old_ext}$", "{new_ext}")'.format(
                                    inp=inner_exp,
                                    old_ext=ext,
                                    new_ext=s.replace("^", ""),
                                )
                            )
                        exp.append(inner_exp)

                elif s.startswith('^'):
                    exp = [f'glob("*{s[1:]}")[0]']
                
                else:
                    raise Exception(
                        f"Unsure how to handle secondary file '{s}' for the tool output '{out.id()}' (ToolId={toolid})"
                        f" as it uses the escape characater '^' but Janis can't determine the extension of the output."
                        f"This could be resolved by ensuring the definition for '{ot.__class__.__name__}' contains an extension."
                    )

                if ot.optional:
                    exp = [
                        f"if defined({expression}) then ({e}) else None" for e in exp
                    ]

                outs.append(wdl.Output(ftype, tag, exp if islist else exp[0]))

        return outs

    @classmethod
    def translate_tool_args(
        cls,
        toolargs: list[ToolArgument],
        inpmap: dict[str, ToolInput],
        tool,
        **debugkwargs,
    ):
        if not toolargs:
            return []
        commandargs = []
        for a in toolargs:
            val = unwrap_expression(
                a.value, inputsdict=inpmap, tool=tool, string_environment=True
            )
            should_wrap_in_quotes = isinstance(val, str) and a.shell_quote is not False
            wrapped_val = f"'{val}'" if should_wrap_in_quotes else val
            commandargs.append(
                wdl.Task.Command.CommandArgument.from_fields(
                    a.prefix, wrapped_val, a.position
                )
            )
        return commandargs

    @classmethod
    def build_command_from_inputs(cls, toolinputs: list[ToolInput]):
        inputsdict = {t.id(): t for t in toolinputs}
        command_ins = []
        for i in toolinputs:
            cmd = translate_command_input(i, inputsdict=inputsdict)
            if cmd:
                command_ins.append(cmd)
        return command_ins

    @classmethod
    def build_commands_for_file_to_create(
        cls, tool: CommandToolBuilder
    ) -> list[wdl.Task.Command]:
        commands = []
        inputsdict = {t.id(): t for t in tool.inputs()}

        directories = tool.directories_to_create()
        files = tool.files_to_create()

        if directories is not None:
            directories = (
                directories if isinstance(directories, list) else [directories]
            )
            for directory in directories:
                unwrapped_dir = unwrap_expression(
                    directory, inputsdict=inputsdict, tool=tool, string_environment=True
                )
                commands.append(f"mkdir -p '{unwrapped_dir}'")
        if files:
            for path, contents in files if isinstance(files, list) else files.items():
                unwrapped_path = unwrap_expression(
                    path, inputsdict=inputsdict, tool=tool, string_environment=True
                )
                unwrapped_contents = unwrap_expression(
                    contents, inputsdict=inputsdict, tool=tool, string_environment=True
                )
                commands.append(
                    generate_cat_command_from_statements(
                        path=unwrapped_path, contents=unwrapped_contents
                    )
                )

        return list(map(wdl.Task.Command, commands))

    @classmethod
    def gen_runtime_block(cls, tool, inmap):
        # These runtime kwargs cannot be optional, but we've enforced non-optionality when we create them
        # ^???
        # TODO profiles: eg slurm = mem:"~{memory_size}M",  cloud = memory:"~{memory_size} MiB" 
        rt = wdl.Task.Runtime()
        rt.add_docker(tool._container)
        if 'runtimeCpu' in inmap:
            rt.kwargs["cpu"] = unwrap_expression(
                InputSelector('runtimeCpu'),
                inputsdict=inmap,
                string_environment=False,
                tool=tool,
            )
        if 'runtimeDisk' in inmap:
            rt.kwargs["disks"] = unwrap_expression(
                StringFormatter("local-disk {value} SSD", value=InputSelector('runtimeDisk')),
                inputsdict=inmap,
                string_environment=False,
                tool=tool,
            )
        if 'runtimeMemory' in inmap:
            rt.kwargs["memory"] = unwrap_expression(
                StringFormatter("{value}G", value=InputSelector('runtimeMemory')),
                inputsdict=inmap,
                string_environment=False,
                tool=tool,
            )
        if 'runtimeSeconds' in inmap:
            rt.kwargs["duration"] = unwrap_expression(
                InputSelector('runtimeSeconds'),
                inputsdict=inmap,
                string_environment=False,
                tool=tool,
            )
        
        # if settings.translate.WITH_RESOURCE_OVERRIDES:
        #     rt.kwargs["zones"] = '"australia-southeast1-b"'
        # rt.kwargs["preemptible"] = 2
        return rt 

    def ordered_resource_inputs(self, tool: CommandToolBuilder) -> list[ToolInput]:
        out: list[ToolInput] = []
        for name, value in [
            ("runtimeCpu", tool._cpus),         # number of CPUs
            ("runtimeDisk", tool._disk),        # GB of storage required
            ("runtimeMemory", tool._memory),    # GB of memory
            ("runtimeSeconds", tool._time),     # seconds of running time
        ]:
            if value is not None:
                out.append(ToolInput(name, Int(optional=True), default=value))
        return out 

    def build_inputs_file(self, entity: WorkflowBuilder | CommandToolBuilder | CodeTool) -> None:
        """
        Recursive is currently unused, but eventually input overrides could be generated the whole way down
        a call chain, including subworkflows: https://github.com/openwdl/wdl/issues/217
        :param merge_resources:
        :param recursive:
        :param tool:
        :return:
        """
        additional_inputs = settings.translate.ADDITIONAL_INPUTS or {}

        inp = {}
        values_provided_from_tool = {}

        if isinstance(entity, WorkflowBuilder):
            values_provided_from_tool = {
                i.id(): i.value or i.default
                for i in entity.input_nodes.values()
                if i.value is not None
                or (i.default is not None and not isinstance(i.default, Selector))
            }

        ad = {**values_provided_from_tool, **(additional_inputs or {})}

        for i in entity.tool_inputs():

            inp_key = f"{entity.id()}.{i.id()}" if isinstance(entity, WorkflowBuilder) else i.id()
            value = ad.get(i.id())
            if self.inp_can_be_skipped(i, value):
                continue

            inp_val = value

            inp[inp_key] = inp_val
            if i.intype.secondary_files():
                for sec in i.intype.secondary_files():
                    inp[
                        utils.get_secondary_tag_from_original_tag(inp_key, sec)
                    ] = apply_secondary_file_format_to_filename(inp_val, sec)
            elif i.intype.is_array() and i.intype.subtype().secondary_files():
                # handle array of secondary files
                for sec in i.intype.subtype().secondary_files():
                    inp[utils.get_secondary_tag_from_original_tag(inp_key, sec)] = (
                        [
                            apply_secondary_file_format_to_filename(iinp_val, sec)
                            for iinp_val in inp_val
                        ]
                        if inp_val
                        else None
                    )

        if settings.translate.MERGE_RESOURCES:
            inp.update(self._build_resources_dict(entity, inputs=ad, is_root=True))
        
        inputs_str = json.dumps(inp, sort_keys=True, indent=4, separators=(",", ": "))
        self.inputs_file = inputs_str
    
    @staticmethod
    def inp_can_be_skipped(inp, override_value=None):
        return (
            inp.default is None
            and override_value is None
            # and not inp.include_in_inputs_file_if_none
            and (inp.intype.optional and inp.default is None)
        )

    def build_resources_file(self, entity: WorkflowBuilder | CommandToolBuilder | CodeTool) -> None:
        resources_dict = self._build_resources_dict(entity)
        resources_str = json.dumps(resources_dict, sort_keys=True, indent=4, separators=(",", ": "))
        self.resources_file = resources_str

    @classmethod
    def _build_resources_dict( 
        cls,
        tool: Tool, 
        inputs: Optional[dict[str, Any]]=None,
        prefix: str="",
        is_root: bool=False,
    ) -> dict[str, Any]:

        is_workflow = tool.type() == ToolType.Workflow
        d = super()._build_resources_dict(
            tool=tool,
            prefix=prefix or "",
            inputs=inputs,
        )
        if is_workflow and is_root:
            return {f"{tool.id()}.{k}": v for k, v in d.items()}
        return d


    ### STRINGIFY ###
    
    def stringify_translated_workflow(self, internal: WorkflowBuilder, translated: wdl.Workflow) -> str:
        return translated.get_string()

    def stringify_translated_tool(self, internal: CommandToolBuilder | CodeTool, translated: wdl.Task) -> str:
        return translated.get_string()


    ### FILENAMES ###

    @staticmethod
    def workflow_filename(workflow: WorkflowBuilder, is_main: Optional[bool]=False) -> str:
        # return workflow.versioned_id() + ".wdl"
        text = workflow.id() 
        text = format_case('file', text)
        return f"{text}.wdl"

    @staticmethod
    def inputs_filename(workflow):
        # return workflow.id() + "-inp.json"
        text = workflow.id()
        text = format_case('file', text)
        return f"{text}.json"

    @staticmethod
    def tool_filename(tool):
        # return (tool.versioned_id() if isinstance(tool, Tool) else str(tool)) + ".wdl"
        text = tool.id()
        text = format_case('file', text)
        return f"{text}.wdl"

    @staticmethod
    def resources_filename(workflow):
        # return workflow.id() + "-resources.json"
        text = workflow.id()
        text = format_case('file', text)
        return f"{text}-resources.json"


    ### VALIDATION ###

    @staticmethod
    def validate_command_for(wfpath, inppath, tools_dir_path, tools_zip_path):
        return ["java", "-jar", "$womtooljar", "validate", wfpath]



### HELPERS ###

def validate_step_with_multiple_sources(node, edge, k, input_name_maps):
    multiple_sources_failure_reasons = []

    unique_types = set()
    for x in edge.source():
        t: DataType = x.source.returntype()
        unique_types.update(t.secondary_files() or [])

    if len(unique_types) > 1:
        multiple_sources_failure_reasons.append(
            f"has {len(unique_types)} different DataTypes with varying secondaries"
        )
    if node.scatter:
        multiple_sources_failure_reasons.append(f"is scattered")

    if len(multiple_sources_failure_reasons) > 0:
        reasons = " and ".join(multiple_sources_failure_reasons)
        Logger.critical(
            f"Conversion to WDL for field '{node.id()}.{k}' does not fully support multiple sources."
            f" This will only work if all of the inputs ({input_name_maps}) have the same secondaries "
            f"AND this field ('{k}') is not scattered. However this connection {reasons}"
        )



def translate_wildcard_selector(
    output: ToolOutput,
    selector: WildcardSelector,
    secondary_format: Optional[str] = None,
    override_select_first: Optional[bool] = None,
    is_optional: Optional[bool] = None,
    inputsdict: Optional[dict] = None,
):
    if selector.wildcard is None:
        raise Exception(
            "No wildcard was provided for wildcard selector: " + str(selector)
        )

    wildcard = selector.wildcard
    if secondary_format:
        wildcard = apply_secondary_file_format_to_filename(wildcard, secondary_format)

    unwrapped_wildcard = unwrap_expression(
        wildcard, entity=output, inputsdict=inputsdict, string_environment=False, for_output=True
    )

    gl = f"glob({unwrapped_wildcard})"
    if selector.select_first or override_select_first:
        if is_optional:
            gl = f"if length({gl}) > 0 then {gl}[0] else None"
        else:
            gl += "[0]"

    return gl


def translate_step_node(
    step: StepNode,
    step_identifier: str,
    resource_overrides: dict[str, str],
    invalid_identifiers: set[str],
    inputsdict: dict[str, Any],
) -> wdl.WorkflowCallBase:
    """
    Convert a step into a wdl's workflow: call { **input_map }, this handles creating the input map and will
    be able to handle multiple scatters on this step step. If there are multiple scatters, the scatters will be ordered
    in to out by alphabetical order.

    This method isn't perfect, when there are multiple sources it's not correctly resolving defaults, and tbh it's pretty confusing.

    :param step:
    :param step_identifier:
    :param step_alias:
    :param resource_overrides:
    :return:
    """
    # Sanity check our step step connections:

    # 1. make sure our inputs are all present:
    missing_keys = [
        k
        for k in step.inputs().keys()
        if k not in step.sources
        and not (step.inputs()[k].intype.optional is True or step.inputs()[k].default is not None)
    ]
    if missing_keys:  # TODO this may pose an issue for user-readability translation
        raise Exception(
            f"Error when building connections for step '{step.id()}', "
            f"missing the required connection(s): '{', '.join(missing_keys)}'"
        )

    # 2. gather the scatters, and make sure none of them are derived from multiple sources, otherwise
    #       we're like double zipping things, it's complicated and it's even MORE complicated in WDL.
    scatterable: list[StepTagInput] = []

    if step.scatter:
        unbound_scatter_keys = [k for k in step.scatter.fields if k not in step.sources]
        if len(unbound_scatter_keys):
            raise Exception(
                f"Attempted to scatter {step.id()} on field(s) [{', '.join(unbound_scatter_keys)}] however "
                "these inputs were not mapped on step construction. Make sure that those unbound keys exist"
                f"in your step definition (eg: "
                f"{step.tool.__class__.__name__}({', '.join(k + '=inp' for k in unbound_scatter_keys)})"
            )
        scatterable = [step.sources[k] for k in step.scatter.fields]

        invalid_sources = [
            si
            for si in scatterable
            if si.multiple_inputs
            or (isinstance(si.source(), list) and len(si.source()) > 1)
        ]
        if len(invalid_sources) > 0:
            invalid_sources_str = ", ".join(f"{si.source()}" for si in invalid_sources)
            raise NotImplementedError(
                f"The edge(s) '{invalid_sources_str}' on step '{step.id()}' scatters"
                f"on multiple inputs, this behaviour has not been implemented"
            )

    # 1. Generate replacement of the scatterable key(s) with some random variable, eg: for i in iterable:
    #
    #       - Currently, Janis does not support operating on the object to scatter, and there's no mechanism from
    #           operating on the scattered value. See the following GH comment for more information:
    #           (https://github.com/PMCC-BioinformaticsCore/janis-core/pull/10#issuecomment-605807815)
    #

    scattered_old_to_new_identifier = generate_scatterable_details(
        scatterable, forbiddenidentifiers=invalid_identifiers
    )

    # Let's map the inputs, to the source. We're using a dictionary for the map atm, but WDL requires the _format:
    #       fieldName: sourceCall.Output

    inputs_details: dict[str, dict[str, Any]] = {}
    if isinstance(step.tool, WorkflowBuilder):
        input_positions = get_workflow_input_positions(list(step.tool.input_nodes.values()))
    elif isinstance(step.tool, CommandToolBuilder):
        input_positions = get_tool_input_positions_cmdtool(step.tool.inputs())
    elif isinstance(step.tool, CodeTool):
        input_positions = get_tool_input_positions_codetool(step.tool.inputs())
    else:
        raise RuntimeError
    last_position = 999
    
    for k, inp in step.inputs().items():
        if k not in step.sources:
            continue    # ignore tool inputs which haven't be given a value.
                        # these will either be optional, or have a default value provided.

        steptag_input: StepTagInput = step.sources[k]
        src: Edge = steptag_input.source()  # potentially single item or array

        ar_source = src if isinstance(src, list) else [src]
        # these two are very closely tied, they'll determine whether our
        # input to the step connection is single or an array
        has_multiple_sources = isinstance(src, list) and len(src) > 1
        array_input_from_single_source = False

        if has_multiple_sources:
            # let's do some checks, make sure we're okay
            validate_step_with_multiple_sources(step, steptag_input, k, inputs_details)

        elif ar_source:
            source = ar_source[0]

            ot = source.source.returntype()
            if inp.intype.is_array() and not ot.is_array() and not source.should_scatter:
                array_input_from_single_source = True
        else:
            Logger.critical(
                f"Skipping connection to '{steptag_input.finish}.{steptag_input.ftag}' had no source or default, "
                f"please raise an issue as investigation may be required"
            )
            continue

        # Checks over, let's continue!

        secondaries = (
            inp.intype.secondary_files()
            if not inp.intype.is_array()
            else inp.intype.subtype().secondary_files()
        ) or []
        # place to put the processed_sources:
        #   Key=None is for the regular input
        #   Key=$sec_tag is for each secondary file
        unwrapped_sources = {k: [] for k in [None, *secondaries]}

        # NOTE: step being passed to unwrap
        unwrap_helper = lambda exprsn: unwrap_expression(
            exprsn,
            inputsdict=inputsdict,
            string_environment=False,
            entity=step,
        )

        for edge in ar_source:
            # we have an expression we need to unwrap,
            # it's going to the step_input [k]

            if secondaries:
                ot = edge.source.returntype()

                sec_out = set(
                    utils.value_or_default(
                        ot.subtype().secondary_files()
                        if ot.is_array()
                        else ot.secondary_files(),
                        default=[],
                    )
                )
                sec_in = set(secondaries)
                if not sec_in.issubset(sec_out):
                    raise Exception(
                        f"An error occurred when connecting '{edge.source}' to "
                        f"'{edge.finish.id()}.{edge.ftag}', there were secondary files in the final step "
                        f"that weren't present in the source: {', '.join(sec_out.difference(sec_in))}"
                    )

            unwrapped_exp = unwrap_helper(edge.source)

            default = None
            if isinstance(edge.source, InputNodeSelector):
                default = unwrap_helper(edge.source.input_node.default)

            is_scattered = unwrapped_exp in scattered_old_to_new_identifier

            if is_scattered:
                unwrapped_exp = scattered_old_to_new_identifier[unwrapped_exp][0]

                for idx in range(len(secondaries)):
                    # we restrict that files with secondaries can't be operated on in the step input
                    sec = secondaries[idx]
                    unwrapped_sources[sec].append(f"{unwrapped_exp}[{idx + 1}]")

                if secondaries:
                    unwrapped_exp += "[0]"
            else:
                for sec in secondaries:
                    unwrapped_sources[sec].append(
                        utils.get_secondary_tag_from_original_tag(unwrapped_exp, sec)
                    )

            unwrapped_sources[None].append(unwrapped_exp)

        should_select_first_element = not (
            array_input_from_single_source or has_multiple_sources
        )
        for tag, value in unwrapped_sources.items():
            if tag is None:
                tag = k
            else:
                tag = utils.get_secondary_tag_from_original_tag(k, tag)

            # get tool input to derive additional information. 
            # used to render comments.
            if isinstance(step.tool, WorkflowBuilder):
                tool_input = [x for x in step.tool.input_nodes.values() if x.id() == k][0]
            else:
                tool_input = [x for x in step.tool.inputs() if x.id() == k][0]
            
            # special label
            special_label = None
            for edge in ar_source:
                if isinstance(edge.source, StepOutputSelector):
                    special_label = '*CONNECTION*'
            
            # prefix
            prefix = None
            if isinstance(step.tool, CommandToolBuilder):
                prefix = tool_input.prefix
                if isinstance(prefix, str):
                    prefix = prefix.rstrip('=')
            
            # position
            # odd grammar here is handle situations where we don't know what position the
            # input should be (eg secondary files). In these cases, just uses the previous position. 
            # should keep secondaries grouped together.
            position = input_positions[tag] if tag in input_positions else last_position
            last_position = position

            inputs_details[tag] = {
                'value': value[0] if should_select_first_element else "[" + ", ".join(value) + "]",
                'special': special_label,
                'prefix': prefix,
                # below - used if we wanted to output '(default)' as default label,
                # rather than the actual default value to the tool input. eg '(100)'
                #'default': True if _is_input_default(inp, source) else False, 
                'default': _get_wrapped_default(inp, tool_input),
                'datatype': inp.intype.wdl(has_default=utils.has_default(tool_input)).get_string(),
                'position': position
            }

    for key, val in resource_overrides.items():
        inputs_details[key] = {'value': val}

    # messages = load_loglines(step.id())   # uuid is currently using janis-core identifiers
    messages = []
    render_comments = settings.translate.RENDER_COMMENTS
    call = wdl.WorkflowCall(step_identifier, step.id(), inputs_details, messages, render_comments)

    if len(scatterable) > 0:
        call = wrap_scatter_call(
            call, step.scatter, scatterable, scattered_old_to_new_identifier
        )
    if step.foreach is not None:
        # NOTE: step being passed to unwrap
        expr = unwrap_expression(
            step.foreach,
            inputsdict=inputsdict,
            string_environment=False,
            entity=step
        )
        call = wdl.WorkflowScatter("idx", expr, [call])

    if step.when is not None:
        condition = unwrap_expression(
            step.when, inputsdict=inputsdict, string_environment=False
        )
        call = wdl.WorkflowConditional(condition, [call])
        # determine how to unwrap when

    return call


def _get_wrapped_default(inp: TInput, tool_input: ToolInput) -> Optional[str]:
    default = inp.default if inp.default is not None else tool_input.default
    if default is None:
        return None
    elif isinstance(inp.intype, String):
        return f'"{default}"'
    else:
        return f'{default}'


def _is_input_default(inp: ToolInput, source: Edge) -> bool:
    # determines whether the value being fed to a step input 
    # is the default value for the underlying tool input.
    # only InputNode sources need to be considered, since connections 
    # can never a considered a 'default' value
    if isinstance(source.source, InputNodeSelector):
        fed_value = source.source.input_node.default
        if fed_value == inp.default:
            return True
    return False


def generate_scatterable_details(
    scatterable: list[StepTagInput], forbiddenidentifiers: set[str]
):
    if not scatterable:
        return {}

    # get the reference from a InputNodeSelector or StepOutputSelector
    get_source = lambda e: unwrap_expression(e.source)

    # this dictionary is what we're going to use to map our current
    # identifier to the scattered identifier. This step is just the
    # setup, and in the next for loop, we'll
    scattered_old_to_new_identifier = {}
    for k in scatterable:
        srcs = k.source()
        for edge in srcs if isinstance(srcs, list) else [srcs]:
            src = get_source(edge)
            scattered_old_to_new_identifier[src] = (src, edge.source)

    # Make a copy of the forbiddenIds and add the identifiers of the source
    forbiddenidentifierscopy = set(forbiddenidentifiers).union(
        set(v[0] for v in scattered_old_to_new_identifier.values())
    )

    # We'll wrap everything in the scatter block later, but let's replace the fields we need to scatter
    # with the new scatter variable (we'll try to guess one based on the fieldname). We might need to eventually
    # pass the workflow inputs to make sure now conflict will arise.

    if len(scatterable) > 1:
        # We'll generate one variable in place
        standin = generate_new_id_from("Q", forbiddenidentifierscopy)

        # Store the the standin variable for us to use later (as an illegal identifier character)
        scattered_old_to_new_identifier["-"] = standin
        forbiddenidentifierscopy.add(standin)

        # Then we'll need to generate something like:
        #       A -> Q[0], B -> Q[0][0] -> ..., N -> Q([0] * (n-1))[1]
        n = len(scatterable)
        for i in range(len(scatterable)):
            s = scatterable[i]
            newid = standin + (i) * ".right" + ".left"
            if i == n - 1:
                newid = standin + (n - 1) * ".right"
            scattered_old_to_new_identifier[get_source(s.source())] = (
                newid,
                s.source_map[0].source,
            )
            forbiddenidentifierscopy.add(newid)
    else:

        for s in scatterable:

            # We asserted earlier that the source_map only has one value (through multipleInputs)
            e: Edge = s.source_map[0]

            # if isinstance(e.source, Operator):
            #     raise Exception(
            #         "Currently, Janis doesn't support operating on a value to be scattered"
            #     )

            original_expr = unwrap_expression(s.source().source)
            newid = generate_new_id_from(original_expr, forbiddenidentifierscopy)
            evaluated_operator = unwrap_expression(
                e.source, string_environment=False
            )
            scattered_old_to_new_identifier[evaluated_operator] = (newid, e)
            forbiddenidentifierscopy.add(newid)

    return scattered_old_to_new_identifier


def wrap_scatter_call(
    call, scatter: ScatterDescription, scatterable, scattered_old_to_new_identifier
):
    from janis_core.workflow.workflow import InputNode

    # Let's start the difficult process of scattering, in WDL we'll:
    #
    #       1. We already generated the new "scatter" variable that will
    #            be used in place of the original .dotted_source()
    #
    #       2. Generate annotations for accessory / secondary files
    #
    #       3. Wrap everything in the appropriate scatter block,
    #           especially considering scattering by multiple variables
    #

    # 2. Explanation:
    #     So, the current way of mixing accessory files is not really                        _
    #     supported, but a little complicated basically, if our scatterable edge           _| |
    #     contains secondary files, they'll all be arrays of separate files, eg:         _| | |
    #                                                                                   | | | | __
    #     File[] bams =     [...]                                                       | | | |/  \
    #     File[] bams_bai = [...]                                                       |       /\ \
    #                                                                                   |       \/ /
    #     We can handle this by transposing the array of both items, eg:                 \        /
    #                                                                                     |      /
    #         transpose([bam1, bam2, ..., bamn], [bai1, bai2, ..., bai3])                 |     |
    #               => [[bam1, bai1], [bam2, bai2], ..., [bamn, bain]]
    #
    #     and then unwrap them using their indices and hopefully have everything line up:
    #
    #     Source: https://software.broadinstitute.org/wdl/documentation/spec#arrayarrayx-transposearrayarrayx

    # We need to generate the source statement, this is easy if we're scattering by one variable

    # sanity check
    if len(scatterable) == 0:
        return call

    # generate the new source map
    get_source = lambda e: unwrap_expression(e.source)

    insource_ar = []
    for s in scatterable:
        secondary = s.finish.tool.inputs_map()[s.ftag].intype.secondary_files()
        if secondary:
            ds = get_source(s.source())
            joined_tags = ", ".join(
                utils.get_secondary_tag_from_original_tag(ds, sec) for sec in secondary
            )
            transformed = f"transpose([{ds}, {joined_tags}])"
            insource_ar.append(transformed)

        else:
            (newid, startnode) = scattered_old_to_new_identifier[get_source(s.source())]
            insource = get_source(s.source())
            if isinstance(startnode, InputNode) and startnode.default is not None:
                resolved = unwrap_expression(
                    startnode.default, scatterstep=insource
                )
                if isinstance(resolved, bool):
                    resolved = "true" if resolved else "false"

                insource_ar.append(f"select_first([{insource}, {resolved}])")
            else:
                insource_ar.append(insource)

    insource = None
    alias = None
    if len(insource_ar) == 1:
        insource = insource_ar[0]
        alias = first_value(scattered_old_to_new_identifier)[0]
    else:
        method = "zip" if scatter.method == ScatterMethod.dot else "cross"
        insource = recursive_2param_wrap(method, insource_ar)
        alias = scattered_old_to_new_identifier["-"]

    return wdl.WorkflowScatter(alias, insource, [call])


def prepare_env_var_setters(
    reqs: dict[str, Any], inputsdict, **debugkwargs
) -> list[wdl.Task.Command]:
    if not reqs:
        return []

    statements = []
    for k, v in reqs.items():
        val = unwrap_expression(
            v, inputsdict=inputsdict, string_environment=True, **debugkwargs
        )
        statements.append(wdl.Task.Command(f"export {k}='{val}'"))

    return statements




### DEPRECATED ### 


    # @classmethod
    # def unwrap_expression(
    #     cls,
    #     expression,
    #     inputsdict=None,
    #     string_environment=False,
    #     tool=None,
    #     for_output=False,
    #     **debugkwargs,
    # ):  
    #     if expression is None:
    #         return ""

    #     wrap_in_code_block = lambda x: f"~{{{x}}}" if string_environment else x

    #     if isinstance(expression, StepNode):
    #         raise Exception(
    #             f"The Step node '{expression.id()}' was found when unwrapping an expression, "
    #             f"you might not have selected an output."
    #         )

    #     if isinstance(expression, list):
    #         toolid = utils.value_or_default(debugkwargs.get("tool_id"), "get-value-list")
    #         joined_values = ", ".join(
    #             str(
    #                 cls.unwrap_expression(
    #                     expression[i],
    #                     inputsdict,
    #                     string_environment=False,
    #                     tool_id=toolid + "." + str(i),
    #                 )
    #             )
    #             for i in range(len(expression))
    #         )
    #         return f"[{joined_values}]"
    #     if is_python_primitive(expression):
    #         if isinstance(expression, str):
    #             if string_environment:
    #                 return expression
    #             return cls.wrap_if_not_string_environment(
    #                 prepare_escaped_string(expression), string_environment
    #             )
    #         if isinstance(expression, bool):
    #             return "true" if expression else "false"

    #         return str(expression)
    #     elif isinstance(expression, Filename):
    #         gen_filename = expression.generated_filename(
    #             replacements={
    #                 "prefix": WdlTranslator.unwrap_expression(
    #                     expression.prefix,
    #                     inputsdict=inputsdict,
    #                     string_environment=True,
    #                     for_output=for_output,
    #                 )
    #             }
    #         )
    #         return cls.wrap_if_not_string_environment(gen_filename, string_environment)
    #     elif isinstance(expression, ForEachSelector):
    #         return wrap_in_code_block("idx")
    #     elif isinstance(expression, AliasSelector):
    #         return cls.unwrap_expression(
    #             expression.inner_selector,
    #             string_environment=string_environment,
    #             inputsdict=inputsdict,
    #             tool=tool,
    #             for_output=for_output,
    #             **debugkwargs,
    #         )

    #     elif isinstance(expression, StringFormatter):
    #         return translate_string_formatter(
    #             selector=expression,
    #             inputsdict=inputsdict,
    #             string_environment=string_environment,
    #             tool=tool,
    #             **debugkwargs,
    #         )
    #     elif isinstance(expression, WildcardSelector):
    #         raise Exception(
    #             f"A wildcard selector cannot be used as an argument value for '{debugkwargs}'"
    #         )

    #     elif isinstance(expression, ResourceSelector):

    #         if not tool:
    #             raise Exception(
    #                 f"Tool must be provided when unwrapping ResourceSelector: {type(expression).__name__}"
    #             )
    #         if isinstance(expression, CpuSelector):
    #             sel = InputSelector("runtimeCpu")
    #         elif isinstance(expression, DiskSelector):
    #             sel = InputSelector("runtimeDisk")
    #         elif isinstance(expression, MemorySelector):
    #             sel = InputSelector("runtimeMemory")
    #         elif isinstance(expression, TimeSelector):
    #             sel = InputSelector("runtimeSeconds")
    #         else:
    #             raise NotImplementedError
            
    #         return cls.unwrap_expression(
    #             sel,
    #             string_environment=string_environment,
    #             inputsdict=inputsdict,
    #             tool=tool,
    #             for_output=for_output,
    #             **debugkwargs,
    #         )

    #     elif isinstance(expression, InputSelector):
    #         if for_output:
    #             val = utils.prepare_filename_replacements_for(
    #                 expression, inputsdict=inputsdict
    #             )
    #             return wrap_in_code_block(val)
    #         return translate_input_selector(
    #             selector=expression,
    #             inputsdict=inputsdict,
    #             string_environment=string_environment,
    #             **debugkwargs,
    #         )
    #     elif callable(getattr(expression, "wdl", None)):
    #         return expression.wdl()

    #     unwrap_expression_wrap = lambda exp: cls.unwrap_expression(
    #         exp,
    #         inputsdict,
    #         string_environment=False,
    #         tool=tool,
    #         for_output=for_output,
    #         **debugkwargs,
    #     )

    #     if isinstance(expression, InputNodeSelector):
    #         # TODO here
    #         value = expression.input_node.id()
    #         if expression.input_node.default is not None:
    #             unwrapped_default = unwrap_expression_wrap(
    #                 expression.input_node.default
    #             )
    #             value = f"select_first([{value}, {unwrapped_default}])"
    #         return wrap_in_code_block(value)

    #     if isinstance(expression, StepOutputSelector):
    #         value = expression.node.id() + "." + expression.tag
    #         return wrap_in_code_block(value)
        
    #     elif isinstance(expression, Operator):
    #         return wrap_in_code_block(
    #             expression.to_wdl(unwrap_expression_wrap, *expression.args)
    #         )

    #     warning = ""
    #     if isclass(expression):
    #         stype = expression.__name__
    #         warning = f", this is likely due to the '{stype}' not being initialised"
    #     else:
    #         stype = expression.__class__.__name__
    #     raise Exception(
    #         f"Could not convert expression '{expression}' as could detect type '{stype}' to convert to input value{warning}"
    #     )

    # @classmethod
    # def unwrap_expression_for_output(
    #     cls,
    #     output: ToolOutput,
    #     expression,
    #     inputsdict=None,
    #     string_environment=False,
    #     **debugkwargs,
    # ):
    #     """
    #     :param output:
    #     :param expression:
    #     :param inputsdict:
    #     :param string_environment:
    #     :param debugkwargs:
    #     :return:
    #     """
    #     if isinstance(expression, CustomGlob):
    #         return expression.expression
    #     elif isinstance(output.output_type, Stdout) or isinstance(expression, Stdout):
    #         # can't get here with secondary_format
    #         return "stdout()"
    #     elif isinstance(output.output_type, Stderr) or isinstance(expression, Stderr):
    #         return "stderr()"

    #     if isinstance(expression, list):
    #         toolid = utils.value_or_default(debugkwargs.get("tool_id"), "get-value-list")
    #         joined_values = ", ".join(
    #             str(
    #                 cls.unwrap_expression_for_output(
    #                     output=output,
    #                     expression=expression[i],
    #                     inputsdict=inputsdict,
    #                     string_environment=False,
    #                     tool_id=toolid + "." + str(i),
    #                 )
    #             )
    #             for i in range(len(expression))
    #         )
    #         return f"[{joined_values}]"
    #     if is_python_primitive(expression):
    #         if isinstance(expression, str):
    #             return cls.wrap_if_not_string_environment(expression, string_environment)
    #         if isinstance(expression, bool):
    #             return "true" if expression else "false"

    #         return str(expression)
    #     elif isinstance(expression, StringFormatter):
    #         return translate_string_formatter_for_output(
    #             out=output,
    #             selector=expression,
    #             inputsdict=inputsdict,
    #             string_environment=string_environment,
    #             **debugkwargs,
    #         )
    #     elif isinstance(expression, WildcardSelector):
    #         is_single = not output.output_type.is_array()
    #         select_first = None
    #         is_single_optional = None
    #         if is_single:
    #             is_single_optional = output.output_type.optional
    #             if not expression.select_first:
    #                 Logger.info(
    #                     f"The command tool ({debugkwargs}).{output.id()}' used a star-bind (*) glob to find the output, "
    #                     f"but the return type was not an array. For WDL, the first element will be used, "
    #                     f"ie: 'glob(\"{expression.wildcard}\")[0]'"
    #                 )
    #                 select_first = True

    #         base_expression = translate_wildcard_selector(
    #             output=output,
    #             selector=expression,
    #             override_select_first=select_first,
    #             is_optional=is_single_optional,
    #             inputsdict=inputsdict,
    #         )

    #         return base_expression

    #     elif isinstance(expression, InputSelector):
    #         return translate_input_selector_for_output(
    #             out=output,
    #             selector=expression,
    #             inputsdict=inputsdict,
    #             string_environment=string_environment,
    #             **debugkwargs,
    #         )
    #     elif callable(getattr(expression, "wdl", None)):
    #         return expression.wdl()

    #     wrap_in_code_block = lambda x: f"~{{{x}}}" if string_environment else x
    #     unwrap_expression_wrap = lambda exp: cls.unwrap_expression_for_output(
    #         output=output,
    #         expression=exp,
    #         inputsdict=inputsdict,
    #         string_environment=False,
    #         **debugkwargs,
    #     )

    #     if isinstance(expression, (StepOutputSelector, InputNodeSelector)):
    #         raise Exception(
    #             "An InputnodeSelector or StepOutputSelector cannot be used to glob outputs"
    #         )

    #     elif isinstance(expression, Operator):
    #         return wrap_in_code_block(
    #             expression.to_wdl(unwrap_expression_wrap, *expression.args)
    #         )

    #     warning = ""
    #     if isclass(expression):
    #         stype = expression.__name__
    #         warning = f", this is likely due to the '{stype}' not being initialised"
    #     else:
    #         stype = expression.__class__.__name__

    #     if output._skip_output_quality_check and expression is None:
    #         return "None"

    #     raise Exception(
    #         f"Tool ({debugkwargs}) has an unrecognised glob type: '{stype}' ({expression}), this is "
    #         f"deprecated. Please use the a Selector to build the outputs for '{output.id()}'"
    #         + warning
    #     )