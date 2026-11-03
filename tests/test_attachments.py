import hashlib
from backend.attachments import Archive, references


def test_snapshot_survives_deletion_and_cannot_be_overwritten(tmp_path):
    home = tmp_path / 'home'
    cache = home / 'cache/documents'
    cache.mkdir(parents=True)
    source = cache / 'program.exe'
    source.write_bytes(b'MZ-original')
    archive = Archive(tmp_path / 'archive')
    body = f"[The user sent a document: 'program.exe'. It is saved at: {source}. Its text is not inlined here]"
    archive.capture(home, 'session', 1, 'user', body)
    row = archive.listing(home, 'session')[0]
    assert row['sha256'] == hashlib.sha256(b'MZ-original').hexdigest()
    source.write_bytes(b'changed')
    archive.capture(home, 'session', 1, 'user', body)
    source.unlink()
    archive.capture(home, 'session', 1, 'user', body)
    assert (archive.root / row['id']).read_bytes() == b'MZ-original'
    archive.capture(home, 'session', 2, 'assistant', f'MEDIA:{source}')
    assert archive.listing(home, 'session')[1]['status'] == 'missing'
    assert archive.listing(home, 'other') == []


def test_arbitrary_files_and_symlinks_are_not_archived(tmp_path):
    home = tmp_path / 'home'
    (home / 'cache').mkdir(parents=True)
    secret = tmp_path / 'secret'
    secret.write_text('secret')
    link = home / 'cache/link'
    link.symlink_to(secret)
    archive = Archive(tmp_path / 'archive')
    for i, path in enumerate([secret, link]):
        archive.capture(home, 's', i, 'assistant', f'MEDIA:{path}')
    assert all(r['status'] == 'blocked' for r in archive.listing(home, 's'))
    assert references('tool', f'MEDIA:{secret}') == []


def test_display_removes_only_matched_transport_annotation():
    from backend.attachments import display_text
    path = '/home/ubuntu/.hermes/cache/documents/file.exe'
    note = f"[The user sent a document: 'file.exe'. It is saved at: {path}. Its text is not inlined here (binary). To read it, extract the document yourself.]"
    body = note + '\n\n这是什么文件\n[Attachment: file.exe]'
    files = [{'name': 'file.exe'}]
    assert display_text('user', body, files) == '这是什么文件'
    assert display_text('user', note, files) == ''
    assert display_text('user', body, []) == body
    assert display_text('assistant', f'文件已发送\nMEDIA:{path}', files) == '文件已发送'
