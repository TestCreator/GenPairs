#  Generate an all-pairs covering test suite
#
# (c) 2007 University of Oregon and Michal Young
# All rights reserved.  
#
License = """
(C) 2007,2017 University of Oregon and Michal Young. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright
  notice, this list of conditions and the following disclaimer.  

* Redistributions in binary form must reproduce the above copyright
  notice, this list of conditions and the following disclaimer in the
  documentation and/or other materials provided with the
  distribution. 

* Neither the name of the University of Oregon nor the names of its
  contributors may be used to endorse or promote products derived
  from this software without specific prior written permission.

This software is provided by the copyright holders and contributors
"as is" and any express or implied warranties, including, but not
limited to, the implied warranties of merchantability and fitness for
a particular purpose are disclaimed. In no event shall the copyright
owner or contributors be liable for any direct, indirect, incidental,
special, exemplary, or consequential damages (including, but not
limited to, procurement of substitute goods or services; loss of use,
data, or profits; or business interruption) however caused and on any
theory of liability, whether in contract, strict liability, or tort
(including negligence or otherwise) arising in any way out of the use
of this software, even if advised of the possibility of such damage.
"""

usage = """Usage: 

# To read a specification (foo.cp) and print the test vector in human-readable
# format: 
   python genpairs.py < foo.cp   

# To read a partial suite of test cases (tests.txt) in CSV format, 
# plus a test specification, and report which pairs of values have not
# been covered: 
  python genpairs.py --csv --initial-suite tests.txt -o -v -p < foo.cp

# To read the same as above, and then produce a test suite that 
# covers the missing pairs: 
  python genpairs.py --csv --initial-suite tests.txt  < foo.cp

"""

#
#  An item is a pair  (slot number, value)
#  An itempair is a pair (item, item), that is, ((slot, value), (slot, value))
#  An obligation is a pair (the two items must occur together in some case)
#  An exclusion is a pair (the two items must not occur together in any case)
#  A case is a list (array) with n columns
#
# Representations: 
#    A test case is represented as a list, indexed by column (category)
#    A test suite is a list of test cases
#    An item is a tuple, and an itempair is a tuple
#
#  Like AETG and several other covering array generators, the outer
#  loop will generate test cases, and the inner loops try to fulfill
#  as many test obligations as possible with each test case.
#   
# Data structures: 
#   We will record obligations in three different data structures, 
#   for different forms of quick access: 
#  ObsList is a list of obligations, some of which may 
#     already have been fulfilled (deletion is lazy). We may scramble 
#     this list so we don't have an unfortunate ordering. 
#  Outstanding is a set of all the obligations still outstanding.
#  ObsByCol is a dictionary obligations by column, also updated lazily.
#  
#  Exclude is a dictionary mapping items to lists of item.
#

import sys    ## for file handling
import random ## for shuffling lists 
import csv    ## for reading and writing test suites 

## Constants (other than tokens for parsing)
DontCare = "_"

## Configuration parameters
DBG = False ## Debugging mode, on (true) or off (false)
DBGp = False ## Performance debugging, December 2006
maxCandidates = 50 ## Bigger = better solutions, smaller = faster 

## Platform compatibility 
# ----------------------------------------
import six # Python 2 and 3 compatibility
from six import print_    

## Logging
#
import logging
logging.basicConfig(format='%(levelname)s:%(message)s',
                        level=logging.WARNING)
Log = logging.getLogger(__name__)

# Debug messages
def dbg(*msg):
    parts = [ str(x) for x in msg ]
    msg_string = " ".join(parts)
    Log.debug(msg_string)

# Performance debug messages
def dbg_p(*msg): 
    if DBGp: 
        dbg(*msg)
# ------------------------------------    

## User arguments
from optparse import OptionParser 
optparser = OptionParser(usage=usage)
optparser.set_defaults(output_format="plain")

