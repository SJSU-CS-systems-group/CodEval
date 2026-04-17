# running from cron

if you run the test_submissions.sh script from corn, you are going to want to use an ssh key without a password to access git.
add the following line into git to make sure the correct key is used:

    GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519'
