

import re 
from copy import deepcopy
from typing import Any, Optional
from abc import ABC, abstractmethod
from Cheetah.Template import Template
from galaxy.util import unicodify

from .. import utils

from .blocks import get_blocks 
from .blocks import get_next_block 
from .blocks import CheetahBlock
from .blocks import BlockType


# from .. import utils


# def sectional_evaluate(text: str, inputs: dict[str, Any]) -> str:
#     raw_lines = utils.split_lines_blanklines(text)
#     evaluator = PartialCheetahEvaluator(raw_lines, inputs)
#     eval_lines = evaluator.evaluate()
#     return utils.join_lines(eval_lines)


class CheetahNoCrashDetector:
    def __init__(self, all_lines: list[str], input_dict: dict[str, Any]):
        self.cmdlines = deepcopy(all_lines)
        self.input_dict = input_dict
        self.ptr: int = 0

    def detect(self) -> list[str]:
        return self.evaluation_worker()
        # try:
        #     return self.evaluation_worker()
        # except Exception as e:
        #     return self.all_lines

    def evaluation_worker(self) -> list[str]:
        while self.ptr < len(self.cmdlines):
            block = get_next_block(self.ptr, self.cmdlines)
            if self.should_evaluate(block):
                evaluated_lines = self.do_eval(block)
            else:
                evaluated_lines = None
            self.update_evaluation_status(block, evaluated_lines)
            self.update_cmdlines(block)
            self.update_ptr(block)
        return self.cmdlines
    
    def should_evaluate(self, block: CheetahBlock) -> bool:
        permitted_blocks = [
            BlockType.INLINE, 
            BlockType.INLINE_ALIAS, 
            BlockType.INLINE_CH, 
            BlockType.CONDITIONAL,
            BlockType.LOOP,
        ]
        if block.type not in permitted_blocks:
            return False
        if block.lines == ['']:
            return False
        # if block.type in [
        #     BlockType.INLINE, 
        #     BlockType.INLINE_ALIAS, 
        #     BlockType.INLINE_CH, 
        # ]:
        #     # weak checks. 
        #     if block.lines[0].startswith('ln '):
        #         return False
        #     if block.lines[0].startswith('mkdir '):
        #         return False
        #     if block.lines[0].startswith('cp '):
        #         return False
        #     if block.lines[0].startswith('mv '):
        #         return False
        return True
    
    def do_eval(self, block: CheetahBlock) -> Optional[list[str]]:
        prior_lines = self.cmdlines[:self.ptr]
        if block.type in [BlockType.INLINE, BlockType.INLINE_ALIAS, BlockType.INLINE_CH]:
            strategy = InlineEvaluationStrategy(block, prior_lines, self.input_dict)
        elif block.type == BlockType.CONDITIONAL:
            strategy = ConditionalEvaluationStrategy(block, prior_lines, self.input_dict)
        elif block.type == BlockType.LOOP:
            strategy = LoopEvaluationStrategy(block, prior_lines, self.input_dict)
        else:
            raise RuntimeError()
        return strategy.eval()

    def update_evaluation_status(self, block: CheetahBlock, evaluated_lines: Optional[list[str]]) -> None:
        if evaluated_lines is not None:
            block.evaluated = True
        else:
            block.evaluated = False
    
    def update_cmdlines(self, block: CheetahBlock) -> None:
        if block.evaluated:
            if block.type == BlockType.LOOP:
                pass
            
            elif block.type == BlockType.CONDITIONAL:
                old_lines_top = self.cmdlines[:block.start]
                old_lines_bottom = self.cmdlines[block.stop + 1:]
                self.cmdlines = old_lines_top + block.lines + old_lines_bottom
            
            elif block.type in [BlockType.INLINE, BlockType.INLINE_ALIAS, BlockType.INLINE_CH]:
                pass
            
            else:
                raise RuntimeError
        else:
            old_lines_top = self.cmdlines[:block.start]
            old_lines_bottom = self.cmdlines[block.stop + 1:]
            self.cmdlines = old_lines_top + [''] * block.height + old_lines_bottom
            print()
        
    def update_ptr(self, block: CheetahBlock) -> None:
        if block.type == BlockType.LOOP:
            self.ptr += block.height
        
        elif block.type == BlockType.CONDITIONAL:
            self.ptr += 1 if block.evaluated else block.height

        elif block.type in [BlockType.INLINE, BlockType.INLINE_ALIAS, BlockType.INLINE_CH]:
            self.ptr += 1
        
        else:
            raise RuntimeError


