

from typing import Any, Optional
import requests
import re 

from galaxy.tool_util.deps.mulled.util import quay_versions
from janis_core import settings
from janis_core import CommandToolBuilder, CodeTool
from janis_core.messages import log_message, ErrorCategory
from Levenshtein import distance as levenshtein_distance

from .symbols.case import split_underscores, split_hyphens, split_lower_upper
from .EntityModifier import EntityModifier

LINUX_CMDS = set([
    'set', 'ln', 'cp', 'mv', 'export', 'mkdir', 'tar', 'ls', 'cd', 'echo', 
    'head', 'wget', 'grep', 'awk', 'cut', 'sed', 'gzip', 'gunzip', 'trap', 'touch'
])

def get_leading_positionals(cmdtool: CommandToolBuilder) -> list[str]:
    # TODO: positional inputs and args in order
    raise NotImplementedError

def handle_cmdtool_commands(cmdwords: list[str], cmdtool: CommandToolBuilder) -> Optional[str]:
    msg = 'tool did not specify container or software requirement, guessed from command.'
    log_message(cmdtool.uuid, msg, ErrorCategory.METADATA)

    container = None
    if container is None:
        container = attempt_linux_binary(cmdwords)
    if container is None:
        container = attempt_coding_script(cmdwords)
    
    # these have to be done together
    if container is None:
        shell_script = extract_shell_script(cmdwords)
        if shell_script is not None:
            container = attempt_shell_script_contents(shell_script, cmdtool)
            if container is None:
                container = attempt_cmdtool_metadata(cmdtool)

    # these have to be done together
    if container is None:
        cmdwords = [x.split('/')[-1] for x in cmdwords]
        container = attempt_quay_io(cmdwords[0])
        if container is None:
            container = attempt_quay_io_fuzzy(cmdwords)
        if container is None:
            container = attempt_cmdtool_metadata(cmdtool)

    return container

def attempt_cmdtool_metadata(cmdtool: CommandToolBuilder) -> Optional[str]:
    container = None
    
    if not container:
        cmdwords = [cmdtool._tool.split('.cwl')[0]]
        cmdwords = split_underscores(cmdwords)
        cmdwords = split_hyphens(cmdwords)
        container = attempt_quay_io(cmdwords[0])
    
    if not container:
        cmdwords = split_lower_upper(cmdwords)
        container = attempt_quay_io(cmdwords[0])

    if not container:
        container = attempt_quay_io_fuzzy(cmdwords)

    return container

def attempt_linux_binary(cmdwords: list[str]) -> Optional[str]:
    if cmdwords[0] in LINUX_CMDS:
        return 'ubuntu:latest'
    return None 

def attempt_coding_script(cmdwords: list[str]) -> Optional[str]:
    PATTERN = r'((python )?([\w./-]+\.py))|((perl )?([\w./-]+\.pl))|((r |R |Rscript |rscript )?([\w./-]+\.[rR]))|((nodejs )?([\w./-]+\.js))'
    cmd = ' '.join(cmdwords)
    for m in re.finditer(PATTERN, cmd):
        if not m:
            continue 
        if m.group(1):
            return 'python:latest'
        elif m.group(4):
            return 'perl:latest'
        elif m.group(7):
            return 'r-base:latest'
        elif m.group(10):
            return 'node:latest'
    return None 

def extract_shell_script(cmdwords: list[str]) -> Optional[str]:
    PATTERN = r'((bash |sh )?([\w./-]+\.sh))'
    cmd = ' '.join(cmdwords)
    for m in re.finditer(PATTERN, cmd):
        if not m:
            continue
        return m.group(3)
    return None 

