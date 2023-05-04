
from typing import Optional, Any

from ..gxtool.tool import XMLToolDefinition
from ..gxtool.text import simplify_xmltool_command

from .cmdstr.CommandString import CommandString
from .cmdstr.generate import gen_command_string
from .annotation import ArgumentCommandAnnotator
from .annotation import CmdstrCommandAnnotator
from .Command import Command

"""
The most complex part of tool ingestion. 

This module is responsible for creating a Command object from a galaxy tool XML definition.

A Command object represents the structure of the command line string for a tool.
I.E all its cmdline input components (options / args - their position and whether they have a prefix etc)

We start with an empty Command() object, then add components as we find them. 

To do this, multiple passes are made. 
    - Multiple interpretations of the galaxy <command> section are created
    - Guesses about options, args etc are made per interpretation
    - Our knowledge of the command as a whole is updated each round using this new information. 

Passes for tool ingestion:
    1. Untemplated (raw) command 
    2. Templated command using test input data (for each test) 

Passes for workflow ingestion:
    1. Templated command using step inputs dict (for each step or just single???)

"""



class CommandFactory:
    def __init__(self, xmltool: XMLToolDefinition, galaxy_step: Optional[Any]=None):
        self.xmltool = xmltool
        self.galaxy_step = galaxy_step
        self.command = Command()

    def create(self) -> Command:
        cmdstrs = self.generate_cmdstrs()
        for cmdstr in cmdstrs:
            self.update_command_via_arguments(cmdstr)
            self.update_command_via_cmdstrs(cmdstr)
        return self.command

    def generate_cmdstrs(self) -> list[str]:
        cmdstrs: list[str] = []
        
        # workflow ingest mode
        if self.galaxy_step:
            inputs_dict = self.galaxy_step['tool_state']
            step_inputs_cmdstr = self.generate_cmdstr(inputs_dict=inputs_dict)
            cmdstrs.append(step_inputs_cmdstr)

        # tool ingest mode
        else:
            general_cmdstr = self.generate_cmdstr()
            cmdstrs.append(general_cmdstr)
            
            for test in self.xmltool.tests.list():
                inputs_dict = test.inputs_dict
                test_cmdstr = self.generate_cmdstr(inputs_dict=inputs_dict)
                cmdstrs.append(test_cmdstr)

        return cmdstrs
    
    def generate_cmdstr(self, inputs_dict: Optional[dict[str, Any]]=None) -> str:
        cmdstr = self.xmltool.raw_command
        cmdstr = simplify_xmltool_command(cmdstr, inputs_dict=inputs_dict)
        return cmdstr

    # def gen_cmdstr_from_xml(self, ) -> CommandString:
    #     command_string = gen_command_string(source='xml', the_string=text, xmltool=self.xmltool)
    #     return command_string

    def update_command_via_arguments(self, cmdstr: str) -> None:
        # TODO
        """uses galaxy params with an 'argument' attribute to update command"""
        annotator = ArgumentCommandAnnotator(self.command, self.xmltool)
        annotator.annotate()
    
    def update_command_via_cmdstrs(self, cmdstr: str) -> None:
        # TODO
        """
        uses valid command line strings from tests, and the tool XML <command> section
        to further identify the structure and options of the underling software tool
        """
        # create command strings (from evaluated tests, simplified xml <command>)
        cmdstrs = self.gen_cmdstrs()
        annotator = CmdstrCommandAnnotator(self.command, self.xmltool, cmdstrs)
        annotator.annotate()

    def gen_cmdstrs(self) -> list[CommandString]:
        # note ordering: xml then test
        return [self.xmlcmdstr]




