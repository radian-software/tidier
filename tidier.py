#!/usr/bin/env python3

import collections
from datetime import datetime, timezone
import functools
import os
import re
import sys
import textwrap

import dotenv
import github
import gql
from gql import gql as GraphQLQuery
from gql.transport.requests import RequestsHTTPTransport
import requests

dotenv.load_dotenv()

NotSet = object()

DEFAULT_COMMENT_FORMAT = """\
This thread is being closed automatically by \
[Tidier](https://github.com/radian-software/tidier) because it is labeled with \
"{label}" and has not seen any activity for {num_days} days. But don't \
worry—if you have any information that might advance the discussion, \
leave a comment and I will be happy to reopen the thread :)\
"""


def die(message):
    """
    Print message to stderr and exit with failure.
    """
    print("tidier: " + message, file=sys.stderr)
    sys.exit(1)


def done():
    """
    Print newline and "Done!" to stdout and exit with success.
    """
    print()
    print("Done!")
    sys.exit(0)


def get_environ_var(name, default=NotSet) -> str:
    """
    Get value of environment variable with given name. If not set,
    return default. If default is not given, then die and ask the user
    to set the environment variable.
    """
    if name not in os.environ and default is NotSet:
        die("you must set ${}".format(name))
    return os.environ.get(name, default)  # type: ignore


def get_issue_repo_name(issue):
    match = re.fullmatch(
        r"https://api.github.com/repos/([^/]+/[^/]+)/issues/[0-9]+", issue.url
    )
    if not match:
        die("unexpected error response from GitHub API")
    return match.group(1)


def normalize_boolean(value):
    if value == "0" or "no".startswith(value.lower()):
        return ""
    return value


@functools.cache
def get_graphql_client(token: str):
    return gql.Client(
        transport=RequestsHTTPTransport(
            url="https://api.github.com/graphql",
            headers={"Authorization": f"Bearer {token}"},
        ),
    )


@functools.cache
def get_graphql_issue_id(client: gql.Client, owner: str, repo: str, number: int):
    return client.execute(
        GraphQLQuery(
            """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    issueOrPullRequest(number: $number) {
      ... on Issue {
        id
      }
      ... on PullRequest {
        id
      }
    }
  }
}
    """
        ),
        variable_values={
            "owner": owner,
            "repo": repo,
            "number": number,
        },
    )["repository"]["issueOrPullRequest"]["id"]


def close_issue(client: gql.Client, graphql_issue_id: str):
    """
    Close the issue with the given internal ID returned from
    get_graphql_issue_id. Why use this method instead of the REST API?
    Because only with the GraphQL API is it possible to close an issue
    when having only triage permission on the repository. This makes
    zero sense but is just a documented bug in the REST API.
    """
    client.execute(
        GraphQLQuery(
            """
mutation($id: ID!) {
  closeIssue(input: {issueId: $id, stateReason: NOT_PLANNED}) {
    clientMutationId
  }
}
        """
        ),
        variable_values={
            "id": graphql_issue_id,
        },
    )


token = get_environ_var("TIDIER_ACCESS_TOKEN").strip()
label = get_environ_var("TIDIER_LABEL", default="waiting on response")
include = get_environ_var("TIDIER_INCLUDE_REPOS", default=".*")
exclude = get_environ_var("TIDIER_EXCLUDE_REPOS", default="(?!)")
num_days = get_environ_var("TIDIER_NUM_DAYS", default="90")
comment_format = get_environ_var(
    "TIDIER_COMMENT_FORMAT", default=DEFAULT_COMMENT_FORMAT
)
for_real = get_environ_var("TIDIER_FOR_REAL", default="")
webhook = get_environ_var("TIDIER_WEBHOOK", default="")

try:
    num_days = int(num_days)
except ValueError:
    die("number of days not an integer: {}".format(num_days))

if num_days < 0:
    die("number of days is negative: {}".format(num_days))

for_real = normalize_boolean(for_real)
webhook = normalize_boolean(webhook)

if not re.fullmatch(r'[^"]+', label):
    die("unacceptable label name: {}".format(label))

try:
    re.compile(include)
except re.error:
    die("invalid include regex: {}".format(include))

try:
    re.compile(exclude)
except re.error:
    die("invalid exclude regex: {}".format(exclude))

comment_text = comment_format.format(label=label, num_days=num_days)

print("Configuration")
print("  label: {}".format(label))
print("  include regex: {}".format(include))
print("  exclude regex: {}".format(exclude))
print("  number of days before closing: {}".format(num_days))
print("  for real: {}".format("yes" if for_real else "no"))
print(
    "  webhook: {}{}".format(
        webhook or "(none)", " (disabled)" if webhook and not for_real else ""
    )
)
print("  comment text:")
print(textwrap.indent(textwrap.fill(comment_text), " " * 4))
print()

now = datetime.now(timezone.utc)

print("Timestamp")
print("  {}".format(now))
print()

graphql_client = get_graphql_client(token)

print('Search for issues with label "{}"'.format(label))
g = github.Github(token)
all_issues = list(g.search_issues('label:"{}"'.format(label)))

if not all_issues:
    print("  No issues found")
    done()

all_issues_by_repo = collections.defaultdict(list)
for issue in all_issues:
    all_issues_by_repo[get_issue_repo_name(issue)].append(issue)

print("Retrieve list of repositories to which you have access")
you = g.get_user()
your_username = you.login
your_repo_names = {repo.full_name for repo in you.get_repos()}

if not your_repo_names:
    print("  No repositories found")
    done()

print()
print("Check your permissions on the repositories")
issues_by_repo = {}
for repo_name, issues in all_issues_by_repo.items():
    if repo_name not in your_repo_names:
        continue
    print("  Repository {}".format(repo_name))
    if not re.fullmatch(include, repo_name):
        print("    Excluding: does not match include regex")
        continue
    if re.fullmatch(exclude, repo_name):
        print("    Excluding: matches exclude regex")
        continue
    print("--> Including: all checks passed")
    issues_by_repo[repo_name] = issues
print()

print("Process issues and pull requests")
for repo_name, issues in issues_by_repo.items():
    print("  Repository {}".format(repo_name))
    for issue in issues:
        issue_type = "Pull request" if issue.pull_request else "Issue"
        print("    {} #{}: {}".format(issue_type, issue.number, issue.title))
        if issue.state == "open":
            how_old = now - issue.updated_at
            if how_old.days >= num_days:
                if for_real:
                    print(
                        "      Closing: {} days since last activity".format(
                            how_old.days
                        )
                    )
                    # Close the issue first because it's possible that we
                    # can comment but not close, if the code above doesn't
                    # do a good job of filtering out repositories where we
                    # aren't collaborators.
                    close_issue(
                        graphql_client,
                        get_graphql_issue_id(
                            graphql_client,
                            issue.repository.owner.login,
                            issue.repository.name,
                            issue.number,
                        ),
                    )
                    issue.create_comment(comment_text)
                    issue.remove_from_labels(label)
                else:
                    print(
                        "----> Would close: {} days since last activity".format(
                            how_old.days
                        )
                    )
            else:
                print(
                    "      Not closing: {} days since last activity".format(
                        how_old.days
                    )
                )
        else:
            if for_real:
                print("      Removing label: already closed")
                issue.remove_from_labels(label)
            else:
                print("----> Would remove label: already closed")

if webhook:
    print()
    print("Webhook {}".format(webhook))
    if for_real:
        print("  {}".format(requests.get(webhook)))
    else:
        print("  Skipping")

done()
