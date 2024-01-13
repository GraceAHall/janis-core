

import regex as re
from typing import Any
from functools import cached_property
from abc import ABC, abstractmethod

from janis_core import settings
from janis_core import Tool, ToolInput, ToolOutput, Filename
from janis_core import CommandToolBuilder, CodeTool, WorkflowBuilder
from janis_core.workflow.workflow import InputNode, StepNode, OutputNode
from .case import format_case

IdentifiedEntity = Tool | ToolInput | ToolOutput | InputNode | StepNode | OutputNode


def fix_illegals(parent: WorkflowBuilder | CommandToolBuilder | CodeTool, entity: Any, text: str) -> str:
    # ignore invalid entities
    if not isinstance(entity, IdentifiedEntity):
        return text
    if not isinstance(parent, WorkflowBuilder | CommandToolBuilder):
        raise RuntimeError
    
    # init class to define and handle illegals
    illegals_map = {
        'cwl': CwlIllegals,
        'nextflow': NxfIllegals,
        'wdl': WdlIllegals,
    }
    illegals_c = illegals_map[settings.translate.DEST]
    illegals = illegals_c(parent, entity)

    # check and handle illegals
    text = illegals.fix_illegal_symbol(text)
    text = illegals.fix_duplicate_symbol(text)
    return text



######################
### identification ###
######################

class Illegals:

    workflow: set[str]
    tool: set[str]
    all_illegals: set[str]

    def __init__(self, parent: WorkflowBuilder | CommandToolBuilder, entity: IdentifiedEntity) -> None:
        # base_keywords = set(keyword.kwlist) | set(dir(builtins)) | self.common
        # self.workflow = base_keywords | self.workflow 
        # self.tool = base_keywords | self.tool 
        self.parent = parent
        self.entity = entity

    ### public methods ###
    def fix_illegal_symbol(self, text: str) -> str:
        if text not in self.all_illegals:   # ignore non illegal
            return text
        return self._alter_symbol(text)
    
    def fix_duplicate_symbol(self, text: str) -> str:
        while self._duplicate_exists(text):
            text = self._alter_symbol(text)
        return text

    def _alter_symbol(self, text: str) -> str:
        for strategy_c in [EntityTypeStrategy, DataTypeStrategy, NumberStrategy]:
            strategy = strategy_c(self.parent, self.entity)
            if strategy.can_alter(text):
                try: 
                    new_text = strategy.do_alter(text)
                    if strategy.valid_alter(new_text):
                        return new_text
                except:
                    continue
        raise RuntimeError
    
    ### private methods ###
    def _duplicate_exists(self, text: str) -> bool:
        # all inputs will have unique ids. same for outputs. 
        # duplicates can still exist - where an input and an output share the same id.
        # in this case we want to correct the output id (just a feeling) rather than input id,
        # so ignore inputs here.
        if isinstance(self.entity, ToolInput | InputNode):
            return False
        entities = self._gather_entities_with_id(text)
        if len(entities) == 0:
            return False
        elif len(entities) == 1:
            if entities[0].uuid == self.entity.uuid:
                return False
            return True
        else:
            return True

    def _gather_entities_with_id(self, ident: str) -> list[IdentifiedEntity]:
        # workflow
        if isinstance(self.parent, WorkflowBuilder):
            out: list[IdentifiedEntity] = []
            if self.parent.id() == ident:
                out.append(self.parent)
            out += [x for x in self.parent.input_nodes.values() if x.id() == ident]
            out += [x for x in self.parent.step_nodes.values() if x.id() == ident]
            out += [x for x in self.parent.output_nodes.values() if x.id() == ident]
            return out
        
        # cmdtool
        if isinstance(self.parent, CommandToolBuilder):
            out: list[IdentifiedEntity] = []
            if self.parent.id() == ident:
                out.append(self.parent)
            out += [x for x in self.parent._inputs if x.id() == ident]
            out += [x for x in self.parent._outputs if x.id() == ident]
            return out
    
        raise RuntimeError



class CwlIllegals(Illegals):
    # is anything illegal?? 
    
    def __init__(self, parent: WorkflowBuilder | CommandToolBuilder, entity: IdentifiedEntity) -> None:
        super().__init__(parent, entity)
        self.common = set()
        self.workflow = set()
        self.tool = set()
        self.all_illegals = self.common | self.workflow | self.tool

    ### public methods ###
    def fix_illegal_symbol(self, text: str) -> str:
        # cwl doesn't seem to have any illegal symbols? 
        return text 
    
    def fix_duplicate_symbol(self, text: str) -> str:
        # duplicates are ok?
        return text 


class NxfIllegals(Illegals):

    def __init__(self, parent: WorkflowBuilder | CommandToolBuilder, entity: IdentifiedEntity) -> None:
        super().__init__(parent, entity)
        self.common = set([
            # general keywords 
            "nextflow",
            "include",
            "params",
            "def",
            "channel",
            
            # datatype keywords
            "tuple",
            "path",
            "val",
            "file", # init a file() object
            "path", # init a path() object?

            # workflow keywords
            "workflow",
            "take",
            "main",
            "emit",
            
            # tool keywords
            "process",
            "input",
            "output",
            "script",
            "exec",
            "container",
            "conda",
            
            # functions
            "map",
        ])
        self.workflow = set()
        self.tool = set()
        self.all_illegals = self.common | self.workflow | self.tool



