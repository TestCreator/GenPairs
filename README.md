# GenPairs
Combinatorial testing:  Create a pairwise covering array of test vectors from a specification of individual categories 

Status:  Under reconstruction.  Starting with a tool created by M Young in 2008 that has been used several times
in classes at USI, this repository is for a rewrite that can be part of a larger tool suite incorporating 
random test generation as well as generation of test vectors. 

genpairs.py is a simple combinatorial test vector generator written in Python. It is not as full-featured or efficient as commercial systems like AETG, but it is free and requires only a Python interpreter to run.

genpairs.py accepts input specifications in a format based loosely on category partition test specifications as originally described by Ostrand and Balcer, and as presented in Pezzè & Young, chapter 11. Details of the syntax are described below. genpairs.py uses a heuristic method similar to that of other tools, including AETG. It produces test vectors, that is, sets of choices that together specify one or test cases. As the program name implies, genpairs.cp creates test vectors that cover all pairwise value combinations. The basic pairwise coverage can be modified by a variety of constraints inspired by the category partition test suite specification method. The test vector output is in a tabular form that can then be processed further for producing actual test cases.