class EvaluationStrategy(ABC):
    def __init__(self, block: CheetahBlock, prior_lines: list[str], input_dict: dict[str, Any]):
        self.block = block
        self.prior_lines = prior_lines
        self.input_dict = input_dict
    
    def eval(self) -> Optional[list[str]]:
        template = self.prepare_template()
        outcome = self.evaluate_template(template)
        if outcome is not None: 
            return self.handle_outcome(outcome)
        return None

    @abstractmethod
    def prepare_template(self) -> list[str]:
        """prepares the template text for evaluation"""
        ...
    
    def evaluate_template(self, source_lines: list[str]) -> Optional[list[str]]:
        """performs cheetah evaluation of template"""
        try:
            text = utils.join_lines(source_lines)
            t = Template(text, searchList=[self.input_dict]) # type: ignore
            evaluation = str(unicodify(t))
            # if evaluation != '':
            #     if not evaluation.startswith('"') and not evaluation.startswith("'"):
            #         evaluation = eval(evaluation)  # python string evaluation
            #         evaluation = str(evaluation)
            evaluation_lines = evaluation.split('\n')
            return evaluation_lines
        except Exception as e:
            return None

    @abstractmethod
    def handle_outcome(self, outcome: list[str]) -> list[str]:
        """handles the evaluated text (if successful) and applies any transformations needed"""
        ...


class InlineEvaluationStrategy(EvaluationStrategy):

    def prepare_template(self) -> list[str]:
        assert(len(self.block.lines) == 1)
        return self.prior_lines + self.block.lines

    def handle_outcome(self, outcome: list[str]) -> list[str]:
        return outcome


class LoopEvaluationStrategy(EvaluationStrategy):

    def prepare_template(self) -> list[str]:
        return self.prior_lines + self.block.lines

    def handle_outcome(self, outcome: list[str]) -> list[str]:
        return outcome


class ConditionalEvaluationStrategy(EvaluationStrategy):

    def prepare_template(self) -> list[str]:
        self.mask_children()
        return self.prior_lines + self.block.lines

    def handle_outcome(self, outcome: list[str]) -> list[str]:
        output = self.create_blank_output()
        output = self.restore_surviving_children(outcome, output)
        self.block.lines = output
        return output

    def mask_children(self) -> None:
        """prepares text ready for evaluation. swaps child blocks with identifiers"""
        self.masked_blocks: dict[str, CheetahBlock] = {}
        for child in self.get_child_blocks():
            self.masked_blocks[child.uuid] = child  # register identifier/block
            self.substitute_identifier(child)

    def get_child_blocks(self) -> list[CheetahBlock]:
        """returns next level of cheetah blocks within this block"""
        return get_blocks(
            ptr=0,
            lines=self.block.lines, 
            indent_level=1
        )

    def substitute_identifier(self, block: CheetahBlock) -> None:
        """swaps block block with identifier in template"""
        old_lines_top = self.block.lines[:block.start]
        old_lines_bottom = self.block.lines[block.stop+1:]
        self.block.lines = old_lines_top + [block.uuid] * block.height + old_lines_bottom

    def create_blank_output(self) -> list[str]:
        return [''] * len(self.block.lines)

    def restore_surviving_children(self, evaluation: list[str], output: list[str]) -> list[str]:
        surviving_children = self.get_surviving_children(evaluation)
        for identifier, block in surviving_children.items():
            line_num = self.get_identifier_line_num(self.block.lines, identifier)
            if line_num is not None:
                block = self.masked_blocks[identifier]
                output = self.substitute_block(output, block)
        return output

    def get_surviving_children(self, evaluation: list[str]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for identifier, block in self.masked_blocks.items():
            position = self.get_identifier_line_num(evaluation, identifier)
            if position is not None:
                out[identifier] = block
        return out

    def get_identifier_line_num(self, lines: list[str], identifier: str) -> Optional[int]:
        for i, line in enumerate(lines):
            if line == identifier:
                return i
        return None

    def substitute_block(self, output: list[str], block: CheetahBlock) -> list[str]:
        """swaps block block with identifier in template"""
        old_lines_top = output[:block.start]
        old_lines_bottom = output[block.stop+1:]
        return old_lines_top + block.lines + old_lines_bottom

