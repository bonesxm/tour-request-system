"""Tour Request System: FastAPI + SQLite. Start: python -m uvicorn app:app --reload"""
import csv
import hashlib
import hmac
import io
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('TOUR_DB_PATH', str(ROOT / 'tour_requests.db')))
app = FastAPI(title='Tour Request System', version='1.0.0', docs_url='/api/docs')
STATUSES = ['Новая', 'В обработке', 'Подтверждена', 'Завершена', 'Отменена']

@contextmanager
def db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def pw_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 240000).hex()
    return f'{salt}${digest}'

def pw_check(password, stored):
    try:
        salt, _ = stored.split('$')
        return hmac.compare_digest(pw_hash(password, salt), stored)
    except ValueError:
        return False

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def initialize():
    first_run = not DB.exists()
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS managers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'manager',
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            phone TEXT, email TEXT UNIQUE, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS statuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER NOT NULL,
            manager_id INTEGER, status_id INTEGER NOT NULL,
            destination TEXT NOT NULL, start_date TEXT, end_date TEXT,
            budget REAL, tourists_count INTEGER NOT NULL DEFAULT 1,
            wishes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(client_id) REFERENCES clients(id),
            FOREIGN KEY(manager_id) REFERENCES managers(id),
            FOREIGN KEY(status_id) REFERENCES statuses(id),
            CHECK(tourists_count > 0), CHECK(budget IS NULL OR budget >= 0),
            CHECK(end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, manager_id INTEGER NOT NULL,
            expires TEXT NOT NULL, FOREIGN KEY(manager_id) REFERENCES managers(id)
        );
        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER,
            manager_id INTEGER, action TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_requests_created ON requests(created_at);
        CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status_id);
        CREATE INDEX IF NOT EXISTS idx_requests_client ON requests(client_id);
        ''')
        for s in STATUSES:
            c.execute('INSERT OR IGNORE INTO statuses(name) VALUES (?)', (s,))
        if not c.execute('SELECT 1 FROM managers LIMIT 1').fetchone():
            password = os.environ.get('TOUR_ADMIN_PASSWORD', 'demo1234')
            c.execute('INSERT INTO managers(name,email,password_hash,role) VALUES(?,?,?,?)',
                      ('Администратор', 'admin@tour.local', pw_hash(password), 'admin'))
        if first_run and os.environ.get('TOUR_SEED_DEMO', '1') == '1' and not c.execute('SELECT 1 FROM requests LIMIT 1').fetchone():
            names = [('Алия Садыкова','+7 700 000 01 01','aliya@example.test'),
                     ('Данияр Омаров','+7 700 000 02 02','daniyar@example.test'),
                     ('Аружан Ермекова','+7 700 000 03 03','aruzhan@example.test'),
                     ('Мадина Серикова','+7 700 000 04 04','madina@example.test'),
                     ('Тимур Абдрахманов','+7 700 000 05 05','timur@example.test')]
            for name, phone, email in names:
                c.execute('INSERT INTO clients(name,phone,email,created_at) VALUES(?,?,?,?)', (name,phone,email,now()))
            items=[(1,2,'Анталья, Турция',2,650000,'Семейный отдых',7),
                   (2,1,'Дубай, ОАЭ',2,920000,'Отель 5 звёзд',5),
                   (3,3,'Бали, Индонезия',2,1480000,'Медовый месяц',3),
                   (4,4,'Тбилиси, Грузия',3,470000,'Экскурсии',2),
                   (5,1,'Пхукет, Таиланд',2,1100000,'У моря',1),
                   (1,5,'Стамбул, Турция',1,380000,'Сити-тур',0)]
            for client,status,dest,count,budget,wishes,days in items:
                ts=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat(timespec='seconds')
                c.execute('''INSERT INTO requests(client_id,manager_id,status_id,destination,tourists_count,budget,wishes,created_at,updated_at)
                    VALUES(?,1,?,?,?,?,?,?,?)''',(client,status,dest,count,budget,wishes,ts,ts))

initialize()

class Login(BaseModel):
    email: str
    password: str

class RequestData(BaseModel):
    client_name: str = Field(min_length=2,max_length=150)
    phone: str = Field(default='',max_length=30)
    email: Optional[str] = Field(default=None,max_length=254)
    destination: str = Field(min_length=2,max_length=150)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget: Optional[float] = Field(default=None,ge=0,le=9999999999)
    tourists_count: int = Field(default=1,ge=1,le=1000)
    wishes: str = Field(default='',max_length=3000)
    status: str = Field(default='Новая')
    manager_id: Optional[int] = None

    @field_validator('email')
    @classmethod
    def clean_email(cls, v):
        return v.strip().lower() or None if v is not None else None

    @model_validator(mode='after')
    def validate_dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError('Дата окончания раньше даты начала')
        if self.status not in STATUSES:
            raise ValueError('Неизвестный статус')
        return self

class StatusData(BaseModel):
    status: str

class ManagerData(BaseModel):
    name: str = Field(min_length=2,max_length=150)
    email: str = Field(min_length=5,max_length=254)
    password: str = Field(min_length=8,max_length=128)

def user(request:Request):
    token=request.cookies.get('tour_session')
    if not token: raise HTTPException(401,'Требуется авторизация')
    with db() as c:
        u=c.execute('''SELECT m.id,m.name,m.email,m.role FROM sessions s JOIN managers m ON m.id=s.manager_id
            WHERE s.token_hash=? AND s.expires>? AND m.active=1''',
            (hashlib.sha256(token.encode()).hexdigest(),now())).fetchone()
    if not u: raise HTTPException(401,'Сессия истекла')
    return dict(u)

def protect(request:Request):
    # Browser-side CSRF defense: require same-origin on write requests.
    origin=request.headers.get('origin')
    if origin:
        from urllib.parse import urlsplit
        host=request.headers.get('host','')
        parsed=urlsplit(origin)
        if parsed.netloc != host or parsed.scheme not in ('http','https'):
            raise HTTPException(403,'Недопустимый Origin')
    return user(request)

@app.get('/')
def home():
    return FileResponse(ROOT/'static'/'index.html')

@app.get('/style.css')
def style(): return FileResponse(ROOT/'static'/'style.css',media_type='text/css')

@app.get('/script.js')
def script(): return FileResponse(ROOT/'static'/'script.js',media_type='application/javascript')

@app.post('/api/login')
def login(body:Login,response:Response,request:Request):
    origin=request.headers.get('origin')
    if origin and __import__('urllib.parse',fromlist=['urlsplit']).urlsplit(origin).netloc != request.headers.get('host',''):
        raise HTTPException(403,'Недопустимый Origin')
    with db() as c:
        m=c.execute('SELECT * FROM managers WHERE email=? AND active=1',(body.email.lower().strip(),)).fetchone()
        if not m or not pw_check(body.password,m['password_hash']):
            raise HTTPException(401,'Неверный email или пароль')
        token=secrets.token_urlsafe(40)
        expires=(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat(timespec='seconds')
        c.execute('INSERT INTO sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),m['id'],expires))
    response.set_cookie('tour_session',token,httponly=True,samesite='strict',secure=os.environ.get('TOUR_HTTPS')=='1',max_age=43200)
    return {'id':m['id'],'name':m['name'],'email':m['email'],'role':m['role']}

@app.post('/api/logout')
def logout(request:Request,response:Response):
    token=request.cookies.get('tour_session')
    if token:
        with db() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
    response.delete_cookie('tour_session')
    return {'ok':True}

@app.get('/api/me')
def me(request:Request): return user(request)

@app.get('/api/meta')
def meta(request:Request):
    user(request)
    with db() as c:
        managers=[dict(x) for x in c.execute('SELECT id,name,email,role FROM managers WHERE active=1 ORDER BY name')]
    return {'statuses':STATUSES,'managers':managers}

def full_requests(c, where='',params=()):
    return [dict(x) for x in c.execute('''SELECT r.*,c.name AS client_name,c.phone,c.email,
        m.name AS manager_name,s.name AS status FROM requests r
        JOIN clients c ON c.id=r.client_id
        LEFT JOIN managers m ON m.id=r.manager_id JOIN statuses s ON s.id=r.status_id
        '''+where+' ORDER BY r.created_at DESC, r.id DESC',params)]

@app.get('/api/requests')
def list_requests(request:Request,search:str='',status:str='',sort:str='newest'):
    user(request)
    where=[];args=[]
    if search.strip():
        where.append('(c.name LIKE ? OR r.destination LIKE ? OR c.phone LIKE ? OR CAST(r.id AS TEXT) LIKE ?)')
        args+=['%'+search.strip()+'%']*4
    if status and status!='Все':
        where.append('s.name=?');args.append(status)
    with db() as c:rows=full_requests(c,' WHERE '+' AND '.join(where) if where else '',args)
    if sort=='oldest':rows.reverse()
    if sort=='budget':rows.sort(key=lambda r:r['budget'] or 0,reverse=True)
    return rows

def upsert_client(c,data,old_id=None):
    if old_id:
        c.execute('UPDATE clients SET name=?,phone=?,email=? WHERE id=?',(data.client_name.strip(),data.phone.strip(),data.email,old_id))
        return old_id
    if data.email:
        ex=c.execute('SELECT id FROM clients WHERE email=?',(data.email,)).fetchone()
        if ex:
            c.execute('UPDATE clients SET name=?,phone=? WHERE id=?',(data.client_name.strip(),data.phone.strip(),ex['id']))
            return ex['id']
    cur=c.execute('INSERT INTO clients(name,phone,email,created_at) VALUES(?,?,?,?)',
                  (data.client_name.strip(),data.phone.strip(),data.email,now()))
    return cur.lastrowid

def write_request(c,data,u,request_id=None):
    status_id=c.execute('SELECT id FROM statuses WHERE name=?',(data.status,)).fetchone()['id']
    manager_id=data.manager_id or u['id']
    if not c.execute('SELECT id FROM managers WHERE id=? AND active=1',(manager_id,)).fetchone():
        raise HTTPException(422,'Менеджер не найден')
    if request_id:
        prev=c.execute('SELECT client_id FROM requests WHERE id=?',(request_id,)).fetchone()
        if not prev:raise HTTPException(404,'Заявка не найдена')
        client_id=upsert_client(c,data,prev['client_id'])
        c.execute('''UPDATE requests SET client_id=?,manager_id=?,status_id=?,destination=?,start_date=?,end_date=?,budget=?,
                    tourists_count=?,wishes=?,updated_at=? WHERE id=?''',
                  (client_id,manager_id,status_id,data.destination.strip(),str(data.start_date) if data.start_date else None,
                   str(data.end_date) if data.end_date else None,data.budget,data.tourists_count,data.wishes.strip(),now(),request_id))
        action='Обновлена заявка'
    else:
        client_id=upsert_client(c,data)
        cur=c.execute('''INSERT INTO requests(client_id,manager_id,status_id,destination,start_date,end_date,budget,tourists_count,wishes,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                (client_id,manager_id,status_id,data.destination.strip(),str(data.start_date) if data.start_date else None,
                 str(data.end_date) if data.end_date else None,data.budget,data.tourists_count,data.wishes.strip(),now(),now()))
        request_id=cur.lastrowid;action='Создана заявка'
    c.execute('INSERT INTO activity(request_id,manager_id,action,created_at) VALUES(?,?,?,?)',(request_id,u['id'],action,now()))
    return request_id