optparser.add_option("-d", "--debug",
		  help="Print a lot of debugging messages",
		  action="store_true", default=False, dest="debug")

optparser.add_option("-l", "--license",
		     help="Print license terms (and then quit)", 
		     action="store_true",default=False, dest="license")

optparser.add_option("--csv", "-c",  "--comma-separated-values",
		  action="store_const", dest="output_format", 
		  const = "csv", 
                  help = """Output format is comma-separated-values
                         (suitable as input to Excel and other spreadsheets, 
                         genpairs with the -i option, and some other 
                         programs).""")

optparser.add_option("-v", "--varying", "--varying-columns-only", 
		     action="store_true", default=False, dest="varying",
                     help="""Include only categories with more than one 
                             non-error and non-single value""")

optparser.add_option("-s", "--singles", "--singles-only",
		     action="store_false", default=True, dest="combinations",
                     help="""Print only test cases covering 'error' 
                             and 'single' values.""") 

optparser.add_option("-o", "--omit-singles",
		     action="store_false", default=True, dest="singles",
                     help = """Do not produce test cases covering 'single'
                               or 'error' values.""")

optparser.add_option("-i", "--initial", "--initial-suite",
                     action="append", default = [], dest="initial_suite",
                     help="""Read initial test suite (in csv format).  Often 
                             used together with -p""")

optparser.add_option("-p", "--pairs", "--print-pairs",
                     action="store_true", default=False, dest="pairs",
                     help="""Report pairs not covered by initial test suites.
                             (Useful only with --initial)""")

(UserOptions, UserArgs) = optparser.parse_args()
Log.info("User options: ",  UserOptions)
if UserOptions.debug :
    print_("Enabling debugging")
    DBG=True
    Log.setLevel(logging.DEBUG)


## Primary data structures
CategoriesList = [ ]    ## List of category names (in order given)
     ## The CategoriesList can also be considered the test case schema
CategoriesValues = [ ]  ## List of value sets
Singles = [] ## List of (slot,value,kind) where kind is "single" or "error"
Excludes = set()  ## Set of ((slot,value),(slot,value)) (not symmetric)

ObsList = [ ]       # All obligations, but only one direction 
Outstanding = set() # All obligations, but only one direction 
ObsByCol = {}       # Per column, both directions 

SingleColumns =   [ ] # Columns with just one (non-error, non-single) choice
MultipleColumns = [ ] # Complement of SingleColumns -- pairs are from these

NCol = 0          # ==len(CategoriesList), set after parsing

## Temporary, for building excludes
PropsSlots      = { } # For each property name, set of slots with it
CategoriesProps = { } # For each category, all props on any values
ValueProps =   { } # Map (slot,value) pair to list of condition names
ValueIfs =     [ ]  #  List of (value, slot, condition) triples
ValueExcepts = [ ]  # List of (value, slot, condition) triples


## What we build
Suite = [ ] ## List of test cases

## Instrumentation
INSTR_N_Comparisons = 0


# ----------  Read spec file using a simple LL parser ----

# Consts for token classification 
EOF = "<EOF>"
CategoryToken = "<CAT>"
ValueToken = "<VAL>"
IfToken = "<IF>"
PropToken = "<PROP>"
ExceptToken = "<EXCEPT>"
ErrorToken = "<ERROR>"
SingleToken = "<SINGLE>"
EOFToken = EOF

def tokenClass( tok ) : 
    if tok == EOF : return EOFToken
    if tok.endswith(":") : return CategoryToken
    if tok == "if" : return IfToken
    if tok == "prop" : return PropToken
    if tok == "except" : return ExceptToken
    if tok == "single" : return SingleToken
    if tok == "error" : return ErrorToken
    return ValueToken

