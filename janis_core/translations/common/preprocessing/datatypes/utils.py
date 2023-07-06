
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .model import SecondaryTypeRegister

from copy import deepcopy
from janis_core.types import DataType


def get_signature(secs: list[str], exact: bool=True) -> str:
    if not exact:
        secs = [x.replace('^', '') for x in secs]
    secs.sort()
    signature = '|'.join(secs)
    return signature

def gen_type(register: SecondaryTypeRegister, old_type: DataType) -> DataType:
    assert(isinstance(old_type.secondary_files(), list))
    # note: we don't want to fix type mismatches for 1+ defined types.
    # this behaviour can be considered normal, and we always get GenericFileWithSecondaries
    # when we have ingest issues. 
    if len(register.defined_types) > 1:
        return old_type
    
    if len(register.unique_valid_signatures) == 1:
        valid_sig = list(register.unique_valid_signatures)[0]
        return _gen_type_from_signature(valid_sig, old_type, register)
    elif len(register.unique_valid_signatures) == 2:
        valid_sig = register.superset_signature
        return _gen_type_from_signature(valid_sig, old_type, register)
    else:
        raise NotImplementedError

def _gen_type_from_signature(valid_sig: str, old_type: DataType, register: SecondaryTypeRegister) -> DataType:
    # old type is the valid one
    query_sig = get_signature(old_type.secondary_files(), exact=False)   # type: ignore
    if query_sig == valid_sig:
        return old_type
    
    # old type is not the valid one
    dtypes = register.get_datatypes_with_signature(valid_sig, exact=False)
    if len(dtypes) == 1:
        new_type = deepcopy(dtypes[0])
        new_type.optional = old_type.optional
        return new_type
    
    # more to add, but only when needed
    raise NotImplementedError