@app.post('/api/requests',status_code=201)
def create_request(body:RequestData,request:Request):
    u=protect(request)
    with db() as c:
        try:rid=write_request(c,body,u)
        except sqlite3.IntegrityError as e:raise HTTPException(409,'Конфликт данных: '+str(e))
    return {'id':rid}

@app.put('/api/requests/{request_id}')
def edit_request(request_id:int,body:RequestData,request:Request):
    u=protect(request)
    with db() as c:
        try:rid=write_request(c,body,u,request_id)
        except sqlite3.IntegrityError as e:raise HTTPException(409,'Конфликт данных: '+str(e))
    return {'id':rid}

@app.patch('/api/requests/{request_id}/status')
def change_status(request_id:int,body:StatusData,request:Request):
    u=protect(request)
    if body.status not in STATUSES:raise HTTPException(422,'Неизвестный статус')
    with db() as c:
        status_id=c.execute('SELECT id FROM statuses WHERE name=?',(body.status,)).fetchone()['id']
        cur=c.execute('UPDATE requests SET status_id=?,updated_at=? WHERE id=?',(status_id,now(),request_id))
        if not cur.rowcount:raise HTTPException(404,'Заявка не найдена')
        c.execute('INSERT INTO activity(request_id,manager_id,action,created_at) VALUES(?,?,?,?)',
                  (request_id,u['id'],'Статус изменён: '+body.status,now()))
    return {'ok':True}

