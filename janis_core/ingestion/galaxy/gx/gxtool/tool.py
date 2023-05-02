

from dataclasses import dataclass

from ..configfiles.Configfile import Configfile
from .metadata import ToolXMLMetadata
from .param.ParamRegister import ParamRegister
from .TestRegister import TestRegister
from .requirements import ContainerRequirement, CondaRequirement

Requirement = ContainerRequirement | CondaRequirement


@dataclass
class XMLToolDefinition:
    """
    High-level component representing a tool. 
    Does not depend on lower level representations or parsing.
    Permits storing and retreiving data about the tool.
    """
    metadata: ToolXMLMetadata
    raw_command: str
    configfiles: list[Configfile]
    inputs: ParamRegister
    outputs: ParamRegister
    tests: TestRegister

