## CREATE AN ASSIGNMENT ON CANVAS.

**New tags introduced are :** 
CRT_HW START <Assignment_name>
CRT_HW END
HW_URL
EXMPLS <no_of_test_cases>
URL_OF_HW "file_name"

### MODIFICATIONS REQUIRED IN THE SPECIFICATION FILE.
1) Start the specification file with the tag CRT_HW START followed by a space followed by the name of assignment.
	```  For ex: CRT_HW START Hello World```
2) The following lines after the first line will contain the description of the assignment in Markdown format.
3) The description ends with the last line containing just the tag CRT_HW END .
	``` For ex: CRT_HW END ```
4) After this tag, the content for grading the submission begins.

	Addition of the Discussion Topic in the assignment description.
	1) Insert the tag HW_URL wherever you want the corresponding discussion topic's link to appear.
		```For ex: To access the discussion topic for this assignment you go here HW_URL```

	#### Addition of sample examples in the assignment description.
	1) Insert the tag EXMPLS followed by single space followed by the value. 
	   Here value is the number of test cases to be displayed as sample examples. 
	   At maximum it will print all the non hidden test cases.
	   For ex: EXMPLS 5
	#### Addition of the links to the files uploaded in the Codeval folder in the assignment description.
	1) In order to add hyperlink to a file the markdown format is as follows:
	   [file_name_to_be_displayed](Url_of_the_file)
	   Here in the parenthesis where the Url is required,insert the tag
	   URL_OF_HW followed by space followed by the file name of the file required to be linked in double quotes.
	   For ex: URL_OF_HW "file name.extension"
	   Note: The file should be present in the Codeval folder.
	   
### UPLOAD THE REQUIRED FILES IN CODEVAL FOLDER IN FILES SECTION.
1) Create a folder called `assignmentFiles` which should conatin all the necessary files including
	the specification file.
	   
### EXAMPLE OF THE SPECIFICATION FILE.	
	
	CRT_HW START Bag Of Strings
	# Description
	## Problem Statement
	- This Is An Example For The Description Of The Assignment In Markdown.
	- To Download The File [Hello_World](URL_OF_HW "Helloworld.Txt")

	## Sample Examples
	EXMPLS 3

	## Discussion Topic
	Here Is The Link To The Discussion Topic: HW_URL

	### Rubric 
	| Cases | Points|
	| ----- |----- |
	| Base Points | 50 |

	CRT_HW END  

	C cc -o bigbag --std=gnu11 bigbag.c 
	
### Command to create the assignment:
**Syntax:**  python3 codeval.py create-assignment <course_name> <specification_file> [ --dry-run/--no-dry-run ] [ --verbose/--no-verbose ] [ --group_name ]
**Example:** python3 codeval.py create-assignment "Practice1" 'a_big_bag_of_strings.txt' --no-dry-run --verbose --group_name "exam 2"

### Command to grade the assignment:
**Syntax:** python3 codeval.py grade-submissions <course_name> [ --dry-run/--no-dry-run ] [ --verbose/--no-verbose ] [ --force/--no-force] [--copytmpdir/--no-copytmpdir]
**Example:** python3 codeval.py grade-submissions "Practice1" --no-dry-run --force --verbose	   