@app.delete('/api/requests/{request_id}')
def delete_request(request_id:int,request:Request):
    u=protect(request)
    if u['role']!='admin': raise HTTPException(403,'Удаление доступно администратору')
    with db() as c:
        cur=c.execute('DELETE FROM requests WHERE id=?',(request_id,))
        if not cur.rowcount:raise HTTPException(404,'Заявка не найдена')
        c.execute('INSERT INTO activity(request_id,manager_id,action,created_at) VALUES(?,?,?,?)',
                  (request_id,u['id'],'Удалена заявка',now()))
    return {'ok':True}

@app.get('/api/dashboard')
def dashboard(request:Request):
    user(request)
    with db() as c:
        counts={r['name']:c.execute('SELECT COUNT(*) FROM requests WHERE status_id=?',(r['id'],)).fetchone()[0]
                for r in c.execute('SELECT id,name FROM statuses')}
        total=c.execute('SELECT COUNT(*) FROM requests').fetchone()[0]
        budget=c.execute('SELECT COALESCE(SUM(budget),0) FROM requests WHERE status_id IN (SELECT id FROM statuses WHERE name IN (?,?))',
                         ('Подтверждена','Завершена')).fetchone()[0]
        recent=full_requests(c)[:5]
        activity=[dict(x) for x in c.execute('''SELECT a.*,m.name AS manager_name FROM activity a LEFT JOIN managers m ON m.id=a.manager_id
                 ORDER BY a.id DESC LIMIT 7''')]
        destinations=[dict(x) for x in c.execute('SELECT destination,COUNT(*) AS count FROM requests GROUP BY destination ORDER BY count DESC LIMIT 5')]
    return {'total':total,'counts':counts,'budget':budget,'recent':recent,'activity':activity,'destinations':destinations}

