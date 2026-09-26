# Partial publication and stale feeds

Status: Accepted
Date: 2026-09-26

An Update Run publishes and commits every successfully obtained Feed even when another Feed fails.
Failed feeds retain their previous files as Stale Feeds, and the workflow fails only after committing
successful changes so consumers receive the freshest available data while operators still receive
a failure notification.
