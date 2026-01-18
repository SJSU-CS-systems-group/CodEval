# CodEval

Currently CodEval has 3 main components:
## 1. Test Simple I/O Programming Assignments on Canvas
### codeval.ini contents
```
[SERVER]
url=<canvas API>
token=<canvas token>
[RUN]
precommand=
command=
```

Refer to a sample codeval.ini file [here](samples/codeval.ini)

### Command to run:  
`python3 codeval.py grade-submissions <a unique part of course name> [FLAGS]`
Example:  
If the course name on Canvas is CS 149 - Operating Systems, the command can be:  
`python3 codeval.py CS\ 149`  
or  
`python3 codeval.py "Operating Systems"`  
Use a part of the course name that can uniquely identify the course on Canvas.

### Flags
- **--dry-run/--no-dry-run** (Optional)
  - Default: --dry-run
  - Do not update the results on Canvas. Print the results to the terminal instead.
- **--verbose/--no-verbose** (Optional)
  - Default: --no-verbose
  - Show detailed logs
- **--force/--no-force** (Optional)
  - Default: --no-force
  - Grade submissions even if already graded
- **--copytmpdir/--no-copytmpdir** (Optional)
  - Default: --no-copytmpdir
  - Copy temporary directory content to current directory for debugging

### Specification Tags
Tags used in a spec file (\<course name>.codeval)

| Tag | Meaning | Function |
|---|---|---|
| C | Compile Code | Specifies the command to compile the submission code |
| CTO | Compile Timeout | Timeout in seconds for the compile command to run |
| RUN | Run Script | Specifies the script to use to evaluate the specification file. Defaults to evaluate.sh. |
| Z | Download Zip | Will be followed by zip files to download from Canvas to use when running the test cases. |
| CF | Check Function | Will be followed by a function name and a list of files to check to ensure that the function is used by one of those files. |
| CC | Check Container | Will be followed by a function name and a list of files to check to ensure that a container is used by one of those files. Primarily supports C++ containers such as std::vector |
| CO | Check Object | Will be followed by a function name and a list of files to check to ensure that an object is used by one of those files. Primarily support C++ stream operations |
| CMD/TCMD | Run Command | Will be followed by a command to run. The TCMD will cause the evaluation to fail if the command exits with an error. |
| CMP | Compare | Will be followed by two files to compare. |
| T/HT | Test Case | Will be followed by the command to run to test the submission. |
| I/IB/IF | Supply Input | Specifies the input for a test case. I adds a newline, IB does not add a newline, IF reads from a file. |
| O/OB/OF | Check Output | Specifies the expected output for a test case. O adds a newline, OB does not add a newline, OF reads from a file. |
| E/EB | Check Error | Specifies the expected error output for a test case. E adds a newline, EB does not. |
| TO | Timeout | Specifies the time limit in seconds for a test case to run. Defaults to 20 seconds. |
| X | Exit Code | Specifies the expected exit code for a test case. Defaults to zero. |
| SS | Start Server | Command containing timeout (wait until server starts), kill timeout (wait to kill the server), and the command to start a server |

Refer to a sample spec file [here](samples/assignment-name.codeval)

## 2. Test Distributed Programming Assignments
### (or complex non I/O programs)
### codeval.ini contents
```
[SERVER]
url=<canvas API>
token=<canvas token>
[RUN]
precommand=
command=
dist_command=
host_ip=
[MONGO]
url=
db=
```

Refer to a sample codeval.ini file [here](samples/codeval.ini)

