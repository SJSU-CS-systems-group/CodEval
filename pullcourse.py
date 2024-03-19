from canvasapi import Canvas
from mkdnparser import MkdnParser
import json
import os

MODULE_REQUIRED_PARAMETERS = {'name'}
MODULE_OPTIONAL_PARAMETERS = {'unlock_at', 'position', 'require_sequential_progress', 'publish_final_grade', 'published'}

MODULE_ITEM_REQUIRED_PARAMETERS = {'type'}
MODULE_ITEM_OPTIONAL_PARAMETERS = {'title', 'position', 'indent', 'external_url', 'new_tab', 'completion_requirement', 'iframe'}

ASSIGNMENT_GROUP_REQUIRED_PARAMETERS = {}
ASSIGNMENT_GROUP_OPTIONAL_PARAMETERS = {'name', 'position', 'group_weight', 'integration_data'}

ASSIGNMENT_REQUIRED_PARAMETERS = {'name'}
ASSIGNMENT_OPTIONAL_PARAMETERS = {'position', 'submission_types', 'allowed_extensions', 'turnitin_enabled', 'vericite_enabled', 'turnitin_settings',
    'integration_data', 'peer_reviews', 'automatic_peer_reviews', 'notify_of_update', 'grade_group_students_individually', 'external_tool_attributes',
    'points_possible', 'grading_type', 'due_at', 'lock_at', 'unlock_at', 'description', 'published', 'omit_from_final_grade', 'quiz_lti', 'moderated_grading', 'grader_count',
    'grader_comments_visible_to_graders', 'graders_anonymous_to_graders', 'graders_names_visible_to_final_grader', 'anonymous_grading', 'allowed_attempts'}

DISCUSSION_TOPIC_REQUIRED_PARAMETERS = {}
DISCUSSION_TOPIC_OPTIONAL_PARAMETERS = {'title', 'message', 'discussion_type', 'published', 'delayed_post_at', 'allow_rating', 'lock_at', 'podcast_enabled',
    'podcast_has_student_posts', 'require_inital_post', 'is_announcement', 'pinned', 'position_after', 'only_graders_can_rate',
    'sort_by_rating', 'attachment', 'specific_sections'}

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
            updated_assignment_dict = update_parameters(assignment_dict, ASSIGNMENT_REQUIRED_PARAMETERS, ASSIGNMENT_OPTIONAL_PARAMETERS)
            self.write_to_json(self.dir_name + assignment_dict['name'] + str(assignment_dict['id']) + '.json', updated_assignment_dict)

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