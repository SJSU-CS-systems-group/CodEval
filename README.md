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

### Codeval File Matching
When looking up the codeval file for an assignment, CodEval first tries to match by filename (case-insensitive). If no filename match is found, it falls back to checking the `ASSIGNMENT START` title inside each `.codeval` file in the codeval directory. This allows the codeval filename to differ from the assignment name on Canvas as long as the `ASSIGNMENT START` title matches.

### Specification Tags
Tags used in a spec file (\<course name>.codeval)

| Tag | Meaning | Function |
|---|---|---|
| C | Compile Code | Specifies the command to compile the submission code |
| CTO | Compile Timeout | Timeout in seconds for the compile command to run |
| RUN | Run Script | Specifies the script to use to evaluate the specification file. Defaults to evaluate.sh. |
| Z | Download Zip | Will be followed by zip files to download from Canvas to use when running the test cases. |
| CF | Check Function | `CF <function_name> [filename]` — checks that the function is used. The filename is **optional** and omitting it (e.g. `CF strtol`) is the preferred usage; source files are inferred from the most recent `C` tag and the check uses compiled-artifact inspection only (objdump/javap/ast). Providing a filename (e.g. `CF strtol mycalc.c`) is supported for backwards compatibility and additionally enables a regex fallback when no compiled artifact is found. |
| NCF | Check Not Function | `NCF <function_name> [filename]` — checks that the function is **not** used. The filename is **optional** (same behaviour as CF). |
| CC | Check Container | Will be followed by a function name and a list of files to check to ensure that a container is used by one of those files. Primarily supports C++ containers such as std::vector |
| CO | Check Object | Will be followed by a function name and a list of files to check to ensure that an object is used by one of those files. Primarily support C++ stream operations |
| PRINT | Print Label | Prints a label/message to stdout. Cleaner alternative to `CMD echo "..."` for section labels. |
| CMD/TCMD | Run Command | Will be followed by a command to run. The TCMD will cause the evaluation to fail if the command exits with an error. |
| CMP | Compare | Will be followed by two files to compare. |
| T/HT | Test Case | Will be followed by the command to run to test the submission. |
| I/IB/IF | Supply Input | Specifies the input for a test case. I adds a newline, IB does not add a newline, IF reads from a file. |
| O/OB/OF | Check Output | Specifies the expected output for a test case. O adds a newline, OB does not add a newline, OF reads from a file. |
| E/EB | Check Error | Specifies the expected error output for a test case. E adds a newline, EB does not. |
| TO | Timeout | Specifies the time limit in seconds for a test case to run. Defaults to 20 seconds. |
| X | Exit Code | Specifies the expected exit code for a test case. Defaults to zero. |
| SS | Start Server | Command containing timeout (wait until server starts), kill timeout (wait to kill the server), and the command to start a server |
| TEMP | Temp File | Registers a file to be deleted before the next T, HT, or TCMD test runs (clean state) and again after it completes (cleanup). Only applies to the immediately following test — use a new TEMP tag for each test that needs it. |

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

* `ASSIGNMENT START <Assignment_name>` - usually at the beginning of the file. The lines that follow are the assignment description in markdown. (`CRT_HW START` is also accepted for backwards compatibility.)

* `ASSIGNMENT END` - ends the assignment description. (`CRT_HW END` is also accepted.)

## Assignment description macros

* DISCSN_URL - this macro will be substituted with the URL of the discussion that was created for this assignment

* EXMPLS <no_of_test_cases> - this macro will be replaced with the specified number of test cases formatted for display

* FILE[file_name] - this macro will be replaced by a link to the specified file

* COMPILE - this macro will be replaced with the compile command from the C tag in the specification file

### MODIFICATIONS REQUIRED IN THE SPECIFICATION FILE.
1) Start the specification file with the tag `ASSIGNMENT START` followed by a space followed by the name of the assignment.
   ```
   ASSIGNMENT START Hello World
   ```
2) The lines after this tag contain the assignment description in Markdown format.
3) The description ends with `ASSIGNMENT END`.
   ```
   ASSIGNMENT END
   ```
4) After this tag, the grading specification begins.

	#### Addition of the Discussion Topic in the assignment description.
	Insert the tag `DISCUSSION_LINK` wherever you want the discussion topic's link to appear.
	```
	To access the discussion topic for this assignment, go here: DISCUSSION_LINK
	```

	#### Addition of sample examples in the assignment description.
	Insert the tag `EXMPLS` followed by a space and the number of test cases to display as sample examples. At most, it will print all non-hidden test cases.
	```
	EXMPLS 5
	```
	#### Addition of links to files uploaded in the Codeval folder.
	Use `FILE[file_name]` in a markdown link where the URL would go:
	```
	[Download starter file](FILE[starter.c])
	```
	If the file is not already in the Codeval folder, it will be extracted from a zip file in the spec and uploaded automatically.

### UPLOAD THE REQUIRED FILES IN CODEVAL FOLDER IN FILES SECTION.
Create a folder called `assignmentFiles` which should contain all the necessary files including the specification file.

### EXAMPLE SPECIFICATION FILE

```
ASSIGNMENT START Hello World
# Hello World

## Problem Statement
Write a C program that reads a name from stdin and prints `Hello, <name>!`

## Submission
Submit your code to GITHUB_DIRECTORY

## Sample Examples
EXMPLS 2

## Discussion
DISCSN_URL

### Rubric
| Cases       | Points |
|-------------|--------|
| Base Points | 20     |
| Test Case 1 | 40     |
| Test Case 2 | 40     |
ASSIGNMENT END

# Compile the submission
C gcc -o hello hello.c

# Test case 1: greet "World"
T ./hello
I World
O Hello, World!

# Test case 2: greet "Alice"
T ./hello
I Alice
O Hello, Alice!
```


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
- The command extracts the assignment description from the codeval file (between `ASSIGNMENT START` and `ASSIGNMENT END` tags; `CRT_HW START`/`CRT_HW END` are also accepted)
- Support files from `support_files/` directory are automatically copied for evaluation
- Results include pass/fail status, response time, and any errors
- Use multiple attempts (`-n`) to account for AI response variability


