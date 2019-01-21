
tabix
=====
*bioinformatics*

Documentation
-------------

URL
******
`http://www.htslib.org/doc/tabix.html <http://www.htslib.org/doc/tabix.html>`_

Docstring
*********
tabix – Generic indexer for TAB-delimited genome position files
    
    Tabix indexes a TAB-delimited genome position file in.tab.bgz and creates an index file (in.tab.bgz.tbi or 
    in.tab.bgz.csi) when region is absent from the command-line. The input data file must be position sorted 
    and compressed by bgzip which has a gzip(1) like interface.

    After indexing, tabix is able to quickly retrieve data lines overlapping regions specified in the format 
    "chr:beginPos-endPos". (Coordinates specified in this region format are 1-based and inclusive.)

    Fast data retrieval also works over network if URI is given as a file name and in this case the 
    index file will be downloaded if it is not present locally.

*This page was automatically generated*
