"""Verify the existing RC13 library-projection contract after library creation."""
import json
from datetime import datetime


def assert_projection_preserves_origins(before,after,library_id):
    keys={'source_families':('source_family_key',),'source_media':('media_id',),
          'source_family_members':('source_family_key','media_id')}
    for table,columns in keys.items():
        live={tuple(r[k] for k in columns):r for r in after[table]}
        assert len(live)==len(after[table])
        for row in before[table]:assert live[tuple(row[k] for k in columns)]==row,(table,row)
    old_canon={r['canonical_family_id']:r for r in before['canonical_families']}
    new_canon={r['canonical_family_id']:r for r in after['canonical_families']}
    assert set(old_canon)==set(new_canon)
    for key,old in old_canon.items():
        current=new_canon[key]
        assert {k:v for k,v in old.items() if k!='updated_at'}=={k:v for k,v in current.items() if k!='updated_at'}
        assert datetime.fromisoformat(current['updated_at'])>=datetime.fromisoformat(old['updated_at'])
    originals={r['source_family_key']:r for r in before['source_families']}
    added=[r for r in after['source_families'] if r['source_family_key'] not in originals]
    assert len(added)==len(originals)
    media={r['media_id']:r for r in after['source_media']}
    old_media={r['media_id'] for r in before['source_media']}
    referenced=set();projections=set()
    for family in added:
        metadata=json.loads(family['metadata_json'])
        origin=originals[metadata['projection_origin']]
        assert metadata['library_id']==library_id and metadata['projected_missing_members']==[]
        assert family['backup_id']==library_id+':'+metadata['job_id']
        assert family['family_key']==origin['family_key']
        assert family['canonical_family_id']==origin['canonical_family_id']
        assert metadata['projection_origin'] not in projections
        projections.add(metadata['projection_origin'])
        members=[r for r in after['source_family_members'] if r['source_family_key']==family['source_family_key']]
        original_members=[r for r in before['source_family_members'] if r['source_family_key']==origin['source_family_key']]
        assert len(members)==len(original_members)
        for row in members:
            match=next(r for r in original_members if r['member_order']==row['member_order'])
            assert row['member_role']==match['member_role']
            current=media[row['media_id']];old=media[match['media_id']]
            assert row['media_id'] not in old_media and current['backup_id']==family['backup_id']
            for field in ('relative_path','size_bytes','sha256','media_type'):
                assert current[field]==old[field],(field,current,old)
            referenced.add(row['media_id'])
    assert projections==set(originals)
    assert referenced==set(media)-old_media
    assert len(after['source_family_members'])==2*len(before['source_family_members'])
