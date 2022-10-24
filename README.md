# Tidier

Tidier cleans up old GitHub issues and pull requests. By default,
Tidier looks for issues and pull requests that have the label `waiting
on response`, and closes them with a friendly comment if no activity
has occurred for 90 days. This allows you to leave behind bug reports
that were never followed up, without needing to aggressively close
issues ahead of time.

## Usage

This is a standard Python app. [Install the dependencies][pipenv] in
`Pipfile.lock`, then run `tidier.py`. You will probably want to do
this in a [cron job][cron] or something similar. I would recommend
creating a free [Railway] app. Then you can set Tidier's environment
variables (see below) as variables.

## Configuration

Configuration is done through environment variables.

* `TIDIER_ACCESS_TOKEN` **(Mandatory)** Personal access token for the
  GitHub API. Needs the `public_repo` scope at least, and possibly
  `repo` if you want Tidier to manage your private repositories also.
* `TIDIER_FOR_REAL` (Defaults to disabled) Unless this variable is
  set, Tidier will do a dry run and tell you what it would close, if
  anything.
* `TIDIER_LABEL` (Defaults to `waiting on response`) The label used to
  identify issues and pull requests that should be closed.
* `TIDIER_INCLUDE_REPOS` (Defaults to including everything) Regex that
  repository names (e.g. `raxod502/straight.el`) must match to be
  considered.
* `TIDIER_EXCLUDE_REPOS` (Defaults to excluding nothing) Regex that
  repository names must **not** match to be considered.
* `TIDIER_NUM_DAYS` (Defaults to 90) Number of days of inactivity
  after which issues and pull requests will be closed.
* `TIDIER_COMMENT_FORMAT` (See below) Template for comment that is
  posted.
* `TIDIER_WEBHOOK` (Defaults to none) URL to which to send an HTTP
  request after Tidier finishes. For example, this allows you to
  integrate with [Dead Man's Snitch][dms] for error reporting.

### Comment format

The default `TIDIER_COMMENT_FORMAT` (with newlines added for
readability) is:

    This thread is being closed automatically by
    [Tidier](https://github.com/radian-software/tidier) because it is labeled with
    "{label}" and has not seen any activity for {num_days} days. But don't
    worry—if you have any information that might advance the discussion,
    leave a comment and the thread may be reopened :)

This is run through Python's `str.format`, so it can use the `{label}`
and `{num_days}` templates. Then the comment will be interpreted by
GitHub as [Markdown].

## Operation

Tidier uses the [GitHub API v3][github-api]. First, it performs a
search for all open issues with the label you specify. That means
Tidier will run faster if you use a less popular label. Then, Tidier
retrieves a list of all the repositories to which you have explicit
access, and uses this to prune the search results. Next, Tidier checks
whether you are a collaborator on the remaining repositories, so that
it can skip ones where you do not permission to close issues. (At this
stage, Tidier also applies the regexes you may have provided in
`TIDIER_INCLUDE_REPOS` and `TIDIER_EXCLUDE_REPOS`.) Finally, Tidier
iterates through the issues by repository, checking if their "last
updated" time is too long ago.

## See also

I previously used [NO CARRIER][no-carrier], until it broke one too
many times. The problems with NO CARRIER are manifold: it has an order
of magnitude more lines of code than it needs to have (~1,100 versus
~200); it is written in overengineered spaghetti-[Scala]; the build
system is byzantine (compare [here][no-carrier-build-1],
[here][no-carrier-build-2], [here][no-carrier-build-3] versus [this
project][tidier-build]); and it lacks facilities for either
customizing the comment format (see [open
issue][no-carrier-comment-format]) or iterating over all your
repositories. Hence this project, which replaces it entirely.

[cron]: https://en.wikipedia.org/wiki/Cron
[dms]: https://deadmanssnitch.com/
[github-api]: https://developer.github.com/v3/
[markdown]: https://guides.github.com/features/mastering-markdown/
[no-carrier]: https://github.com/twbs/no-carrier
[no-carrier-build-1]: https://github.com/twbs/no-carrier/blob/502932181d5c2573d7ffece50d18a788f63b8693/build.sbt
[no-carrier-build-2]: https://github.com/twbs/no-carrier/blob/502932181d5c2573d7ffece50d18a788f63b8693/project/build.properties
[no-carrier-build-3]: https://github.com/twbs/no-carrier/blob/502932181d5c2573d7ffece50d18a788f63b8693/project/plugins.sbt
[no-carrier-comment-format]: https://github.com/twbs/no-carrier/issues/22
[pipenv]: https://pipenv.readthedocs.io/en/latest/
[railway]: https://railway.app/
[scala]: https://www.scala-lang.org/
[tidier-build]: https://github.com/radian-software/tidier/blob/b69dd894301bf532d8849fa5cc2ffe73abb40cae/Pipfile