class WdlIllegals(Illegals):

    def __init__(self, parent: WorkflowBuilder | CommandToolBuilder, entity: IdentifiedEntity) -> None:
        super().__init__(parent, entity)
        self.common = set([
            # general keywords 
            "import",
            "meta",
            "parameter_meta",

            # workflow keywords
            "workflow",
            "take",
            "main",
            "emit",
            "call",
            "as",
            
            # tool keywords
            "task",
            "input",
            "command",
            "output",
            "runtime",
            
            # functions
            "defined",
            "basename",
            # TODO
            
            # datatype keywords
            "struct",
            "File",
            "Float",
            "Int",
            "String",
            "Boolean",
            "Array",
            "Map",
            "Object",
        ])
        self.workflow = set()
        self.tool = set()
        self.all_illegals = self.common | self.workflow | self.tool

    def fix_illegal_symbol(self, text: str) -> str:
        # edge case
        text = self.fix_string_path(text)
        text = super().fix_illegal_symbol(text)
        return text
    
    def fix_string_path(self, text: str) -> str:
        # only alter if correct entity
        if not isinstance(self.entity, ToolInput | ToolOutput | InputNode | OutputNode):
            return text
        
        # get datatype
        if isinstance(self.entity, ToolInput):
            dtype = self.entity.input_type
        elif isinstance(self.entity, ToolOutput):
            dtype = self.entity.output_type
        elif isinstance(self.entity, InputNode | OutputNode):
            dtype = self.entity.datatype
        else:
            raise RuntimeError

        # alter if satisfies edge case
        if isinstance(dtype, Filename) and not text.endswith("Path"):
            text = text + 'Path'
        
        return text



##################
### resolution ###
##################

class AlterStrategy(ABC):

    def __init__(self, parent: Any, entity: IdentifiedEntity) -> None:
        self.parent = parent
        self.entity = entity

    @abstractmethod
    def can_alter(self, text: str) -> bool:
        ...

    @abstractmethod
    def do_alter(self, text: str) -> str:
        ...
    
    @abstractmethod
    def valid_alter(self, text: str) -> bool:
        ...


class EntityTypeStrategy(AlterStrategy):

    def can_alter(self, text: str) -> bool:
        """
        ignore this strategy for select inputs / outputs
        eg 'output' should not become 'out_output' since this sucks. 
        should instead be 'output_file' (using datatype instead) or something
        """
        # inputs
        PATTERN = r'[iI]np?(ut)?([_A-Z0-9]|$)'
        if isinstance(self.entity, ToolInput | InputNode):
            if re.match(PATTERN, text):
                return False
        # outputs
        PATTERN = r'[oO]ut(put)?([_A-Z0-9]|$)'
        if isinstance(self.entity, ToolOutput | OutputNode):
            if re.match(PATTERN, text):
                return False
        return True

    def do_alter(self, text: str) -> str:
        if isinstance(self.entity, ToolInput | InputNode):
            text = f'in_{text}'
        elif isinstance(self.entity, ToolOutput | OutputNode):
            text = f'out_{text}'
        elif isinstance(self.entity, WorkflowBuilder):
            text = f'{text}_wf'
        elif isinstance(self.entity, CommandToolBuilder):
            text = f'{text}_tool'
        elif isinstance(self.entity, StepNode):
            suffix_map = {
                'cwl': 'step',
                'wdl': 'task',
                'nextflow': 'task',
            }
            suffix = suffix_map[settings.translate.DEST]
            text = f'{text}_{suffix}'
        else:
            raise NotImplementedError
        return format_case(self.entity, text) 
    
    def valid_alter(self, text: str) -> bool:
        return True
    
    

class DataTypeStrategy(AlterStrategy):

    def can_alter(self, text: str) -> bool:
        if isinstance(self.entity, ToolInput | ToolOutput | InputNode | OutputNode):
            return True
        return False

    def do_alter(self, text: str) -> str:
        # get datatype
        if isinstance(self.entity, ToolInput):
            dtype = self.entity.input_type
        elif isinstance(self.entity, ToolOutput):
            dtype = self.entity.output_type
        elif isinstance(self.entity, InputNode | OutputNode):
            dtype = self.entity.datatype
        else:
            raise RuntimeError
        
        # overriding suffixes for these types
        suffix_map = {
            'String': 'str',
        }

        # select suffix (unformatted, doesn't matter since case will be formatted later)
        classname = dtype.__class__.__name__
        simplename = dtype.name()
        suffix = classname if classname.lower() == simplename.lower() else simplename
        suffix = suffix_map.get(suffix, suffix)

        # append suffix and return
        text = f'{text}_{suffix}'
        return format_case(self.entity, text)
    
    def valid_alter(self, text: str) -> bool:
        """
        checks for duplicate substrings of length 3 or more.
        eg. in_file_file is invalid since it contains 'file_file'.
        """
        text_l = text.lower()
        PATTERN = r'(.{3,}).*\1'
        if re.match(PATTERN, text_l):
            return False
        return True


class NumberStrategy(AlterStrategy):

    def can_alter(self, text: str) -> bool:
        return True

    def do_alter(self, text: str) -> str:
        # get existing trailing integers
        num_suffix = re.match(r'\d+$', text)
        
        # no trailing ints  (eg. infile -> infile_2)
        if num_suffix is None:
            text = f'{text}_2'
        # yes trailing ints (eg. infile_2 -> infile_3)
        else:
            num_suffix = int(num_suffix.group()) + 1
            text = text[:-len(str(num_suffix))] + str(num_suffix)
        
        return text
    
    def valid_alter(self, text: str) -> bool:
        return True
