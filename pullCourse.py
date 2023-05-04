from canvasapi import Canvas
from canvasParameters import *
from convertDictToMkdn import MkdnParser
import json
import os


# Update parameters given set, otherwise set to None
def update_parameters(dict_to_update, REQUIRED_PARAMETERS, OPTIONAL_PARAMETERS):
    """
    :type dict_to_update: dict
    :type REQUIRED_PARAMETERS: set
    :rtype: dict
    """
    updated_dict = {}

    for parameter in REQUIRED_PARAMETERS:
        if parameter in dict_to_update:
            updated_dict.update({parameter: dict_to_update[parameter]})
        else:
            updated_dict.update({parameter: None})
    for parameter in OPTIONAL_PARAMETERS:
        if parameter in dict_to_update and not dict_to_update[parameter] is None:
            updated_dict.update({parameter: dict_to_update[parameter]})

    return updated_dict

class CourseParser:
    def __init__(self, course, assignment_name, dir_name, api_url, api_key):
        self.course = course
        self.assignment_name = assignment_name
        self.dir_name = dir_name
        self.api_url = api_url
        self.api_key = api_key

    def get_assignments(self):
        assignment_list = self.course.get_assignments()

        selected_assignment_list = []
        if self.assignment_name != '*':    
            for assignment in assignment_list:
                assignment_dict = vars(assignment)
                if assignment_dict['name'] == self.assignment_name:
                    selected_assignment_list.append(assignment_dict)
        
        return selected_assignment_list

    def export_to_MD(self):
        selected_assignment_list = self.get_assignments()
        for assignment_dict in selected_assignment_list:
            assignmentParser = MkdnParser(assignment_dict, self.dir_name, self.api_url, self.api_key)
            assignmentParser.parse_links_to_files()
            with open(self.dir_name + assignment_dict['name'] + str(assignment_dict['id']), 'wb') as outfile:
                outfile.write(bytes(assignmentParser.get_mkdn(), 'utf-8'))
            

    def export_to_json(self):
        selected_assignment_list = self.get_assignments()
        for assignment_dict in selected_assignment_list:
            updated_assignment = update_parameters(assignment_dict, ASSIGNMENT_REQUIRED_PARAMETERS, ASSIGNMENT_OPTIONAL_PARAMETERS)
            self.write_to_json(self.dir_name + assignment_dict['name'] + str(assignment_dict['id']) + '.json', assignment_dict)

    def write_to_json(self, filename, dict_to_write):
        """
        Writes to json file with given filename and dictionary
        
        Keyword arguments:
        filename -- string
        dict_to_write -- string
        Return: None
        """
        dict_json = json.dumps(dict_to_write, indent=4, default=str)
        with open(filename, 'w') as outfile:
            outfile.write(dict_json)