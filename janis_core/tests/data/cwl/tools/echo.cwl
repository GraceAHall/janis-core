
#!/usr/bin/env cwl-runner
cwlVersion: v1.0
class: CommandLineTool

baseCommand: echo

inputs:
 text: 
  type: string
  inputBinding:
    position: 1

outputs:
  out:
    type: stdout