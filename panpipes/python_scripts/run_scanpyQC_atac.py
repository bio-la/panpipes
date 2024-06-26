'''
scanpy QC script ATAC
'''
from calendar import c
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import matplotlib.pyplot as plt
plt.ioff()
import numpy as np
import pandas as pd
import scanpy as sc
import anndata as ad
import os
import argparse
import seaborn as sns
from muon import atac as ac
import muon as mu

import sys
import logging
L = logging.getLogger()
L.setLevel(logging.INFO)
log_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s: %(levelname)s - %(message)s')
log_handler.setFormatter(formatter)
L.addHandler(log_handler)

from panpipes.funcs.io import  write_obs
from panpipes.funcs.processing import check_for_bool


sc.settings.verbosity = 3

parser = argparse.ArgumentParser()

parser.add_argument("--sampleprefix",
                    default="",
                    help="prefix to prepend when saving the metadata file")
parser.add_argument("--input_anndata",
                    default="adata_unfilt.h5ad",
                    help="")
parser.add_argument("--outfile",
                    default="adata_unfilt.h5ad",
                    help="")
parser.add_argument("--figdir",
                    default="./figures/",
                    help="path to save the figures to")
parser.add_argument("--figure_suffix",
                    default="_qc-plot.png",
                    help="figures filename suffix to be appended to figures/umap")
parser.add_argument('--is_paired',
                    default=True,
                    help='If ATAC data comes from a paired multiome experiment or is a standalone ATAC.')
parser.add_argument('--paired_rna',
                    default=None,
                    help='If ATAC data comes from standalone ATAC, do you have an rna anndata with obs.interval that you can use for Tss')
parser.add_argument('--tss_coordinates',
                    default=None,
                    help='If ATAC data comes from standalone ATAC, do you have a TSS annotation file? mm10 or hg19 supported')
parser.add_argument("--atac_qc_metrics",
                    default="",
                    help="comma sep list of params to quantify and plot")
parser.add_argument("--use_muon",
                    default="",
                    help="")
                



args, opt = parser.parse_known_args()
L.info("Running with params: %s", args)

figdir = args.figdir

if not os.path.exists(figdir):
    os.mkdir(figdir)

sc.settings.figdir = figdir
sc.set_figure_params(scanpy=True, fontsize=14, dpi=300, facecolor='white', figsize=(5,5))
args.is_paired= check_for_bool(args.is_paired)

if args.is_paired:
    args.use_muon= True
    L.info("I'm working on a multiome experiment")
else:
    L.info("QC'ing an atac standalone assay")

L.info("Reading in MuData from '%s'" % args.input_anndata)
mdata = mu.read(args.input_anndata)
atac = mdata.mod['atac']


# CALCULATE SOME GENERAL QC metrics
L.info("Calculating QC metrics with scanpy.pp.calculate_qc_metrics()")
sc.pp.calculate_qc_metrics(atac, percent_top=None, log1p=False, inplace=True)
checkfiles = 'files' in list(atac.uns.keys()) 
if checkfiles:
    if atac.uns["files"]["fragments"] is not None:
        L.info("Computing nucleosome signal")
        ac.tl.nucleosome_signal(atac, n=1e6)
        atac.obs['NS']=np.where(atac.obs['nucleosome_signal'] >3, 'trinucleosome', 'mono_trinucleosome')
        L.info("Plotting nucleosome signal as histogram")
        mu.pl.histogram(atac, "nucleosome_signal", groupby='NS')
        plt.savefig(os.path.join(figdir, "nucleosome.png"))


if args.is_paired & checkfiles :
    if atac.uns["files"]["fragments"] is not None:
        #ac.tl.get_gene_annotation_from_rna(mdata['rna'])  # accepts MuData with 'rna' modality or mdata['rna'] AnnData directly if
        L.info("Computing TSS enrichment")
        tss = ac.tl.tss_enrichment(mdata, n_tss=1000) # by default, features=ac.tl.get_gene_annotation_from_rna(mdata), but it could work with a custom annotation 
        tss.obs['tss_class'] = np.where(tss.obs["tss_score"]>2 , "High","Low") 
        L.info("Plotting TSS enrichment")
        ac.pl.tss_enrichment(tss, color="tss_class")
        plt.savefig(os.path.join(figdir, "tss_enrichment.png"))
        mdata.mod["tss"] = tss # add the tss anndata to the mudata, no point in saving it outside
        
else:
    #since we're here, change some names
    for col in atac.obs.columns:
        if "peak_region_fragments" in col:
            L.info("Saving '%s' to column 'atac_peak_region_fragments'" % col)
            atac.obs["atac_peak_region_fragments"] = atac.obs[col]
        if col.endswith("mitochondrial"):
            if atac.obs["atac_mitochondrial_reads"] is not None:
                L.info("Saving '%s' to column 'atac_mitochondrial_reads'" % col)
                atac.obs["atac_mitochondrial_reads"] = atac.obs[col]
        if col.endswith("passed_filters"): 
            L.info("Saving '%s' to column 'atac_fragments'" % col) 
            atac.obs['atac_fragments']= atac.obs[col]
    
    if args.paired_rna is not None:
        L.info("Reading in paired RNA data from '%s" % args.paired_rna)
        rna = mu.read(args.paired_rna)
        L.info("Running muon.atac.tl.get_gene_annotation_from_rna()")
        tss_features = ac.tl.get_gene_annotation_from_rna(rna)
    elif args.tss_coordinates is not None:
        L.info("Reading in TSS features from '%s'" % args.tss_coordinates)
        tss_features = pd.read_csv(args.tss_coordinates, index_col=0, sep="\t")
        L.info("Computing TSS enrichment with features from tsv file")
        tss_data = ac.tl.tss_enrichment(atac, features= tss_features, n_tss=1000)
        L.info("Creating column 'tss_class' in .obs")
        tss_data.obs['tss_class'] = np.where(tss_data.obs["tss_score"]>2 , "High","Low") 
        L.info("Plotting TSS enrichment")
        ac.pl.tss_enrichment(tss_data, color="tss_class")
        plt.savefig(os.path.join(figdir, "tss_enrichment.png"))
        mdata.mod["tss"] = tss_data
    
if args.paired_rna is None :
    if args.tss_coordinates is None:
        L.warning("""No RNA AnnData and feature coordinate file was provided to
        run the TSS enrichment analysis, this will be skipped
        """)

# calc pct fragments in peaks 
if "atac_fragments" in atac.obs.columns:
    L.debug("Adding percent fragments in peaks")
    atac.obs['pct_fragments_in_peaks']=atac.obs['atac_peak_region_fragments']/atac.obs['atac_fragments'] *100          

#PLOTS

L.info("Plotting violin plots of QC vars")
if args.atac_qc_metrics is not None:
    qc_vars=args.atac_qc_metrics.split(",")
    qc_vars= [a.strip() for a in qc_vars]
else:
    qc_vars = ["n_genes_by_counts","total_counts","pct_fragments_in_peaks"]

qc_vars_plot = [gg for gg in qc_vars if gg in atac.obs.columns]
sc.pl.violin(atac, qc_vars_plot, 
             jitter=0.4, multi_panel=True, save = "atac_metrics_violin.png")

mdata.update()

L.info("Saving updated obs in a metadata tsv file to ./" + args.sampleprefix + "_cell_metadata.tsv")
write_obs(mdata, output_prefix=args.sampleprefix, 
        output_suffix="_cell_metadata.tsv")

L.info("Saving updated MuData to '%s'" % args.outfile)
mdata.write(args.outfile)

L.info("Done")

