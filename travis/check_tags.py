import collections
import re
import requests


DEVELOPMENT_TAGS = [':memo:', ':fire:', ':fire_engine:', ':tv:', ':lock:', ':bath:', ':green_heart:', ':cat:', ':bomb:']
RELEASE_TAGS = [':tada:', ':zap:', ':sparkles:', ':rainbow:', ':ambulance:', ':heart_eyes:', ':cherries:', ':book:',
                ':euro:', ':handshake:', ':shield:', ':arrow_up:', ':arrow_down:', ':x:', ':sos:', ':peace_symbol:',
                ':alien:']
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
    sha_commits = []
    commits_order = []
    for commit in commits:
        parents_commit = commit.get('parents')
        if len(parents_commit) > 1:
            # we don't check merge commits
            continue
        url_commit = commit.get('url')
        sha = commit.get('sha')
        commit = commit.get('commit').get('message')
        print('Commit: %s' % commit)
        commits_order.append(commit)
        commit_url.update({commit: url_commit})
        sha_commits.append(sha)
        if commit:
            first_word = commit.split(' ', 1)[0]
            if first_word == 'Revert':
                continue
            errors_commit = handler_commit(commit, symbol_in_branch, version)
            real_errors.update(errors_commit)
    error_version_docs = check_stable_branch_docs(commit_url, sha_commits, travis_repo_slug, commits_order)
    real_errors.update(error_version_docs)
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


def check_stable_branch_docs(commit_url, sha_commits, travis_repo_slug, commits_order):
    error_version_docs = {}
    commit_filename_versions, commit_manifest = get_changed_version(commit_url, commits_order)
    manifest_commits = {}
    for commit, manifest in commit_manifest:
        if manifest is None:
            continue
        manifest_commits.setdefault(manifest, [])
        manifest_commits[manifest].append(commit)
    # https://developer.github.com/v3/repos/commits/#compare-two-commits
    manifest_version = get_manifest_version(travis_repo_slug, sha_commits)
    if manifest_version != {}:
        for manifest, commit in manifest_commits.items():
            versions = manifest_version.get(manifest)
            str_commit = ', '.join(commit)
            error_manifest = check_manifest_version(manifest, versions, str_commit)
            error_version_docs.update(error_manifest)
    error_changelog_index_readme = check_changelog_index_readme(commit_filename_versions)
    error_version_docs.update(error_changelog_index_readme)
    return error_version_docs


def check_changelog_index_readme(commit_filename_versions):
    changelog = 'doc/changelog.rst'
    error_changelog_manifest_index_readme = {}
    for commit_msg, filename_versions in commit_filename_versions.items():
        list_changed_files = [filename for filename in filename_versions.keys()]
        error_change_changelog_manifest_index_readme = get_change_changelog_index_readme_file(commit_msg, list_changed_files, changelog)
        error_changelog_manifest_index_readme.update(error_change_changelog_manifest_index_readme)
        error_changelog = {}
        for filename, versions in filename_versions.items():
            if changelog not in filename or versions is not 'Updated!':
                continue
            error_changelog = check_changelog_version(filename, commit_msg, versions)
            error_changelog.update(error_changelog)
        error_changelog_manifest_index_readme.update(error_changelog)
    return error_changelog_manifest_index_readme


def get_manifest_version(travis_repo_slug, sha_commits):
    manifest = '__manifest__.py'
    sha_start = sha_commits[0]
    sha_end = sha_commits[-1]
    # GET /repos/:owner/:repo/compare/:base...:head
    url_request = 'https://github.it-projects.info/repos/{}/compare/{}~1...{}'.format(
        str(travis_repo_slug), str(sha_start),  str(sha_end))
    resp = requests.get(url_request)
    compare = resp.json()
    if resp.status_code != 200:
        print('GITHUB API response for compare two commits: %s', [resp, resp.headers, compare])
    updated_files = compare.get('files')
    manifest_versions = {}
    for file in updated_files:
        filename = file.get('filename')
        if manifest not in filename:
            continue
        patch = file.get('patch')
        versions = re.findall(r'(\d+.\d+.\d+.\d+.\d+)', patch)
        manifest_versions[filename] = versions
    return manifest_versions


