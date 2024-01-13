

from typing import Optional

from janis_core import (
    CommandTool,
    ToolInput,
    ToolArgument,
    ToolOutput,
    Workflow,
    WildcardSelector
)
from janis_core.types import (
    Filename,
    File,
    String,
    Int,
    Float,
    Array,
    Boolean,
)
from janis_core.redefinitions.types import Bam, BamBai


class IllegalSymbolsTestWF(Workflow):
    
    def friendly_name(self):
        return "TEST: IllegalSymbolsTestWF"

    def id(self) -> str:
        return self.__class__.__name__

    def constructor(self):
        self.input("theFile", File())
        self.input("theFileOpt", File(optional=True))
        self.input("theFileArr", Array(File()))
        self.input("theFilename", Filename())
        self.input("theBam", Bam())
        self.input("theBamBai", BamBai())
        self.input("theBamBaiArr", Array(BamBai()))
        self.input("theStr", String())
        self.input("theStrOpt", String(optional=True))
        self.input("theInt", Int())
        self.input("theIntOpt", Int(optional=True))
        self.input("theFloat", Float())
        self.input("theFloatOpt", Float(optional=True))
        self.input("theBool", Boolean())

        self.step(
            "cwl", 
            CwlIllegalTestTool(
                inFilename=self.theFile,
                inp=self.theFile,
                input=self.theFile,
                out=self.theFile,
                output=self.theFile,
            )
        )
        self.step(
            "nextflow", 
            NextflowIllegalTestTool(
                inFile=self.theFile,
                inp=self.theFile,
                input=self.theFilename,
                container=self.theStr,
                path=self.theStr,
                val=self.theInt,
            )
        )
        self.step(
            "wdl", 
            WdlIllegalTestTool(
                bam=self.theBam,
                inFile=self.nextflow.outFile,
                inp=self.theFile,
                input=self.theFilename,
                command=self.theStr,
                container=self.theStr,
                Int=self.theInt,
                defined=self.theBool,
            )
        )
        self.step(
            "duplicates_step", 
            DuplicateSymbolsTestTool(
                theFile=self.cwl.outFile,
                theBam=self.theBam,
            )
        )

        self.output('theFile', source=self.duplicates_step.theFile)


# TOOLS
class CwlIllegalTestTool(CommandTool):
    
    def container(self) -> str:
        return "ubuntu:latest"

    def version(self) -> str:
        return "TEST"
        
    def base_command(self) -> Optional[str | list[str]]:
        return ['echo']

    def friendly_name(self):
        return "TEST: CWLIllegalTestTool"

    def tool(self):
        return "CWLIllegalTestTool"
    
    def inputs(self):
        return [
            # all ok
            ToolInput("inFilename", File(), position=1), 
            ToolInput("inp", File(), position=2),    
            ToolInput("input", File(), position=2), 
            ToolInput("out", File(), position=4),
            ToolInput("output", File(), position=4),
        ]
    
    def outputs(self):
        return [
            # all ok
            ToolOutput("outFile", File(), selector=WildcardSelector('results.txt')),    
            ToolOutput("out", File(), selector=WildcardSelector('results.txt')),        
            ToolOutput("output", File(), selector=WildcardSelector('results.txt')),
        ]


class NextflowIllegalTestTool(CommandTool):
    
    def container(self) -> str:
        return "ubuntu:latest"

    def version(self) -> str:
        return "TEST"
        
    def base_command(self) -> Optional[str | list[str]]:
        return ['echo']

    def friendly_name(self):
        return "TEST: NextflowIllegalTestTool"

    def tool(self):
        return "NextflowIllegalTestTool"
    
    def inputs(self):
        return [
            ToolInput("inFile", File(), position=1), # ok
            ToolInput("inp", File(), position=2),    # ok
            ToolInput("input", Filename(), position=2), 
            ToolInput("container", String(), position=4),
            ToolInput("path", String(), position=5),
            ToolInput("val", Int(), position=6),
        ]
    
    def outputs(self):
        return [
            ToolOutput("outFile", File(), selector=WildcardSelector('results.txt')),    # ok 
            ToolOutput("out", File(), selector=WildcardSelector('results.txt')),        # ok 
            ToolOutput("output", File(), selector=WildcardSelector('results.txt')),
        ]


class WdlIllegalTestTool(CommandTool):
    
    def container(self) -> str:
        return "ubuntu:latest"

    def version(self) -> str:
        return "TEST"
        
    def base_command(self) -> Optional[str | list[str]]:
        return ['echo']

    def friendly_name(self):
        return "TEST: NextflowIllegalTestTool"

    def tool(self):
        return "NextflowIllegalTestTool"
    
    def inputs(self):
        return [
            ToolInput("bam", Filename(), position=1),   # convention: bam -> bamPath
            ToolInput("inFile", File(), position=1),    # ok
            ToolInput("inp", File(), position=2),       # ok
            ToolInput("input", File(), position=2),     
            ToolInput("command", String(), position=3),     
            ToolInput("container", String(), position=4),
            ToolInput("Int", Int(optional=True), position=6),
            ToolInput("defined", Boolean(), position=7),
        ]
    
    def outputs(self):
        return [
            ToolOutput("outFile", File(), selector=WildcardSelector('results.txt')),    # ok 
            ToolOutput("out", File(), selector=WildcardSelector('results.txt')),        # ok 
            ToolOutput("output", File(), selector=WildcardSelector('results.txt')),
        ]


class DuplicateSymbolsTestTool(CommandTool):
    
    def container(self) -> str:
        return "ubuntu:latest"

    def version(self) -> str:
        return "TEST"
        
    def base_command(self) -> Optional[str | list[str]]:
        return ['echo']

    def friendly_name(self):
        return "TEST: DuplicateSymbolsTestTool"

    def tool(self):
        return "DuplicateSymbolsTestTool"
    
    def inputs(self):
        return [
            ToolInput("theFile", File(), position=1),
            ToolInput("theBam", Bam(), position=2),
        ]
    
    def arguments(self):
        return [
            ToolArgument('-b', position=1)
        ]

    def outputs(self):
        return [
            ToolOutput("theFile", File(), selector=WildcardSelector('results.txt')),
        ]

