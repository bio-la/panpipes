#downsampling script
## written for this pipeline by Charlotte Rich-Griffin 2020-09-30

import scanpy as sc
import argparse
import pandas as pd
from muon import MuData
from anndata import AnnData
import muon as mu
import re

from panpipes.funcs.io import write_obs
from panpipes.funcs.processing import downsample_mudata


import sys
import logging
L = logging.getLogger()
L.setLevel(logging.INFO)
log_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s: %(levelname)s - %(message)s')
log_handler.setFormatter(formatter)
L.addHandler(log_handler)

sc.settings.verbosity = 0  # verbosity: errors (0), warnings (1), info (2), hints (3)

# parse arguments
parser = argparse.ArgumentParser()

parser.add_argument('--input_mudata',
                    default='data/mudata-n5000-filt.h5ad',
                    help='')
parser.add_argument('--output_mudata',
                    default='data/mudata-n5000-filt.h5ad',
                    help='')
parser.add_argument('--sampleprefix', default="", help="")
parser.add_argument('--downsample_value', default=None,
                    help='')
parser.add_argument('--downsample_col', default=None,
                    help='')
parser.add_argument('--intersect_mods', default=None,
                    help='comma separated string of modalities we want to intersect_obs on')                 


parser.set_defaults(verbose=True)
args, opt = parser.parse_known_args()
L.info("Running with params: %s", args)

# load data
L.info("Reading in MuData from '%s'" % args.input_mudata)
mdata = mu.read(args.input_mudata)

if isinstance(mdata, AnnData):
    # convert anndata to muon
    mdata=MuData({'mod':mdata})

orig_obs = mdata.obs

L.info("Before downsampling: number of cells per sample \n%s" % mdata.obs.sample_id.value_counts())


if args.downsample_col == "None":
    args.downsample_col = None

if args.intersect_mods is None:
    # we assume all mods
    mods = list(mdata.mod.keys())
else:
    mods = args.intersect_mods.split(',')


# remove unused categories in batch col
if args.downsample_col is not None:
    mdata.obs[args.downsample_col] = mdata.obs[args.downsample_col].cat.remove_unused_categories()

# do the downsample.
L.info("Downsampling modalities %s" % mods)
downsample_mudata(mdata, nn=int(args.downsample_value),
    cat_col=args.downsample_col,
    mods = mods,
    inplace=True)
print(mdata)


mdata.update()
L.info("After downsampling: number of cells per sample \n%s" % mdata.obs.sample_id.value_counts())

# write out the observations
prefix = re.sub("\\.(.*)", "", args.output_mudata)
L.info("Saving updated obs in a metadata tsv file to " + prefix + "_downsampled_cell_metadata.tsv")
write_obs(mdata, output_prefix=prefix, output_suffix="_downsampled_cell_metadata.tsv")

L.info("Saving updated MuData to '%s'" % args.output_mudata)
mdata.write(args.output_mudata)

L.info("Done")