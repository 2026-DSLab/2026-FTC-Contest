import httpx
url = 'http://www.law.go.kr/DRF/lawService.do?target=law&type=XML&OC=sgrhee3&MST=240974'
resp = httpx.get(url)
content = resp.content.decode('utf-8')
print('Length:', len(content))
print('Has 제19조:', '제19조' in content)
print('Has CDATA:', '<![CDATA[' in content)
