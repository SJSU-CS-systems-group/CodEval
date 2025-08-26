from markdownify import markdownify as md
import re
import os
import requests

        

class MkdnParser:

    def __init__(self, assignment_dict, dir_name, api_url, api_key):
        # Get api key for making file download requests later
        self.assignment_dict = assignment_dict
        self.dir_name = dir_name
        self.api_url = api_url
        self.api_key = api_key

    def clean_brackets(self, s):
        """
        Removes directory from filename inside brackets
        
        Keyword arguments:
        s -- re.Match object containing the directory
        Return: string
        """
        print(s.group(2))

        return '[' + s.group(2) + ']'
        

    def check_links(self, s):
        """
        Checks if the given link is a canvas file, if so, downloads the file and gives a path to the file
        
        Keyword arguments:
        s -- re.Match object containing a link
        Return: string
        """
        link = s.group(1)
        if "instructure" in link:
            filename = s.group(2)
            headers = {'Authorization': 'Bearer ' + self.mParser['CANVAS CLONE']['api_key']}
            response = requests.get(link, headers)
            if 'Content-Length' in response.headers:
                with open('CodEvalTooling/' + self.dir_name + filename, 'wb') as outfile:
                    outfile.write(response.content)

            relinked_link = s.group().replace(s.group(1), 'URL_OF_HW')
            relinked_link = relinked_link.replace(s.group(2), self.dir_name + filename)

            return relinked_link
        else:
            return s

    
    def clean_description(self):
        """
        Removes newline characters from the description in the assignment json
        
        Keyword arguments:
        Return: None
        """
        self.assignment_dict.update({'description': self.assignment_dict['description'].replace(r'\n', '').replace(r'&nbsp', ' ')})


    def parse_links_to_files(self):
        """
        Takes json structure of assignment and takes files, downloads them and changes the locations in the json
        
        Keyword arguments:
        Return: None
        """
        linkPattern = r'<a[^>]*?href="([^"]*)"[^>]*>([^<]*)'

        linkTags = re.sub(linkPattern, self.check_links, self.assignment_dict['description'])
        
        self.assignment_dict.update({'description': linkTags})

    def get_mkdn(self):
        """
        Opens the file, reads the file and writes it to markdown
        
        Keyword arguments:
        filename -- string, file to write to
        Return: None
        """
        self.clean_description()
        file_mkdn = ''
        file_mkdn += 'CRT_HW START ' + self.assignment_dict['name'] + '\n'
        file_mkdn += md(self.assignment_dict['description'], autolinks = False, escape_asterisks = False, escape_underscores = False, heading_style = 'ATX', strip = ['ul'])
        file_mkdn += '\nCRT_HW END'

        prepared_pattern = r'\[(%filename%)([^]]*)\]'.replace('%filename%', self.dir_name.replace('\\', '/'))
        file_mkdn = re.sub(prepared_pattern, self.clean_brackets, file_mkdn)

        return file_mkdn