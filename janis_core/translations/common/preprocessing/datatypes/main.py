

"""
This module exists to standardise datatypes which have secondary files. 

Secondary type parsing during ingestion can be difficult, especially in cases like 
CWL where the secondary files can be determine by a javascript expression. 

This may result in connections between types where the secondary files don't match, which 
throws an error in some translate units. 

The goal is to find such connections, then standardise impacted nodes so they have the same type
(or ensure types are valid for the workflow connections).

These are the specific cases we run into & fix in this module:
- source is defined secondary type, dest is GenericFileWithSecondaries(secondaries=[])
- source is GenericFileWithSecondaries(secondaries=[]), dest is defined secondary type
- source is GenericFileWithSecondaries, dest is GenericFileWithSecondaries, but their secondary files don't match. 

Once we fix one connection, we need to re-run the process to ensure we haven't created a new mismatch.
"""

from janis_core import WorkflowBuilder
from janis_core import settings
from .gather import gather_connections
from .groups import get_mismatch_group
# from .balancing import get_standard_signatures
from .balancing import gen_secondary_register
from .apply import apply_new_types

MAX_ITERATIONS = 10

def repair_secondary_mismatches(main_wf: WorkflowBuilder) -> None:
    # wrapping for safe mode
    if settings.general.SAFE_MODE:
        try:
            do_balance_mismatch_secondary_types(main_wf)
        except Exception as e:
            print('warning: error encountered while analysing mismatched datatypes. continuing.')
            raise e
    else:
        do_balance_mismatch_secondary_types(main_wf)

def do_balance_mismatch_secondary_types(main_wf: WorkflowBuilder) -> None:
    iter_count = 0
    conn_register = gather_connections(main_wf)
    while conn_register.mismatched_secondary_connections and iter_count < MAX_ITERATIONS:
        print('found a mismatched secondary connection')
        group = get_mismatch_group(conn_register)
        type_register = gen_secondary_register(group)
        apply_new_types(main_wf, type_register, group)
        # apply_new_types(main_wf, new_type, group)
        conn_register = gather_connections(main_wf)

