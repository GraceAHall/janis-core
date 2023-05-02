

from typing import Optional, Any
from ..gxtool.tool import XMLToolDefinition
from .factory import CommandFactory
from .Command import Command


def gen_command(xmltool: XMLToolDefinition, galaxy_step: Optional[Any]=None) -> Command:
    factory = CommandFactory(xmltool, galaxy_step)
    return factory.create()



