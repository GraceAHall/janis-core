

from enum import Enum, auto
from dataclasses import dataclass
from typing import Any


class VariableType(Enum): 
    INPUT   = auto()
    PARAM   = auto()
    STATIC  = auto()
    IGNORED = auto()
    CHANNEL = auto()
    LOCAL   = auto()

@dataclass
class Variable:
    vtype: VariableType
    value: Any