def check_manifest_version(manifest, versions, str_commit):
    error_version_msg_value = 'If you use tag(s) {} the version in the "{}" file must be updated to {}!'
    error_version_msg_key = 'commit(s): {}\nold version is {} and new version is {}'
    error_manifest = {}
    version_old = versions[0]
    base_version = re.search(r'^(\d+.\d+).', version_old).group(1)
    match_tags_commit = re.findall(r'(:[^\s]+:)', str_commit)
    match_tags_commit_str = ', '.join(match_tags_commit)
    versions_need = versions
    version_true = versions[-1]
    error_indicator = False
    for tag in match_tags_commit:
        if tag == ':sparkles:':
            value_first_old, value_second_old, value_third_old, value_first_new,  value_second_new,  value_third_new = get_first_second_third_values(versions_need)
            if value_first_new <= value_first_old or value_second_new != 0 or value_third_new != 0:
                version_true = '{}.{}.{}.{}'.format(base_version, "(" + str(value_first_old) + " + \{NUMBER_OF_NEW_FEATURES\})", 0, 0)
                if error_indicator:
                    versions_need = [versions_need[-1], version_true]
                else:
                    versions_need = [version_true, version_true]
                    error_indicator = True
        if tag == ':zap:':
            value_first_old, value_second_old, value_third_old, value_first_new,  value_second_new,  value_third_new = get_first_second_third_values(versions_need)
            if value_second_new <= value_second_old or value_third_new != 0:
                version_true = '{}.{}.{}.{}'.format(base_version, value_first_old, "(" + str(value_second_old) + " + \{NUMBER_OF_IMPROVEMENTS\})", 0)
                if error_indicator:
                    versions_need = [versions_need[-1], version_true]
                else:
                    versions_need = [version_true, version_true]
                    error_indicator = True
        if tag == ':ambulance:':
            value_first_old, value_second_old, value_third_old, value_first_new,  value_second_new,  value_third_new = get_first_second_third_values(versions_need)
            if value_third_new <= value_third_old:
                version_true = '{}.{}.{}.{}'.format(base_version, value_first_old, value_second_old, "(" + str(value_third_old) + " + \{NUMBER_OF_FIXES\})")
                if error_indicator:
                    versions_need = [versions_need[-1], version_true]
                else:
                    versions_need = [version_true, version_true]
                    error_indicator = True
    if error_indicator:
        error = {'{}'.format(error_version_msg_key).format(str_commit, versions[0], versions[1]):
                     '{}'.format(error_version_msg_value).format(match_tags_commit_str, manifest, version_true)}
    else:
        error = {}
    error_manifest.update(error)
    return error_manifest


def check_changelog_version(filename, commit_msg, versions):
    error_version_msg_value = 'If you use tag {} the version in the "{}" file must be updated to {}!'
    error_version_msg_key = 'commit: {}\nold version is {} and new version is {}'
    error_changelog = {}
    value_first_old, value_second_old, value_third_old, value_first_new,  value_second_new,  value_third_new = get_first_second_third_values(versions)
    if ':sparkles:' in commit_msg:
        if value_first_new - value_first_old != 1 or value_second_new != 0 or value_third_new != 0:
            version_true = '{}.{}.{}'.format(value_first_old + 1, 0, 0)
            error = {'{}'.format(error_version_msg_key).format(commit_msg, versions[0], versions[1]):
                         '{}'.format(error_version_msg_value).format(':sparkles:', filename, version_true)}
            error_changelog.update(error)
    if ':zap:' in commit_msg:
        if value_second_new - value_second_old != 1 or value_third_new != 0:
            version_true = '{}.{}.{}'.format(value_first_old, value_second_old + 1, 0)
            error = {'{}'.format(error_version_msg_key).format(commit_msg, versions[0], versions[1]):
                         '{}'.format(error_version_msg_value).format(':zap:', filename, version_true)}
            error_changelog.update(error)
    if ':ambulance:' in commit_msg:
        if value_third_new - value_third_old != 1:
            version_true = '{}.{}.{}'.format(value_first_old, value_second_old, value_third_old + 1)
            error = {'{}'.format(error_version_msg_key).format(commit_msg, versions[0], versions[1]):
                         '{}'.format(error_version_msg_value).format(':ambulance:', filename, version_true)}
            error_changelog.update(error)
    return error_changelog


