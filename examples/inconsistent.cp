// A simple, inconsistent specification.  Expected output is
// given at the end of this file
//


// col0, col1, and col2 are categories. 
col0: 
   e0 error  // e0 is an error entry.  
   e1 error  // So is e1.  They will each appear only once in output. 
   v0.0 prop v0  // v0.0 satisfies property v0
   v0.1 prop v1

col1:
   s0 single
   s1 single
   v1.0 if v0  // v1.0 must be paired with v0.0 (property v0)
   v1.1 if v1 //  v1.1 must be paired with v0.1 (property v1)

col2: 
   v2.0 if v0 if v1  // v2.0 requires properties v0 AND v1 (impossible)
   v2.1

// Expected output: 
//
// Warning - No pair possible:  [ col1=v1.1 col2=v2.0 ]
// Warning - No pair possible:  [ col1=v1.0 col2=v2.0 ]
// Pairwise coverage: 2  test vectors
//
//           col0            col1            col2 
// ____________________________________________________________
//           v0.1            v1.1            v2.1 
//           v0.0            v1.0            v2.1 
// 
// Single and error vectors: 4  test vectors
// 
//            col0            col1            col2 
// ____________________________________________________________
//             e0            v1.1            v2.0 
//           e1            v1.1            v2.0 
//           v0.0              s0            v2.1 
//           v0.0              s1            v2.1 
//
// 
