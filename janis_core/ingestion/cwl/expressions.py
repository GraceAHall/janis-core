


"""
docstring here! sphinx
"""


from typing import Any, Tuple, Optional

import re
import janis_core as j


# functions: "${func}"
function_token_matcher = re.compile(r"^\$\{[\s\S]*return[\s\S]*\}$")  # TODO imperfect. see test_initial_workdir_requirement_listing test

# simple functions: ${ return "over 80000" },  ${return 16;}
simple_function_token_matcher = re.compile(r"^\s*\$\{\s*return ([^\s'\";{}]+|['\"][^;{}]*?['\"])[\s;]*?\}$")

# single javascript expression: "$(expr)"
single_token_matcher = re.compile(r"^\$\((.+)\)$")  

# used for matching multiple expressions in a line: "$(expr1) + $(expr2)"
# up to 3 levels of recursion
inline_expression_matcher = re.compile(r"(?<=\$\()(?:[^)(]|\((?:[^)(]|\((?:[^)(]|\([^)(]*\))*\))*\))*(?=\))")  

# cwl input references to StepOutputSelector: valueFrom: $(steps.combine.result) -> StepOutputSelector()
step_output_selector_matcher = re.compile(r"^steps\.([A-z0-9_]+)\.([A-z0-9_]+)$")

# cwl input references to InputSelector / InputNodeSelector 
# depends on 'context' field of ExpressionParser
# valueFrom: $(inputs.myName) -> InputSelector("myName")
# valueFrom: $(inputs.myWfInp) -> InputNodeSelector("myWfInp")
input_selector_matcher = re.compile(r"^inputs\.([A-z0-9_]+)$")  

# literal strings
string_matcher = re.compile(r'^".+?"$')  

# ints
int_matcher = re.compile(r"^\s*\d+\s*$")

# floats
float_matcher = re.compile(r"^\s*(\d*\.\d+)|(\d+\.\d*)\s*$")



def parse_basic_expression(expr: Any, context: str='clt', wf: Optional[j.Workflow]=None) -> Tuple[Any, bool]: 
    parser = ExpressionParser(context, wf)
    return parser.parse(expr)


class ExpressionParser:
    def __init__(self, context: str, wf: Optional[j.Workflow]=None) -> None:
        self.context = context
        self.wf = wf
        self.success: bool = True

    def parse(self, expr: Any) -> Tuple[Any, bool]:
        """parses """
        
        # early exits
        if expr is None:
            return (None, True)
        elif not isinstance(expr, str):
            return (expr, True)
        
        single_token_match = single_token_matcher.match(expr)
        simple_function_match = simple_function_token_matcher.match(expr)
        function_match = function_token_matcher.match(expr)
        all_token_matches = set(inline_expression_matcher.findall(expr)) # non-full length expressions "$(expr1).fastq" etc
        
        # if only single $(expr) 
        if single_token_match:
            res = self.convert_javascript_token(single_token_match.groups()[0])

        # if simple function ${return 16;}
        elif simple_function_match:
            res = self.convert_javascript_token(simple_function_match.group(1))
            if isinstance(res, str):
                res = res.replace('\n', '')

        # if function ${func}
        elif function_match:
            res = self.convert_javascript_token(function_match.group(0))
            if isinstance(res, str):
                res = res.replace('\n', '')

        # if multiple expressions $(expr1) + $(expr2) etc
        elif all_token_matches:
            string_format = f"{expr}"
            token_replacers = {}

            for token, idx in zip(all_token_matches, range(len(all_token_matches))):
                key = f"JANIS_CWL_TOKEN_{idx+1}"
                string_format = string_format.replace(f"$({token})", f"{{{key}}}")
                val = self.convert_javascript_token(token)
                token_replacers[key] = val

            if len(token_replacers) == 0:
                res = string_format
            else:
                res = j.StringFormatter(string_format, **token_replacers)
        
        # no matches
        else:
            res = expr
    
        return (res, self.success)

    def convert_javascript_token(self, token: str) -> Any:
        step_output_selector_match = step_output_selector_matcher.match(token)
        input_selector_match = input_selector_matcher.match(token)
        
        if input_selector_match:
            tag = input_selector_match.groups()[0]
            return self.convert_input_selector_token(token, tag)
        elif step_output_selector_match:
            tag = step_output_selector_match.groups()[0]
            return self.convert_input_node_selector_token(token, tag)
        elif input_selector_match:
            return j.InputSelector(input_selector_match.groups()[0])
        elif token.endswith(".size"):
            return j.FileSizeOperator(self.convert_javascript_token(token[:-5]))
        elif token.endswith(".nameroot"):
            return j.NamerootOperator(self.convert_javascript_token(token[:-9]))
        elif token.endswith(".basename"):
            return j.BasenameOperator(self.convert_javascript_token(token[:-9]))
        elif token.endswith(".path"):
            # Ignore it because Janis will automatically put this back in where relevant
            return self.convert_javascript_token(token[:-5])
        elif token.endswith(".contents"):
            return j.ReadContents(self.convert_javascript_token(token[:-9]))
        elif string_matcher.match(token):
            return token[1:-1]
        elif int_matcher.search(token):
            return int(token)
        elif float_matcher.search(token):
            return float(token)
        
        else:
            # j.Logger.warn(
            #     f"Couldn't translate javascript token, will use the placeholder '<js>{token}</js>'"
            # )
            self.success = False
            # if token.startswith('$(') and token.endswith(')'):
            #     token = token[2:-1]
            return f"<js>{token}</js>"
        
    def convert_input_selector_token(self, token: str, tag: str) -> j.InputNodeSelector | j.InputSelector | str:
        if self.context == 'clt':
            return j.InputSelector(tag)
        elif self.context == 'workflow':
            return self.convert_input_node_selector_token(token, tag)
        else:
            raise NotImplementedError

    def convert_input_node_selector_token(self, token: str, tag: str) -> j.InputNodeSelector | str:
        assert(self.wf)
        # fallback
        if tag not in self.wf.input_nodes:
            self.success = False
            return f"<js>{token}</js>"
        # success
        else:
            inp = self.wf.input_nodes[tag]
            return j.InputNodeSelector(inp)