nextflow.enable.dsl=2

include { FGS } from '../modules/FGS'
include { POST_PROCESSING } from '../modules/post_processing'
include { PRODIGAL } from '../modules/prodigal'

workflow COMBINED_GENE_CALLER {

    take:
    ch_input_fasta
    ch_maskfile

    main:
    FGS(
        ch_input_fasta,
        ch_input_fasta
    )

    POST_PROCESSING(
        ch_maskfile,
        FGS.out.predicted_proteins_faa,
        FGS.out.predicted_proteins_ffn,
        FGS.out.predicted_proteins_out,
        PRODIGAL.out.predicted_proteins_faa,
        PRODIGAL.out.predicted_proteins_ffn,
        PRODIGAL.out.predicted_proteins_out,
        ch_input_fasta
    )

    PRODIGAL(
        ch_input_fasta
    )

    emit:
    predicted_proteins = POST_PROCESSING.out.predicted_proteins
    predicted_seq = POST_PROCESSING.out.predicted_seq

}


workflow COMBINED_GENE_CALLER {

    take:
    ch_input_fasta
    ch_maskfile

    main:
    FGS(
        ch_input_fasta,
        ch_input_fasta
    )

    FGS(
        ch_input_fasta,
        ch_input_fasta
    )

    POST_PROCESSING(
        ch_maskfile,
        FGS.out.predicted_proteins_faa,
        FGS.out.predicted_proteins_ffn,
        FGS.out.predicted_proteins_out,
        ch_input_fasta
    )

    POST_PROCESSING(
        ch_maskfile,
        FGS.out.predicted_proteins_faa,
        FGS.out.predicted_proteins_ffn,
        FGS.out.predicted_proteins_out,
        ch_input_fasta
    )

    emit:
    predicted_proteins = POST_PROCESSING.out.predicted_proteins
    predicted_seq = POST_PROCESSING.out.predicted_seq

}