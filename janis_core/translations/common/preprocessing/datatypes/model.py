

from dataclasses import dataclass, field
from collections import defaultdict
from functools import cached_property

from janis_core.workflow.workflow import TInput, TOutput
from janis_core.types import DataType

from . import utils


@dataclass 
class Node:
    node: TInput | TOutput  # the specific graph node
    task_name: str          # either "__main__" or step name

    @cached_property
    def dtype(self) -> DataType:
        if isinstance(self.node, TInput):
            return self.node.intype
        elif isinstance(self.node, TOutput):
            return self.node.outtype
        else:
            raise NotImplementedError

@dataclass
class Connection:
    src: Node
    dest: Node

    @cached_property
    def is_secondary_mismatch(self) -> bool:
        # ensure both types have secondary files
        if isinstance(self.src.dtype.secondary_files(), list) and isinstance(self.dest.dtype.secondary_files(), list):
            # check if secondary files of dest are subset of src
            src_secs = set([x.replace('^', '') for x in self.src.dtype.secondary_files()])  # type: ignore
            dest_secs = set([x.replace('^', '') for x in self.dest.dtype.secondary_files()])  # type: ignore
            if not dest_secs.issubset(src_secs):
                return True
            
        # if not isinstance(self.src.dtype, GenericFileWithSecondaries) or self.src.dtype.secondary_files() is None:
        #     return False
        # if not isinstance(self.dest.dtype, GenericFileWithSecondaries) or self.dest.dtype.secondary_files() is None:
        #     return False
        return False

@dataclass
class ConnectionRegister:
    connections: list[Connection] = field(default_factory=list)

    @cached_property
    def mismatched_secondary_connections(self) -> list[Connection]:
        return [x for x in self.connections if x.is_secondary_mismatch]
    
    def add(self, connection: Connection) -> None:
        self.connections.append(connection)

@dataclass
class ConnectionGroup:
    central_node: Node
    connections: list[Connection] = field(default_factory=list)

    @cached_property
    def node_signatures(self) -> set[str]:
        signatures: set[str] = set()
        for conn in self.connections:
            src_signature = '|'.join([conn.src.task_name, conn.src.node.id()])
            dest_signature = '|'.join([conn.dest.task_name, conn.dest.node.id()])
            signatures.add(src_signature)
            signatures.add(dest_signature)
        return signatures
    
@dataclass
class SecondaryTypeRegister:
    # TODO this has poor algorithmic complexity
    # ^^^ bandaid with cached_property
    sec_list: list[list[str]] = field(default_factory=list)
    dtype_list: list[DataType] = field(default_factory=list)
    
    ### type stuff

    @cached_property
    def unique_types(self) -> set[str]:
        return set([x.__class__.__name__ for x in self.dtype_list])
    
    @cached_property
    def defined_types(self) -> set[str]:
        return set([x for x in self.unique_types if x != 'GenericFileWithSecondaries'])
    
    @cached_property
    def has_generic_type(self) -> bool:
        if 'GenericFileWithSecondaries' in self.unique_types:
            return True
        return False 
       
    def get_datatypes_with_signature(self, target_sig: str, exact: bool=False) -> list[DataType]:
        included_types: set[str] = set()
        out: list[DataType] = []
        for dtype in self.dtype_list:
            if dtype.__class__.__name__ in included_types:
                continue
            query_sig = utils.get_signature(dtype.secondary_files(), exact=exact)
            if query_sig == target_sig:
                out.append(dtype)
                included_types.add(dtype.__class__.__name__)
        return out


    ### secondary signature stuff

    @cached_property
    def unique_signatures(self) -> set[str]:
        return set([utils.get_signature(x, exact=False) for x in self.sec_list])
    
    @cached_property
    def unique_exact_signatures(self) -> set[str]:
        return set([utils.get_signature(x) for x in self.sec_list])
    
    @cached_property
    def unique_valid_signatures(self) -> set[str]:
        sigs = set([utils.get_signature(x, exact=False) for x in self.sec_list])
        if '' in sigs:
            sigs.remove('')
        return sigs
    
    @cached_property
    def most_common_valid_signature(self) -> str:
        sig_counts: defaultdict[str, int] = defaultdict(int)
        for sig in self.unique_signatures:
            if sig != '':
                sig_counts[sig] += 1
        sigs = list(sig_counts.items())
        sigs.sort(key=lambda x: x[1], reverse=True)
        return sigs[0][0]
    
    @cached_property
    def superset_signature(self) -> str:
        all_secondaries: set[str] = set()
        
        # get all secondaries
        for sig in self.unique_valid_signatures:
            secs = set(sig.split('|'))
            all_secondaries.update(secs)

        # get the signature which is the superset
        for sig in self.unique_valid_signatures:
            secs = set(sig.split('|'))
            if secs == all_secondaries:
                return sig

        # or fail if theres no superset
        raise NotImplementedError

    def add(self, dtype: DataType) -> None:
        assert(isinstance(dtype.secondary_files(), list))
        self.sec_list.append(dtype.secondary_files())
        self.dtype_list.append(dtype)
    

