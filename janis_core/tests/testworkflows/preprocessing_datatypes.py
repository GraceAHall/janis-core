

from typing import Optional

from janis_core import (
    Workflow, 
    CommandTool, 
    ToolInput, 
    ToolOutput, 
)

from janis_core.types import GenericFileWithSecondaries
from janis_core.redefinitions.types import FastaWithIndexes
from janis_core.redefinitions.types import FastaDict
from janis_core.redefinitions.types import Fasta
from janis_core.redefinitions.types import BamBai
from janis_core.redefinitions.types import Bam


### WORKFLOWS ###

class NoSecondaryMismatchTW(Workflow):
    """no mismatches"""
    
    def tool(self):
        return "NoSecondaryMismatchTW"
    
    def friendly_name(self):
        return "TEST: NoSecondaryMismatchTW"

    def id(self) -> str:
        return self.__class__.__name__

    def constructor(self):
        self.input('inGeneric1', GenericFileWithSecondaries(secondaries=['.crai']))
        self.input('inGeneric2', GenericFileWithSecondaries(secondaries=[]))
        self.input('inFastaWithIndexes', FastaWithIndexes())
        self.input('inFastaDict', FastaDict())
        self.input('inFasta', Fasta())
        self.input('inBamBai', BamBai())
        self.input('inBam', Bam())

        self.step(
            "stp1", 
            SecondaryMismatchTT1(
                inGeneric1=self.inGeneric1,
                inGeneric2=self.inGeneric2,
                inFastaWithIndexes=self.inFastaWithIndexes,
                inFastaDict=self.inFastaDict,
                inFasta=self.inFasta,
                inBamBai=self.inBamBai,
                inBam=self.inBam,
            )
        )
        
        self.output("outGeneric1", GenericFileWithSecondaries(secondaries=['.crai']), source=self.stp1.outGeneric1)
        self.output("outGeneric2", GenericFileWithSecondaries(secondaries=[]), source=self.stp1.outGeneric2)
        self.output("outFastaWithIndexes", FastaWithIndexes(), source=self.stp1.outFastaWithIndexes)
        self.output("outFastaDict", FastaDict(), source=self.stp1.outFastaDict)
        self.output("outFasta", Fasta(), source=self.stp1.outFasta)
        self.output("outBamBai", BamBai(), source=self.stp1.outBamBai)
        self.output("outBam", Bam(), source=self.stp1.outBam)


class SingleSecondaryMismatchTW1(Workflow):
    """single generic <-> generic mismatch"""
    
    def tool(self):
        return "SingleSecondaryMismatchTW"
    
    def friendly_name(self):
        return "TEST: SingleSecondaryMismatchTW"

    def id(self) -> str:
        return self.__class__.__name__

    def constructor(self):
        self.input('inGeneric1', GenericFileWithSecondaries(secondaries=['.crai']))
        self.input('inGeneric2', GenericFileWithSecondaries(secondaries=[]))
        self.input('inFastaWithIndexes', FastaWithIndexes())
        self.input('inFastaDict', FastaDict())
        self.input('inFasta', Fasta())
        self.input('inBamBai', BamBai())
        self.input('inBam', Bam())

        self.step(
            "stp1", 
            SecondaryMismatchTT1(
                inGeneric1=self.inGeneric2,
                inGeneric2=self.inGeneric2,
                inFastaWithIndexes=self.inFastaWithIndexes,
                inFastaDict=self.inFastaDict,
                inFasta=self.inFasta,
                inBamBai=self.inBamBai,
                inBam=self.inBam,
            )
        )
        
        self.output("outGeneric1", GenericFileWithSecondaries(secondaries=['.crai']), source=self.stp1.outGeneric1)
        self.output("outGeneric2", GenericFileWithSecondaries(secondaries=[]), source=self.stp1.outGeneric2)
        self.output("outFastaWithIndexes", FastaWithIndexes(), source=self.stp1.outFastaWithIndexes)
        self.output("outFastaDict", FastaDict(), source=self.stp1.outFastaDict)
        self.output("outFasta", Fasta(), source=self.stp1.outFasta)
        self.output("outBamBai", BamBai(), source=self.stp1.outBamBai)
        self.output("outBam", Bam(), source=self.stp1.outBam)


class SingleSecondaryMismatchTW2(Workflow):
    """single generic <-> defined mismatch"""
    
    def tool(self):
        return "SingleSecondaryMismatchTW2"
    
    def friendly_name(self):
        return "TEST: SingleSecondaryMismatchTW2"

    def id(self) -> str:
        return self.__class__.__name__

    def constructor(self):
        self.input('inGeneric1', GenericFileWithSecondaries(secondaries=['.crai']))
        self.input('inGeneric2', GenericFileWithSecondaries(secondaries=[]))
        self.input('inFastaWithIndexes', FastaWithIndexes())
        self.input('inFastaDict', FastaDict())
        self.input('inFasta', Fasta())
        self.input('inBamBai', BamBai())
        self.input('inBam', Bam())

        self.step(
            "stp1", 
            SecondaryMismatchTT1(
                inGeneric1=self.inGeneric1,
                inGeneric2=self.inGeneric2,
                inFastaWithIndexes=self.inFastaWithIndexes,
                inFastaDict=self.inFastaDict,
                inFasta=self.inFasta,
                inBamBai=self.inGeneric2,
                inBam=self.inBam,
            )
        )
        
        self.output("outGeneric1", GenericFileWithSecondaries(secondaries=['.crai']), source=self.stp1.outGeneric1)
        self.output("outGeneric2", GenericFileWithSecondaries(secondaries=[]), source=self.stp1.outGeneric2)
        self.output("outFastaWithIndexes", FastaWithIndexes(), source=self.stp1.outFastaWithIndexes)
        self.output("outFastaDict", FastaDict(), source=self.stp1.outFastaDict)
        self.output("outFasta", Fasta(), source=self.stp1.outFasta)
        self.output("outBamBai", BamBai(), source=self.stp1.outBamBai)
        self.output("outBam", Bam(), source=self.stp1.outBam)


