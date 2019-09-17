import re
import requests


DEVELOPMENT_TAGS = [':memo:', ':fire:', ':fire_engine:', ':tv:', ':lock:', ':bath:', ':green_heart:', ':cat:', ':bomb:']
RELEASE_TAGS = [':tada:', ':zap:', ':sparkles:', ':rainbow:', ':ambulance:', ':heart_eyes:', ':cherries:', ':book:',
                ':euro:', ':handshake:', ':shield:', ':arrow_up:', ':arrow_down:', ':x:', ':sos:', ':peace_symbol:',
                ':alien:',
]
VERSION_TAGS_DICT = {'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6',
                    'seven': '7', 'eight': '8', 'nine': '9'}
VERSION_TAGS = [':zero:', ':one:', ':two:', ':three:', ':four:', ':five:', ':six:', ':seven:', ':eight:', ':nine:']
REQUIREMENTS_TAGS_OF_VERSION = [':x:', ':arrow_up:', ':arrow_down:', ':tada:']


def get_errors_msgs_commits(travis_repo_slug, travis_pull_request_number, travis_branch, version, token, travis_build_dir, travis_pr_slug):
    symbol_in_branch = re.search(r'-', str(travis_branch))
    #GET /repos/:owner/:repo/pulls/:pull_number/commits
    #See API Github: https://developer.github.com/v3/repos/commits/#list-commits-on-a-repository
    real_errors = {}
    if not travis_pull_request_number or travis_pull_request_number == "false":
        return real_errors
    # GET / repos /: owner /:repo / commits
    url_request = 'https://github.it-projects.info/repos/%s/pulls/%s/commits' % (str(travis_repo_slug), str(travis_pull_request_number))
    resp = requests.get(url_request)
    commits = resp.json()
    if resp.status_code != 200:
        print('GITHUB API response for commits: %s', [resp, resp.headers, commits])
    commit_url = {}
    for commit in commits:
        parents_commit = commit.get('parents')
        if len(parents_commit) > 1:
            # we don't check merge commits
            continue
        url_commit = commit.get('url')
        commit = commit.get('commit').get('message')
        print('Commit: %s' % commit)
        commit_url.update({commit: url_commit})
        if commit:
            first_word = commit.split(' ', 1)[0]
            if first_word == 'Revert':
                continue
            errors_commit = handler_commit(commit, symbol_in_branch, version, travis_build_dir, travis_repo_slug, travis_pull_request_number, travis_branch, travis_pr_slug)
            real_errors.update(errors_commit)
    error_version_docs = check_stable_branch_docs(commit_url)
    real_errors.update(error_version_docs)
    return real_errors


def handler_commit(commit, symbol_in_branch, version, travis_build_dir, travis_repo_slug, travis_pull_request_number, travis_branch, travis_pr_slug):
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


def check_stable_branch_docs(commit_url):
    error_version_docs = {}
    commit_filename_versions = get_changed_version(commit_url)
    error_changelog_index_readme = check_changelog_manifest_index_readme(commit_filename_versions)
    error_version_docs.update(error_changelog_index_readme)
    return error_version_docs


def check_changelog_manifest_index_readme(commit_filename_versions):
    changelog = 'doc/changelog.rst'
    manifest = '__manifest__.py'
    error_changelog_manifest_index_readme = {}
    i = 0
    for commit_msg, filename_versions in commit_filename_versions.items():
        i += 1
        list_changed_files = [filename for filename in filename_versions.keys()]
        error_change_changelog_index_readme = get_change_changelog_index_readme_file(commit_msg, list_changed_files, changelog, i)
        error_changelog_manifest_index_readme.update(error_change_changelog_index_readme)
        error_manifest_changelog = {}
        for filename, versions in filename_versions.items():
            if changelog not in filename:
                continue
            error_changelog = check_changelog_version(filename, commit_msg, versions, i)
            error_manifest_changelog.update(error_changelog)
        error_changelog_manifest_index_readme.update(error_manifest_changelog)
    return error_changelog_manifest_index_readme


# def check_manifest_version(error_version_msg, filename, commit_msg, versions):
#     value_first_old, value_first_new = get_first_second_third_values(versions, first=True)
#     value_second_old, value_second_new = get_first_second_third_values(versions, second=True)
#     value_third_old, value_third_new = get_first_second_third_values(versions)
#     error_manifest = {}
#     version_old = versions[0]
#     base_version = re.search(r'^(\d+.\d).', version_old)
#     if ':sparkles:' in commit_msg:
#         if value_first_new - value_first_old != 1 and value_second_new != 0 and value_third_new != 0:
#             version_true = '{}.{}.{}.{}'.format(base_version, value_first_old + 1, 0, 0)
#             error = {commit_msg: '{}'.format(error_version_msg).format(':sparkles:', filename, version_true)}
#             error_manifest.update(error)
#     if ':zap:' in commit_msg:
#         if value_second_new - value_second_old != 1 and value_third_new != 0:
#             version_true = '{}.{}.{}.{}'.format(base_version, value_first_old, value_second_old + 1, 0)
#             error = {commit_msg: '{}'.format(error_version_msg).format(':zap:', filename, version_true)}
#             error_manifest.update(error)
#     if ':ambulance:' in commit_msg:
#         if value_third_new - value_third_old != 1:
#             version_true = '{}.{}.{}.{}'.format(base_version, value_first_old, value_second_old, value_third_old + 1)
#             error = {commit_msg: '{}'.format(error_version_msg).format(':ambulance:', filename, version_true)}
#             error_manifest.update(error)
#     return error_manifest


