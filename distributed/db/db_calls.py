from typing import List
from .mongo import MongoConnection
from datetime import datetime
from assignment_codeval.commons import debug


"""
    This file contains all the database calls

    DB structure:
    Collection: <assignment_id>
    Documents: {
        student_id: str,
        student_name: str,
        attachments: [
            {
                display_name: str,
                url: str
            },
            ...
        ],
        submitted_at: ISODate,
        score: int,
        active: boolean
    }
        
"""


def get_other_user_submissions(
    assignment_id: str,
    current_user_id: str
) -> List[dict]:
    """Get other user submissions"""
    submissions_collection = MongoConnection().get_db()[
        'a_' + str(assignment_id)]
    return list(submissions_collection.find(
        {'student_id': {'$ne': current_user_id}, 'active': True},
    ))


def add_user_submission_if_not_present(
    assignment_id: str,
    student_id: str,
    student_name: str,
    submitted_at: datetime,
    attachments: List[dict],
) -> None:
    """Add a submission to the database"""
    submissions_collection = MongoConnection().get_db()[
        'a_' + str(assignment_id)]
    doc = submissions_collection.find_one({'student_id': student_id})
    if doc is None:
        submissions_collection.insert_one({
            'student_id': student_id,
            'student_name': student_name,
            'submitted_at': submitted_at,
            'attachments': attachments,
            'score': 0,
            'active': True
        })
        debug("Added %s's (%s) submission to the pool" % (
            student_name, student_id
        ))
    elif doc['active'] is False:
        submissions_collection.update_one(
            {'student_id': student_id},
            {
                '$set': {
                    'attachments': attachments,
                    'active': True,
                    'submitted_at': submitted_at,
                }
            }
        )
        debug("Reactivated %s's (%s) submission" % (
            student_name, student_id
        ))
    else:
        submissions_collection.update_one(
            {'student_id': student_id},
            {
                '$set': {
                    'attachments': attachments,
                    'submitted_at': submitted_at,
                }
            }
        )
        debug("Updated %s's (%s) submission" % (
            student_name, student_id
        ))


def deactivate_user_submission(
        assignment_id: str,
        student_id: str,
        submitted_at: datetime,
) -> None:
    """Deactivate a submission"""
    submissions_collection = MongoConnection().get_db()[
        'a_' + str(assignment_id)]
    submissions_collection.update_one(
        {'student_id': student_id},
        {
            '$set': {
                'active': False,
                'submitted_at': submitted_at,
            }
        }
    )
    debug("Deactivated %s's submission" % (student_id))


def add_score_to_submissions(
        assignment_id: str,
        student_ids: List[str]
) -> None:
    """Add 1 to score of user submissions"""
    submissions_collection = MongoConnection().get_db()[
        'a_' + str(assignment_id)]
    submissions_collection.update_many(
        {'student_id': {'$in': student_ids}},
        {'$inc': {'score': 1}}
    )
    debug("Added score to %s's submissions" % student_ids)
