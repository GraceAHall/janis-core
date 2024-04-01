
import os 
import shutil
from typing import Tuple, Any,Optional

from janis_core import Logger
from janis_core import settings
from janis_core.settings.translate.general import ScriptFile
from janis_core.translation_deps.exportpath import ExportPathKeywords
from janis_core.ingestion.common import safe_init_folder

PERMISSIONS=0o777


def write_tool_to_console(str_tool: str) -> None:
    print(str_tool)


def write_tool_to_disk(str_tool: str, filename: str, tup_helpers: list[Tuple[str, str]]) -> None:
    # set output folder
    basedir = ExportPathKeywords.resolve(
        settings.translate.EXPORT_PATH, 
        workflow_spec=settings.translate.DEST, 
        workflow_name=None
    )
    # create output folder
    if not os.path.exists(basedir):
        os.makedirs(basedir)

    # write tool file
    _write_file((filename, str_tool), basedir, 'tool', None)

    # write helper files (files_to_create scripts)
    for tup_helper in tup_helpers:
        _write_file(tup_helper, basedir, 'helper', None)


def write_workflow_to_console(
    tup_workflow: Tuple[str, str], 
    tup_tools: list[Tuple[str, str]], 
    tup_inp: Tuple[str, str], 
    tup_resources: Optional[Tuple[str, str]]
    ) -> None:
    """Each tuple is (filename, string). Tells us where to write each file, followed by the file contents."""

    print(tup_workflow[1])
    if settings.translate.TOOL_TO_CONSOLE:
        print("\n=== TOOLS ===")
        [print(f":: {t[0]} ::\n" + t[1]) for t in tup_tools]
    print("\n=== INPUTS ===")
    print(tup_inp)
    if tup_resources is not None:
        if not settings.translate.MERGE_RESOURCES and settings.translate.WITH_RESOURCE_OVERRIDES:
            print("\n=== RESOURCES ===")
            print(tup_resources[1])


def write_workflow_to_disk(
    tup_main: Tuple[str, str], 
    tup_subworkflows: list[Tuple[str, str]], 
    tup_tools: list[Tuple[str, str]], 
    tup_inputs: Tuple[str, str], 
    tup_helpers: list[Tuple[str, str]], 
    tup_resources: Optional[Tuple[str, str]],
    outdir_structure: dict[str, Any]
    ) -> None:
    """Each tuple is (filename, string). Tells us where to write each file, followed by the file contents."""
    
    # prepare base output directory
    basedir = ExportPathKeywords.resolve(
        settings.translate.EXPORT_PATH, 
        workflow_spec=settings.translate.DEST,
        workflow_name=None
    )
    safe_init_folder(basedir)
    
    # subdir structure
    for subdir in outdir_structure.values():
        safe_init_folder(os.path.join(basedir, subdir))

    # writing main workflow
    Logger.info(f"Writing main workflow to \'{basedir}\'")
    _write_file(tup_main, basedir, 'main', None)
    
    # writing inputs file
    if settings.translate.WRITE_INPUTS_FILE:
        Logger.info(f"Writing inputs file to \'{basedir}\'")
        _write_file(tup_inputs, basedir, 'inputs', None)
    else:
        Logger.log("Skipping writing inputs config file")

    # writing resources file
    if tup_resources is not None:
        Logger.info(f"Writing resources file to \'{basedir}\'")
        if settings.translate.WITH_RESOURCE_OVERRIDES and not settings.translate.MERGE_RESOURCES:
            _write_file(tup_resources, basedir, 'resources', None)
        else:
            Logger.log("Skipping writing resources config file")
    
    # writing tools
    if tup_tools:
        Logger.info(f"Writing tools to \'{os.path.join(basedir, outdir_structure['tools'])}\'")
        for tup_tool in tup_tools:
            _write_file(tup_tool, basedir, 'tools', outdir_structure['tools'])
    
    # writing subworkflows
    if tup_subworkflows:
        Logger.info(f"Writing subworkflows to \'{os.path.join(basedir, outdir_structure['subworkflows'])}\'")
        for tup_subworkflow in tup_subworkflows:
            _write_file(tup_subworkflow, basedir, 'subworkflows', outdir_structure['subworkflows'])

    # writing helper files
    for tup_helper in tup_helpers:
        Logger.info(f"Writing script/helper files to \'{os.path.join(basedir, outdir_structure['helpers'])}\'")
        _write_file(tup_helper, basedir, 'helpers', outdir_structure['helpers'])

    # writing source files 
    _write_source_files_to_disk(basedir, outdir_structure)


def _write_source_files_to_disk(basedir: str, outdir_structure: dict[str, Any]) -> None:
    # TODO permissions
    # copying source files - this one is a bit weird & specific to galaxy.  
    
    def _get_dest_abspath(basedir: str, outdir_structure: dict[str, Any], the_file: ScriptFile) -> str:
        if the_file.is_source:
            parentdir = os.path.join(basedir, outdir_structure['source'])
        else:
            parentdir = os.path.join(basedir, outdir_structure['helpers'])
        
        if the_file.dest_parentdir is not None:
            parentdir = os.path.join(parentdir, the_file.dest_parentdir)
        
        filename = os.path.basename(the_file.src_abspath)
        return os.path.join(parentdir, filename)

    if settings.general.SCRIPT_FILES.all:
        for the_file in settings.general.SCRIPT_FILES.all:
            dest = _get_dest_abspath(basedir, outdir_structure, the_file)
            if not os.path.isdir(os.path.dirname(dest)):
                os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(the_file.src_abspath, dest)

def _write_file(tup_file: Tuple[str, str], basedir: str, ftype: str, fsubdir: str | None) -> None:
    filename, contents = tup_file
    
    # format outdir using basedir and subdir if provided
    outdir = os.path.join(basedir, fsubdir) if fsubdir is not None else basedir
    safe_init_folder(outdir)
    
    filepath = os.path.join(outdir, filename)

    # write to disk
    
    with open(filepath, "w+") as f:
        Logger.log(f"Writing {filename} to disk")
        f.write(contents)
        Logger.log(f"Written {filename} to disk")
        os.chmod(filepath, PERMISSIONS)

