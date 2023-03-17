import markdown
import re

assignment_name = ""

def sampleTestCases(listOfTC,numOfTC):
    counter = 0
    samples = "<pre><code>"
    for line in listOfTC:
        if line.startswith('T ',0,2):
            counter = counter + 1
            if counter > numOfTC :
                break
            samples = samples + "\n"+"Command to RUN: " + line[2:]
        elif line.startswith('I ',0,2):
            samples = samples + "<span style=\"color:green\">" + line[2:]+ "</span>"
        elif line.startswith('O ',0,2):
            samples = samples + "<span style=\"color:blue\">" + line[2:] + "</span>"
        elif line.startswith('X ',0,2):
            samples = samples + "Expected Exit Code: " + line[2:]
        elif line.startswith('E ',0,2):
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
        global assignment_name
        numOfSampleTC = 1
        for line in f:
            if 'CRT_HW START' in line:
                assignment_name=line[13:]
            elif 'CRT_HW END' in line:
                assignment = text
            elif line.startswith('T ',0,2) or line.startswith('I ',0,2) or line.startswith('O ',0,2) or line.startswith('X ',0,2) or line.startswith('E ',0,2):
                examples.append(line)
            elif 'HT ' in line:
                samples = sampleTestCases(examples,numOfSampleTC)
                assignment = re.sub('EXMPLS [0-9]+',samples,assignment)
                break
            else:
                if 'URL_OF_HW ' in line:
                    start_index = line.index('URL_OF_HW') + len("URL_OF_HW \"")
                    end_index=line.index('\")')
                    file_name=line[start_index:end_index]
                    file_url = "URL_OF_HW " + "\"" + file_name +  "\""
                    try:
                        check_file_in_dict = file_dict[file_name]
                    except:
                        print (f'{file_name} is not present in the CodeEval folder. Make sure that the file in the CodEval folder and the value of corresponding URL_OF_HW tag is same')
                    else:
                        line=line.replace(file_url,file_dict[file_name])
                if 'EXMPLS ' in line:
                    numOfSampleTC = int(line[7:])
                text = text + line
        html=markdown.markdown(assignment, extensions=['markdown.extensions.tables'])
    f.close()
    return html


    
