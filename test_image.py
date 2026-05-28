import sys
import json
import requests

if len(sys.argv) < 2:
    print("Usage: python test_image.py <path-to-image>")
    sys.exit(1)

image_path = sys.argv[1]

with open(image_path, "rb") as f:
    response = requests.post(
        "http://localhost:8000/validate-screenshot",
        files={"file": f},
    )

result = response.json()

print("\n=== BACKEND RESPONSE ===")
print(f"is_real      : {result['is_real']}")
print(f"confidence   : {int(result['confidence'] * 100)}%")
print(f"sources found: {len(result.get('sources', []))}")
print(f"\nextracted_text:\n  {result.get('extracted_text', '(none)')}")
print(f"\nsources:")
for s in result.get("sources", []):
    print(f"  {s}")
if result.get("details"):
    print(f"\ndetails: {result['details']}")
print("========================\n")
