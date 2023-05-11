import canvasapi
from commons import warn, info
# from codeval import CanvasHandler

class SubmissionHandler:
    submission: canvasapi.submission.Submission
    
    def __init__(self, submission):
        self.submission = submission

    def upload_attachment(self, path_to_file):
        success = self.submission.upload_comment(path_to_file)
        if success:
            info(f"successfully uploaded {path_to_file} to the submission")
        else:
            warn(f"failed to upload {path_to_file} to the submission")


# def main():
#     canvasHandler = CanvasHandler()
#     course = canvasHandler.get_course("PracticeCourse_Reed_2")
#     assignment = course.get_assignment(6542273)
#     submission = assignment.get_submission(4373187)
#     sHandler = SubmissionHandler(submission)
#     sHandler.upload_attachment("./assignmentFiles/pa01.asm")

# if __name__ == '__main__':
#     main()