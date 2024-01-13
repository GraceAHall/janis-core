
import json
import wdlgen as wdl
from inspect import isclass
from typing import Optional, Any

from janis_core.operators import (
    InputSelector,
    WildcardSelector,
    CpuSelector,
    MemorySelector,
    FloorOperator,
    StringFormatter,
    Selector,
    Operator,
    StepOutputSelector,
    InputNodeSelector,
    TimeSelector,
    DiskSelector,
    ResourceSelector,
    AliasSelector,
    ForEachSelector,
)
from janis_core.tool.commandtool import ToolInput, ToolOutput, CommandToolBuilder

from janis_core.types.common_data_types import (
    Stdout,
    Stderr,
    Array,
    Filename,
    File,
    Directory,
)
from janis_core.types.data_types import is_python_primitive
from janis_core.utils.logger import Logger
from janis_core.utils.secondary import apply_secondary_file_format_to_filename
from janis_core.workflow.workflow import WorkflowBuilder
from janis_core.workflow.workflow import InputNode, StepNode, OutputNode
from . import utils

Entity = ToolInput | ToolOutput | InputNode | StepNode | OutputNode 


class CustomGlob(Selector):
    def __init__(self, expression):
        self.expression = expression

    def returntype(self):
        return Array(File)

    def to_string_formatter(self):
        raise Exception("Not supported for CustomGlob")


def unwrap_expression(
    expr: Any,
    inputsdict: Optional[dict]=None, 
    string_environment: bool=False, 
    tool: Optional[CommandToolBuilder | WorkflowBuilder]=None,
    toolid: Optional[str]=None,
    entity: Optional[Entity]=None,
    for_output=False,
    **contextkwargs
    ) -> str:
    if 'scatterstep' in contextkwargs:
        raise NotImplementedError
    unwrapper = Unwrapper(
        inputsdict=inputsdict,
        string_environment=string_environment,
        tool=tool,
        toolid=toolid,
        entity=entity,
        for_output=for_output,
    )
    return unwrapper.unwrap_expression(expr, **contextkwargs)


