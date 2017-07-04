
class_size:
  0 error  // Can't generate teams in a class with less than 3
  1 error
  2 error
  small prop small_class   // 9,10,11
  medium prop medium_class // 27-35
  large prop large_class   // 50-100

team_size:
   0 error
   1 error
   2 3 5 
   9  except small_class 

time_overlap:
   none single
   minimal prop no_times except large_class
   typical  // Randomly generate 20% times free
   maximal  // Randomly generate 80% times free 

skill_overlap:
   none single  if small_class // No overlapping skills
   unskilled single if small_class // Some student has no skills
   minimal prop few_skills     // 10% of skills
   typical                     // Randomly 20% of skills
   maximal                     // Randomly 80% of skills