### Command to run
is the same as the [command in #1](#command-to-run):  
`python3 codeval.py grade-submissions <a unique part of course name> [FLAGS]`

### Distributed Specification Tags  

| Tag | Meaning | Function |
|---|---|---|
| --DT-- | Distributed Tests Begin | Marks the beginning of distributed tests. Is used to determine if the spec file has distributed tests |
| GTO | Global timeout | A total timeout for all distributed tests, for each of homogenous and heterogenous tests. Homogenous tests = GTO value. Heterogenous tests = 2 * GTO value |
| PORTS | Exposed ports count | Maximum number of ports needed to expose per docker container |
| ECMD/ECMDT SYNC/ASYNC | External Command | Command that runs in the a controller container, emulating a host machine. ECMDT: Evaluation fails if command returns an error. SYNC: CodEval waits for command to execute or fail. ASYNC: CodEval doesn't wait for command to execute, failure is checked if ECMDT |
| DTC $int [HOM] [HET] | Distributed Test Config Group | Signifies the start of a new group of Distributed tests. Replace $int with the number of containers that needs to be started for the test group. HOM denotes homogenous tests, i.e., user's own submissions will be executed in the contianers. HET denotes heterogenous tests, i.e., a combination of $int - 1 other users' and current user's submissions will be executed in the containers. Can enter either HOM or HET or both |
| ICMD/ICMDT SYNC/ASYNC */n1,n2,n3... | Internal Command | Command that runs in each of the containers. ICMDT: Evaluation fails if command returns an error. SYNC: wait for command to execute or fail. ASYNC: Don't wait for command to execute, failure is checked if ICMDT *: run command in all the containers. n1,n2..nx: Run command in containers indexed n1,n2..nx only. Containers follow zero-based indexing  |
| TESTCMD | Test Command | Command run on the host machine to validate the submission(s) |
| --DTCLEAN-- | Cleanup Commands | Commands to execute after the tests have completed or failed. Can contain only ECMD or ECMDT |  

### Special placeholders in commands
| Placeholder | Usage |
| --- | --- |
| TEMP_DIR | used in ECMD/ECMDT to be replaced by the temporary directory generated by CodEval during execution |
| HOST_IP | used in ECMD/ECMDT/ICMD/ICMDT to be replaced by the host's IP specified in codeval.ini |
| USERNAME | used in ICMD/ICMDT to be replaced by the user's username whose submission is being evaluated |
| PORT_$int | used in ICMD/ICMDT to be replaced by a port number assigned to the running docker continer. $int needs to be < PORT value in the specification |

Refer to a sample spec file [here](samples/assignment-name.codeval)

### Notes
- The config file `codeval.ini` needs to contain the extra entries only if the tag `--DT--` exists in the specification file
- Distributed tests need a running mongodb service to persists the progress of students running heterogenous tests


## 3. Test SQL Assignments
### codeval.ini contents
```
[SERVER]
url=<canvas API>
token=<canvas token>
[RUN]
precommand=
command=
dist_command=
host_ip=
sql_command=
```

Refer to a sample codeval.ini file [here](SQL/samples/codeval.ini)

### Command to run
is the same as the [command in #1](#command-to-run):  
`python3 codeval.py grade-submissions <a unique part of course name> [FLAGS]`

### SQL Specification Tags  

| Tag              | Meaning                 | Function                                                                                     |
|------------------|-------------------------|----------------------------------------------------------------------------------------------|
| --SQL--          | SQL Tests Begin         | Marks the beginning of SQL tests. Is used to determine if the spec file has SQL based tests  |
| INSERT           | Insert rows in DB       | Insert rows in the SQL database using files/ individual insert queries.                      |
| CONDITIONPRESENT | Check condition in file | Validate submission files for a required condition to be present in submissions.             |
| SCHEMACHECK      | External Command        | Validate submission files for database related checks like constraints.                      |
| TSQL             | SQL Test                | Marks the SQL test, take input as a file or individual query and run it on submission files. |

Refer to a sample spec file [here](SQL/samples/ASSIGNMENT:CREATE.codeval)

### Notes
- The config file `codeval.ini` needs to contain the extra entries only if the tag `--SQL--` exists in the specification file
- SQL tests need a separate container image to run SQL tests in MYSQL.


## Create an assignment on Canvas

### Command to create the assignment:
**Syntax:** `python3 codeval.py create-assignment <course_name> <specification_file> [ --dry-run/--no-dry-run ] [ --verbose/--no-verbose ] [ --group_name ]`  
**Example:** `python3 codeval.py create-assignment "Practice1" 'a_big_bag_of_strings.txt' --no-dry-run --verbose --group_name "exam 2"`

### Command to grade the assignment:
**Syntax:** `python3 codeval.py grade-submissions <course_name> [ --dry-run/--no-dry-run ] [ --verbose/--no-verbose ] [ --force/--no-force][--copytmpdir/--no-copytmpdir]`  
**Example:** `python3 codeval.py grade-submissions "Practice1" --no-dry-run --force --verbose`

### Assignment description tags

* CRT_HW START <Assignment_name> - usually at the beginning of the file. Then lines that follow this tag are the assignment description in markdown.

* CRT_HW END - ends the assignment description

## Assignment description macros

* DISCSN_URL - this macro will be substituted with the URL of the discussion that was created for this assignment

* EXMPLS <no_of_test_cases> - this macro will be replaced with the specified number of test cases formatted for display

* FILE[file_name] - this macro will be replaced by a link to the specified file

### MODIFICATIONS REQUIRED IN THE SPECIFICATION FILE.
1) Start the specification file with the tag CRT_HW START followed by a space followed by the name of assignment.
	```  For ex: CRT_HW START Hello World```
2) The following lines after the first line will contain the description of the assignment in Markdown format.
3) The description ends with the last line containing just the tag CRT_HW END .
	``` For ex: CRT_HW END ```
