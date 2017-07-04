// Bug 7/3/2017, "except skills" should give some reasonable error but
// I am getting
//   File "genpairs.py", line 403, in makeExcludes
//    for conflict_slot in PropsSlots[ cond ] : 
//    KeyError: 'unskilled'
//
// We need to check the key explicitly and warn if misspelled
//

team_size:
   2 
   9  except unskilled         // should be few_skills 

skill_overlap:
   minimal  prop few_skills 
   typical                     // Randomly 20% of skills




