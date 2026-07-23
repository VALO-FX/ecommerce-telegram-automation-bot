import cv2
import pytesseract
import re
import os
import logging

logger = logging.getLogger(__name__)

def preprocess_image(image_path: str) -> str:
    img = cv2.imread(image_path)
    if img is None:
        return image_path
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    temp_path = image_path + "_processed.jpg"
    cv2.imwrite(temp_path, thresh)
    return temp_path

def extract_amount(image_path: str) -> int | None:
    try:
        processed = preprocess_image(image_path)
        text = pytesseract.image_to_string(processed, lang='eng')
        os.remove(processed)
        logger.debug(f"OCR text: {text}")

        pattern = r'(\d[\d\s]*)\s*(?:\$|USD|EUR)'
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            amount_str = re.sub(r'\s+', '', matches[0])
            return int(amount_str)

        numbers = re.findall(r'(\d[\d\s]*)', text)
        if numbers:
            amounts = [int(re.sub(r'\s+', '', n)) for n in numbers if int(re.sub(r'\s+', '', n)) > 10]
            if amounts:
                return max(amounts)
        return None
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return None
