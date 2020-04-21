from janis_core.types import UnionType

from janis_core.types.common_data_types import String, Array, AnyType
from janis_core.operators.operator import Operator


class JoinOperator(Operator):
    def argtypes(self):
        return [Array(UnionType(AnyType)), String]

    def returntype(self):
        return String

    def to_wdl(self, unwrap_operator, *args):
        raise Exception("This functionality doesn't fully work yet")
        iterable, separator = [unwrap_operator(a) for a in self.args]

        return f"'~{{sep={separator} {iterable}}}'"

    def to_cwl(self, unwrap_operator, *args):
        iterable, separator = [unwrap_operator(a) for a in self.args]
        return f"{iterable}.join({separator})"


class BasenameOperator(Operator):
    def to_wdl(self, unwrap_operator, *args):
        arg = args[0]
        return f"basename({unwrap_operator(arg)})"

    def to_cwl(self, unwrap_operator, *args):
        return unwrap_operator(args[0]) + ".basename"

    def argtypes(self):
        return [String]

    def returntype(self):
        return String()

    def __str__(self):
        return str(self.args[0]) + ".basename"

    def __repr__(self):
        return str(self)


class TransformOperator(Operator):
    def argtypes(self):
        return [Array(Array(AnyType))]

    def returntype(self):
        return Array(Array(AnyType))

    def __str__(self):
        return str(f"transform({self.args[0]})")

    def __repr__(self):
        return str(self)

    def to_wdl(self, unwrap_operator, *args):
        return f"transform({unwrap_operator(args[0])})"

    def to_cwl(self, unwrap_operator, *args):
        return (
            unwrap_operator(args[0])
            + ".map(function(c, i) { return q.map(function(row) { return row[i]; }); })"
        )
