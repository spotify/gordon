How to Contribute
=================

Every open source project lives from the generous help by contributors that sacrifice their time and ``gordon`` is no different.


This project adheres to the `Open Code of Conduct`_. By participating, you are expected to honor this code. If the core project maintainers/owners feel that this Code of Conduct has been violated, we reserve the right to take appropriate action, including but not limited to: private or public reprimand; temporary or permanent ban from the project; request for public apology.


Communication/Support
---------------------

Feel free to drop by the `Spotify FOSS Slack organization`_ in the #gordon channel.

Contributor Guidelines/Requirements
-----------------------------------

Contributors should expect a response within one week of an issue being opened or a pull request being submitted. More time should be allowed around holidays. Feel free to ping your issue or PR if you have not heard a timely response.

Submitting Bugs
~~~~~~~~~~~~~~~

Before submitting, users/contributors should do the following:

* Basic troubleshooting:
    - Make sure you’re on the latest supported version. The problem may be solved already in a later release.
    - Try older versions. If you’re on the latest version, try rolling back a few minor versions. This will help maintainers narrow down the issue.
    - Try the same for dependency versions - up/downgrading versions.
* Search the project’s issues to make sure it’s not already known, or if there is already an outstanding pull request to fix it.
* If you don’t find a pre-existing issue, check the discussion on Slack. There may be some discussion history, and if not, you can ask for help in figuring out if it’s a bug or not.

What to include in a bug report:

* What version of Python is being used? i.e. 2.7.13, 3.6.2, PyPy 2.0
* What operating system are you on? i.e. Ubuntu 14.04, RHEL 7.4
* What version(s) of the software are you using?
* How can the developers recreate the bug? Steps to reproduce or a simple base case that causes the bug is extremely helpful.


Contributing Patches
~~~~~~~~~~~~~~~~~~~~

No contribution is too small. We welcome fixes for typos and grammar bloopers just as much as feature additions and fixes for code bloopers!

* Check the outstanding issues and pull requests first to see if development is not already being done for what you which to change/add/fix.
* If an issue has the ``available`` label on it, it’s up for grabs for anyone to work on. If you wish to work on it, just comment on the ticket so we can remove the ``available`` label.
* Do not break backwards compatibility.
* Once any feedback is addressed, please comment on the pull request with a short note, so we know that you’re done.
* Write `good commit messages`_.


Workflow
********

* This project follows the `gitflow`_ branching model. Please name your branch accordingly.
* Always make a new branch for your work, no matter how small. Name the branch a short clue to the problem you’re trying to fix or feature you’re adding.
* Ideally, a branch should map to a pull request. It is possible to have multiple pull requests on one branch, but is discouraged for simplicity.
* Do not submit unrelated changes on the same branch/pull request.
* Multiple commits on a branch/pull request is fine, but all should be atomic, and relevant to the goal of the PR. Code changes for a bug fix, plus additional tests (or fixes to tests) and documentation should all be in one commit.
* Pull requests should be rebased off of the ``develop`` branch.
* To finish and merge a release branch, project maintainers should first create a PR to merge the branch into ``develop``. Then, they should merge the release branch into ``master`` locally and push to master afterwards.
* Bugfixes meant for a specific release branch should be merged into that branch through PRs.

Code
****

* See docs on how to setup your environment for development.
* Code should follow the `Google Python Style Guide`_.
* Documentation is not optional.
    - Docstrings are required for public API functions, methods, etc. Any additions/changes to the API functions should be noted in their docstrings (i.e. “added in 2.5”)
    - If it’s a new feature, or a big change to a current feature, consider adding additional prose documentation, including useful code snippets.
* Tests aren’t optional.
    - Any bug fix should have a test case that invokes the bug.
    - Any new feature should have test coverage hitting at least $PERCENTAGE.
    - Make sure your tests pass on our CI. You will not get any feedback until it’s green, unless you ask for help.
    - Write asserts as “expected == actual” to avoid any confusion.
    - Add good docstrings for test cases.

Github Labels
~~~~~~~~~~~~~

The super secret decoder ring for the labels applied to issues and pull requests.

Triage Status
*************

* ``needs triaging``: a new issue or pull request that needs to be triaged by the goalie
* ``no repro``: a filed (closed) bug that can not be reproduced - issue can be reopened and commented upon for more information
* ``won’t fix``: a filed issue deemed not relevant to the project or otherwise already answered elsewhere (i.e. questions that were answered via linking to documentation or stack overflow, or is about GCP products/something we don’t own)
* ``duplicate``: a duplicate issue or pull request
* ``waiting for author``: issue/PR has questions or requests feedback, and is awaiting the other for a response/update


Development Status
******************

To be prefixed with ``Status:``, e.g. ``Status: abandoned``.

* ``abandoned``: issue or PR is stale or otherwise abandoned
* ``available``: bug/feature has been confirmed, and is available for anyone to work on (but won’t be worked on by maintainers)
* ``blocked``: issue/PR is blocked (reason should be commented)
* ``completed``: issue has been addressed (PR should be linked)
* ``wip``: issue is currently being worked on
* ``on hold``: issue/PR has development on it, but is currently on hold (reason should be commented)
* ``pending``: the issue has been triaged, and is pending prioritization for development by maintainers
* ``review needed``: awaiting a review from project maintainers

Types
*****

To be prefixed with ``Type:`` e.g. ``Type: bug``.

* ``bug``: a bug confirmed via triage
* ``feature``: a feature request/idea/proposal
* ``improvement``: an improvement on existing features
* ``maintenance``: a task for required maintenance (e.g. update a dependency for security patches)
* ``extension``: issues, feature requests, or PRs that support other services/libraries separate from core


Local Development Environment
-----------------------------

TODO

.. _`Open Code of Conduct`: https://github.com/spotify/code-of-conduct/blob/master/code-of-conduct.md
.. _`Spotify FOSS Slack organization`: https://slackin.spotify.com/
.. _`gitflow`: http://nvie.com/posts/a-successful-git-branching-model/
.. _`good commit messages`: http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html
.. _`Google Python Style Guide`: https://google.github.io/styleguide/pyguide.html
