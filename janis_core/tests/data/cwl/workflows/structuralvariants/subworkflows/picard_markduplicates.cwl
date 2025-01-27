cwlVersion: v1.0
class: Workflow
label: picard_markduplicates

doc: |
  Mark duplicates

inputs:
  input: {type: File}

outputs:
  alignments: {type: File, outputSource: samtools_index/output}
  metrics: {type: File, outputSource: picard_markduplicates/metrics}

steps:
  picard_markduplicates:
    run: ../tools/picard_markduplicates.cwl
    in:
      input: input
    out: [alignments, metrics]

  samtools_index:
    run: ../tools/samtools_index.cwl
    in:
      input:
        source: picard_markduplicates/alignments
    out: [output]
