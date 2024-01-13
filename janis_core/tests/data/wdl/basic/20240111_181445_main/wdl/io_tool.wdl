version 1.0

task IoTool {
    input {
        Int inInt = 10
        Boolean inBool
        String inFilePath = basename(inFile)
        File inFile
        File? inFileOpt
        Array[File] inFileArr
        BamBai inSecondary
    }

    command <<<
        set -e
        echo \
        ~{inInt} \
        ~{inFilePath} \
        ~{true="--flag1" false="" inBool} \
        --in-file=~{inFile} \
        ~{inFileOpt} \
        ~{sep="," inFileArr} \
        ~{inSecondary} \
        > stdout.txt
    >>>

    output {
        File outFile = inFile
        File? outFileOpt = inFileOpt
        Array[File] outFileArr = inFileArr
        BamBai outSecondary = inSecondary
        File outStdout = "stdout.txt"
    }

    parameter_meta {
        inFile: {
            description: "input file"
        }
    }
}

struct BamBai {
    File bam
    File bai
}