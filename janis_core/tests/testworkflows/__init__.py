

from .basics import BasicIOTestWF
from .basics import WildcardSelectorOutputTestWF
from .basics import InputSelectorTestWF
from .basics import DirectivesTestWF
from .basics import ArrayIOTestWF
from .basics import ArrayIOExtrasTestWF

from .steps import StepInputsTestWF
from .steps import StepInputsWFInputTestWF
from .steps import StepInputsStaticTestWF
from .steps import StepInputsPartialStaticTestWF
from .steps import StepInputsMinimalTestWF
from .steps import StepConnectionsTestWF
from .steps import ArrayStepInputsTestWF
from .steps import ArrayStepConnectionsTestWF

from .scatter import BasicScatterTestWF
from .scatter import ChainedScatterTestWF
from .scatter import ScatterDotTestWF
from .scatter import ScatterCrossTestWF
from .scatter import ComprehensiveScatterTestWF

from .secondaries import SecondariesTestWF
from .secondaries import SecondariesTestTool
from .filenames import FilenameTestWF

from .combos import ScatterSecondariesTestWF
from .outputs import OutputCollectionTestWF
from .unwrap import UnwrapTestWF
from .subworkflow import SubworkflowTestWF
from .subworkflow2 import Subworkflow2TestWF
from .subworkflow2 import Subworkflow3TestWF
from .data_sources import DataSourceTestWF
from .naming import NamingTestWF
from .filepairs import FilePairsTestWF
from .process_inputs import ProcessInputsTestWF
from .ordering import OrderingTestWF
from .plumbing_edge_cases import PlumbingEdgeCaseTestWF
from .plumbing_type_mismatch import PlumbingTypeMismatchTestWF
from .trace import EntityTraceTestWF
from .optional import OptionalTestWF
from .duplicate_tasks import DuplicateTasksTestWF

from .assembly import w as AssemblyTestWF
from .string_formatter import StringFormatterTestWF

from .additional_features import (
    StepInputExpressionTestWF,
    ConditionStepTestWF,
    AliasSelectorTestWF,
    ArraysOfSecondaryFilesOutputsTestWF,
    ForEachTestWF,
    IndexOperatorTestWF,
)

from .codetools import (
    InputsPythonToolTestWF,
    OutputsPythonToolTestWF
)

