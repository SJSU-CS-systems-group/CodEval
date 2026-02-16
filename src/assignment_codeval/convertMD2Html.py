import os
import re

import markdown

from assignment_codeval.commons import info, get_config


def _read_file_content(filename, spec_dir):
    """Read the content of a file referenced by an OF or IF tag."""
    if not spec_dir:
        return None
    filepath = os.path.join(spec_dir, filename)
    try:
        with open(filepath, 'r') as f:
            return f.read()
    except (FileNotFoundError, OSError):
        return None


def sampleTestCases(listOfTC, numOfTC, spec_dir=None):
    counter = 0
    samples = "<pre><code>"
    for line in listOfTC:
        if line.startswith('T ', 0, 2):
            counter = counter + 1
            if counter > numOfTC:
                break
            samples = samples + "\n" + "Command to RUN: " + line[2:]
        elif line.startswith('IF '):
            filename = line[3:].strip()
            content = _read_file_content(filename, spec_dir)
            if content is not None:
                samples = samples + "<span style=\"color:green\">" + content + "</span>"
            else:
                samples = samples + "<span style=\"color:green\">Input from file: " + filename + "\n</span>"
        elif line.startswith('IB '):
            samples = samples + "<span style=\"color:green\">" + line[3:] + "</span>"
        elif line.startswith('I '):
            samples = samples + "<span style=\"color:green\">" + line[2:] + "</span>"
        elif line.startswith('OF '):
            filename = line[3:].strip()
            content = _read_file_content(filename, spec_dir)
            if content is not None:
                samples = samples + "<span style=\"color:blue\">" + content + "</span>"
            else:
                samples = samples + "<span style=\"color:blue\">Expected output from file: " + filename + "\n</span>"
        elif line.startswith('OB '):
            samples = samples + "<span style=\"color:blue\">" + line[3:] + "</span>"
        elif line.startswith('O '):
            samples = samples + "<span style=\"color:blue\">" + line[2:] + "</span>"
        elif line.startswith('X '):
            samples = samples + "Expected Exit Code: " + line[2:]
        elif line.startswith('EB '):
            samples = samples + "<span style=\"color:Tomato\">" + line[3:] + "</span>"
        elif line.startswith('E '):
            samples = samples + "<span style=\"color:Tomato\">" + line[2:] + "</span>"
        else:
            continue
    samples = samples + "</code></pre>"
    return samples


def mdToHtml(file_name, files_resolver=None):
    with open(file_name, 'r') as f:
        text = ""
        examples = []
        assignment = ""
        numOfSampleTC = 1
        for line in f:
            if 'CRT_HW START' in line:
                assignment_name = line[13:].strip()
            elif 'CRT_HW END' in line:
                assignment = text
            elif line.startswith(('T ', 'I ', 'IB ', 'IF ', 'O ', 'OB ', 'OF ', 'X ', 'E ', 'EB ')):
                examples.append(line)
            elif line.startswith('HT '):
                break
            else:
                if 'EXMPLS ' in line:
                    numOfSampleTC = int(line[7:])
                text = text + line
        spec_dir = os.path.dirname(os.path.abspath(file_name))
        samples = sampleTestCases(examples, numOfSampleTC, spec_dir)
        assignment = re.sub('EXMPLS [0-9]+', samples, assignment)
        # Handle FILE macros in two passes:
        # 1. FILE inside markdown link syntax: [text](FILE[name]) -> [text](url)
        assignment = re.sub(r'\]\(FILE\[([^]]+)]\)',
                            lambda m: f']({files_resolver(m.group(1))})' if files_resolver else f'](FILE[{m.group(1)}])',
                            assignment)
        # 2. Standalone FILE macros: FILE[name] -> [name](url)
        assignment = re.sub(r'FILE\[([^]]+)]',
                            lambda m: f'[{m.group(1)}]({files_resolver(m.group(1))})' if files_resolver else f'FILE[{m.group(1)}]',
                            assignment)
        html = markdown.markdown(assignment,
                                 extensions=['mdx_better_lists', 'extra'],
                                 extension_configs={'mdx_better_lists': {'split_paragraph_lists': True}})

    if get_config().dry_run:
        html_file_name = file_name + '.html'
        with open(html_file_name, 'w') as f:
            f.write(html)
            info(f'HTML preview created in the path : {html_file_name}')
    return assignment_name, html
