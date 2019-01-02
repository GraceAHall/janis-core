from unittest import TestCase

from Pipeline import File, Array
from Pipeline.graph.edge import Edge
from Pipeline.types.common_data_types import String
from Pipeline.unix.data_types.tar_file import TarFile
from Pipeline.unix.steps.echo import Echo
from Pipeline.unix.steps.tar import Tar
from Pipeline.unix.steps.untar import Untar
from Pipeline.workflow.input import Input
from Pipeline.workflow.output import Output
from Pipeline.workflow.step import Step
from Pipeline.workflow.workflow import Workflow
from Pipeline.unix.steps.cat import Cat


class TestWorkflow(TestCase):

    def test_name(self):
        wn = "test_name"
        w = Workflow(wn)
        self.assertEqual(w.identifier, wn)

    def test_rename(self):
        wn1 = "test_rename"
        wn2 = "test_rename2"
        w = Workflow(wn1)
        w.identifier = wn2
        self.assertEqual(w.identifier, wn2)

    def test_add_input(self):
        w = Workflow("test_add_input")
        inp = Input("inputLabel", String())
        w.add_input(inp)
        self.assertEqual(len(w._inputs), 1)
        self.assertEqual(w._inputs[0].input, inp)
        self.assertIsNotNone(w._labels[inp.id()])

    def test_add_step(self):
        w = Workflow("test_add_input")
        step = Step("catStep", Cat())
        w.add_step(step)
        self.assertEqual(len(w._steps), 1)
        self.assertEqual(w._steps[0].step, step)
        self.assertIsNotNone(w._labels[step.id()])

    def test_add_output(self):
        w = Workflow("test_add_input")
        outp = Output("outputStep", String())
        w.add_output(outp)
        self.assertEqual(len(w._outputs), 1)
        self.assertEqual(w._outputs[0].output, outp)
        self.assertIsNotNone(w._labels[outp.id()])

    def test_add_node(self):
        w = Workflow("test_add_node")
        inp = Input("inp", String())
        stp = Step("stp", Cat())
        w.add_items([inp, stp])
        self.assertEqual(len(w._inputs), 1)
        self.assertEqual(len(w._steps), 1)
        self.assertEqual(len(w._outputs), 0)
        self.assertEqual(w._labels[inp.id()].id(), inp.id())
        self.assertEqual(w._labels[stp.id()].id(), stp.id())

    def test_add_qualified_edge(self):
        w = Workflow("test_add_edge")
        inp = Input("inp", String())
        stp = Step("stp", Echo())  # Only has one input, with no output
        w.add_items([inp, stp])
        e = w.add_edge(inp, stp.inp)

        self.assertEqual(e.start.id(), inp.id())
        self.assertEqual(e.finish.id(), stp.id())
        self.assertIsNone(e.stag)
        self.assertEqual(e.ftag, next(iter(stp.requires())))

    def test_add_edge(self):
        w = Workflow("test_add_edge")
        inp = Input("inp", String())
        stp = Step("stp", Echo())       # Only has one input, with no output
        w.add_items([inp, stp])
        e = w.add_edge(inp, stp)

        self.assertEqual(e.start.id(), inp.id())
        self.assertEqual(e.finish.id(), stp.id())
        self.assertIsNone(e.stag)
        self.assertEqual(e.ftag, next(iter(stp.requires())))

    def test_anonymous_add_edge(self):
        w = Workflow("test_add_edge")
        inp = Input("inp", String())
        stp = Step("stp", Echo())       # Only has one input, with no output
        # w.add_items([inp, stp])
        e = w.add_edge(inp, stp)

        self.assertEqual(e.start.id(), inp.id())
        self.assertEqual(e.finish.id(), stp.id())
        self.assertIsNone(e.stag)
        self.assertEqual(e.ftag, next(iter(stp.requires())))

    def test_anonymous_add_qualified_edge(self):
        w = Workflow("test_add_edge")
        inp = Input("inp", String())
        stp = Step("stp", Echo())       # Only has one input, with no output
        # w.add_items([inp, stp])
        e = w.add_edge(inp, stp.inp)

        self.assertEqual(e.start.id(), inp.id())
        self.assertEqual(e.finish.id(), stp.id())
        self.assertIsNone(e.stag)
        self.assertEqual(e.ftag, next(iter(stp.requires())))

    def test_pipe(self):
        w = Workflow("test_add_edge")
        inp = Input("tarred", TarFile())
        stp = Step("stp", Untar())  # Only has one input, with no output
        out = Output("outp", Array(File()))

        w.add_items([inp, stp, out])
        w.add_pipe(inp, stp, out)

        # the nodes are usually internal
        inp_node = w._labels[inp.id()]
        stp_node = w._labels[stp.id()]
        out_node = w._labels[out.id()]

        self.assertEqual(len(inp_node.connection_map), 0)
        self.assertEqual(len(stp_node.connection_map), 1)
        self.assertEqual(len(out_node.connection_map), 1)

        e1: Edge = next(iter(stp_node.connection_map.values()))
        e2: Edge = next(iter(out_node.connection_map.values()))

        self.assertEqual(e1.start.id(),  inp.id())
        self.assertEqual(e1.finish.id(), stp.id())
        self.assertEqual(e2.start.id(),  stp.id())
        self.assertEqual(e2.finish.id(), out.id())

    def test_qualified_pipe(self):
        w = Workflow("test_add_edge")
        inp = Input("tarred", TarFile())
        stp = Step("stp", Untar())  # Only has one input, with no output
        out = Output("outp", Array(File()))

        w.add_items([inp, stp, out])
        w.add_pipe(inp, stp.files, out)

        # the nodes are usually internal
        inp_node = w._labels[inp.id()]
        stp_node = w._labels[stp.id()]
        out_node = w._labels[out.id()]

        self.assertEqual(len(inp_node.connection_map), 0)
        self.assertEqual(len(stp_node.connection_map), 1)
        self.assertEqual(len(out_node.connection_map), 1)

        e1: Edge = next(iter(stp_node.connection_map.values()))
        e2: Edge = next(iter(out_node.connection_map.values()))

        self.assertEqual(e1.start.id(), inp.id())
        self.assertEqual(e1.finish.id(), stp.id())
        self.assertEqual(e2.start.id(), stp.id())
        self.assertEqual(e2.finish.id(), out.id())

    def test_subworkflow(self):

        w = Workflow("test_subworkflow")

        sub_w = Workflow("subworkflow")
        sub_inp = Input("sub_inp", TarFile())
        sub_stp = Step("sub_stp", Untar())
        sub_out = Output("sub_out", Array(File()))
        sub_w.add_items([sub_inp, sub_stp, sub_out])
        sub_w.add_pipe(sub_inp, sub_stp, sub_out)

        inp = Input("inp", TarFile())
        stp = Step("stp_workflow", sub_w)
        out = Output("out", Array(File()))
        w.add_items([inp, stp, out])
        w.add_pipe(inp, stp, out)

        w.dump_cwl(to_disk=True)

        self.assertTrue(True)

    def test_add_default_value(self):

        w = Workflow("Workflow with default value")
        default_value = "myFile.tar"

        inp1 = Input("inp1", Array(File()))
        step = Step("tar", Tar())
        out = Output("tarred", TarFile())

        w.add_pipe(inp1, step, out)
        w.add_default_value(step.tarName, default_value)
        cwl, _, _ = w.cwl(is_nested_tool=False, with_docker=False)

        self.assertIn("steps", cwl)
        steps = cwl["steps"]
        self.assertIn(step.id(), steps)
        inp = steps[step.id()]
        self.assertIn("in", inp),
        in_map = inp["in"]
        self.assertIn("tarName", in_map)
        tarName_props = in_map["tarName"]
        self.assertIn("default", tarName_props)
        self.assertEqual(tarName_props["default"], default_value)