class SingleSecondaryMismatchTW3(Workflow):
    """single defined <-> defined mismatch"""
    
    def tool(self):
        return "SingleSecondaryMismatchTW3"
    
    def friendly_name(self):
        return "TEST: SingleSecondaryMismatchTW3"

    def id(self) -> str:
        return self.__class__.__name__

    def constructor(self):
        self.input('inGeneric1', GenericFileWithSecondaries(secondaries=['.crai']))
        self.input('inGeneric2', GenericFileWithSecondaries(secondaries=[]))
        self.input('inFastaWithIndexes', FastaWithIndexes())
        self.input('inFastaDict', FastaDict())
        self.input('inFasta', Fasta())
        self.input('inBamBai', BamBai())
        self.input('inBam', Bam())

        self.step(
            "stp1", 
            SecondaryMismatchTT1(
                inGeneric1=self.inGeneric1,
                inGeneric2=self.inGeneric2,
                inFastaWithIndexes=self.inFastaDict,
                inFastaDict=self.inFastaDict,
                inFasta=self.inFasta,
                inBamBai=self.inBamBai,
                inBam=self.inBam,
            )
        )
        
        self.output("outGeneric1", GenericFileWithSecondaries(secondaries=['.crai']), source=self.stp1.outGeneric1)
        self.output("outGeneric2", GenericFileWithSecondaries(secondaries=[]), source=self.stp1.outGeneric2)
        self.output("outFastaWithIndexes", FastaWithIndexes(), source=self.stp1.outFastaWithIndexes)
        self.output("outFastaDict", FastaDict(), source=self.stp1.outFastaDict)
        self.output("outFasta", Fasta(), source=self.stp1.outFasta)
        self.output("outBamBai", BamBai(), source=self.stp1.outBamBai)
        self.output("outBam", Bam(), source=self.stp1.outBam)



class MultipleSecondaryMismatchTW(Workflow):
    """multiple random mismatches"""
    
    def tool(self):
        return "MultipleSecondaryMismatchTW"
    
    def friendly_name(self):
        return "TEST: MultipleSecondaryMismatchTW"

    def id(self) -> str:
        return self.__class__.__name__

    def constructor(self):
        self.input('inGeneric1', GenericFileWithSecondaries(secondaries=['.crai']))
        self.input('inGeneric2', GenericFileWithSecondaries(secondaries=[]))
        self.input('inFastaWithIndexes', FastaWithIndexes())
        self.input('inFastaDict', FastaDict())
        self.input('inFasta', Fasta())
        self.input('inBamBai', BamBai())
        self.input('inBam', Bam())

        self.step(
            "stp1", 
            SecondaryMismatchTT1(
                inGeneric1=self.inGeneric2,
                inGeneric2=self.inGeneric2,
                inFastaWithIndexes=self.inFastaDict,
                inFastaDict=self.inFastaDict,
                inFasta=self.inFasta,
                inBamBai=self.inBamBai,
                inBam=self.inBam,
            )
        )
        
        self.output("outGeneric1", GenericFileWithSecondaries(secondaries=['.crai']), source=self.stp1.outGeneric1)
        self.output("outGeneric2", GenericFileWithSecondaries(secondaries=[]), source=self.stp1.outGeneric2)
        self.output("outFastaWithIndexes", FastaWithIndexes(), source=self.stp1.outFastaWithIndexes)
        self.output("outFastaDict", FastaDict(), source=self.stp1.outFastaDict)
        self.output("outFasta", Fasta(), source=self.stp1.outFasta)
        self.output("outBamBai", BamBai(), source=self.stp1.outBamBai)
        self.output("outBam", Bam(), source=self.stp1.outBam)



### TOOLS ###
    
class SecondaryMismatchTT1(CommandTool):
    
    def inputs(self) -> list[ToolInput]:
        return [
            ToolInput('inGeneric1', GenericFileWithSecondaries(optional=True, secondaries=['.crai'])),
            ToolInput('inGeneric2', GenericFileWithSecondaries(optional=True, secondaries=[])),
            ToolInput('inFastaWithIndexes', FastaWithIndexes(optional=True)),
            ToolInput('inFastaDict', FastaDict(optional=True)),
            ToolInput('inFasta', Fasta(optional=True)),
            ToolInput('inBamBai', BamBai(optional=True)),
            ToolInput('inBam', Bam(optional=True)),
        ]

    def outputs(self):
        return [
            ToolOutput('outGeneric1', GenericFileWithSecondaries(secondaries=['.crai']), glob='outGeneric1'),
            ToolOutput('outGeneric2', GenericFileWithSecondaries(secondaries=[]), glob='outGeneric2'),
            ToolOutput('outFastaWithIndexes', FastaWithIndexes(), glob='outFastaWithIndexes'),
            ToolOutput('outFastaDict', FastaDict(), glob='outFastaDict'),
            ToolOutput('outFasta', Fasta(), glob='outFasta'),
            ToolOutput('outBamBai', BamBai(), glob='outBamBai'),
            ToolOutput('outBam', Bam(), glob='outBam'),
        ]
    
    def base_command(self) -> Optional[str | list[str]]:
        return "echo"
    
    def id(self) -> str:
        return self.__class__.__name__
    
    def tool(self) -> str:
        return self.__class__.__name__
    
    def container(self) -> str:
        return "ubuntu:latest"

    def version(self) -> str:
        return "TEST"


    

