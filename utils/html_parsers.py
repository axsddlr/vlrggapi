"""
Common HTML parsing utilities for VLR.GG scrapers
"""
import re
from typing import Optional


def extract_text_content(element, strip: bool = True) -> str:
    """Extract text content from an HTML element safely"""
    if not element:
        return ""
    return element.text(strip=strip)


def extract_prize_value(prize_elem) -> str:
    """
    Extract prize value from VLR.GG prize elements.
    Handles both monetary values ($250,000) and TBD cases.
    """
    if not prize_elem:
        return ""
    
    full_text = prize_elem.text(strip=True)
    
    # Split before "Prize Pool" label to get just the value
    parts = re.split(r'(?=Prize Pool|prize pool)', full_text, flags=re.IGNORECASE)
    if not parts:
        return ""
    
    first_part = re.sub(r'\s+', ' ', parts[0].strip())
    
    # Check for TBD
    if first_part.upper() == "TBD":
        return "TBD"
    # Check for dollar amounts
    elif re.match(r'^\$[\d,]+$', first_part):
        return first_part
    # Check for numeric values (add $ if missing)
    elif re.match(r'^[\d,]+$', first_part) and len(first_part) > 2:
        return "$" + first_part
    
    return ""


def extract_date_range(dates_elem) -> str:
    """
    Extract date range from VLR.GG date elements.
    Handles patterns like "Jul 15—Aug 31" and "Sep 15—TBD"
    """
    if not dates_elem:
        return ""
    
    full_text = dates_elem.text(strip=True)
    
    # Try to find date patterns first
    date_match = re.search(r"[A-Za-z]{3}\s+\d+[—\-–]+[A-Za-z]*\s*\d+", full_text)
    if date_match:
        return date_match.group()
    
    # Check for TBD in dates or fallback parsing
    if re.search(r"\bTBD\b", full_text, re.IGNORECASE):
        return "TBD"
    
    # Fallback: look for month abbreviations
    lines = full_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line or any(keyword in line.lower() for keyword in ['dates', 'label', 'prize', 'pool']):
            continue
        
        if (any(month in line for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']) or
            '—' in line):
            return line
    
    return ""


def extract_region_from_flag(flag_elem) -> str:
    """Extract region code from flag element class attribute"""
    if not flag_elem:
        return ""
    
    class_attr = flag_elem.attributes.get("class", "")
    return class_attr.replace("flag mod-", "").strip()


def normalize_image_url(src: str, base_url: str = "https://www.vlr.gg") -> str:
    """Normalize image URLs to absolute URLs"""
    if not src:
        return ""
    
    if src.startswith("//"):
        return "https:" + src
    elif src.startswith("/"):
        return base_url + src
    else:
        return src


def build_full_url(href: str, base_url: str = "https://www.vlr.gg") -> str:
    """Build full URL from relative href"""
    if not href:
        return ""
    return base_url + href if href.startswith("/") else href