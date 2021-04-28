# Aggregation Dynamics

Collection of scripts for estimating aggregation dynamics from simulated and experimental data sets.

# pyCytosim

Python driver for cytosim (Python 3.7+). Consists of following scripts:

* ``import_data.py`` -- a front-end for the ``report`` cytosim executable that converts its output into Python data structures and stores its output as a pickle file;

* ``make_tiff.py`` -- a front-end for the ``play`` cytosim executable that converts binary simulation data into TIFF sequences, which are compatible with ImageJ.

# cytosim-driver

Driver scripts to run cytosim simulations:

* ``run_job.sh`` -- submit a cytosim simulation with given paramters as a batch job on a SLURM cluster
* ``run_analysis.sh`` -- run analysis using pyCytosim scripts

# pyPattern

Scripts for performing spatial correlation analysis on TIFF files
