from typing import List
from .mongo import MongoConnection
from datetime import datetime
from commons import *


"""
    This file contains all the database calls

    DB structure:
    Collection: <assignment_id>
    Documents: {
        student_id: <student_id>,
        student_name: <student_name>,
        attachments: [
            {
                display_name: <display_name>,
                url: <url>
            },
            ...
        ],
        submitted_at: ISODate<submitted_at>,
        score: <score>
    }
        
"""


def get_other_user_submissions(
    assignment_id: str,
    current_user_id: str
) -> List[dict]:
    """Get other user submissions"""
    submissions_collection = MongoConnection().get_db()[assignment_id]
    return list(submissions_collection.find(
        {'student_id': {'$ne': current_user_id}}
    ))


def add_user_submission_if_not_present(
    assignment_id: str,
    student_id: str,
    student_name: str,
    submitted_at: datetime,
    attachments: List[dict],
) -> None:
    """Add a submission to the database"""
    submissions_collection = MongoConnection().get_db()[assignment_id]
    doc = submissions_collection.find_one({'student_id': student_id})
    if doc is None:
        submissions_collection.insert_one({
            'student_id': student_id,
            'student_name': student_name,
            'submitted_at': submitted_at,
            'attachments': attachments,
            'score': 0
        })
        debug("Added %s's (%s) submission to the pool" % (
            student_name, student_id
        ))


def add_score_to_submissions(
        assignment_id: str,
        student_ids: List[str]
) -> None:
    """Add 1 to score of user submissions"""
    submissions_collection = MongoConnection().get_db()[assignment_id]
    submissions_collection.update_many(
        {'student_id': {'$in': student_ids}},
        {'$inc': {'score': 1}}
    )
