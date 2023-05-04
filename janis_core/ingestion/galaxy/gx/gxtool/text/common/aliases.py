
from __future__ import annotations
from typing import Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum, auto

import regex as re
from copy import deepcopy
from .. import utils

from janis_core.ingestion.galaxy import expressions
from janis_core.ingestion.galaxy.expressions.patterns import (
    CHEETAH_SET,
    LINUX_LN,
    LINUX_MV,
    LINUX_CP
)




class AssociationType(Enum):
    STATIC_VALUE = auto()
    LOCAL_VAR    = auto()
    INPUT_VAR    = auto() 

@dataclass
class Association:
    atype: AssociationType
    source: str
    dest: str


def extract_associations(cmdstr: str, inputs_dict: dict[str, Any]) -> AssociationRegister:
    flattened_dict = deepcopy(inputs_dict)
    flattened_dict = flatten(inputs_dict)
    extractor = AssociationExtractor(flattened_dict)
    extractor.extract(cmdstr)
    return extractor.register

def resolve_associations(cmdstr: str, register: AssociationRegister) -> str:
    resolver = AssociationResolver(register)
    return resolver.resolve(cmdstr)

def get_vars_in_text(text: str) -> list[re.Match[str]]:
    MATCHER = r'(?<=\$\{|\$)(([\w\d]+)(\.[\w\d]+)*)'
    return expressions.get_matches(text, MATCHER)

def is_association_line(line: str) -> bool: 
    source, dest = extract_association(line)
    if source and dest:
        return True
    return False

def extract_association(line: str) -> Tuple[Optional[str], Optional[str]]:
    source, dest = None, None
    for func in [
        get_set,
        get_symlink, 
        #get_move, 
        #get_copy, 
    ]:
        source, dest = func(line)
        if source and dest:
            break
    return source, dest

def get_set(line: str) -> Tuple[Optional[str], Optional[str]]:
    matches = expressions.get_matches(line, CHEETAH_SET)
    if matches:
        m = matches[0]
        return m.group(1), m.group(2)
    return None, None

def get_symlink(line: str) -> Tuple[Optional[str], Optional[str]]:
    matches = expressions.get_matches(line, LINUX_LN)
    if matches:
        m = matches[0]
        return m.group(2), m.group(1)
    return None, None

def get_copy(line: str) -> Tuple[Optional[str], Optional[str]]:
    matches = expressions.get_matches(line, LINUX_CP)
    if matches:
        m = matches[0]
        return m.group(2), m.group(1)
    return None, None

def get_move(line: str) -> Tuple[Optional[str], Optional[str]]:
    matches = expressions.get_matches(line, LINUX_MV)
    if matches:
        m = matches[0]
        return m.group(1), m.group(2)
    return None, None

# class because it may change in future. 
# want to keep the .get() and .add() methods stable
class AssociationRegister:
    def __init__(self):
        self.accs: dict[str, list[Association]] = {}
    
    def get(self, source: str, depth: int=0) -> list[str]:
        depth += 1
        if depth >= 4:
            return []
        out: list[str] = []
        if source in self.accs:
            for a in self.accs[source]:
                if a.atype == AssociationType.INPUT_VAR:
                    out.append(a.dest)
                elif a.atype == AssociationType.LOCAL_VAR:
                    out += self.get(a.dest, depth)
        return out
    
    def add(self, acc: Association) -> None:
        if acc.source not in self.accs:
            self.accs[acc.source] = []    
        self.accs[acc.source].append(acc)


from janis_core.ingestion.galaxy.gx.gxworkflow.parsing.tool_state.flatten import flatten

class AssociationExtractor:
    def __init__(self, inputs_dict: dict[str, Any]):
        self.inputs_dict = inputs_dict
        self.register: AssociationRegister = AssociationRegister()

    def extract(self, cmdstr: str) -> None:
        lines = utils.split_lines(cmdstr)
        for line in lines:
            if is_association_line(line):
                self.register_line(line)
    
    def register_line(self, line: str) -> None:
        source, dest = extract_association(line)
        if source and dest and source != dest:
            association = self.generate_association(source, dest)
            if association:
                self.register.add(association)

    def generate_association(self, source: str, dest: str) -> Optional[Association]:
        source = source.strip('${}')
        matches = get_vars_in_text(dest)
        for match in matches:
            v = match.groups()[0]
            if v in self.inputs_dict:
                return Association(AssociationType.INPUT_VAR, source, v)
            else:
                return Association(AssociationType.LOCAL_VAR, source, v)

    def looks_like_local_var(self, word: str) -> bool:
        if not word in ['False', 'True']:
            is_quoted: bool = False
            if word.startswith('"') or word.startswith("'"):
                is_quoted = True

            if not is_quoted and not word.isnumeric():
                return True
            elif is_quoted:
                word = word[1:-1].strip()
                if word.startswith('$'):
                    return True
        
        return False
    


class AssociationResolver:
    def __init__(self, register: AssociationRegister):
        self.register = register

    def resolve(self, cmdstr: str) -> str:
        resolved_lines: list[str] = []
        cmdstr_lines = cmdstr.split('\n')
        for line in cmdstr_lines:
            line = self.resolve_line(line)
            resolved_lines.append(line)
        cmdstr = utils.join_lines(resolved_lines)
        return cmdstr

    def resolve_line(self, line: str) -> str:
        if not is_association_line(line):
            matches = get_vars_in_text(line)
            for match in reversed(matches):
                v = match.groups()[0]
                accs = self.register.get(v)
                if accs:
                    smallest_acc = min(accs, key=lambda x: len(x))
                    line = self.perform_replacement(match, smallest_acc, line)

        # for source in self.register.accs:
        #     dest = self.register.get(source)
        #     if dest:
        #         # ensure ends/starts with whitespace or quotes or forwardslash or is curly brackets
        #         matches = self.get_line_matches(source, line)
        #         for match in matches:
        #             line = self.perform_replacement(match, dest, line)
        return line

    def get_line_matches(self, source: str, line: str) -> list[re.Match[str]]:
        pattern = re.escape(source)
        raw_matches = re.finditer(pattern, line)
        delims = ['"', "'", ' ', '}']
        matches: list[re.Match[str]] = []

        for m in raw_matches:
            if m.end() == len(line):
                matches.append(m)
            elif line[m.end()] in delims:
                matches.append(m)
            elif m.end()+1 < len(line) and line[m.end()+1] in delims:
                matches.append(m)
        
        return matches

    def perform_replacement(self, match: re.Match[str], dest: str, line: str) -> str:
        line = line[:match.start()] + dest + line[match.end():]
        return line
        
        