4) After this tag, the content for grading the submission begins.

	Addition of the Discussion Topic in the assignment description.
	1) Insert the tag DISCUSSION_LINK wherever you want the corresponding discussion topic's link to appear.
		```For ex: To access the discussion topic for this assignment you go here DISCUSSION_LINK```

	#### Addition of sample examples in the assignment description.
	1) Insert the tag EXMPLS followed by single space followed by the value. 
	   Here value is the number of test cases to be displayed as sample examples. 
	   At maximum it will print all the non hidden test cases.
	   For ex: EXMPLS 5
	#### Addition of the links to the files uploaded in the Codeval folder in the assignment description.
	1) In order to add hyperlink to a file the markdown format is as follows:
	   [file_name_to_be_displayed](Url_of_the_file)
	   Here in the parenthesis where the Url is required,insert the tag
	   FILE[name of file].
	   For ex: FILE[file_name.extension]
       If the file is not already in the Codeval folder, it will be extracted from a zip file in the
       CodEval spec and uploaded automatically.
	   
### UPLOAD THE REQUIRED FILES IN CODEVAL FOLDER IN FILES SECTION.
1) Create a folder called `assignmentFiles` which should contain all the necessary files including
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
	Here Is The Link To The Discussion Topic: DISCSN_URL

	### Rubric 
	| Cases | Points|
	| ----- |----- |
	| Base Points | 50 |

	CRT_HW END  

	C cc -o bigbag --std=gnu11 bigbag.c


## 4. Test Assignments with AI Models

Test programming assignments against multiple AI models (Claude, GPT, Gemini) to benchmark their performance.

### Installation

Install the AI provider packages you want to use:

```bash
# Install all AI providers
pip install assignment-codeval[ai]

# Or install specific providers
pip install anthropic        # For Claude models
pip install openai           # For GPT models
pip install google-generativeai  # For Gemini models
```

### codeval.ini contents (optional)
```
[AI]
anthropic_key=sk-ant-...
openai_key=sk-...
google_key=...
```

API keys can also be provided via:
- Environment variables: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`
- Command line options: `--anthropic-key`, `--openai-key`, `--google-key`

### Command to run
```bash
assignment-codeval test-with-ai <codeval_file> [OPTIONS]
```

### Options
| Option | Description |
|--------|-------------|
| `-o, --output-dir` | Directory to store solutions and results (default: `ai_test_results`) |
| `-n, --attempts` | Number of attempts per model (default: 1) |
| `-m, --models` | Specific models to test (can be used multiple times) |
| `-p, --providers` | Only test models from specific providers: `anthropic`, `openai`, `google` |
| `--anthropic-key` | Anthropic API key |
| `--openai-key` | OpenAI API key |
| `--google-key` | Google API key |

### Examples
```bash
# Test with all Anthropic models
assignment-codeval test-with-ai my_assignment.codeval -p anthropic

# Test with specific model, 3 attempts each
assignment-codeval test-with-ai my_assignment.codeval -m "Claude Sonnet 4" -n 3

# Test with all providers (requires all API keys)
assignment-codeval test-with-ai my_assignment.codeval -n 2

# Pass API key directly
assignment-codeval test-with-ai my_assignment.codeval --anthropic-key sk-ant-xxx -p anthropic
```

### Supported Models

| Provider | Models |
|----------|--------|
| Anthropic | Claude Sonnet 4, Claude Opus 4 |
| OpenAI | GPT-4o, GPT-4o Mini, o1, o3-mini |
| Google | Gemini 2.0 Flash, Gemini 1.5 Pro |

Note: You can add additional models using `-m "model-id"`. Check each provider's documentation for available model IDs.

### Output Structure
```
ai_test_results/
├── prompt.txt                    # The prompt sent to AI models
├── results.json                  # Summary of all results
├── Claude_Sonnet_4/
│   └── attempt_1/
│       ├── raw_response.txt      # Raw AI response
│       ├── solution.c            # Extracted code
│       └── <codeval files>       # Copied for evaluation
├── GPT-4o/
│   └── attempt_1/
│       └── ...
└── ...
```

### Notes
- The command extracts the assignment description from the codeval file (between `CRT_HW START` and `CRT_HW END` tags)
- Support files from `support_files/` directory are automatically copied for evaluation
- Results include pass/fail status, response time, and any errors
- Use multiple attempts (`-n`) to account for AI response variability