# Generator to produce tokens, one by one
# 
def getToken() : 
    while 1:
        s = sys.stdin.readline()
        if not s: 
            dbg("#DBG <<EOF reached>>")
            yield EOF
            return
        commentPos = s.find("//");
        if commentPos >= 0 : 
            s = s[0:commentPos]
        for word in s.split() : 
               dbg("#DBG <<%s: %s>>" % ( word, tokenClass(word)  ) )
               yield word

Token = "UNINITIALIZED"
tokenStream = getToken()

def parse(): 
    global Token
    global NCol 
    Token = six.next(tokenStream)
    parseSpec()
    NCol = len(CategoriesList) 

def parseSpec(): 
    global Token
    dbg("#DBG (parseSpec)")
    if Token == EOF : return [ ]
    if tokenClass( Token ) != CategoryToken : 
        print_("Syntax error on ", Token, " looking for 'category:'")
        print_("Skipping to next category")
        ## Error recovery to next category
        while tokenClass( Token ) != CategoryToken : 
            if tokenClass( Token ) == EOF : 
                print_("Discarding rest of file")
                return [ ] 
            Token = tokenStream.next()
        print_("Resuming from" , Token)
    category = Token[0:-1]
    Token = six.next(tokenStream)
    values = parseValues()
    dbg("#DBG Parsed: ", category, " ::= ", values)
    slotNum = len(CategoriesList)
    CategoriesList.append( category ) 
    vlist = [ ] 
    CategoriesValues.append(vlist)
    CategoriesProps[ category ] = [ ] 
    for valDesc in values : 
        val = valDesc[0] ## The name of the value itself
        ## Postpone marking val as a possible value of the property
        ## until we know whether it is a singleton 
        singleton = False
        ValueProps[ (slotNum, val) ] = [] ## List of its properties
        for cond in valDesc[1:] : 
            kind = nameOf(cond)
            condVal = valOf(cond)
            if kind == "prop" : 
                CategoriesProps[ category ].append(condVal)
                ValueProps[ (slotNum, val ) ].append(condVal)
                if condVal not in PropsSlots : 
                    PropsSlots[condVal] = set()
                PropsSlots[condVal].add(slotNum) 
            elif kind == "if" : 
                ValueIfs.append( (val, slotNum, condVal ) ) 
            elif kind == "except" : 
                ValueExcepts.append( (val, slotNum, condVal) ) 
            elif kind == "error" or kind == "single" : 
                Singles.append( (val, slotNum, kind) ) 
                singleton = True
            else : 
                print_("*ERR* Unrecognized condition attribute:", cond)
        if not singleton:  vlist.append( val )

    parseSpec()


def parseValues(): 
    global Token
    dbg("#DBG (parseValues)")
    values = [ ] 
    while tokenClass( Token ) == ValueToken : 
        val = parseValue()
        dbg("#DBG (parsed value: ", val, ")")
        values.append( val )
    return values

def parseValue(): 
    global Token
    dbg("#DBG (parseValue, looking at ", Token, ")")
    if tokenClass( Token ) != ValueToken : 
        print_("Syntax error, expecting value, saw ", Token )
        return [ "--bogus--"] 
    value = [ Token ]
    Token = six.next(tokenStream)
    conditions = parseConditions()
    dbg("#DBG parseValue returns", value + conditions)
    return value + conditions 

def parseConditions(): 
    global Token 
    dbg("#DBG (parseConditions)")
    if tokenClass( Token ) == ErrorToken : 
        Token = six.next(tokenStream)
        return [("error", None )] + parseConditions()
    if tokenClass( Token ) == SingleToken : 
        Token = six.next(tokenStream)
        return [("single", None)] + parseConditions()
    if tokenClass( Token ) == IfToken : 
        Token = six.next(tokenStream) 
        ifcond = Token
        Token = six.next(tokenStream)
        return [("if" , ifcond)] + parseConditions()
    if tokenClass( Token ) == PropToken : 
        Token = six.next(tokenStream) 
        condname = Token
        Token = six.next(tokenStream)
        return [("prop" , condname)] + parseConditions()
    if tokenClass( Token ) == ExceptToken : 
        Token = six.next(tokenStream) 
        condname = Token
        Token = six.next(tokenStream)
        return [("except" , condname)] + parseConditions()
    dbg("#DBG No more conditions")
    return [ ]


