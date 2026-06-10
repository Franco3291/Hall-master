import json, urllib.request
BASE='http://127.0.0.1:8001'

def get(path):
    with urllib.request.urlopen(BASE+path) as r:
        return r.status, r.read().decode()

def post(path, data=None):
    data_b = json.dumps(data or {}).encode()
    req = urllib.request.Request(BASE+path, data=data_b, headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req) as r:
        return r.status, r.read().decode()

if __name__=='__main__':
    print('POST /students/login for TEST100')
    try:
        s,b = post('/students/login', {"reg_no":"TEST100","password":"pwd"})
        print(s,b)
    except Exception as e:
        print('error',e)

    print('\nPOST /admin/login using default ADMIN_PASSWORD')
    try:
        s,b = post('/admin/login', {"admin_password":"Campus@123"})
        print(s,b)
    except Exception as e:
        print('error',e)

    print('\nPOST /rooms/reset')
    try:
        s,b = post('/rooms/reset')
        print(s,b)
    except Exception as e:
        print('error',e)
