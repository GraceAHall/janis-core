

from __future__ import annotations
import re 

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional
from uuid import uuid4
from enum import Enum, auto

from janis_core.ingestion.galaxy.gx.command.cmdstr import constructs
from janis_core.ingestion.galaxy import expressions
from janis_core.ingestion.galaxy.expressions.patterns import CHEETAH_EDGE_CASE_INPUT
from janis_core.ingestion.galaxy.expressions.patterns import CHEETAH_SET


def get_blocks(ptr: int, lines: list[str], indent_level: int) -> list[CheetahBlock]:
    block_lines = LineFactory(lines).get_lines()
    factory = BlockFactory(ptr, block_lines, indent_level)
    return factory.get_blocks()

def get_next_block(ptr: int, lines: list[str]) -> CheetahBlock:
    blocks = get_blocks(ptr=ptr, lines=lines[ptr:], indent_level=0)
    return blocks[0]


@dataclass
class BlockLine:
    line_num: int
    indent: int
    text: str

class LineFactory:
    """creates BlockLines from normal text lines"""

    def __init__(self, lines: list[str]):
        self.text_lines = lines
        self.block_lines: list[BlockLine] = []
        self.construct_tracker: constructs.ConstructTracker = constructs.ConstructTracker()

    def get_lines(self) -> list[BlockLine]:
        if len(self.text_lines) == 0:
            return []
        else:
            for i, line in enumerate(self.text_lines):
                self.add_block_line(i, line)
            return self.block_lines

    def add_block_line(self, i: int, line: str) -> None:
        indent = self.construct_tracker.stack.depth
        self.construct_tracker.update(line) # LEAVE THIS HERE
        block_line = BlockLine(
            line_num=i,
            indent=indent,
            text=line
        )
        self.block_lines.append(block_line)
    
    


IGNORE_CONSTRUCTS = constructs.CH_WITHIN_CONDITIONAL | constructs.CH_CLOSE_CONDITIONAL | constructs.CH_CLOSE_LOOP | constructs.CH_CLOSE_FUNC

class BlockFactory:
    """
    gets all cheetah blocks occurring in self.lines on a particular 
    indent level
    """
    def __init__(self, offset: int, block_lines: list[BlockLine], indent_level: int):
        self.offset = offset
        self.block_lines = block_lines
        self.target_indent = indent_level
        self.active_lines: list[BlockLine] = []
        self.blocks: list[CheetahBlock] = []

    def get_blocks(self) -> list[CheetahBlock]:
        for line in self.block_lines:
            if self.start_block(line): # new block begins
                self.add_block() # add previous block
                self.active_lines = [] # reset active lines
            if self.within_block(line):
                self.active_lines.append(line)
        self.add_block()
        self.filter_blocks()
        return self.blocks

    def start_block(self, line: BlockLine) -> bool:
        if line.indent == self.target_indent:
            return True
        return False
    
    def within_block(self, line: BlockLine) -> bool:
        if line.indent >= self.target_indent:
            return True
        return False

    def add_block(self) -> None:
        if self.active_lines:
            block = CheetahBlock(
                type=self.select_block_type(),
                start=self.active_lines[0].line_num + self.offset,
                stop=self.active_lines[-1].line_num + self.offset,
                lines=[ln.text for ln in self.active_lines]
            )
            self.blocks.append(block)
    
    def select_block_type(self) -> BlockType:
        line = self.active_lines[0].text
        types = [
            (constructs.CH_OPEN_CONDITIONAL, BlockType.CONDITIONAL),
            (constructs.CH_OPEN_LOOP, BlockType.LOOP),
            (constructs.CH_OPEN_FUNC, BlockType.FUNCTION),
            (constructs.CH_ENV, BlockType.INLINE_CH),
            (constructs.LINUX_ALIAS, BlockType.INLINE_ALIAS),
        ]
        for construct, block_type in types:
            if any ([line.startswith(text) for text in construct]):
                return block_type
        return BlockType.INLINE

    def filter_blocks(self):
        filtered: list[CheetahBlock] = []
        for block in self.blocks:
            if len(block.lines) == 1:
                line = block.lines[0]
                if not any ([line.startswith(text) for text in IGNORE_CONSTRUCTS]):
                    filtered.append(block)
            else:
                filtered.append(block)
        self.blocks = filtered


class BlockType(Enum):
    MAIN            = auto()
    INLINE          = auto()
    INLINE_CH       = auto()
    INLINE_ALIAS    = auto()
    CONDITIONAL     = auto()
    FUNCTION        = auto()
    LOOP            = auto()


class CheetahBlock:
    """
    The smallest unit of evaluatable cheetah logic
    examples: single line statement, conditional block, loop block
    """
    def __init__(self, type: BlockType, start: int, stop: int, lines: list[str]):
        self.type = type
        self.start = start
        self.stop = stop
        self.lines = lines
        self.uuid: str = str(uuid4())
        self.evaluated: bool = False
    
    @property 
    def height(self) -> int:
        return self.stop - self.start + 1
    
    # def evaluate(self, input_dict: dict[str, Any]) -> None:
    #     # if self.is_import():
    #     #     self.evaluated = True
    #     #     self.lines = ['']
        
    #     # elif self.is_set():
    #     #     self.update_input_dict(input_dict)
    #     #     self.evaluated = True
    #     #     self.lines = ['']

    #     if self.should_evaluate(input_dict):
    #         evaluation = self.do_eval(self.lines, input_dict)
    #         if evaluation is not None:
    #             assert(len(self.lines) == len(evaluation))
    #             self.evaluated = True
    #             self.lines = evaluation

    # def is_import(self) -> bool:
    #     if self.type == BlockType.INLINE_CH and self.lines[0].startswith('#import '):
    #         return True
    #     return False

    # def is_set(self) -> bool:
    #     if self.type == BlockType.INLINE_CH and self.lines[0].startswith('#set '):
    #         return True
    #     return False

    # def update_input_dict(self, input_dict: dict[str, Any]) -> None:
    #     matches = expressions.get_matches(self.lines[0], CHEETAH_SET)
    #     match = matches[0]
    #     key = match.group(1)
    #     value = match.group(2)
    #     value = self.do_eval([value], input_dict)
    #     if value is not None:
    #         input_dict[key] = value[0]
    #     else:
    #         print()
        
    # def should_evaluate(self, input_dict: dict[str, Any]) -> bool:
    #     """dictates whether this block should be evaluated or left as original text"""
    #     permitted_blocks = [
    #         BlockType.INLINE, 
    #         BlockType.INLINE_ALIAS, 
    #         BlockType.INLINE_CH, 
    #         BlockType.CONDITIONAL
    #     ]
    #     if self.lines == ['']:
    #         return False
    #     elif self.type not in permitted_blocks:
    #         return False
    #     elif self.edge_case_input(input_dict):
    #         return False
    #     return True

    # def edge_case_input(self, input_dict: dict[str, Any]) -> bool:
    #     for line in self.lines:
    #         matches = expressions.get_matches(line, CHEETAH_EDGE_CASE_INPUT)
    #         if matches:
    #             if 'input' not in input_dict:
    #                 return True
    #     return False