@app.get('/api/export')
def export_csv(request:Request):
    user(request)
    with db() as c:rows=full_requests(c)
    buffer=io.StringIO();buffer.write('\ufeff')
    writer=csv.writer(buffer)
    writer.writerow(['ID','Клиент','Телефон','Email','Направление','Статус','Менеджер','Начало','Окончание','Бюджет (₸)','Туристов','Пожелания','Создано'])
    for r in rows:
        writer.writerow([r['id'],r['client_name'],r['phone'],r['email'],r['destination'],r['status'],r['manager_name'],r['start_date'],r['end_date'],r['budget'],r['tourists_count'],r['wishes'],r['created_at']])
    return Response(buffer.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="tour_requests.csv"'})

@app.get('/api/managers')
def list_managers(request:Request):
    user(request)
    with db() as c:return [dict(r) for r in c.execute('SELECT id,name,email,role,active FROM managers ORDER BY id')]

@app.post('/api/managers',status_code=201)
def add_manager(body:ManagerData,request:Request):
    u=protect(request)
    if u['role']!='admin':raise HTTPException(403,'Недостаточно прав')
    with db() as c:
        try:
            cur=c.execute('INSERT INTO managers(name,email,password_hash,role) VALUES (?,?,?,?)',
                 (body.name.strip(),body.email.strip().lower(),pw_hash(body.password),'manager'))
        except sqlite3.IntegrityError:raise HTTPException(409,'Email уже используется')
    return {'id':cur.lastrowid}
