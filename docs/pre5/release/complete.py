"""Complete the frozen pre.5 publication. No git-ref, Docker or registry writer."""
import hashlib
import json
import os
from pathlib import Path
import shutil
from urllib.parse import urlencode

import core as c
import oci
import publish as p

ARTIFACT = 13175578019
ORIGINAL_RUN = 41515697003
ORIGINAL_PUBLISHER = 'cf8702290f3170250aa134d80d52b52472d7c413'
ZIP_SHA = 'e2296cdbfcca63bf8c9b5bbd3e23e84edf123ae4727efbbf556d5b14c3348200'
DIGEST = 'sha256:3c36813f69a3e743d703dc573f1f1359c6c059e9f6183a2e73c756e8a2805d60'
BRANCH = 'codex/complete-1.0.0-pre.5'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def context():
    for key, value in {
        'GITHUB_REPOSITORY': c.REPO, 'GITHUB_REF': 'refs/heads/' + BRANCH,
        'GITHUB_EVENT_NAME': 'push', 'GITHUB_RUN_ATTEMPT': '1',
        'APPROVE_COMPLETE': 'COMPLETE v1.0.0-pre.5',
        'RUNNER_ENVIRONMENT': 'self-hosted', 'RUNNER_OS': 'Linux', 'RUNNER_ARCH': 'X64',
    }.items():
        assert os.environ.get(key) == value, 'Completion context refused: ' + key
    assert c.git('rev-parse', 'HEAD') == os.environ['GITHUB_SHA']
    assert not c.git('diff', '--name-only', 'HEAD')
    c.git('merge-base', '--is-ancestor', ORIGINAL_PUBLISHER, 'HEAD')
    allowed = {'.github/workflows/complete-pre5.yml', 'FORTSETZUNG.md', 'docs/pre5/PROGRESS.md'}
    assert all(n in allowed or n.startswith('docs/pre5/release/')
               for n in c.git('diff', '--name-only', ORIGINAL_PUBLISHER, 'HEAD').splitlines())
    assert c.git('rev-parse', p.BUILD + ':app') == c.git('rev-parse', 'HEAD:app')
    ref = c.github('repos/' + c.REPO + '/git/ref/heads/' + BRANCH)
    assert ref['object']['sha'] == os.environ['GITHUB_SHA']


def identity(work):
    p.unchanged(work)
    ref = c.github('repos/' + c.REPO + '/git/ref/tags/' + p.TAG)
    assert ref['object'] == {
        'sha': p.BUILD, 'type': 'commit',
        'url': 'https://api.github.com/repos/' + c.REPO + '/git/commits/' + p.BUILD,
    }, 'Existing tag changed'
    raw, headers = c.registry_manifest(p.VERSION)
    assert oci.digest(raw) == headers.get('Docker-Content-Digest') == DIGEST
    proof, config, documents = oci.verify_graph(
        DIGEST, c.registry_manifest, lambda ref: c.registry_manifest(ref, blob=True), p.BUILD)
    original = json.loads((work / 'release-assets/OCI-VERIFICATION.json').read_text())
    assert proof == {k: original[k] for k in proof}, 'OCI graph changed'
    assert config['config']['Labels']['org.opencontainers.image.version'] == p.VERSION
    for digest, data in documents.items():
        assert data == (work / ('release-assets/registry-' + digest[7:] + '.json')).read_bytes()


def write_api(url, method, data):
    raw, _ = c.http(url, {
        'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
        'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json',
        'X-GitHub-Api-Version': '2022-11-28',
    }, method, json.dumps(data).encode())
    return json.loads(raw)


