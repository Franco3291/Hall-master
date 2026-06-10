import urllib.request, json
print(urllib.request.urlopen('http://127.0.0.1:8001/api/geo-nodes').read().decode())
