
from __future__ import annotations
from typing import Optional, Any, Tuple
from janis_core.translation_deps.exportpath import ExportPathKeywords
from enum import Enum
from dataclasses import dataclass
from collections import defaultdict

class ERenderCmd(Enum):
    OFF       = "skeleton"
    ON        = "full"

    @staticmethod
    def frombool(nocmd: bool) -> ERenderCmd:
        if nocmd == True:
            return ERenderCmd.OFF
        elif nocmd == False:
            return ERenderCmd.ON
        else:
            raise ValueError(f"Invalid value for ERenderCmd: {str(thestr)}")

class ESimplification(Enum):
    AGGRESSIVE  = "aggressive"
    ON          = "on"
    OFF         = "off"

    @staticmethod
    def fromstr(thestr: str) -> ESimplification:
        if thestr == "aggressive":
            return ESimplification.AGGRESSIVE
        elif thestr == "off":
            return ESimplification.OFF
        elif thestr == "on":
            return ESimplification.ON
        else:
            raise ValueError(f"Invalid value for ESimplification: {thestr}")

@dataclass
class ScriptFile:
    tool_uuid: str 
    src_lang: str 
    src_abspath: str
    dest_parentdir: Optional[str] = None    # how to place in export_path/source
    is_source: bool = False                 # is this an ingested workflow file

class ScriptFileRegister:
    def __init__(self) -> None:
        self.files: dict[str, list[ScriptFile]] = defaultdict(list)

    def add(self, the_file: ScriptFile) -> None:
        parent, filename = the_file.src_abspath.split('/')[-2:]
        signature = f"{the_file.tool_uuid}|{parent}|{filename}"
        self.files[signature].append(the_file)

    def get(self, uuid: str) -> list[ScriptFile]:
        return [x for x in self.all if x.tool_uuid == uuid]
    
    @property 
    def all(self) -> list[ScriptFile]:
        return [item for sublist in self.files.values() for item in sublist]

        

DEST:                       str = ''                                # destination language: one of 'nextflow' | 'cwl' | 'wdl'
RENDERCMD:                  ERenderCmd = ERenderCmd.ON              # whether to render commmand block in trx tools
SIMPLIFICATION:             ESimplification = ESimplification.OFF   # whether to simplify tool inputs / args / outputs
AS_WORKFLOW:                bool = False        # wrap tool translation in workflow

EXPORT_PATH:                str = ExportPathKeywords.default # base output directory

ALLOW_EMPTY_CONTAINER:      bool = True  # makes docker containers optional
MERGE_RESOURCES:            bool = False # merge resource requirements into inputs config
RENDER_COMMENTS:            bool = True  # whether to render info comments in the translation
SHOULD_VALIDATE:            bool = False # whether to validate translated files
SHOULD_ZIP:                 bool = False # whether to zip translated tool folder
TO_DISK:                    bool = False # whether to write translated files to disk
TO_CONSOLE:                 bool = False  # whether to write main translated file to console
TOOL_TO_CONSOLE:            bool = False # whether to write translated tool files to console 
                                         # (workflow translation only)
WITH_CONTAINER:             bool = True  # with_container=True, with_docker=True,
WITH_RESOURCE_OVERRIDES:    bool = False # whether to add computational resources to inputs dict. 
                                         # uses resources specified in ingested workflow, else default values.
WRITE_INPUTS_FILE:          bool = True  # whether to write the inputs file to disk

CONTAINER_OVERRIDE:         Optional[dict[str, Any]] = None   # val, or key, val map where keys are tool ids, vals are containers to use
SCRIPT_FILES:               ScriptFileRegister = ScriptFileRegister()  # list of files/directories to copy into export_path/source (src, dest) 
ADDITIONAL_INPUTS:          Optional[dict[str, Any]] = None # key, val map for additional tool / workflow inputs supplied by user
HINTS:                      Optional[dict[str, Any]] = None # key, val map for cwl type hints
MAX_CORES:                  Optional[int] = None            # ceiling value for cores resource
MAX_DURATION:               Optional[int] = None            # ceiling value for duration resource
MAX_MEM:                    Optional[int] = None            # ceiling value for memory resource