def attempt_shell_script_contents(relpath: str, cmdtool: CommandToolBuilder) -> Optional[str]:
    # 1. get the contents of the relevant file. 
    # 2. assess software commands in the contents to identify container. 
    filename = relpath.split('/')[-1]
    contents = None
    container = None

    # first, try to get contents assuming file is in cmdtool._files_to_create
    if contents is None:
        if isinstance(cmdtool._files_to_create, list):
            raise RuntimeError
        if isinstance(cmdtool._files_to_create, dict):
            if filename in cmdtool._files_to_create:
                val = cmdtool._files_to_create[filename]
                if isinstance(val, str):
                    contents = val 

    # first, try to get contents assuming file is ScriptFile for this tool
    if contents is None:
        script_files = settings.translate.SCRIPT_FILES.get(cmdtool.uuid)
        for the_file in script_files:
            if the_file.src_abspath.endswith(filename):
                with open(the_file.src_abspath, 'r') as f:
                    contents = f.read()
                    break

    if contents is not None:
        cmdwords = get_commands_from_shell_script(contents)
        if cmdwords:
            return handle_cmdtool_commands(cmdwords, cmdtool)
    
    return None

def get_commands_from_shell_script(contents: str) -> list[str]:
    RESERVED = set([
        'if', 'then', 'elif', 'else', 'fi', 'time', 'for', 'in', 'until', 'while', 
        'do', 'done', 'case', 'esac', 'coproc', 'select', 'function'
    ])

    # this is bad. very basic. 
    cmds = []
    lines = contents.split('\n')

    PATTERN = r'^(["\']?((\$\{\w+\}|\$\w+)["\']?)?\/?\w+)\s.*$'
    for ln in lines:
        m = re.match(PATTERN, ln)
        if not m:
            continue
        if m.group(1) in RESERVED:
            continue
        
        cmds.append(m.group(1).split('/')[-1])
    return cmds

def attempt_quay_io(pkg: str) -> Optional[str]:
    # single package -> single container    
    print(f'making quay.io request for "{pkg}"')
    tags = quay_versions('biocontainers', pkg)
    if len(tags) > 0:
        return f'quay.io/biocontainers/{pkg}:{tags[0]}'
    return None

def attempt_quay_io_fuzzy(words: list[str]) -> Optional[str]:
    session = None
    words = words[:2]
    if len(words) == 0:
        raise RuntimeError
    elif len(words) == 1:
        queries = [words[0]]
    elif len(words) == 2:
        queries = []
        queries.append(words[0])
        queries.append('-'.join(words))
        queries.append('_'.join(words))
        queries.append(''.join(words))
    else:
        raise NotImplementedError
    
    for query in queries:
        print(f'making quay.io request for packages similar to "{query}"')
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
            return attempt_quay_io(pkg)
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
            return attempt_quay_io(best_pkg)
    
    return None 



class ContainerModifier(EntityModifier):

    def handle_codetool(self, codetool: CodeTool) -> Any:
        # early exit if ok
        if codetool.container() is not None:
            return codetool
        
        # CodeTools don't have a container I can assign to. 
        # container() is a method on a CodeTool. I hate this. 
        raise NotImplementedError

    def handle_cmdtool(self, cmdtool: CommandToolBuilder) -> Any:
        # early exit if container override
        if settings.translate.CONTAINER_OVERRIDE is not None:
            if cmdtool.id().lower() in settings.translate.CONTAINER_OVERRIDE:
                cmdtool._container = settings.translate.CONTAINER_OVERRIDE[cmdtool.id().lower()]
                return cmdtool

        # early exit if already has container
        if cmdtool._container is not None:
            return cmdtool
        
        # gather commands
        cmds = []
        # single string
        if isinstance(cmdtool._base_command, str):
            cmds = [cmdtool._base_command]
        # list of strings
        elif isinstance(cmdtool._base_command, list):
            cmds = cmdtool._base_command      
        # no base command
        if len(cmds) > 0:
            # identify container from commands
            container = handle_cmdtool_commands(cmds, cmdtool)
            if container is not None:
                cmdtool._container = container
        
        if cmdtool._container is None:
            msg = "could not identify container for tool. used 'ubuntu:latest' as fallback."
            log_message(cmdtool.uuid, msg, ErrorCategory.FALLBACKS)
            cmdtool._container = 'ubuntu:latest'
        
        return cmdtool
    
    
        

    

    
