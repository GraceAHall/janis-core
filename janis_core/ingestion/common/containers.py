

from typing import Tuple, Optional

from galaxy.tool_util.deps.mulled.util import quay_versions
from galaxy.tool_util.deps.mulled.util import v1_image_name
from galaxy.tool_util.deps.mulled.util import v2_image_name
from galaxy.tool_util.deps.mulled.util import build_target

from janis_core import settings


def fetch_container_for_software_packages(packages: list[Tuple[str, str]]) -> Optional[str]:
    # packages: (name, version)
    # from galaxy <packages>, from cwl SoftwareRequirement, SoftwarePackage.
    # find a useable container from quay.io.
    
    if settings.testing.TESTING_USE_DEFAULT_CONTAINER:
        return None

    elif len(packages) == 0:
        return None
    
    # single package -> single container    
    elif len(packages) == 1:
        repo, version = packages[0]
        tags = quay_versions('biocontainers', repo)
        version_tags = [x for x in tags if x.startswith(version)]
        if len(version_tags) == 0:
            # TODO return closest version
            raise RuntimeError
        return f'quay.io/biocontainers/{repo}:{version_tags[0]}'

    # multiple packages -> single container
    else:
        return _fetch_multi(packages)
        
def _fetch_multi(packages: list[Tuple[str, str]]) -> Optional[str]:
    items = [build_target(pkg[0], version=pkg[1]) for pkg in packages]
    resource = v2_image_name(items)
    repo = resource.split(':')[0]
    tags = quay_versions('biocontainers', repo)
    if len(tags) == 0:
        resource = v1_image_name(items)
        repo = resource.split(':')[0]
        tags = quay_versions('biocontainers', repo)
        if len(tags) == 0:
            raise RuntimeError
    return f'quay.io/biocontainers/{repo}:{tags[0]}'
    