def check_changelog_version(filename, commit_msg, versions, i):
    error_version_msg_value = 'If you use tag {} the version in the "{}" file must be updated to {}!'
    error_version_msg_key = '{} commit: {}\nold version is {} and new version is {}'
    error_changelog = {}
    value_first_old, value_first_new = get_first_second_third_values(versions, first=True)
    value_second_old, value_second_new = get_first_second_third_values(versions, second=True)
    value_third_old, value_third_new = get_first_second_third_values(versions)
    if ':sparkles:' in commit_msg:
        if value_first_new - value_first_old != 1 and value_second_new != 0 and value_third_new != 0:
            version_true = '{}.{}.{}'.format(value_first_old + 1, 0, 0)
            error = {'{}'.format(error_version_msg_key).format(i, commit_msg, versions[0], versions[1]):
                         '{}'.format(error_version_msg_value).format(':sparkles:', filename, version_true)}
            error_changelog.update(error)
    if ':zap:' in commit_msg:
        if value_second_new - value_second_old != 1 and value_third_new != 0:
            version_true = '{}.{}.{}'.format(value_first_old, value_second_old + 1, 0)
            error = {'{}'.format(error_version_msg_key).format(i, commit_msg, versions[0], versions[1]):
                         '{}'.format(error_version_msg_value).format(':zap:', filename, version_true)}
            error_changelog.update(error)
    if ':ambulance:' in commit_msg:
        if value_third_new - value_third_old != 1:
            version_true = '{}.{}.{}'.format(value_first_old, value_second_old, value_third_old + 1)
            error = {'{}'.format(error_version_msg_key).format(i, commit_msg, versions[0], versions[1]):
                         '{}'.format(error_version_msg_value).format(':ambulance:', filename, version_true)}
            error_changelog.update(error)
    return error_changelog


def get_change_changelog_index_readme_file(commit_msg, list_changed_files, changelog, i):
    error_change_changelog_manifest_index_readme = {}
    str_change_files = ', '.join(list_changed_files)
    list_readme_index = ['README.rst', 'doc/index.rst']
    error_change_msg = 'If you use one of the tags {} - file(s) {} must be updated!'
    if changelog not in str_change_files:
        error = {'{} commit: {}\nupdated files: {}\nnot updated file: {}'.format(i, commit_msg, str_change_files, changelog):
                '{}'.format(error_change_msg).format(':sparkles:, :zap: or :ambulance:', changelog)}
        error_change_changelog_manifest_index_readme.update(error)
    if ':sparkles:' in commit_msg or ':zap:' in commit_msg:
        error_index_redme = {}
        for file in list_readme_index:
            if file in str_change_files:
                continue
            error = {'{} commit: {}\nupdated files: {}\nnot updated file: {}'.format(i, commit_msg, str_change_files, file):
                    '{}'.format(error_change_msg).format(':sparkles: or :zap:', ' and '.join(list_readme_index))}
            error_index_redme.update(error)
        error_change_changelog_manifest_index_readme.update(error_index_redme)
    return error_change_changelog_manifest_index_readme


def get_first_second_third_values(versions, first=False, second=False):
    if len(versions) > 5:
        if first:
            match = r'^\d+.\d.(\d).'
        elif second:
            match = r'^\d+.\d.\d.(\d).'
        else:
            match = r'^\d+.\d.\d.\d.(\d)'
    else:
        if first:
            match = r'^(\d).'
        elif second:
            match = r'^\d.(\d).'
        else:
            match = r'^\d.\d.(\d)'
    values = [int((re.search(match, value)).group(1)) for value in versions]
    return values


def get_changed_version(commit_url):
    tags = [':sparkles:', ':zap:', ':ambulance:']
    commit_filename_versions = {}
    for commit, url in commit_url.items():
        filename_versions = {}
        url = url.replace('api.github.com', 'github.it-projects.info')
        commit_content = requests.get(url)
        commit_content = commit_content.json()
        commit_msg = commit_content.get('commit').get('message')
        list_tags = re.findall(r'^(:[^\s]+:)', commit_msg)
        release_tag = list(set(list_tags) & set(tags))
        if release_tag == []:
            continue
        files = commit_content.get('files')
        for file in files:
            filename = file.get('filename')
            patch = file.get('patch')
            if '__manifest__.py' in filename:
                versions = re.findall(r'(\d+.\d.\d.\d.\d)', patch)
                filename_versions.update({filename: versions})
            if 'doc/changelog.rst' in filename:
                versions = re.findall(r'(\d+.\d.\d)', patch)
                filename_versions.update({filename: versions})
            if 'doc/index.rst' in filename:
                filename_versions.update({filename: 'Updated!'})
            if 'README.rst' in filename:
                filename_versions.update({filename: 'Updated!'})
        commit_filename_versions[commit_msg] = filename_versions
    return commit_filename_versions


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