class Unwrapper:
    def __init__(
        self, 
        inputsdict: Optional[dict]=None, 
        string_environment: bool=False, 
        tool: Optional[CommandToolBuilder | WorkflowBuilder]=None, 
        toolid: Optional[str]=None,
        entity: Optional[Entity]=None,
        for_output=False, 
        ):
        self.inputsdict = inputsdict
        self.string_environment = string_environment
        self.tool = tool
        self.toolid = toolid
        self.entity = entity
        self.for_output = for_output
    
    def unwrap_expression(self, expr: Any, **contextkwargs) -> Any:
        # copy and update self vars
        tempvars = {}
        for k, v in contextkwargs.items():
            if hasattr(self, k):
                tempvars[k] = getattr(self, k)
            setattr(self, k, v)

        expr = self.do_unwrap(expr)

        # restore self vars
        for k, v in tempvars.items():
            setattr(self, k, v)

        return expr
    
    def do_unwrap(self, expr: Any) -> Any:
        # context: ToolOutput
        if self.for_output:
            if isinstance(expr, (StepOutputSelector, InputNodeSelector)):
                raise Exception(
                    "An InputnodeSelector or StepOutputSelector cannot be used to glob outputs"
                )
            assert isinstance(self.entity, ToolOutput)
            if isinstance(expr, CustomGlob):
                return expr.expression
            elif isinstance(self.entity.output_type, Stdout) or isinstance(expr, Stdout):
                # can't get here with secondary_format
                return "stdout()"
            elif isinstance(self.entity.output_type, Stderr) or isinstance(expr, Stderr):
                return "stderr()"
            elif isinstance(expr, WildcardSelector):
                return self.unwrap_expression(expr.wildcard, string_environment=False)

        # context: general
        if expr is None:
            return ""
        
        elif isinstance(expr, StepNode):
            raise Exception(
                f"The Step node '{expr.id()}' was found when unwrapping an expression, "
                f"you might not have selected an output."
            )

        elif isinstance(expr, list):
            return self.unwrap_list(expr)
        
        elif is_python_primitive(expr):
            return self.unwrap_primitive(expr)

        elif isinstance(expr, Filename):
            return self.unwrap_filename(expr)
        
        elif isinstance(expr, ForEachSelector):
            return self.wrap_in_code_block("idx")
        
        elif isinstance(expr, AliasSelector):
            return self.unwrap_expression(expr.inner_selector)

        elif isinstance(expr, StringFormatter):
            return self.unwrap_string_formatter(expr)
        
        elif isinstance(expr, ResourceSelector):
            return self.unwrap_resource_selector(expr)

        elif isinstance(expr, InputSelector):
            return self.unwrap_input_selector(expr)
                    
        elif callable(getattr(expr, "wdl", None)):
            return expr.wdl()

        if isinstance(expr, InputNodeSelector):
            return self.unwrap_input_node_selector(expr)

        if isinstance(expr, StepOutputSelector):
            value = expr.node.id() + "." + expr.tag
            return self.wrap_in_code_block(value)
        
        elif isinstance(expr, Operator):
            unwrap_expression_wrap = lambda exp: unwrap_expression(
                exp,
                inputsdict=self.inputsdict,
                string_environment=False,
                tool=self.tool,
                toolid=self.toolid,
                entity=self.entity, 
                for_output=self.for_output,
            )
            wdlstr = expr.to_wdl(unwrap_expression_wrap, *expr.args)
            return self.wrap_in_code_block(wdlstr)

        # error handling
        warning = ""
        if isclass(expr):
            stype = expr.__name__
            warning = f", this is likely due to the '{stype}' not being initialised"
        else:
            stype = expr.__class__.__name__
        raise Exception(
            f"Could not convert expression '{expr}' as could detect type '{stype}' to convert to input value{warning}"
        )
    
    def unwrap_list(self, expr: list[Any]) -> Any:
        toolid = self.toolid if self.toolid is not None else "get-value-list" # TODO check
        # toolid = utils.value_or_default(self.debugkwargs.get("tool_id"), "get-value-list")
        
        for i in range(len(expr)):
            self.toolid = toolid + "." + str(i)
            expr[i] = str(self.unwrap_expression(expr[i], string_environment=False))
        
        joined_values = ", ".join(expr)
        return f"[{joined_values}]"
    
    def unwrap_primitive(self, expr: Any) -> str:
        if isinstance(expr, str):
            if self.string_environment:
                return expr
            return self.wrap_if_not_string_environment(self.prepare_escaped_string(expr))
        if isinstance(expr, bool):
            return "true" if expr else "false"
        return str(expr)
    
    def unwrap_filename(self, expr: Filename) -> str:
        prefix = self.unwrap_expression(expr.prefix, string_environment=True)
        expr_str = expr.generated_filename(replacements={"prefix": prefix})
        expr_str = self.wrap_if_not_string_environment(expr_str)
        return expr_str

    def unwrap_resource_selector(self, selector: ResourceSelector) -> str:
        if self.inputsdict is None:
            raise Exception(
                f"ToolInputs dict must be provided when unwrapping ResourceSelector: {type(selector).__name__}"
            )
        if isinstance(selector, CpuSelector):
            sel = InputSelector("runtimeCpu")
        elif isinstance(selector, DiskSelector):
            sel = FloorOperator(InputSelector("runtimeDisk"))
        elif isinstance(selector, MemorySelector):
            sel = FloorOperator(InputSelector("runtimeMemory"))
        elif isinstance(selector, TimeSelector):
            sel = InputSelector("runtimeSeconds")
        else:
            raise NotImplementedError
        
        return self.unwrap_expression(sel)
    
    def unwrap_input_selector(self, selector: InputSelector) -> str:
        if selector.input_to_select is None:
            raise Exception("No input was selected for input selector: " + str(selector))
        
        if self.inputsdict is None:
            raise Exception(
                f"An internal error has occurred when selecting the input '{selector.input_to_select}'"
            )

        if selector.input_to_select not in self.inputsdict:
            raise Exception(
                f"Couldn't find input '{selector.input_to_select}' in tool '{self.toolid}'"
            )
        
        # if self.for_output:
            # if not utils.is_defined(inp):
            #     expr = f'if defined({inp.id()}) then {expr} else "generated"'

        inp = self.inputsdict[selector.input_to_select]
        expr = utils.resolve_tool_input_value(inp)

        intype = inp.input_type
        if selector.remove_file_extension and (
            File().can_receive_from(intype) or Directory().can_receive_from(intype)
        ):
            if isinstance(intype, File):
                extensions = {
                    e
                    for e in [intype.extension, *(intype.alternate_extensions or [])]
                    if e is not None
                }
                if extensions:
                    for ext in extensions:
                        expr = f'basename({expr}, "{ext}")'
                else:
                    expr = f"basename({expr})"
            else:
                expr = f"basename({expr})"

        if self.string_environment:
            return f"~{{{expr}}}"
        else:
            return expr
        
    def unwrap_input_node_selector(self, selector: InputNodeSelector) -> str:
        value = selector.input_node.id()
        if selector.input_node.default is not None:
            unwrapped_default = self.unwrap_expression(selector.input_node.default, string_environment=False)
            value = f"select_first([{value}, {unwrapped_default}])"
        return self.wrap_in_code_block(value)
    
    def unwrap_string_formatter(self, selector: StringFormatter):
        # we should raise an Exception if any of our inputs are optional without a default
        assert self.inputsdict is not None

        invalid_select_inputs = [
            (k, selector.kwargs[k].input_to_select)
            for k in selector.kwargs
            # Our selector is getting an input
            if isinstance(selector.kwargs[k], InputSelector)
            and not isinstance(
                selector.kwargs[k],
                (CpuSelector, MemorySelector, DiskSelector, TimeSelector),
            )
            and selector.kwargs[k].input_to_select in self.inputsdict
            and not isinstance(
                self.inputsdict[selector.kwargs[k].input_to_select].input_type, Filename
            )
            # our selected input is optional
            and self.inputsdict[selector.kwargs[k].input_to_select].input_type.optional
            # our selected input does NOT have a default
            # tbh, this ToolInput might have a default that selects a different input that is null,
            # but I'm not going down this rabbit hole
            and self.inputsdict[selector.kwargs[k].input_to_select].default is None
        ]

        if len(invalid_select_inputs) > 0:
            tags = ", ".join(f"'{k[0]}'" for k in invalid_select_inputs)
            inps = ", ".join(f"'{k[1]}'" for k in invalid_select_inputs)
            Logger.log(
                f'There might be an error when resolving the format "{selector._format}", the tag(s) {tags} respectively '
                f"selected input(s) {inps} that were optional and did NOT have a default value. This might be okay if "
                f"{tags} was wrapped in a IfDefined operator"
            )

        resolved_kwargs = {}
        for k, v in selector.kwargs.items():
            resolved_kwargs[k] = self.unwrap_expression(v, string_environment=True)
        expr = selector.resolve_with_resolved_values(**resolved_kwargs)
        
        return expr if self.string_environment else f'"{expr}"'

    def wrap_in_code_block(self, value: str) -> str:
        return f"~{{{value}}}" if self.string_environment else value

    def wrap_if_not_string_environment(self, value: Any):
        return f'"{value}"' if not self.string_environment else value

    def prepare_escaped_string(self, value: str):
        return json.dumps(value)[1:-1]
    
    




    # def translate_string_formatter_for_output(self, selector: StringFormatter) -> str:
    #     """
    #     The output glob was a string formatter, so we'll need to build the correct glob
    #     by resolving the string formatter. Some minor complications involve how an output
    #     with a secondary file must resolve input selectors.

    #     For example, if you are generating an output with the Filename class, and your output
    #     type has secondary files, you will need to translate the generated filename with
    #     respect to the secondary file extension. Or the File class also has a recommended
    #     "extension" property now that this should consider.

    #     :param inputsdict:
    #     :param out:
    #     :param selector:
    #     :return:
    #     """
    #     inputs_to_retranslate = {
    #         k: v
    #         for k, v in selector.kwargs.items()
    #         if not any(isinstance(v, t) for t in StringFormatter.resolved_types)
    #     }

    #     resolved_kwargs = {
    #         **selector.kwargs,
    #         **{
    #             k: self.unwrap_expression(v, string_environment=True)
    #             for k, v in inputs_to_retranslate.items()
    #         },
    #     }

    #     return f'"{selector.resolve_with_resolved_values(**resolved_kwargs)}"'
    
    # def translate_input_selector_for_secondary_output(
    #     self,
    #     out: ToolOutput,
    #     selector: InputSelector,
    #     inputsdict: dict[str, ToolInput],
    #     **debugkwargs,
    # ) -> list[wdl.Output]:
    #     expression = translate_input_selector(
    #         selector, inputsdict, string_environment=False, **debugkwargs
    #     )

    #     tool_in = inputsdict.get(selector.input_to_select)
    #     if not tool_in:
    #         raise Exception(
    #             f"The InputSelector for tool '{debugkwargs}.{out.id()}' did not select an input (tried: '{selector.input_to_select}')"
    #         )

    #     return expression

