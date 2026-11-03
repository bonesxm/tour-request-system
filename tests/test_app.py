import os
import tempfile
from pathlib import Path

fd, path = tempfile.mkstemp(suffix='.db')
os.close(fd)
os.environ['TOUR_DB_PATH'] = path
os.environ['TOUR_SEED_DEMO'] = '0'
os.environ['TOUR_ADMIN_PASSWORD'] = 'testpassword123'
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_auth_required():
    assert client.get('/api/requests').status_code == 401

def test_invalid_login():
    assert client.post('/api/login',json={'email':'admin@tour.local','password':'wrong'}).status_code == 401

def test_login():
    r=client.post('/api/login',json={'email':'admin@tour.local','password':'testpassword123'})
    assert r.status_code==200
    assert r.json()['role']=='admin'

def test_create_list_edit_status_export_delete():
    test_login()
    data={'client_name':'Тестовый Клиент','phone':'+7 700 123 12 12','email':'test@example.test',
          'destination':'Алматы, Казахстан','start_date':'2027-04-10','end_date':'2027-04-17',
          'budget':350000,'tourists_count':2,'wishes':'Вид на горы','status':'Новая','manager_id':1}
    r=client.post('/api/requests',json=data)
    assert r.status_code==201,r.text
    rid=r.json()['id']
    rows=client.get('/api/requests?search=Алматы').json()
    assert len(rows)==1 and rows[0]['client_name']=='Тестовый Клиент'
    assert client.patch(f'/api/requests/{rid}/status',json={'status':'Подтверждена'}).status_code==200
    assert client.get('/api/dashboard').json()['counts']['Подтверждена']==1
    assert client.put(f'/api/requests/{rid}',json={**data,'destination':'Астана, Казахстан'}).status_code==200
    assert 'Астана' in client.get('/api/export').text
    assert client.delete(f'/api/requests/{rid}').status_code==200
    assert len(client.get('/api/requests').json())==0

def test_validation():
    test_login()
    x={'client_name':'Тест','destination':'Дубай','tourists_count':0,'status':'Новая'}
    assert client.post('/api/requests',json=x).status_code==422
    x['tourists_count']=1
    x['start_date']='2027-06-10';x['end_date']='2027-06-01'
    assert client.post('/api/requests',json=x).status_code==422
    x['start_date']='2027-06-01';x['end_date']='2027-06-10';x['budget']=-5
    assert client.post('/api/requests',json=x).status_code==422

def test_frontend():
    assert client.get('/').status_code==200
    assert 'TourFlow' in client.get('/').text
    assert client.get('/script.js').status_code==200
    assert client.get('/style.css').status_code==200
