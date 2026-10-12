# Playbook: Profile uploads
base_url: http://localhost:8001

## Requirements
### REQ-1: Users can set an avatar image
- acceptance: Choosing an image and saving shows that the avatar was updated and names the file.
- priority: high

### REQ-2: Only images are accepted as an avatar
- acceptance: Choosing any other kind of file shows an error and does not change the avatar.
- priority: high

## Edge cases
### EC-1: Wrong file type
- applies_to: upload-avatar
- expect: An error says only image files are allowed. The avatar does not change.
- covers: REQ-2
- test_data: file=sample.txt

## Flows
### Flow: upload-avatar
- covers: REQ-1
- severity: high

#### Steps
1. Open /profile
2. Choose the avatar image
3. Click Save avatar

#### Expect
- A message says the avatar was updated and shows the file name

#### Test data
- file: sample.png
