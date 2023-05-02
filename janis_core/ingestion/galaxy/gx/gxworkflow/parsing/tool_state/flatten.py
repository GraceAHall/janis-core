


from typing import Any
from copy import deepcopy
from janis_core.ingestion.galaxy.gx.gxtool.param import BoolParam
from janis_core.ingestion.galaxy.gx.gxtool import XMLToolDefinition


def get_flattened_tool_state(gxstep: dict[str, Any], xmltool: XMLToolDefinition) -> dict[str, Any]:
    flattener = ToolStateFlattener(xmltool)
    return flattener.flatten(gxstep)

class ToolStateFlattener:
    def __init__(self, xmltool: XMLToolDefinition):
        self.xmltool = xmltool

    def flatten(self, step: dict[str, Any]) -> dict[str, Any]:
        curr_path: list[str] = []
        input_dict = self.explore_node(step['tool_state'], curr_path)
        return input_dict

    def explore_node(self, the_dict: dict[str, Any], path: list[str]) -> dict[str, Any]:
        for key, value in the_dict.items():
            if value == {"__class__": "RuntimeValue"}:
                the_dict[key] = '__RuntimeValue__'
                
            elif value == {"__class__": "ConnectedValue"}:
                the_dict[key] = '__ConnectedValue__'

            elif isinstance(value, dict):
                curr_path = deepcopy(path)
                curr_path.append(key)
                the_dict[key] = self.explore_node(value, curr_path)  # type: ignore
            
            else:
                # resolving bool flag values
                gxvarname = self.get_path_as_str(key, path)
                param = self.xmltool.inputs.get(gxvarname)
                if not param:
                    print()
                if param and isinstance(param, BoolParam):
                    if value == 'false':
                        the_dict[key] = param.falsevalue
                        # the_dict[key] = f'"{param.falsevalue}"'
                    else:
                        the_dict[key] = param.truevalue
                        # the_dict[key] = f'"{param.truevalue}"'
                    continue
                
                # # str wrapping
                # if isinstance(value, str):
                #     try:
                #         # if successfully eval'd, its not an actual string
                #         eval(value)
                #         print()
                #     except:
                #         the_dict[key] = f'"{value}"'
                #         print()

        return the_dict

    def get_path_as_str(self, name: str, path_copy: list[str]) -> str:
        if len(path_copy) > 0:
            full_name = f'{".".join(path_copy)}.{name}'
        else:
            full_name = name
        return full_name
    




class ToolStateFlattenerOld:
    def __init__(self):
        self.flattened_tool_state: dict[str, Any] = {}

    def flatten(self, step: dict[str, Any]) -> dict[str, Any]:
        for name, value in step['tool_state'].items():
            self.explore_node(name, value, [])
        return self.flattened_tool_state

    def explore_node(self, name: str, value: Any, path: list[str]) -> Any:
        path_copy = deepcopy(path)
        if name == '__current_case__':
            pass
        elif value == {"__class__": "RuntimeValue"}:
            self.add_to_flattened_tool_state(name, '__RuntimeValue__', path_copy)
        elif value == {"__class__": "ConnectedValue"}:
            pass
        elif isinstance(value, dict):
            path_copy.append(name)
            for key, val in value.items():
                self.explore_node(key, val, path_copy)
        else:
            self.add_to_flattened_tool_state(name, value, path_copy)
    
    def add_to_flattened_tool_state(self, name: str, value: Any, path_copy: list[str]) -> None:
        if len(path_copy) > 0:
            full_name = f'{".".join(path_copy)}.{name}'
        else:
            full_name = name
        self.flattened_tool_state[full_name] = value


