import urllib.request, json

BASE = 'http://127.0.0.1:8000'

def test(desc, method, path, data=None):
    try:
        if method == 'GET':
            req = urllib.request.Request(f'{BASE}{path}')
        else:
            req = urllib.request.Request(f'{BASE}{path}', 
                data=json.dumps(data).encode() if data else None,
                headers={'Content-Type': 'application/json'})
        
        res = urllib.request.urlopen(req)
        print(f'✅ {desc}: {res.status}')
        return json.loads(res.read())
    except Exception as e:
        print(f'❌ {desc}: {e}')
        return None

# 1. Health check
h = test('Health', 'GET', '/health')
if h: print(f'   DB has {h["counts"]["schedules"]} schedules, {h["counts"]["nodes"]} nodes')

# 2. Register student
r = test('Register student', 'POST', '/students/register', {
    'reg_no': 'TEST100', 'password': 'pwd123', 'course': 'Computer Science',
    'year': 2, 'semester': 1, 'units': 'CCS 311,BCS 304'
})

# 3. Login
l = test('Login student', 'POST', '/students/login', {
    'reg_no': 'TEST100', 'password': 'pwd123'
})

# 4. Get schedule
s = test('Get schedule', 'GET', '/students/schedule/TEST100')
if s and 'schedule' in s:
    print(f'   Student: {s.get("student", {}).get("course")}')
    print(f'   Classes today: {len(s["schedule"])}')
    for c in s['schedule'][:3]:
        print(f'     - {c["course_code"]} @ {c["venue"]} at {c["time"]}')

# 5. Admin login
a = test('Admin login', 'POST', '/admin/login', {'admin_password': 'Campus@123'})

print('\nDone!')