def get_change_changelog_index_readme_file(commit_msg, list_changed_files, changelog):
    error_change_changelog_manifest_index_readme = {}
    tags = [':sparkles:', ':zap:', ':ambulance:']
    str_tags = ' or '.join(tags)
    srt_tags_readme_index = ' or '.join(tags[:-1])
    str_change_files = ', '.join(list_changed_files)
    list_readme_index = ['README.rst', 'doc/index.rst']
    str_readme_index = ' or '.join(list_readme_index)
    error_change_msg = 'If you use one of the tags {} - file(s) {} must be updated!'
    list_tags = re.findall(r'^(:[^\s]+:)', commit_msg)
    release_tag = list(set(list_tags) & set(tags))
    if release_tag == []:
        return error_change_changelog_manifest_index_readme
    if changelog not in str_change_files:
        error = {
            'commit: {}\nupdated files: {}\nnot updated file: {}'.format(commit_msg, str_change_files, changelog):
                '{}'.format(error_change_msg).format(str_tags, changelog)}
        error_change_changelog_manifest_index_readme.update(error)
    if ':ambulance:' not in release_tag:
        error_index_redme = {}
        if 'README.rst' in str_change_files or 'doc/index.rst' in str_change_files:
            pass
        else:
            error = {'commit: {}\nupdated files: {}\nnot updated file: {}'.format(commit_msg, str_change_files, str_readme_index):
                    '{}'.format(error_change_msg).format(srt_tags_readme_index, ' or '.join(list_readme_index))}
            error_index_redme.update(error)
        error_change_changelog_manifest_index_readme.update(error_index_redme)
    return error_change_changelog_manifest_index_readme


def get_first_second_third_values(versions):
    result = []
    for version in versions:
        result += list(re.match(r".*(\d+)\.(\d+)\.(\d+)$", version).groups())
    result = list(map(int, result))
    return result


def get_changed_version(commit_url, commits_order):
    commits_order_filtered = []
    for commit in commits_order:
        if ':sparkles:' in commit or ':zap:' in commit or ':ambulance:' in commit:
            commits_order_filtered.append(commit)
    tags = [':sparkles:', ':zap:', ':ambulance:']
    commit_filename_versions = {}
    commit_manifest = {}
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
                commit_manifest[commit_msg] = filename
            if 'doc/changelog.rst' in filename:
                update_of_version_from_patch = re.search(r'\+`(\d+.\d+.\d+)', patch)
                if update_of_version_from_patch:
                    update_of_version_from_patch = update_of_version_from_patch.group(1)
                    raw_url = file.get('raw_url')
                    resp = requests.get(raw_url)
                    changelog_content = resp.text
                    versions = re.findall(r'(\d+.\d+.\d+)', changelog_content)
                    versions = [update_of_version_from_patch, versions[1]]
                    versions = sorted(versions)
                    filename_versions.update({filename: versions})
                else:
                    filename_versions.update({filename: 'Updated!'})
            if 'doc/index.rst' in filename:
                filename_versions.update({filename: 'Updated!'})
            if 'README.rst' in filename:
                filename_versions.update({filename: 'Updated!'})
        commit_filename_versions[commit_msg] = filename_versions
    commit_manifest = list((i, commit_manifest.get(i)) for i in commits_order_filtered)
    return commit_filename_versions, commit_manifest


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