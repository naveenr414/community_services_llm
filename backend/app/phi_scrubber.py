"""PHI scrubbing utility for HIPAA compliance."""

import re
from typing import Dict, Tuple
import scrubadub

class PHIScrubber:
    """Scrubs Protected Health Information from text."""
    
    # Patterns to scrub
    PATTERNS = {
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'date': r'\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b',
        'account': r'\b[Aa]ccount\s*#?\s*:?\s*\d+\b',
        'mrn': r'\b[Mm][Rr][Nn]\s*#?\s*:?\s*\d+\b',
    }
    
    @staticmethod
    def scrub_text(text: str, patient_id: str = None) -> Tuple[str, Dict]:
        """
        Scrub PHI from text.
        
        Args:
            text: Text to scrub
            patient_id: Optional patient ID to replace names with
            
        Returns:
            Tuple of (scrubbed_text, scrubbing_map)
        """
        if not text:
            return text, {}
        
        scrubbing_map = {}
        scrubbed = text
        
        # Use scrubadub for names
        scrubber = scrubadub.Scrubber()
        scrubbed = scrubber.clean(scrubbed)
        
        # Replace with patient ID if provided
        if patient_id:
            scrubbed = re.sub(r'{{NAME}}', f'[PATIENT_{patient_id}]', scrubbed)
        
        # Scrub phone numbers
        phones = re.findall(PHIScrubber.PATTERNS['phone'], scrubbed)
        for phone in phones:
            scrubbing_map[phone] = '[PHONE]'
            scrubbed = scrubbed.replace(phone, '[PHONE]')
        
        # Scrub SSN
        ssns = re.findall(PHIScrubber.PATTERNS['ssn'], scrubbed)
        for ssn in ssns:
            scrubbing_map[ssn] = '[SSN]'
            scrubbed = scrubbed.replace(ssn, '[SSN]')
        
        # Scrub emails
        emails = re.findall(PHIScrubber.PATTERNS['email'], scrubbed)
        for email in emails:
            scrubbing_map[email] = '[EMAIL]'
            scrubbed = scrubbed.replace(email, '[EMAIL]')
        
        # Scrub dates (keep only year)
        dates = re.findall(PHIScrubber.PATTERNS['date'], scrubbed)
        for date in dates:
            year_match = re.search(r'(\d{4})', date)
            if year_match:
                scrubbing_map[date] = f'[DATE_YEAR_{year_match.group(1)}]'
                scrubbed = scrubbed.replace(date, f'[DATE_YEAR_{year_match.group(1)}]')
            else:
                scrubbing_map[date] = '[DATE]'
                scrubbed = scrubbed.replace(date, '[DATE]')
        
        # Scrub account numbers
        accounts = re.findall(PHIScrubber.PATTERNS['account'], scrubbed)
        for account in accounts:
            scrubbing_map[account] = '[ACCOUNT_NUMBER]'
            scrubbed = scrubbed.replace(account, '[ACCOUNT_NUMBER]')
        
        # Scrub MRNs
        mrns = re.findall(PHIScrubber.PATTERNS['mrn'], scrubbed)
        for mrn in mrns:
            scrubbing_map[mrn] = '[MRN]'
            scrubbed = scrubbed.replace(mrn, '[MRN]')
        
        return scrubbed, scrubbing_map
    
    @staticmethod
    def scrub_for_gpt(text: str, patient_id: str = None) -> str:
        """
        Scrub text for GPT requests.
        
        Args:
            text: Text to scrub
            patient_id: Patient ID to use instead of name
            
        Returns:
            Scrubbed text safe for GPT
        """
        scrubbed, _ = PHIScrubber.scrub_text(text, patient_id)
        return scrubbed
    
    @staticmethod
    def scrub_for_logging(data: Dict) -> Dict:
        """
        Scrub dictionary data for audit logging.
        
        Args:
            data: Dictionary potentially containing PHI
            
        Returns:
            Scrubbed dictionary
        """
        if not data:
            return data
        
        scrubbed = {}
        sensitive_keys = [
            'password', 'ssn', 'social_security', 'email', 'phone',
            'address', 'name', 'first_name', 'last_name', 'dob',
            'date_of_birth', 'medical_record_number', 'mrn'
        ]
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # Redact sensitive keys
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                scrubbed[key] = '[REDACTED]'
            # Recursively scrub nested dicts
            elif isinstance(value, dict):
                scrubbed[key] = PHIScrubber.scrub_for_logging(value)
            # Scrub string values
            elif isinstance(value, str):
                scrubbed[key], _ = PHIScrubber.scrub_text(value)
            else:
                scrubbed[key] = value
        
        return scrubbed