# -------------- The form of a pair (obligation or exclusion) -----

def makePair( s1, v1, s2, v2 ): 
    return ((s1, v1), (s2, v2)) 

def reversePair( pair ): 
    return ( pair[1], pair[0] )

# Each item in the pair is a <slot,value> or <name,value> pair
def slotOf( tuple ): 
    return tuple[0]

def nameOf( tuple ): 
    return tuple[0]

def valOf( tuple ): 
    return tuple[1]

# --------------- Build initial data structures ---- 

# Single columns are those in which all but one value is 
# listed as a "single" or "error" choice, i.e., for pairs 
# generation the value will be fixed.  We can save some time by 
# always fixing these at the beginning of pairs generation, and 
# we can save space in output by suppressing them. 
# (Note they may still participate in excludes.) 
#
# We'll identify the multiples (non-single columns) as well, 
# because they are useful in several places
# 
def identifySingles() : 
    for slot in range(len(CategoriesList)) : 
        if len(CategoriesValues[slot]) == 0 : 
            print_("Warning: No non-singular value choices for ",
                       CategoriesList[slot], 
                       "; Pairs generation will fail.")
        elif len(CategoriesValues[slot]) == 1 : 
            SingleColumns.append(slot)
        else: 
            MultipleColumns.append(slot)
    

# Obligations depend on excludes, so call makeExcludes before 
# calling makeObligations 
#
def makeExcludes() : 
    # Excludes that come from "except" clauses
    for ExceptCond in ValueExcepts : 
        val, slot, cond = ExceptCond
        for conflict_slot in PropsSlots[ cond ] : 
            for cs_value in CategoriesValues[ conflict_slot ] : 
                if cond in ValueProps[ (conflict_slot, cs_value) ] : 
                    Excludes.add( makePair( slot, val, conflict_slot, cs_value))
    # Excludes that come from "if" clauses --- reverse sense 
    for IfCond in ValueIfs : 
        val, slot, cond = IfCond
        for conflict_slot in PropsSlots[ cond ] : 
            for cs_value in CategoriesValues[ conflict_slot ] : 
                if cond not in ValueProps[ (conflict_slot, cs_value) ] : 
                    Excludes.add( makePair( slot, val, conflict_slot, cs_value))


def makeObligations() : 
   if DBG:
       print_("--- Creating obligations list ---")
   keys = CategoriesList
   nslots = len(keys)
   for i in range(nslots): 
       ObsByCol[i] = []
   for i in MultipleColumns : 
       for v1 in CategoriesValues[i] : 
           i_item = (i, v1)
           for j in range(i+1,nslots) : 
               ## if j in SingleColumns: continue ## 
               ##  --- short cut doesn't work if only one varying column -- 
               for v2 in CategoriesValues[j] : 
                   j_item = (j, v2)
                   obforward = (i_item, j_item)
                   obbackward = (j_item, i_item)
                   if obforward not in Excludes and obbackward not in Excludes: 
                       ObsList.append(obforward)
                       Outstanding.add(obforward)
                       ObsByCol[ i ].append(obforward)
                       ObsByCol[ j ].append(obbackward)
   random.shuffle(ObsList)
   dbg("--- ObsList complete, ", len(ObsList), " obligations  ---")

#  When we complete a test case, we remove obligations from
#  the outstanding obligations list.  The other lists are 
#  cleared lazily, when we bring up an obligation. 
#
def clearObligations(testcase) : 
    testCaseValue = 0
    for i in range( len(testcase) ): 
        for j in range ( i+1, len(testcase) ): 
            ob = makePair(i, testcase[i], j, testcase[j]) 
            if ob in Outstanding: 
                Outstanding.remove(ob)
                testCaseValue = testCaseValue + 1
    dbg("*** Value ", testCaseValue, testcase )


