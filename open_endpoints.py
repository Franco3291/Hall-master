import sqlite3, json, urllib.request

BASE = 'http://127.0.0.1:8001'

def db_info():
    conn = sqlite3.connect('campus_navigation.db')
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    nodes = [r[0] for r in cur.execute('SELECT name FROM nodes LIMIT 5').fetchall()]
    conn.close()
    return tables, nodes

def get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return r.status, r.read().decode()

def post(path, data):
    data_b = json.dumps(data).encode()
    req = urllib.request.Request(BASE+path, data=data_b, headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req) as r:
        return r.status, r.read().decode()

if __name__ == '__main__':
    print('DB tables and sample nodes:')
    tables, nodes = db_info()
    print(tables)
    print('nodes sample:', nodes)

    print('\nGET /rooms/status')
    try:
        s, b = get('/rooms/status')
        print(s, b[:1000])
    except Exception as e:
        print('error', e)

    print('\nPOST /students/register')
    test_student = {"reg_no":"TEST100","password":"pwd","course":"CS","year":2,"semester":1,"units":"CS101"}
    try:
        s, b = post('/students/register', test_student)
        print(s, b)
    except Exception as e:
        print('error', e)

    print('\nGET /students/schedule/TEST100')
    try:
        s, b = get('/students/schedule/TEST100')
        print(s, b)
    except Exception as e:
        print('error', e)

    if len(nodes) >= 2:
        start, end = nodes[0], nodes[1]
        print(f"\nPOST /navigate from {start} to {end}")
        try:
            s, b = post('/navigate', {"start_node": start, "end_node": end})
            print(s, b)
        except Exception as e:
            print('error', e)

    print('\nPOST /verify (mark a venue)')
    try:
        s, b = post('/verify', {"venue": nodes[0] if nodes else 'Unknown', "status": 'BUSY'})
        print(s, b)
    except Exception as e:
        print('error', e)
