nextflow.enable.dsl=2

import groovy.json.JsonSlurper
def jsonSlurper = new JsonSlurper()

process MOVE_TO_PATHWAYS_SYSTEMS_FOLDER {
    debug true
    container "node:latest"
    publishDir "${params.outdir}/after_qc/functional_annotation_and_post_processing/move_to_pathways_systems_folder"

    input:
    path file_list

    output:
    path "${jsonSlurper.parseText(file("${task.workDir}/cwl.output.json").text)['out']}", emit: out

    script:
    """
    nodejs return_directory.js \
    > cwl.output.json \
    """

}