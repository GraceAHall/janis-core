version 1.0

import "../tasks/BWA.wdl" as alg
import "../tasks/chunk_lists.wdl"
import "../tasks/utils.wdl" as utils 

workflow CreateAlignmentFromFamilies {
    input {
        File families_info
        ReferenceFasta references
        Int max_cores
        Boolean rm_dupli
        Boolean gatk_mchap
        Int chunk_size
    }

    call chunk_lists.SepareChunksFastqString {
        input:
            families_info=families_info,
            chunk_size = chunk_size
    }

    scatter (chunk in SepareChunksFastqString.chunks) {

        Array[Array[String]] sample_file = read_tsv(chunk)

        call alg.RunBwaAlignment {
            input:
                sampleName  = sample_file[1],
                reads       = sample_file[0],
                libraries   = sample_file[2],
                references  = references,
                max_cores   = max_cores,
                rm_dupli    = rm_dupli
        }
    }

    # Store for MCHap
    call utils.MergeBams {
            input:
                bam_files = flatten(RunBwaAlignment.bam)
    }
    

    output {
        Array[File] bam = flatten(RunBwaAlignment.bam)
        Array[File] bai = flatten(RunBwaAlignment.bai)
        Array[Array[File]] dup_metrics = RunBwaAlignment.dup_metrics
        File merged_bam = MergeBams.merged_bam
    }
}
