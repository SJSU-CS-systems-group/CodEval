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