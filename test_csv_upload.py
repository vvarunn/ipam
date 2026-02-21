import requests
import urllib3

# Disable SSL warnings for self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Create a session
session = requests.Session()
session.verify = False

# Login first
login_url = 'https://localhost/auth/local/login'
login_data = {'username': 'admin', 'password': 'admin123'}

print("Logging in...")
login_response = session.post(login_url, json=login_data)

if login_response.status_code != 200:
    print(f"Login failed! Status: {login_response.status_code}")
    print(login_response.text)
    exit(1)

print("Login successful!")

# Upload the CSV file
url = 'https://localhost/api/bulk/upsert'
files = {'file': open('test_duplicate_upload.csv', 'rb')}

print("Uploading CSV file...")
response = session.post(url, files=files)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")

# Print the results
if response.status_code == 200:
    result = response.json()
    print(f"\nUpload successful!")
    print(f"  - Created: {result['created']} entries")
    print(f"  - Updated: {result['updated']} entries")
    print(f"  - Errors: {len(result.get('errors', []))} errors")
    
    if result.get('errors'):
        print("\nErrors:")
        for error in result['errors']:
            print(f"  Row {error['row']}: {error['error']}")
else:
    print(f"\nUpload failed!")


