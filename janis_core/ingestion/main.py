

from janis_core import Tool
from janis_core import settings
from janis_core.messages import configure_logging

from .SupportedIngestion import SupportedIngestion
from .galaxy import parse_galaxy
from .cwl import parse as parse_cwl
from .wdl import WdlParser

def ingest_galaxy(uri: str) -> Tool:
    return parse_galaxy(uri)

def ingest_cwl(path: str) -> Tool:
    return parse_cwl(path)

def ingest_wdl(path: str) -> Tool:
    return WdlParser.from_doc(path)


# this is using the SupportedIngestion Enum values. 
# should it just be the Enum? these strings are in 2 places now.  
ingestor_map = {  
    'galaxy': ingest_galaxy,
    'cwl': ingest_cwl,
    'wdl': ingest_wdl
}

def ingest(
    path: str, 
    format: str, 
    galaxy_build_images: bool=False, 
    galaxy_no_image_cache: bool=False,
    galaxy_no_wrapper_cache: bool=False
    ) -> Tool:
    # setup logging
    configure_logging()                         
    
    # set ingest settings
    settings.ingest.SOURCE = format                     
    settings.validation.STRICT_IDENTIFIERS = False
    settings.validation.VALIDATE_STRINGFORMATTERS = False
    
    if galaxy_build_images:
        settings.ingest.galaxy.GEN_IMAGES = True
    if galaxy_no_image_cache:
        settings.ingest.galaxy.DISABLE_IMAGE_CACHE = True
    if galaxy_no_wrapper_cache:
        settings.ingest.galaxy.DISABLE_WRAPPER_CACHE = True

    # do ingest
    assert(format in SupportedIngestion.all())  # validate format
    ingest_func = ingestor_map[format]          # select ingestor
    internal = ingest_func(path)                # ingest
    return internal