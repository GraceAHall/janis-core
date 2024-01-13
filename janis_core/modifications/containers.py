

from typing import Any, Optional
import requests

from galaxy.tool_util.deps.mulled.util import quay_versions
from janis_core import CommandToolBuilder, CodeTool
from janis_core.messages import log_message, ErrorCategory
from Levenshtein import distance as levenshtein_distance

from .EntityModifier import EntityModifier

LINUX_CMDS = set([
    'set', 'ln', 'cp', 'mv', 'export', 'mkdir', 'tar', 'ls', 'cd', 'echo', 
    'head', 'wget', 'grep', 'awk', 'cut', 'sed', 'gzip', 'gunzip', 'trap', 'touch'
])


def is_linux_binary(word: str) -> bool:
    if word in LINUX_CMDS:
        return True
    return False 

def fetch_quay_io(pkg: str) -> Optional[str]:
    # single package -> single container    
    tags = quay_versions('biocontainers', pkg)
    if len(tags) == 0:
        raise RuntimeError
    return f'quay.io/biocontainers/{pkg}:{tags[0]}'

def search_quay_io(words: list[str]) -> Optional[str]:
    session = None
    queries = [
        '-'.join(words),
        '_'.join(words),
        ''.join(words),
    ]
    for query in queries:
        uri = f'https://quay.io/api/v1/find/repositories?query={query}'
        if not session:
            session = requests.session()
        response = session.get(uri, timeout=10)
        if response.status_code != 200:
            continue 
        data = response.json()
        data = data.get('results', [])
        all_repos = [x for x in data if x.get('kind') == 'repository']
        bio_repos = [x for x in all_repos if x.get('href').startswith('/repository/biocontainers/')]
        if len(bio_repos) == 0:
            continue
        elif len(bio_repos) == 1:
            pkg = bio_repos[0].get('name')
            return fetch_quay_io(pkg)
        elif len(bio_repos) > 1:
            target = ''.join(words)
            original_names = [x.get('name') for x in bio_repos]
            scores = []
            for original in original_names:
                standard = original.lower()
                standard = standard.replace('-', '')
                standard = standard.replace('_', '')
                score = levenshtein_distance(standard, target)
                scores.append((original, score))
            best_pkg = sorted(scores, key=lambda x: x[1])[0][0]
            return fetch_quay_io(best_pkg)
    
    raise NotImplementedError





class ContainerModifier(EntityModifier):

    def handle_codetool(self, codetool: CodeTool) -> Any:
        # early exit if ok
        if codetool.container() is not None:
            return codetool
        
        # CodeTools don't have a container I can assign to. 
        # container() is a method on a CodeTool. I hate this. 
        raise NotImplementedError

    def handle_cmdtool(self, cmdtool: CommandToolBuilder) -> Any:
        # early exit if ok
        if cmdtool._container is not None:
            return cmdtool
        
        cmds = []

        # single string
        if isinstance(cmdtool._base_command, str):
            cmds = [cmdtool._base_command]
        # list of strings
        elif isinstance(cmdtool._base_command, list):
            cmds = cmdtool._base_command      
        # no base command
        if len(cmds) == 0:
            cmds = self._get_leading_positionals(cmdtool)
        
        # identify container
        if len(cmds) == 1:
            cmdtool._container = self._handle_cmdtool_one_command(cmds[0], cmdtool)
        elif len(cmds) == 2:
            cmdtool._container = self._handle_cmdtool_multiple_commands(cmds, cmdtool)
        else:
            # TODO: LOG MESSAGE
            pass
            # raise NotImplementedError
        
        return cmdtool
    
    def _get_leading_positionals(self, cmdtool: CommandToolBuilder) -> list[str]:
        # TODO: positional inputs and args in order
        return []

    def _handle_cmdtool_one_command(self, cmdword: str, cmdtool: CommandToolBuilder) -> str:
        msg = 'tool did not specify container or software requirement, guessed from command.'
        log_message(cmdtool.uuid, msg, ErrorCategory.METADATA)

        if is_linux_binary(cmdword):
            return 'ubuntu:latest'
        
        container = fetch_quay_io(cmdword)
        if container is None:
            raise NotImplementedError
        return container

    def _handle_cmdtool_multiple_commands(self, cmdwords: list[str], cmdtool: CommandToolBuilder) -> str:
        msg = 'tool did not specify container or software requirement, guessed from command.'
        log_message(cmdtool.uuid, msg, ErrorCategory.METADATA)

        if is_linux_binary(cmdwords[0]):
            return 'ubuntu:latest'
        
        container = search_quay_io(cmdwords)
        if container is None:
            raise NotImplementedError
        return container

    

    
