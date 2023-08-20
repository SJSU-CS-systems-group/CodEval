import markdown
import re
from commons import errorWithException,debug,error,info,warn,get_config

def sampleTestCases(listOfTC,numOfTC):
    counter = 0
    samples = "<pre><code>"
    for line in listOfTC:
        if line.startswith('T ',0,2):
            counter = counter + 1
            if counter > numOfTC :
                break
            samples = samples + "\n"+"Command to RUN: " + line[2:]
        elif line.startswith('I '):
            samples = samples + "<span style=\"color:green\">" + line[2:]+ "</span>"
        elif line.startswith('O '):
            samples = samples + "<span style=\"color:blue\">" + line[2:] + "</span>"
        elif line.startswith('X '):
            samples = samples + "Expected Exit Code: " + line[2:]
        elif line.startswith('E '):
            samples = samples + "<span style=\"color:Tomato\">" + line[2:] + "</span>"
        else:
            continue
    samples = samples + "</code></pre>"
    return samples
	
def mdToHtml(file_name,file_dict):
    with open(file_name,'r') as f:
        text = ""
        examples=[]
        assignment = ""
        numOfSampleTC = 1
        for line in f:
            if 'CRT_HW START' in line:
                assignment_name=line[13:].strip()
            elif 'CRT_HW END' in line:
                assignment = text
            elif line.startswith(('T ', 'I ', 'O ', 'X ', 'E ')):
                examples.append(line)
            elif line.startswith('HT '):
                break
            else:
                if 'URL_OF_HW ' in line:
                    start_index = line.index('URL_OF_HW') + len("URL_OF_HW \"")
                    end_index=line.index('")')
                    hw_name=line[start_index:end_index]
                    file_url = "URL_OF_HW " + '"' + hw_name +  '"'
                    try:
                        check_file_in_dict = file_dict[hw_name]
                    except:
                        errorWithException (f'{hw_name} is not present in the CodeEval folder. Make sure that the file in the CodEval folder and the value of corresponding URL_OF_HW tag is same')
                    else:
                        line=line.replace(file_url,file_dict[hw_name])
                if 'EXMPLS ' in line:
                    numOfSampleTC = int(line[7:])
                text = text + line
        samples = sampleTestCases(examples,numOfSampleTC)
        assignment = re.sub('EXMPLS [0-9]+',samples,assignment)
        html=markdown.markdown(assignment, extensions=['markdown.extensions.tables'])
    
    if get_config().dry_run:
        with open(file_name+'.html','w') as f:
            f.write(html)
            info(f'File created in the path : {file_name}')
    return (assignment_name, html)

    