# ---------------------------------------------------------

#
# Is a given (slot,value) pair compatible with the test case so far? 
# 
def compatible( item, testcase ) : 
    slot, val = item 
    if ( testcase[ slot ] != DontCare and testcase[slot] != val) : 
        return False
    for tslot in range(len(testcase)) : 
        if ((slot, val), (tslot, testcase[tslot])) in Excludes: 
            return False
        if ((tslot, testcase[tslot]),(slot,val)) in Excludes: 
            return False
    return True

# ---------------------------------------------------------

def MakeTuple ( len ): 
   newList = []
   for i in range(0,len): 
      newList.append(DontCare)
   return newList


def CreateCase(): 
    seedObligation = ObsList.pop() 
    while seedObligation not in Outstanding: 
        if (len(ObsList) == 0): return
        seedObligation = ObsList.pop() 
    s1, v1 = seedObligation[0]
    s2, v2 = seedObligation[1]
    testcase = MakeTuple( len(CategoriesList) ) 
    testcase[s1] = v1
    testcase[s2] = v2
    for slot in SingleColumns : 
        testcase[slot] = CategoriesValues[slot][0]
    dbg("#DBG === Attempting tuple seeded with", testcase)
    columnOrder = list(range( len(CategoriesList) ) )
    random.shuffle(columnOrder)
    if ( completeCase( columnOrder, testcase ) ) : 
        Suite.append( testcase )
        clearObligations( testcase )
    else: 
        CaseMessage( "Warning - No pair possible: ", testcase ) 
	
def CreateSingles(): 
    for single in Singles: 
        CreateSingle(single)

def CreateSingle( single ): 
    testcase = MakeTuple( len(CategoriesList) ) 
    columnOrder = list(range( len(CategoriesList) ) )
    random.shuffle(columnOrder)
    value, slot,  kind = single
    dbg("#DBG single obligation: ",  slot, value, kind)
    testcase[slot] = value
    if completeCase( columnOrder, testcase ) : 
        Suite.append( testcase )
    else: 
        CaseMessage( "Warning - No pair possible: ", testcase )