def main():
    context()
    work = Path(os.environ['WORK'])
    assert work.is_dir() and not any(work.iterdir()), 'Completion scratch is not empty'
    run = c.github('repos/' + c.REPO + '/actions/runs/' + str(ORIGINAL_RUN))
    assert run['head_sha'] == ORIGINAL_PUBLISHER and run['conclusion'] == 'failure'
    assert run['status'] == 'completed' and run['run_attempt'] == 1
    jobs = c.github('repos/' + c.REPO + '/actions/runs/' + str(ORIGINAL_RUN) + '/jobs')['jobs']
    assert len(jobs) == 1 and jobs[0]['id'] == 125518582502
    steps = {s['number']: s for s in jobs[0]['steps']}
    assert all(steps[n]['conclusion'] == 'success' for n in range(3, 9))
    assert steps[9]['conclusion'] == 'failure' and steps[10]['conclusion'] == 'success'
    meta = c.github('repos/' + c.REPO + '/actions/artifacts/' + str(ARTIFACT))
    assert meta['workflow_run']['id'] == ORIGINAL_RUN and not meta['expired']
    assert meta['workflow_run']['head_sha'] == ORIGINAL_PUBLISHER
    assert meta['digest'] == 'sha256:' + ZIP_SHA
    raw, _ = c.http(meta['archive_download_url'], {'Authorization': 'Bearer ' + os.environ['GH_TOKEN']})
    assert sha(raw) == ZIP_SHA
    original = work / 'original'
    c.safe_extract(raw, original)
    assets = original / 'release-assets'
    sums = (assets / 'SHA256SUMS').read_text().splitlines()
    assert len(sums) == 70
    names = set()
    for line in sums:
        digest, name = line.split('  ', 1)
        assert Path(name).name == name and name not in names and name != 'SHA256SUMS'
        names.add(name)
        assert sha((assets / name).read_bytes()) == digest
    assert {f.name for f in assets.iterdir()} == names | {'SHA256SUMS'}
    assert [f.name for f in assets.iterdir() if f.stat().st_size == 0] == ['QA-SOURCE-DIFF.patch']
    assert (assets / 'QA-SOURCE-DIFF.patch').read_bytes() == b''
    paths = ['app', 'tests', 'qa', 'Dockerfile', 'requirements.txt', 'requirements-rc.constraints.txt']
    assert not c.git('diff', p.BUILD, p.DOC, '--', *paths)
    assert (assets / 'IMAGE-DIGEST.txt').read_text().strip() == p.IMAGE.rsplit(':', 1)[0] + '@' + DIGEST
    # All six original accepted QA ZIPs stay byte-identical and digest-bound.
    for role, spec in p.APPROVAL['artifacts'].items():
        assert 'sha256:' + sha((assets / ('pre5-' + role + '-accepted.zip')).read_bytes()) == spec['digest']
    identity(original)
    assert c.github('repos/' + c.REPO + '/releases/tags/' + p.TAG, missing=True) is None
    assert c.github('repos/' + c.REPO + '/releases/431924706', missing=True) is None
    output = work / 'completed-assets'
    shutil.copytree(assets, output)
    (output / 'QA-SOURCE-DIFF.patch').unlink()
    (output / 'QA-SOURCE-IDENTITY.md').write_text(
        '# No application source difference\n\n'
        'Build/tag: `' + p.BUILD + '`\n\nDocumentation: `' + p.DOC + '`\n\n'
        'The original QA-SOURCE-DIFF.patch is intentionally zero bytes. '
        'The exact git diff between these commits for ' + ', '.join(paths) +
        ' was checked again and is empty. Its SHA-256 is `' + sha(b'') + '`. '
        'No application change is represented or concealed by this replacement.\n\n'
        'GitHub rejected the original zero-byte upload (HTTP 400 Bad Content-Length). '
        'This nonempty explanation replaces that standalone release attachment only. '
        'The original empty file and original SHA256SUMS are preserved unchanged inside '
        'original-publication-evidence.zip, artifact ' + str(ARTIFACT) + ', SHA-256 `' + ZIP_SHA + '`. '
        'The new SHA256SUMS describes the completed release assets. No rebuild, registry push '
        'or git-tag mutation is performed.\n')
    (output / 'original-publication-evidence.zip').write_bytes(raw)
    c.dump(output / 'COMPLETION-EVIDENCE.json', {
        'status': 'PREPUBLICATION_IDENTITIES_VERIFIED', 'application_commit': p.BUILD,
        'tag': p.TAG, 'image_digest': DIGEST, 'original_run': ORIGINAL_RUN,
        'original_artifact': ARTIFACT, 'original_artifact_sha256': ZIP_SHA,
        'completion_run': int(os.environ['GITHUB_RUN_ID']), 'completion_commit': os.environ['GITHUB_SHA'],
        'no_build': True, 'no_push': True, 'no_tag_write': True,
        'only_replaced_asset': 'QA-SOURCE-DIFF.patch -> QA-SOURCE-IDENTITY.md',
        'test_limits': p.APPROVAL['limits'],
    })
    c.checksums(output)
    assert all(f.stat().st_size > 0 for f in output.iterdir())
    context()
    identity(original)
    assert c.github('repos/' + c.REPO + '/releases/tags/' + p.TAG, missing=True) is None
    release_url = 'https://api.github.com/repos/' + c.REPO + '/releases'
    release = write_api(release_url, 'POST', {
        'tag_name': p.TAG, 'target_commitish': p.BUILD, 'name': p.VERSION,
        'body': (output / 'RELEASE-NOTES.md').read_text(),
        'draft': True, 'prerelease': True, 'make_latest': 'false',
    })
    c.dump(work / 'created-draft.json', release)
    assert release['draft'] and release['prerelease'] and release['tag_name'] == p.TAG
    upload_url = release['upload_url'].split('{')[0]
    expected_url = 'https://uploads.github.com/repos/' + c.REPO + '/releases/' + str(release['id']) + '/assets'
    assert upload_url == expected_url
    for path in sorted(output.iterdir()):
        data = path.read_bytes()
        reply, _ = c.http(upload_url + '?' + urlencode({'name': path.name}), {
            'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
            'Content-Type': 'application/octet-stream',
        }, 'POST', data)
        asset = json.loads(reply)
        assert asset['name'] == path.name and asset['state'] == 'uploaded'
        assert asset['size'] == len(data) and asset['digest'] == 'sha256:' + sha(data)
        print('Uploaded and SHA256 verified:', path.name, flush=True)
    current = c.github('repos/' + c.REPO + '/releases/' + str(release['id']))
    expected_names = {f.name for f in output.iterdir()}
    assert current['draft'] and current['prerelease'] and current['tag_name'] == p.TAG
    assert len(current['assets']) == len(expected_names)
    assert {a['name'] for a in current['assets']} == expected_names
    identity(original)
    release = write_api(release_url + '/' + str(release['id']), 'PATCH', {
        'draft': False, 'prerelease': True, 'make_latest': 'false',
    })
    assert not release['draft'] and release['prerelease'] and release['tag_name'] == p.TAG
    downloaded = work / 'downloaded-release'
    downloaded.mkdir()
    final = c.github('repos/' + c.REPO + '/releases/tags/' + p.TAG)
    assert final['id'] == release['id'] and not final['draft'] and final['prerelease']
    assert len(final['assets']) == len(expected_names)
    assert {a['name'] for a in final['assets']} == expected_names
    for asset in final['assets']:
        data, _ = c.http(asset['url'], {
            'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
            'Accept': 'application/octet-stream',
        })
        assert data == (output / asset['name']).read_bytes(), 'Downloaded asset mismatch'
        assert len(data) == asset['size'] and 'sha256:' + sha(data) == asset['digest']
        (downloaded / asset['name']).write_bytes(data)
    for line in (downloaded / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert sha((downloaded / name).read_bytes()) == digest
    identity(original)
    result = {
        'status': 'PASS', 'release': final['html_url'], 'release_id': final['id'],
        'prerelease': True, 'application_commit': p.BUILD, 'tag': p.TAG,
        'image_digest': DIGEST, 'assets': len(expected_names),
        'all_assets_downloaded_and_sha256_verified': True, 'protected_unchanged': True,
        'repository_private': True, 'package_visibility': c.package()['visibility'],
        'no_build': True, 'no_push': True, 'no_tag_write': True,
    }
    c.dump(work / 'completion-result.json', result)
    print(json.dumps(result, indent=2))
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
        f.write('## Pre.5 completion PASS\n\n' + json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
