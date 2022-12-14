
from typing import Optional, Any

from janis_bioinformatics.data_types.bam import BamBai
from janis_core import (
    ToolOutput,
    ToolInput,
    CommandTool,
    ToolArgument,
    WildcardSelector,
    InputSelector

)

from .types import (
    SecondaryTestType,
    AppendedSecondaryTestType,
    ReplacedSecondaryTestType,
    NonEscapedSecondaryTestType
)

from janis_core.types import (
    File,
    String,
    Int,
    Stdout,
    Boolean,
)


class StdoutTestTool(CommandTool):
    def tool(self) -> str:
        return "StdoutTestTool"

    def base_command(self) -> Optional[str | list[str]]:
        return "echo"

    def inputs(self) -> list[ToolInput]:
        return []

    def outputs(self):
        return [ToolOutput("out", Stdout)]

    def container(self) -> str:
        return "quay.io/biocontainers/bedtools:2.29.2--hc088bd4_0"

    def version(self) -> str:
        return "TEST"

class FileTestTool(StdoutTestTool):
    def tool(self) -> str:
        return "FileStdoutTestTool"

    def inputs(self) -> list[ToolInput]:
        return [ToolInput("inp", File, position=1)]

class StringTestTool(StdoutTestTool):
    def tool(self) -> str:
        return "StringStdoutTestTool"

    def inputs(self) -> list[ToolInput]:
        return [ToolInput("inp", String, position=1)]

class IntTestTool(StdoutTestTool):
    def tool(self) -> str:
        return "IntStdoutTestTool"

    def inputs(self) -> list[ToolInput]:
        return [ToolInput("inp", Int, position=1)]



class ResourcesTestTool(CommandTool):
    def tool(self) -> str:
        return "ResourcesTestTool"

    def base_command(self) -> Optional[str | list[str]]:
        return "echo"

    def inputs(self) -> list[ToolInput]:
        return [
            ToolInput("inp", File, position=1), 
            ToolInput("threads", Int)
        ]

    def outputs(self):
        return [ToolOutput("out", Stdout)]

    def container(self) -> str:
        return "quay.io/biocontainers/bedtools:2.29.2--hc088bd4_0"

    def version(self) -> str:
        return "TEST"
    
    def disk(self, hints: dict[str, Any]):
        return 100

    def memory(self, hints: dict[str, Any]):
        return 4

    def cpus(self, hints: dict[str, Any]):
        return 1 * InputSelector("threads")

    def time(self, hints: dict[str, Any]):
        return 60




class EchoBase(CommandTool):
    def base_command(self) -> Optional[str | list[str]]:
        return "echo"
    
    def container(self) -> str:
        return "ubuntu:latest"

    def version(self) -> str:
        return "TEST"


class WildcardSelectorTestTool(EchoBase):
    def tool(self) -> str:
        return "WildcardSelectorTestTool"

    def inputs(self) -> list[ToolInput]:
        return [ToolInput("inp", File, position=1)]

    def outputs(self):
        return [ToolOutput("out", File, selector=WildcardSelector('myfile.txt'))]


class FileInputSelectorTestTool(EchoBase):
    def tool(self) -> str:
        return "FileInputSelectorTestTool"

    def inputs(self) -> list[ToolInput]:
        return [ToolInput("inp", File, position=1)]

    def outputs(self):
        return [ToolOutput("out", File, selector=InputSelector('inp'))]


class StringInputSelectorTestTool(EchoBase):
    def tool(self) -> str:
        return "StringInputSelectorTestTool"
    
    def inputs(self) -> list[ToolInput]:
        return [ToolInput("inp", String, position=1)]

    def outputs(self):
        return [ToolOutput("out", String, selector=InputSelector('inp'))]




class ComponentsTestTool(CommandTool):
    def tool(self) -> str:
        return "ComponentStdoutTestTool"

    def base_command(self) -> Optional[str | list[str]]:
        return "echo"

    def inputs(self) -> list[ToolInput]:
        return [
            ToolInput("pos_basic", File, position=1),
            ToolInput("pos_basic2", File(optional=True), position=999),
            ToolInput("pos_default", Int, default=95, position=2),
            ToolInput("pos_optional", String(optional=True), position=3),

            ToolInput("flag_true", Boolean, position=4, prefix="--flag-true", default=True),
            ToolInput("flag_false", Boolean, position=5, prefix="--flag-false", default=False),
            
            ToolInput("opt_basic", String, position=6, prefix="--opt-basic"),
            ToolInput("opt_default", Int, position=7, default=5, prefix="--opt-default"),
            ToolInput("opt_optional", String(optional=True), position=8, prefix="--opt-optional"),
        ]

    def outputs(self):
        return [ToolOutput("out", Stdout)]

    def container(self) -> str:
        return "ubuntu:latest"

    def version(self) -> str:
        return "TEST"


class SecondariesTestTool(CommandTool):
    def tool(self) -> str:
        return "SecondariesTestTool"

    def base_command(self) -> Optional[str | list[str]]:
        return ['echo']

    def inputs(self) -> list[ToolInput]:
        return [ToolInput("inp", BamBai, position=4)]

    def outputs(self):
        return [
            ToolOutput(
                "out", 
                BamBai,
                selector=WildcardSelector("*.bam"),
                secondaries_present_as={".bai": ".bai"},
            )
        ]

    def container(self) -> str:
        return "ubuntu:latest"

    def version(self) -> str:
        return "TEST"


class SecondariesReplacedTestTool(CommandTool):
    def tool(self) -> str:
        return "SecondariesReplacedTestTool"

    def base_command(self) -> Optional[str | list[str]]:
        return []

    def inputs(self) -> list[ToolInput]:
        return [ToolInput("inp", BamBai, position=4)]

    def arguments(self) -> list[ToolArgument]:
        return [
            ToolArgument("echo hello > out.bam", position=1, shell_quote=False),
            ToolArgument("&& echo there > out.bam.bai", position=2, shell_quote=False),
            ToolArgument("&& echo", position=3, shell_quote=False),
        ]

    def outputs(self):
        return [
            ToolOutput(
                "out", 
                BamBai,
                selector=WildcardSelector("*.bam"),
                secondaries_present_as={".bai": "^.bai"},
            )
        ]

    def container(self) -> str:
        return "ubuntu:latest"

    def version(self) -> str:
        return "TEST"



