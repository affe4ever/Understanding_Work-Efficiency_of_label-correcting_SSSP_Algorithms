#Python script to run benchmrks :D
# intention is to have: 
# --build flag that runs cmake on the underlying structure with the correct flag
# -v, --verbose to print what commands are actually being run
# -r, --runs flag to decide how many times each algorithm is run
# -j, --num_threads set amount of threads both for the build and for the run
# -g, --graph selects what graph the alg should be run on
# -o, --output_dir defines output directory, output files will have the form, <name of alg>_<name of graph>_run_<N>

# additional flag functionality may include utilization of the analyze_quality