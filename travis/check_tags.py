import re
import requests


DEVELOPMENT_TAGS = [':memo:', ':fire:', ':fire_engine:', ':tv:', ':lock:', ':bath:', ':green_heart:', ':cat:', ':bomb:']
RELEASE_TAGS = [':tada:', ':zap:', ':sparkles:', ':rainbow:', ':ambulance:', ':heart_eyes:', ':cherries:', ':book:',
                ':euro:', ':handshake:', ':shield:', ':arrow_up:', ':arrow_down:', ':x:', ':sos:', ':peace_symbol:']
VERSION_TAGS_DICT = {'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6',
                    'seven': '7', 'eight': '8', 'nine': '9'}
VERSION_TAGS = [':zero:', ':one:', ':two:', ':three:', ':four:', ':five:', ':six:', ':seven:', ':eight:', ':nine:']
REQUIREMENTS_TAGS_OF_VERSION = [':x:', ':arrow_up:', ':arrow_down:', ':sos:', ':tada:']


def get_errors_msgs_commits(travis_repo_slug, travis_pull_request_number, travis_branch, version, token):
    symbol_in_branch = re.search(r'-', str(travis_branch))

    #GET /repos/:owner/:repo/pulls/:pull_number/commits
    #See API Github: https://developer.github.com/v3/repos/commits/#list-commits-on-a-repository
    real_errors = {}
    if not travis_pull_request_number or travis_pull_request_number == "false":
        return real_errors
    # GET / repos /: owner /:repo / commits
    url_request = 'https://api.github.com/repos/%s/pulls/%s/commits' % (str(travis_repo_slug), str(travis_pull_request_number))
    if token:
        commits = requests.get(url_request, headers={'Authorization': 'token %s' % token})
    else:
        commits = requests.get(url_request)
    commits = commits.json()
    # print('GITHUB API response for commits: %s\n%s', url_request, commits)
    for commit in commits:
        parents_commit = commit.get('parents')
        if len(parents_commit) > 1:
            # we don't check merge commits
            continue
        commit = commit.get('commit').get('message')
        print('Commit: %s' % commit)
        if commit:
            errors_commit = handler_commit(commit, symbol_in_branch, version)
            real_errors.update(errors_commit)
    return real_errors


def handler_commit(commit, symbol_in_branch, version):
    errors_commit = {}
    # looks tags starting at the beginning of the line and until first whitespace
    match_tags_commit = re.search(r'^(:[^\s]+:)', commit)
    if not match_tags_commit:
        error = {commit: 'There are no tags in the commit!'}
        errors_commit.update(error)
        return errors_commit
    match_tags_commit = match_tags_commit.group(1)
    # list of tags from match_tags_commit
    list_tags = re.findall(r'(:\w+:)', match_tags_commit)
    # list of tags that should not be in the commit
    extra_tags = [i for i in list_tags if i not in DEVELOPMENT_TAGS + RELEASE_TAGS + VERSION_TAGS]
    if extra_tags != []:
        error = {commit: 'There should not be such tags in the commit!'}
        errors_commit.update(error)
        return errors_commit
    # lists of Development tag and Release tag in commit
    dev_tag = list(set(list_tags) & set(DEVELOPMENT_TAGS))
    release_tag = list(set(list_tags) & set(RELEASE_TAGS))
    version_tags = list(set(list_tags) & set(VERSION_TAGS))
    if symbol_in_branch:
        errors_dev = check_dev_branch_tags(release_tag, dev_tag, commit)
        errors_commit.update(errors_dev)
    else:
        errors_stable = check_stable_branch_tags(dev_tag, release_tag, commit)
        errors_commit.update(errors_stable)

    if any(tag in REQUIREMENTS_TAGS_OF_VERSION for tag in list_tags):
        errors_version = check_version_tags(version_tags, list_tags, commit, version)
        errors_commit.update(errors_version)
    return errors_commit


def check_version_tags(version_tags, list_tags, commit, version):
    errors_version = {}
    if version_tags == []:
        error = {commit: 'Must be Version tags!'}
        errors_version.update(error)
        return errors_version
    # # list of digit from tag's of commit
    # list_digits = [x.replace(':', '') for x in list_tags if x in VERSION_TAGS]
    # version_in_commit = ''
    # for digit in list_digits:
    #     # calculates version in commit
    #     version_in_commit += VERSION_TAGS_DICT.get(digit)
    # if version.replace(".", "") != version_in_commit:
    #     error = {commit: 'Version in commit is wrong!'}
    #     errors_version.update(error)
    #     return errors_version
    # # list of indices (requirements of version's tags in commit)
    # index_requirements_tags_version = [list_tags.index(i) for i in list_tags if i in REQUIREMENTS_TAGS_OF_VERSION]
    # # list of indices (version's tags in commit)
    # index_verion_tags = [list_tags.index(i) for i in list_tags if i in VERSION_TAGS]
    # # Check proper order of tags in commit: comparison indices "requirements of versions tags" and "versions tags"
    # if not index_requirements_tags_version[-1] < index_verion_tags[0]:
    #     error = {commit: 'Version tag must be after the main tag!'}
    #     errors_version.update(error)
    #     return errors_version
    return errors_version


def check_dev_branch_tags(release_tag, dev_tag, commit):
    errors_dev = {}
    if release_tag != []:
        error = {commit: 'You cannot use release tags in development branch!'}
        errors_dev.update(error)
        return errors_dev
    if dev_tag == []:
        error = {commit: 'There should be a Development tag in the dev branches!'}
        errors_dev.update(error)
        return errors_dev
    # checking the number of dev tags in commit
    if len(dev_tag) > 1:
        error = {commit: 'You must use only one Development tag!'}
        errors_dev.update(error)
        return errors_dev
    return errors_dev


def check_stable_branch_tags(dev_tag, release_tag, commit):
    errors_stable = {}
    if dev_tag != []:
        error = {commit: 'You cannot use Development tag in stable branch!'}
        errors_stable.update(error)
        return errors_stable
    if release_tag == []:
        error = {commit: 'There should be a Release tag in the stable branches!'}
        errors_stable.update(error)
        return errors_stable
    # checking the number of release tags in commit
    if len(release_tag) > 1:
        error = {commit: 'You must use only one Release tag (along with version tags when they are required)!'}
        errors_stable.update(error)
        return errors_stable
    return errors_stable
