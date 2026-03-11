# Analyzing Work-Efficiency of Relaxed Single Source Shortest Path Algorithms
This git repo is for a Master Thesis at Chalmers Universty of Technology


## How to build
```git submodule update --init --recursive```

```cd multiqueue_experiments/```
```cmake --preset default```

```cmake --build build``` 

A tip is to add the -j flag to the build command to run on multiple threads, eg.

```cmake --build build -j16``` 