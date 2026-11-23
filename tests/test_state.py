import copy,json,math,sys,zipfile
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from state import Store,validate,DEFAULT

def test_defaults_are_independent(tmp_path):
    a=Store(tmp_path/'a');b=Store(tmp_path/'b');a.data['widgets']['clock']['x']=999
    assert b.data['widgets']['clock']['x']==DEFAULT['widgets']['clock']['x']

def test_atomic_round_trip_and_corrupt_recovery(tmp_path):
    a=Store(tmp_path);a.data['memo']='살구빛 오후\n오늘의 이야기';a.save()
    assert Store(tmp_path).data['memo']==a.data['memo']
    assert not list(tmp_path.glob('*.tmp'))
    a.path.write_text('{bad',encoding='utf-8');b=Store(tmp_path)
    assert b.load_warning and (tmp_path/'settings.damaged.json').read_text()=='{bad'

def test_validate_clamps_and_rejects_nonfinite():
    d=validate({'volume':float('nan'),'dim':float('inf'),'widgets':{'clock':{'x':float('inf'),'y':-400,'scale':200}},'photos':['ok',None,4]})
    assert d['volume']==DEFAULT['volume'] and d['dim']==0
    assert d['widgets']['clock']=={'x':DEFAULT['widgets']['clock']['x'],'y':0,'scale':1.8,'visible':True,'color':''}
    assert d['photos']==['ok']
    json.dumps(d,allow_nan=False)

def test_media_copy_and_dedup(tmp_path):
    file=tmp_path/'한로로 사진.jpg';file.write_bytes(b'photo bytes')
    a=Store(tmp_path/'data');p=a.ingest(file)
    assert p==a.ingest(file) and Path(p).read_bytes()==file.read_bytes()
    file.unlink();assert Path(p).exists()

def test_self_contained_export_import(tmp_path):
    a=Store(tmp_path/'a');p=tmp_path/'사진.png';p.write_bytes(b'media data')
    a.data.update(photos=[str(p)],playlist=[str(p)],background=str(p),imageBackground=str(p),videoBackground=str(p),memo='기록')
    output=tmp_path/'room.hanroom';a.export_scene(output,tmp_path)
    p.unlink();b=Store(tmp_path/'b');b.import_scene(output)
    assert b.data['memo']=='기록'
    assert Path(b.data['photos'][0]).read_bytes()==b'media data'
    assert b.data['photos'][0]==b.data['playlist'][0]==b.data['imageBackground']
    assert len(list(b.media.iterdir()))==1
    with zipfile.ZipFile(output) as z:
        assert all(not name.startswith('/') for name in z.namelist())

@pytest.mark.parametrize('name',['../../escaped','/tmp/escaped','media/../../escaped','media\\..\\escaped','C:/escaped'])
def test_import_rejects_external_paths_without_mutating(tmp_path,name):
    a=Store(tmp_path/'data');a.data['memo']='keep';a.save()
    output=tmp_path/'evil.hanroom'
    with zipfile.ZipFile(output,'w') as z:z.writestr('scene.json',json.dumps({'photos':[name]}));z.writestr(name,b'bad')
    with pytest.raises(ValueError):a.import_scene(output)
    assert a.data['memo']=='keep' and not list(a.media.iterdir())

def test_missing_member_preserves_previous_state(tmp_path):
    a=Store(tmp_path/'data');a.data['memo']='before';a.save();output=tmp_path/'missing.hanroom'
    with zipfile.ZipFile(output,'w') as z:z.writestr('scene.json',json.dumps({'photos':['media/missing.jpg']}))
    with pytest.raises(KeyError):a.import_scene(output)
    assert Store(a.directory).data['memo']=='before'


def test_legacy_room_migration_preserves_user_content():
    old={'version':1,'backgroundMode':'room','memo':'사용자 메모','playlist':['track.flac'],'links':[{'title':'직접 추가','target':'https://example.com','glyph':'globe'}]}
    result=validate(old)
    assert result['backgroundMode']=='image' and result['version']==4
    assert result['memo']=='사용자 메모' and result['playlist']==['track.flac']
    assert result['links'][0]['title']=='직접 추가' and len(result['links'])>8


def test_custom_button_icon_is_portable(tmp_path):
    a=Store(tmp_path/'a');icon=tmp_path/'icon.png';icon.write_bytes(b'custom icon')
    a.data['links']=[{'title':'버튼','target':'https://example.com','glyph':'app','icon':str(icon)}]
    archive=tmp_path/'icon.hanroom';a.export_scene(archive,tmp_path);icon.unlink()
    b=Store(tmp_path/'b');b.import_scene(archive)
    assert Path(b.data['links'][0]['icon']).read_bytes()==b'custom icon'

def test_legacy_tasks_migrate_to_title_and_detail_schema():
    result=validate({'version':3,'tasks':[{'text':'공연 예매','done':False},{'title':'앨범 듣기','detail':'수록곡 전체 듣기','done':True}]})
    assert result['tasks'][0]['title']=='공연 예매'
    assert result['tasks'][0]['detail']==''
    assert result['tasks'][1]['title']=='앨범 듣기'
    assert result['tasks'][1]['detail']=='수록곡 전체 듣기'
    assert result['selectedTask']==-1

def test_task_attachments_survive_theme_export_import(tmp_path):
    a=Store(tmp_path/'a')
    attachment=tmp_path/'poster.png';attachment.write_bytes(b'poster')
    a.data['tasks']=[{'title':'공연 준비','text':'공연 준비','detail':'티켓 확인','done':False,'attachments':[str(attachment)]}]
    a.data['events']=[{'title':'공연','date':'2026-12-01','attachment':str(attachment)}]
    archive=tmp_path/'tasks.hanroom';a.export_scene(archive,tmp_path)
    b=Store(tmp_path/'b');b.import_scene(archive)
    task=b.data['tasks'][0]
    assert task['title']=='공연 준비' and task['detail']=='티켓 확인'
    assert Path(task['attachments'][0]).read_bytes()==b'poster'
    assert Path(b.data['events'][0]['attachment']).read_bytes()==b'poster'

def test_v3_default_memo_calendar_layout_migrates_without_touching_custom_layout():
    default=validate({'version':3,'layoutRevision':3,'widgets':{'memo':{'x':436,'y':296},'calendar':{'x':436,'y':532}}})
    assert default['widgets']['calendar']['x']==820
    custom=validate({'version':3,'layoutRevision':3,'widgets':{'memo':{'x':500,'y':300},'calendar':{'x':900,'y':530}}})
    assert custom['widgets']['calendar']['y']==530
    assert default['layoutRevision']==4
