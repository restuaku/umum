
"""
SheerID Verification Logic (UNIVERSITY BOT VERSION)
Handles the complete verification workflow with document upload
Supports user-provided school data from SheerID OrgSearch API
"""
import re
import random
import logging
import httpx
import time
import uuid
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass

from config import SHEERID_BASE_URL, get_random_verified_school
from name_generator import NameGenerator, generate_birth_date, generate_student_email
from img_generator import generate_student_id_card

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

@dataclass
class VerificationResult:
    success: bool
    pending: bool = False
    message: str = ""
    verification_id: str = ""
    redirect_url: Optional[str] = None
    student_info: Optional[Dict[str, str]] = None
    current_step: Optional[str] = None

class SheerIDVerifier:
    """SheerID student verification handler with user-provided school support"""

    # Random User-Agent pools
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]

    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 1.0

    def __init__(self, verification_id: str):
        if not re.match(r'^[a-f0-9]{32}$', verification_id, re.I):
            raise ValueError(f"Invalid verification_id format: {verification_id}")
        
        self.verification_id = verification_id
        self.user_agent = self._get_random_user_agent()
        self.device_fingerprint = self._generate_device_fingerprint()
        self.http_client = httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        self.session_start = time.time()
        
        logger.info(f"🎭 Random UA: {self.user_agent[:60]}...")
        logger.info(f"🖥️ Random Fingerprint: {self.device_fingerprint[:16]}...")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Properly close HTTP client"""
        try:
            self.http_client.close()
        except Exception:
            pass

    @staticmethod
    def _get_random_user_agent() -> str:
        """Get random User-Agent from pool"""
        return random.choice(SheerIDVerifier.USER_AGENTS)

    @staticmethod
    def _generate_device_fingerprint() -> str:
        """Generate random 32-char device fingerprint"""
        base = str(uuid.uuid4()).replace('-', '')[:16]
        random_part = ''.join(random.choice('0123456789abcdef') for _ in range(16))
        return base + random_part

    @staticmethod
    def parse_verification_id(url: str) -> Optional[str]:
        """Extract verification ID from SheerID URL"""
        patterns = [
            r"verificationId=([a-f0-9]{32})",
            r"verification/([a-f0-9]{32})",
            r"ver/([a-f0-9]{32})"
        ]
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _make_request(self, method: str, endpoint: str, body: Optional[Dict] = None,
                     retries: int = 3) -> Tuple[Dict[str, Any], int]:
        """Enhanced request dengan random UA setiap request"""
        url = f"{SHEERID_BASE_URL}/rest/v2/verification/{self.verification_id}/{endpoint}"
        
        current_ua = self._get_random_user_agent()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": current_ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Origin": "https://verify.sheerid.com"
        }
        
        logger.debug(f"🌐 Request UA: {current_ua[:50]}...")
        
        for attempt in range(retries):
            try:
                response = self.http_client.request(
                    method=method,
                    url=url,
                    json=body,
                    headers=headers
                )
                
                try:
                    data = response.json()
                except (httpx.JSONDecodeError, ValueError):
                    data = {"error": response.text, "status_code": response.status_code}
                
                # Rate limiting handling
                if response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                return data, response.status_code
                
            except httpx.TimeoutException:
                logger.warning(f"Timeout (attempt {attempt + 1}/{retries})")
            except httpx.RequestError as e:
                logger.warning(f"Network error (attempt {attempt + 1}/{retries}): {e}")
            
            if attempt < retries - 1:
                time.sleep(self.RETRY_DELAY * (2 ** attempt))
        
        raise Exception(f"Request failed after {retries} attempts")

    def _upload_to_s3(self, upload_url: str, img_data: bytes, file_name: str = "student_id.png") -> bool:
        """Enhanced S3 upload"""
        try:
            headers = {
                "Content-Type": "image/png",
                "Content-Length": str(len(img_data))
            }
            response = self.http_client.put(
                upload_url,
                content=img_data,
                headers=headers,
                timeout=httpx.Timeout(60.0, connect=10.0)
            )
            
            if 200 <= response.status_code < 300:
                logger.info(f"✅ S3 upload successful: {file_name}")
                return True
            else:
                logger.error(f"❌ S3 upload failed ({response.status_code}): {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ S3 upload exception: {e}")
            return False

    def regenerate_fingerprint(self) -> str:
        """Regenerate new random fingerprint mid-session"""
        old_fp = self.device_fingerprint
        self.device_fingerprint = self._generate_device_fingerprint()
        logger.info(f"🔄 Fingerprint regenerated: {old_fp[:8]}... → {self.device_fingerprint[:8]}...")
        return self.device_fingerprint

    def verify(self, first_name: Optional[str] = None, last_name: Optional[str] = None,
               email: Optional[str] = None, birth_date: Optional[str] = None,
               school: Optional[Dict] = None) -> VerificationResult:
        """
        Execute complete SheerID verification workflow

        Args:
            first_name: Student first name (optional, will generate if None)
            last_name: Student last name (optional, will generate if None)
            email: Student email (optional, will generate if None)
            birth_date: Birth date YYYY-MM-DD (optional, will generate if None)
            school: School data from SheerID OrgSearch (optional, will use random if None)

        Returns:
            VerificationResult: Complete verification result
        """
        try:
            # Generate student data if not provided
            if not first_name or not last_name:
                name_data = NameGenerator.generate()
                first_name = name_data['first_name']
                last_name = name_data['last_name']
            else:
                logger.info(f"👤 Using provided name: {first_name} {last_name}")

            # Get school - PRIORITY: user-provided > random
            if school:
                logger.info(f"🎓 Using user-selected school: {school.get('name', 'Unknown')}")
                # Normalize school data for consistency
                school_normalized = {
                    'id': str(school.get('id', '')),
                    'name': school.get('name', 'Unknown University'),
                    'city': school.get('city', ''),
                    'state': school.get('state', ''),
                    'idExtended': school.get('idExtended', '')
                }
            else:
                school_normalized = get_random_verified_school()
                logger.info(f"🎓 Using random school: {school_normalized['name']}")

            # Generate other data if not provided
            email = email or generate_student_email(first_name, last_name)
            birth_date = birth_date or generate_birth_date()

            logger.info(f"👤 Verifying: {first_name} {last_name} @ {school_normalized['name']}")
            logger.info(f"📧 Email: {email}")
            logger.info(f"📍 Location: {school_normalized['city']}, {school_normalized['state']}")
            logger.info(f"🆔 SheerID Org ID: {school_normalized['id']}")
            logger.info(f"🎂 Birth Date: {birth_date}")

            # Step 1: Submit personal information
            logger.info("📝 Step 1/4: Submitting personal info...")
            personal_info = {
                "firstName": first_name.title(),
                "lastName": last_name.title(),
                "birthDate": birth_date,
                "email": email,
                "phoneNumber": "",
                "organization": {
                    "id": int(school_normalized['id']),
                    "idExtended": school_normalized.get('idExtended', ''),
                    "name": school_normalized['name']
                },
                "deviceFingerprintHash": self.device_fingerprint,
                "locale": "en-US",
                "metadata": {
                    "marketConsentValue": False,
                    "verificationId": self.verification_id
                }
            }

            step1_data, step1_status = self._make_request("POST", "step/collectStudentPersonalInfo", personal_info)
            
            if step1_status != 200:
                error_msg = step1_data.get('errorIds', step1_data.get('error', 'Unknown error'))
                raise Exception(f"Step 1 failed (HTTP {step1_status}): {error_msg}")

            current_step = step1_data.get('currentStep')
            if current_step == 'error':
                raise Exception(f"Step 1 validation failed: {step1_data.get('errorIds', 'Unknown')}")

            logger.info(f"✅ Step 1 complete: {current_step}")

            # Step 2: Handle SSO if present
            if current_step == 'sso':
                logger.info("⏭️ Step 2/4: Skipping SSO...")
                step2_data, _ = self._make_request("DELETE", "step/sso")
                current_step = step2_data.get('currentStep')
                logger.info(f"✅ SSO skipped: {current_step}")

            # Step 3: Document upload
            logger.info("📸 Step 3/4: Generating & uploading ID card...")
            img_data = generate_student_id_card(first_name, last_name, school_normalized)

            doc_upload_body = {
                "files": [{
                    "fileName": "student_id.png",
                    "mimeType": "image/png",
                    "fileSize": len(img_data)
                }]
            }

            step3_data, step3_status = self._make_request("POST", "step/docUpload", doc_upload_body)
            
            if step3_status != 200 or not step3_data.get('documents'):
                raise Exception("Failed to get S3 upload URLs")

            upload_url = step3_data['documents'][0]['uploadUrl']
            if not self._upload_to_s3(upload_url, img_data):
                raise Exception("S3 document upload failed")

            # Step 4: Complete verification
            logger.info("✅ Step 4/4: Completing verification...")
            final_data, _ = self._make_request("POST", "step/completeDocUpload")

            result = VerificationResult(
                success=True,
                pending=True,
                message="✅ Verification submitted successfully! Results in 24-48 hours.",
                verification_id=self.verification_id,
                redirect_url=final_data.get('redirectUrl'),
                current_step=final_data.get('currentStep'),
                student_info={
                    "name": f"{first_name} {last_name}",
                    "email": email,
                    "birth_date": birth_date,
                    "school": school_normalized['name'],
                    "school_id": school_normalized['id'],
                    "location": f"{school_normalized['city']}, {school_normalized['state']}"
                }
            )

            logger.info("🎉 Verification workflow completed successfully")
            return result

        except Exception as e:
            logger.error(f"❌ Verification failed: {e}", exc_info=True)
            return VerificationResult(
                success=False,
                message=f"❌ Verification failed: {str(e)}",
                verification_id=self.verification_id
            )

# Test function (backward compatible)
def main():
    import sys
    print("=" * 70)
    print("🔍 SheerID Student Verification Tool (University Bot)")
    print("=" * 70)

    url = sys.argv[1] if len(sys.argv) > 1 else input("\n🔗 Enter SheerID verification URL: ").strip()
    verification_id = SheerIDVerifier.parse_verification_id(url)

    if not verification_id:
        print("❌ Invalid verification URL. Expected format: ?verificationId=xxx or /verification/xxx")
        sys.exit(1)

    print(f"✅ Found Verification ID: {verification_id[:8]}...{verification_id[-8:]}")

    # Use context manager for proper cleanup
    with SheerIDVerifier(verification_id) as verifier:
        result = verifier.verify()

    print("\n" + "=" * 70)
    print("📊 VERIFICATION RESULT")
    print("=" * 70)
    status_emoji = "✅" if result.success else "❌"
    print(f"{status_emoji} Status: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"📝 Message: {result.message}")

    if result.student_info:
        info = result.student_info
        print(f"\n👤 Student: {info['name']}")
        print(f"📧 Email: {info['email']}")
        print(f"🏫 School: {info['school']}")
        print(f"📍 Location: {info['location']}")

    if result.redirect_url:
        print(f"\n🔗 Redirect: {result.redirect_url}")

    print("=" * 70)

if __name__ == "__main__":
    main()
