
from .model import ConnectionGroup
from .model import SecondaryTypeRegister


def gen_secondary_register(group: ConnectionGroup) -> SecondaryTypeRegister:
    register = SecondaryTypeRegister()
    for conn in group.connections:
        for node in [conn.src, conn.dest]:
            register.add(node.dtype)
    return register





# def get_standard_signatures(group: ConnectionGroup) -> set[str]:
#     register = gen_secondary_register(group)
    
#     dtype: DataType = GenericFileWithSecondaries(secondaries=[])
#     if register.single_valid_signature:
#         dtype = _get_dtype_from_single_valid_signature(group)
#     elif len(register.unique_signatures) == 2:
#         dtype = _get_dtype_from_two_valid_signatures(group, register)
#     else:
#         raise NotImplementedError
#     return dtype

# def _get_dtype_from_single_valid_signature(group: ConnectionGroup) -> DataType:
#     for conn in group.connections:
#         if len(conn.src.dtype.secondary_files()) > 0:       # type: ignore
#             return conn.src.dtype
#         elif len(conn.dest.dtype.secondary_files()) > 0:    # type: ignore
#             return conn.dest.dtype
    
#     raise RuntimeError # will only arrive here if issues

# def _get_dtype_from_two_valid_signatures(group: ConnectionGroup, signature_counts: dict[str, int]) -> DataType:
#     # get the two signatures
#     sig1, _ = signature_counts.popitem()
#     sig2, _ = signature_counts.popitem()
#     assert(len(signature_counts) == 0)
    
#     # get the corresponding secondary files lists
#     secs1 = set(sig1.split('|'))
#     secs2 = set(sig2.split('|'))
    
#     # get the signature which is the superset
#     if secs1.issubset(secs2):
#         target_sig = sig2
#     elif secs2.issubset(secs1):
#         target_sig = sig1
#     else:
#         raise NotImplementedError
    
#     # go through the connections and find the first node with datatype matching the signature
#     for conn in group.connections:
#         src_sig = utils.get_signature(conn.src.dtype)
#         dest_sig = utils.get_signature(conn.dest.dtype)
#         if src_sig == target_sig:
#             return conn.src.dtype
#         elif dest_sig == target_sig:
#             return conn.dest.dtype

#     raise RuntimeError # will only arrive here if issues
    

    

    