def completeCase( columnOrder, testcase ) : 
    if len (columnOrder) == 0 : 
        dbg_p("#DBG: *** Success: ", testcase)
        return True
    dbg_p("#DBG * Attempting to complete", testcase )
    col = columnOrder[0]
    if testcase[col] != DontCare: 
        dbg_p("#DBG *  Skipping column ", col, " (already filled in)")
        return completeCase( columnOrder[1:], testcase )
    dbg("#DBG ***Trying columns ", columnOrder, " in ",  testcase)

    # How shall we fill this DontCare with something useful? 
    # Let's try for an outstanding obligation.
    # Dec 2006 --- Let's look at all the outstanding obligations
    #   and choose the one with highest score.  This is fairly expensive 
    # (10^20 takes about 9 minutes wall time on G4 laptop), so now we 
    # set a limit (maxCandidates) on number of candidates considered 
    colObs = ObsByCol[col]
    candidates = [ ] 
    obindex = 0
    while obindex < len(colObs) and len(candidates) < maxCandidates : 
        ob = colObs[obindex]
        if not (ob in Outstanding or reversePair(ob) in Outstanding): 
            # Here is our lazy deletion of obligations; we 
            # clip from the end of the list
            dbg_p("#DBG * Lazy deletion")
            colObs[obindex] = colObs[ len(colObs) - 1 ]
            colObs.pop()
        else: 
            if compatible(ob[0], testcase) and compatible(ob[1], testcase): 
                dbg_p("#DBG *** Compatible", ob, testcase )
                # Score the 
                # Note one (but not both) of these may coincide with 
                # an existing element.  We'll only consider *added* value, 
                # so we score the *new* parts only. 
                value = 1 ## For at least meeting one obligation
                ((s1, v1), (s2, v2)) = ob 
                if testcase[s1] != v1 : 
                    for ccol in range( len(testcase) ): 
                        if ((s1,v1),(ccol,testcase[ccol])) in Outstanding : 
                            value = value + 1
                        if ((ccol,testcase[ccol]),(s1,v1)) in Outstanding :
                            value = value + 1
                if testcase[s2] != v2 : 
                    for ccol in range( len(testcase) ): 
                        if ((s2,v2),(ccol,testcase[ccol])) in Outstanding : 
                            value = value + 1
                        if ((ccol,testcase[ccol]),(s2,v2)) in Outstanding :
                            value = value + 1
                candidates.append( (value, ob) ) 
            obindex = obindex + 1
    candidates.sort() 
    candidates.reverse() 
    dbg_p("### Candidates: ", candidates)
    for cand in candidates: 
        (score, ((s1, v1),(s2,v2))) = cand
        old_v1 = testcase[ s1 ]
        testcase[ s1 ] = v1
        old_v2 = testcase[ s2 ]
        testcase[ s2 ] = v2
        if completeCase( columnOrder[1:] , testcase ): 
            return True
        else: 
            dbg_p("#DBG *** Rolling back ", s1, s2)
            # Restore previous values
            testcase[ s1 ] = old_v1
            testcase[ s2 ] = old_v2
    ## If we couldn't score any more obligations, can we at least
    ## fill in some compatible value and move on? 
    dbg_p("#DBG *** Trying any value, regardless of obligation")
    for val in CategoriesValues[ col ] : 
        if compatible((col,val), testcase) :
            testcase[ col ] = val
            if completeCase( columnOrder[1:], testcase ): 
                return True
            else: 
                testcase[ col ] = DontCare
    dbg_p("#DBG ** Failing to fill column ", col , " with ", testcase)
    return False
	    
# ------------------------------------------------------------
# Print Warnings (to stderr unless otherwise specified)
# ------------------------------------------------------------

def CaseMessage( msg, vector, dest=sys.stderr ) : 
    """Print a warning or error message concerning a 
    particular partially-defined test vector"""
    print_( "{} [".format(msg), end="", file=dest)
    sep=""
    for col in range(len(vector)) : 
            if vector[col] == DontCare :
                print_(sep+"_",end="", file=dest)
            else: 
                print_("{}{}={}".format(sep,CategoriesList[col],vector[col]),
                           end="", file=dest)
            sep=", "
    print_("]",file=dest)

def ObToVector( ob ) : 
    """Convert obligation to vector for debugging messages"""
    t = MakeTuple( NCol ) 
    s1,v1 = ob[0]
    s2,v2 = ob[1]
    t[s1]=v1
    t[s2]=v2
    return t
    

# ------------------------------------------------------------
# Print results
# ------------------------------------------------------------
def PrintTable( columns, descriptive_title ) : 
    if UserOptions.output_format == "csv" : 
        PrintAsCSV( columns )
    else: 
        PrintAsText( columns, descriptive_title )

def PrintAsText( columns, descriptive_title ): 
    print_(descriptive_title + ":", len(Suite), " test vectors")
    print_("")
    for slot in columns : 
        parm = CategoriesList[ slot ]
        print_("%15s" % parm  , end="")
    print_("")
    print_("_"*60)
    for t in Suite : 
        for slot in columns : 
            value =  t[slot]
            print_("%15s" % value , end="")
        print_( "" )
    print_( "" )

def PrintAsCSV(columns): 
    """ Print vectors as comma-separated values, for import 
        into a spreadsheet or other CSV-consuming application. """
    dbg("Print as CSV")
    csv_writer = csv.writer( sys.stdout, dialect=csv.excel ) 
    schema_row = [ ] 
    for slot in columns : 
        schema_row.append( CategoriesList[slot] )
    csv_writer.writerow(schema_row)
    for t in Suite : 
        dbg("write row " , t )
        csv_writer.writerow( t ) 

