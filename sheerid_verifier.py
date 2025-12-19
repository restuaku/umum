"""
SheerID Verification Logic
Handles the complete verification workflow with document upload
"""
import re
import random
import logging
import httpx
from typing import Dict, Optional, Tuple

from config import SHEERID_BASE_URL, get_random_verified_school
from name_generator import NameGenerator, generate_birth_date, generate_student_email
from img_generator import generate_student_id_card

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class SheerIDVerifier:
    """SheerID student verification handler"""

    def __init__(self, verification_id: str):
        self.verification_id = verification_id
        self.device_fingerprint = ''.join(random.choice('0123456789abcdef') for _ in range(32))
        self.http_client = httpx.Client(timeout=30.0)

    def __del__(self):
        if hasattr(self, 'http_client'):
            self.http_client.close()

    @staticmethod
    def parse_verification_id(url: str) -> Optional[str]:
        """Extract verification ID from SheerID URL"""
        match = re.search(r"verificationId=([a-f0-9]+)", url, re.IGNORECASE)
        return match.group(1) if match else None

    def _sheerid_request(self, method: str, url: str, body: Optional[Dict] = None) -> Tuple[Dict, int]:
        """Make request to SheerID API"""
        headers = {"Content-Type": "application/json"}
        try:
            response = self.http_client.request(method=method, url=url, json=body, headers=headers)
            try:
                data = response.json()
            except:
                data = {"error": response.text}
            return data, response.status_code
        except Exception as e:
            logger.error(f"❌ SheerID request failed: {e}")
            raise

    def _upload_to_s3(self, upload_url: str, img_data: bytes) -> bool:
        """Upload student ID card to S3"""
        try:
            headers = {"Content-Type": "image/png"}
            response = self.http_client.put(
                upload_url, 
                content=img_data, 
                headers=headers, 
                timeout=60.0
            )
            success = 200 <= response.status_code < 300
            if success:
                logger.info("✅ S3 upload successful")
            else:
                logger.error(f"❌ S3 upload failed: {response.status_code}")
            return success
        except Exception as e:
            logger.error(f"❌ S3 upload exception: {e}")
            return False

    def verify(self, first_name: str = None, last_name: str = None, 
               email: str = None, birth_date: str = None) -> Dict:
        """
        Execute complete SheerID verification workflow

        Returns:
            dict: Verification result with success status and details
        """
        try:
            # Step 0: Generate student data
            if not first_name or not last_name:
                name = NameGenerator.generate()
                first_name, last_name = name['first_name'], name['last_name']

            # Get verified university
            logger.info("🎓 Finding verified university...")
            school = get_random_verified_school()

            email = email or generate_student_email(first_name, last_name)
            birth_date = birth_date or generate_birth_date()

            logger.info(f"👤 Student: {first_name} {last_name}")
            logger.info(f"📧 Email: {email}")
            logger.info(f"🏫 School: {school['name']}")
            logger.info(f"📍 Location: {school['city']}, {school['state']}")
            logger.info(f"🆔 SheerID Org ID: {school['id']}")
            logger.info(f"🎂 Birth Date: {birth_date}")

            # Step 1: Generate student ID card
            logger.info("📸 Step 1/4: Generating student ID card...")
            img_data = generate_student_id_card(first_name, last_name, school)
            logger.info(f"✅ Card generated: {len(img_data) / 1024:.2f} KB")

            # Step 2: Submit personal information
            logger.info("📤 Step 2/4: Submitting student information...")
            step2_body = {
                "firstName": first_name,
                "lastName": last_name,
                "birthDate": birth_date,
                "email": email,
                "phoneNumber": "",
                "organization": {
                    "id": int(school['id']),
                    "idExtended": school['idExtended'],
                    "name": school['name']
                },
                "deviceFingerprintHash": self.device_fingerprint,
                "locale": "en-US",
                "metadata": {
                    "marketConsentValue": False,
                    "verificationId": self.verification_id
                }
            }

            step2_data, step2_status = self._sheerid_request(
                "POST",
                f"{SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/collectStudentPersonalInfo",
                step2_body
            )

            if step2_status != 200:
                error_msg = step2_data.get('errorIds', [step2_data.get('error', 'Unknown error')])
                raise Exception(f"Step 2 failed (HTTP {step2_status}): {error_msg}")

            if step2_data.get('currentStep') == 'error':
                error_msg = step2_data.get('errorIds', ['Unknown error'])
                raise Exception(f"Step 2 validation error: {error_msg}")

            logger.info(f"✅ Step 2 complete: {step2_data.get('currentStep')}")

            # Step 3: Skip SSO if required
            current_step = step2_data.get('currentStep')
            if current_step in ['sso', 'collectStudentPersonalInfo']:
                logger.info("⏭️ Step 3/4: Skipping SSO verification...")
                step3_data, _ = self._sheerid_request(
                    "DELETE",
                    f"{SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/sso"
                )
                logger.info(f"✅ SSO skipped: {step3_data.get('currentStep')}")
                current_step = step3_data.get('currentStep')
            else:
                logger.info("⏭️ Step 3/4: SSO not required")

            # Step 4: Upload student ID document
            logger.info("📤 Step 4/4: Requesting document upload URL...")
            step4_body = {
                "files": [{
                    "fileName": "student_id_card.png",
                    "mimeType": "image/png",
                    "fileSize": len(img_data)
                }]
            }

            step4_data, step4_status = self._sheerid_request(
                "POST",
                f"{SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/docUpload",
                step4_body
            )

            if not step4_data.get('documents'):
                raise Exception("Failed to get S3 upload URL from SheerID")

            upload_url = step4_data['documents'][0]['uploadUrl']
            logger.info("✅ Got S3 upload URL")

            # Upload to S3
            logger.info("☁️ Uploading student ID to S3...")
            if not self._upload_to_s3(upload_url, img_data):
                raise Exception("S3 upload failed")

            # Complete document upload
            logger.info("✅ Completing document submission...")
            final_data, _ = self._sheerid_request(
                "POST",
                f"{SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/step/completeDocUpload"
            )

            logger.info(f"✅ Verification submitted: {final_data.get('currentStep')}")

            return {
                "success": True,
                "pending": True,
                "message": "✅ Document submitted successfully! Check your email in 24-48 hours for verification result.",
                "verification_id": self.verification_id,
                "redirect_url": final_data.get('redirectUrl'),
                "student_info": {
                    "name": f"{first_name} {last_name}",
                    "email": email,
                    "birth_date": birth_date,
                    "school": school['name'],
                    "school_id": school['id'],
                    "location": f"{school['city']}, {school['state']}"
                }
            }

        except Exception as e:
            logger.error(f"❌ Verification failed: {e}")
            return {
                "success": False,
                "message": f"❌ Verification failed: {str(e)}",
                "verification_id": self.verification_id
            }

# Test
if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("SheerID Student Verification Tool")
    print("=" * 60)

    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("\nEnter SheerID verification URL: ").strip()

    verification_id = SheerIDVerifier.parse_verification_id(url)

    if not verification_id:
        print("❌ Error: Invalid verification ID format")
        sys.exit(1)

    print(f"✅ Verification ID: {verification_id}\n")

    verifier = SheerIDVerifier(verification_id)
    result = verifier.verify()

    print("\n" + "=" * 60)
    print("VERIFICATION RESULT")
    print("=" * 60)
    print(f"Status: {'✅ SUCCESS' if result['success'] else '❌ FAILED'}")
    print(f"Message: {result['message']}")

    if result.get('student_info'):
        info = result['student_info']
        print(f"\nStudent: {info['name']}")
        print(f"Email: {info['email']}")
        print(f"School: {info['school']}")
        print(f"Location: {info['location']}")

    if result.get('redirect_url'):
        print(f"\nRedirect: {result['redirect_url']}")

    print("=" * 60)
