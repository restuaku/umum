"""
Student ID Card Image Generator
Creates realistic university student ID cards with photos
"""
from PIL import Image, ImageDraw, ImageFont
import qrcode
import requests
from io import BytesIO
import random
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_random_student_photo():
    """Get realistic student photo from randomuser.me API"""
    try:
        gender = random.choice(['male', 'female'])
        response = requests.get(
            f"https://randomuser.me/api/?gender={gender}&nat=us",
            timeout=10
        )
        data = response.json()
        photo_url = data['results'][0]['picture']['large']
        
        photo_response = requests.get(photo_url, timeout=10)
        img = Image.open(BytesIO(photo_response.content))
        logger.info(f"✅ Got random {gender} photo")
        return img
        
    except Exception as e:
        logger.warning(f"⚠️ Photo fetch failed: {e}, using placeholder")
        # Fallback placeholder
        img = Image.new('RGB', (300, 300), color='#cccccc')
        draw = ImageDraw.Draw(img)
        draw.text((100, 140), "PHOTO", fill='white', font=ImageFont.load_default())
        return img

def generate_student_id_card(first_name, last_name, school_dict):
    """
    Generate realistic student ID card
    
    Args:
        first_name: Student first name
        last_name: Student last name
        school_dict: Dictionary with 'name', 'city', 'state' keys
    
    Returns:
        bytes: PNG image data
    """
    # Card dimensions (credit card ratio)
    width, height = 1012, 638
    card = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(card)
    
    # Load fonts
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        logger.warning("⚠️ System fonts not found, using default")
        font_title = font_large = font_medium = font_small = font_tiny = ImageFont.load_default()
    
    # University header (blue bar)
    header_color = '#003366'  # Navy blue
    draw.rectangle([0, 0, width, 150], fill=header_color)
    
    # University name (truncate if too long)
    uni_name = school_dict['name']
    if len(uni_name) > 50:
        uni_name = uni_name[:47] + "..."
    
    draw.text((30, 30), uni_name, fill='white', font=font_title)
    draw.text((30, 85), f"{school_dict['city']}, {school_dict['state']}", fill='white', font=font_small)
    draw.text((30, 115), "STUDENT IDENTIFICATION CARD", fill='white', font=font_tiny)
    
    # Student photo
    photo = get_random_student_photo()
    photo = photo.resize((250, 300))
    card.paste(photo, (30, 180))
    
    # Student information
    x, y = 310, 180
    
    # Name
    draw.text((x, y), "STUDENT NAME", fill='#666666', font=font_small)
    draw.text((x, y + 28), f"{first_name} {last_name}", fill='#000000', font=font_large)
    
    # Student ID number
    draw.text((x, y + 85), "STUDENT ID", fill='#666666', font=font_small)
    student_id = f"S{random.randint(10000000, 99999999)}"
    draw.text((x, y + 110), student_id, fill='#000000', font=font_medium)
    
    # Class level
    draw.text((x, y + 165), "CLASS", fill='#666666', font=font_small)
    class_level = random.choice(['Freshman', 'Sophomore', 'Junior', 'Senior'])
    draw.text((x, y + 190), class_level, fill='#000000', font=font_medium)
    
    # QR Code
    qr = qrcode.QRCode(box_size=5, border=1)
    qr_data = f"STUDENT_ID:{student_id}\nNAME:{first_name} {last_name}\nUNIVERSITY:{school_dict['name']}"
    qr.add_data(qr_data)
    qr.make()
    qr_img = qr.make_image(fill_color="black", back_color="white").resize((120, 120))
    card.paste(qr_img, (850, 490))
    
    # Issue and expiry dates
    issue_date = datetime.now()
    expire_date = issue_date + timedelta(days=1460)  # 4 years
    
    draw.text((30, 520), f"Issued: {issue_date.strftime('%m/%d/%Y')}", fill='#666666', font=font_small)
    draw.text((30, 555), f"Expires: {expire_date.strftime('%m/%d/%Y')}", fill='#666666', font=font_small)
    
    # Footer
    draw.text((310, 555), "This card is property of the university", fill='#999999', font=font_tiny)
    
    # Border
    draw.rectangle([0, 0, width - 1, height - 1], outline=header_color, width=5)
    
    # Convert to bytes
    bio = BytesIO()
    card.save(bio, 'PNG', quality=95)
    img_bytes = bio.getvalue()
    
    logger.info(f"✅ Generated student ID card ({len(img_bytes) / 1024:.2f} KB)")
    return img_bytes

# Test
if __name__ == "__main__":
    test_school = {
        'name': 'Stanford University',
        'city': 'Stanford',
        'state': 'CA'
    }
    
    img_data = generate_student_id_card("John", "Smith", test_school)
    
    with open('test_student_id.png', 'wb') as f:
        f.write(img_data)
    
    print(f"✅ Test card saved: test_student_id.png ({len(img_data) / 1024:.2f} KB)")