# ----------------

## Read an initial test suite (or several), and 
## eliminate those obligations, so we are creating 
## a test suite to fill in the remainder of the test 
## obligations. 
##
## NOTE: Currently considering only pair obligations, 
## not singletons.  We should look at single and error 
## cases first, and
##   * Not consider any test case with more than one 
##     single or error value (we don't know which will be handled
##     by the application, and we assume special case processing 
##     may miss other features, including other special cases)
##   * Not consider any pairs as being satisfied by a single 
##     or error case. 
## For now, we just assume that the initial test suite is not 
## a suite of special and error cases. 
##

class csv_dialect(csv.excel): 
    skipinitialspace=True ## Seems to have no effect

def initial_suite_clear( initial_suite ) : 
    matches = False
    reader = csv.reader( open(initial_suite, "r"), 
                         csv_dialect) ## Working yet? (No.) 
    ## First line should be schema 
    in_schema = reader.next()
    in_schema_map = [ ] 
    for i in range(len(in_schema)): 
        col = in_schema[i]
        if col in CategoriesList: 
            to_col = CategoriesList.index(col)
            in_schema_map.append(to_col)
        else: 
            print_("Warning: schema mismatch in", initial_suite)
            print_("  Column ", i, "'" +  col + "'", "not in specification")
            in_schema_map.append(-1)

    for vec in reader: 
        if len(vec) == len(in_schema) : 
            trvec = MakeTuple(len(CategoriesList))
            for i in range(len(vec)) : 
                if in_schema_map[i] != -1 : 
                    trvec[in_schema_map[i]] = vec[i]
            clearObligations( trvec ) 
        else: 
            print_("*** Warning, format mismatch with initial suite ", 
                initial_suite)
            print_("*** Expecting columns ", 
                in_schema , " but saw ",  vec)

# ----------------

## Print the set of outstanding obligations.  Typical use is when 
## we are trying to see what is missing in an initial test suite. 
## 
def print_required_pairs( ) : 
    for ob in Outstanding : 
        s1, v1 = ob[0]
        name1=CategoriesList[s1]
        s2, v2 = ob[1]
        name2=CategoriesList[s2]
        print_("%s=%s, %s=%s" % (name1, v1, name2, v2))


## ------------------------------------------------------------
## MAIN PROGRAM (after initialization above)
## ------------------------------------------------------------


# -- Respond to special diagnostic options -- 

if UserOptions.license: 
    print_(License)
    exit(0)

if UserOptions.debug: 
    print_("---------------------------")
    print_("Options in effect: ")
    print_("debug: ", UserOptions.debug)
    print_("output_format:", UserOptions.output_format)
    print_("varying:", UserOptions.varying)
    print_("combinations:", UserOptions.combinations)
    print_("singles:", UserOptions.singles)
    print_("initial_suite:", UserOptions.initial_suite)
    print_("pairs:", UserOptions.pairs)
    print_("---------------------------")


# -- Main processing: Parse the script, execute, print -- 

parse() 
identifySingles() 
makeExcludes()
makeObligations()

for suite in UserOptions.initial_suite : 
    initial_suite_clear( suite ) 


if UserOptions.pairs : 
    print_("=== Pairs required for completion ===" )
    print_required_pairs() 
    print_("=====================================")

if UserOptions.combinations : 
    while len(ObsList) > 0 : 
        CreateCase()
    if UserOptions.varying : 
        PrintTable( MultipleColumns, "Pairwise coverage, varying columns only" )
    else: 
        PrintTable( range(len(CategoriesList)), "Pairwise coverage" ) 

if UserOptions.singles : 
    Suite = [ ] 
    CreateSingles() 
    PrintTable( range(len(CategoriesList)), "Single and error vectors" ) 

