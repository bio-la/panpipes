import argparse
import yaml
# import scanpy as sc
import pandas as pd
# import numpy as np
# from scipy.sparse import csr_matrix
import muon as mu
import warnings
from muon._atac.tools import add_peak_annotation, locate_fragments
import squidpy as sq
from mudata import MuData
"""
this script copies the make_adata_from_csv.py that creates
ONE MUDATA PER SAMPLE, with in each ONE LAYER per modality
for cell-suspension, saves them to temp. 
concatenation of the mudatas saved in tmp happens 
in the concat_anndata.py script
"""

import sys
import logging

L = logging.getLogger()
L.setLevel(logging.INFO)
log_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s: %(levelname)s - %(message)s')
log_handler.setFormatter(formatter)
L.addHandler(log_handler)

from panpipes.funcs.io import check_filetype, load_mdata_from_multiple_files, update_intersecting_feature_names, read_yaml
from panpipes.funcs.processing import check_for_bool, add_var_mtd, update_var_index, intersection, intersect_obs_by_mod

parser = argparse.ArgumentParser()
#parser.add_argument('--mode_dictionary',default=mode_dictionary,type=json.loads)
parser.add_argument('--mode_dictionary',default="",
                    help="accepts a yaml speficication of modalities dictionary", 
                    type=yaml.safe_load)
parser.add_argument('--sample_id',
                    default=None,
                    help='')
parser.add_argument('--output_file',
                    default=None,
                    help='')
# start of spatial args
parser.add_argument('--spatial_infile', 
                    default=None,
                    help='')
parser.add_argument('--spatial_filetype', 
                    default=None,
                    help='')
parser.add_argument('--spatial_counts', 
                    default=None,
                    help='')
parser.add_argument('--spatial_metadata', 
                    default=None,
                    help='')
parser.add_argument('--spatial_transformation', 
                    default=None,
                    help='')

parser.set_defaults(verbose=True)
args, opt = parser.parse_known_args()
L.info(args)


# unimodal mu (check if all the modalities)
if isinstance(args.mode_dictionary, dict):
    mode_dictionary = args.mode_dictionary
else:
    mode_dictionary = read_yaml(args.mode_dictionary) 
#{'spatialT': True}

permf = [key for key, value in mode_dictionary.items() if value == True]
all_files = {"rna": [args.rna_infile, args.rna_filetype], #remove other modalities at the end
            "prot": [args.prot_infile, args.prot_filetype], 
            "atac": [args.atac_infile, args.atac_filetype], 
            "tcr":[args.tcr_filtered_contigs, args.tcr_filetype],
            "bcr":[args.bcr_filtered_contigs, args.bcr_filetype],
            "spatialT":[args.spatial_infile, #path, mandatory for squidpy
                        args.spatial_filetype, #needed for the load_adata_in function to call one of vizgen,visium
                        args.spatial_counts, #name of the counts file, mandatory for squidpy
                        args.spatial_metadata, #name of the metadata file, mandatory for squidpy
                        args.spatial_transformation]}
#subset to the modalities we want from permf (in this case only spatial)
all_files = {nm: x  for (nm, x) in all_files.items() if nm in permf}

[check_filetype(x[0], x[1]) for x in all_files.values()]
# read the spatial data with one of the functions inside
# load_mdata_from_multiple_files
#     |
#      -------->load_adata_in
# this function creates ONE mudata per row of the CAF file 
# and saves it with sample_id.h5mu in tmp/ 
  
if args.spatial_filetype=="vizgen":
    adata = sq.read.vizgen(path = args.spatial_infile, #path, mandatory for squidpy
                        counts_file=args.spatial_counts, #name of the counts file, mandatory for squidpy
                        meta_file = args.spatial_metadata, #name of the metadata file, mandatory for squidpy
                        transformation_file=args.spatial_transformation,
                        library_id = str(args.sample_id)) #this also has kwargs for read_10x_h5 but keep simple
elif args.spatial_filetype =="visium":
    adata = sq.read.visium(path = args.spatial_infile, #path, mandatory for squidpy
                        counts_file=args.spatial_counts, #name of the counts file, mandatory for squidpy
                        library_id = str(args.sample_id)
                        ) #this also has kwargs for read_10x_h5 but keep simple

L.info("adata is now: %s" % adata)
L.info("creating mudata")

mdata = MuData({"spatialT": adata})


#---------------
# do some extra processing on the different modalities as needed
#---------------

#make var names unique
for mm in mdata.mod.keys():
    mdata[mm].var_names_make_unique()

mdata.obs['sample_id'] = str(args.sample_id)

# copy the sample_id to each modality
for mm in mdata.mod.keys():
    print("saving sample_id to each modality")
    # mdata[mm].obs['sample_id'] = mdata.obs['sample_id']
    mdata[mm].obs['sample_id'] = mdata.obs.loc[mdata[mm].obs_names,:]['sample_id']

mdata.update()


L.info("saving data")
L.debug(mdata)
# this will write the file as anndata or muon depending on the class of mdata.
mdata.write(args.output_file)

L.info("done")

