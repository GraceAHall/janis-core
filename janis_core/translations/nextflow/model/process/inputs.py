


from typing import Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass

from janis_core import DataType, File, Directory
from janis_core import translation_utils as utils


@dataclass
class NFProcessInput(ABC):
    name: str
    
    @abstractmethod
    def get_string(self) -> str:
        ...


@dataclass
class NFValProcessInput(NFProcessInput):

    def get_string(self) -> str:
        return f'val {self.name}'


@dataclass
class NFPathProcessInput(NFProcessInput):
    dtype: Optional[DataType]=None
    presents_as: Optional[str]=None

    @property
    def stage_as(self) -> str:
        if self.presents_as:
            outstr = f", stageAs: '{self.presents_as}'"
        elif isinstance(self.dtype, (File, Directory)):
            exts = utils.get_extensions(self.dtype)
            if exts and exts[0] != 'primary':
                outstr = f", stageAs: '{self.name}{exts[0]}'"
            else:
                outstr = f", stageAs: '{self.name}'"
        else:
            outstr = ''
        return outstr
    
    def get_string(self) -> str:
        return f'path {self.name}{self.stage_as}'


@dataclass
class NFTupleProcessInput(NFProcessInput):
    qualifiers: list[str]
    subnames: list[str]

    @property
    def fields(self) -> str:
        out: str = ''
        for qual, subname in zip(self.qualifiers, self.subnames):
            out += f'{qual}({subname}), '
        out = out.rstrip(', ') # strip off the last comma & space
        return out

    def get_string(self) -> str:
        return f'tuple {self.fields}'